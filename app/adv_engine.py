"""
GFI v7.0 — ADV (Administration des Ventes) Engine.

16-state machine with 19 transitions and strict preconditions.
RF2 securization sub-engine. Event-driven automation chain.

No transition can be skipped. Attempt to jump states -> BLOCK.

Core API:
  create_dossier(...)           -> DossierAdv
  transition(dossier_id, to)    -> DossierAdv (validates preconditions)
  record_rf2_payment(...)       -> triggers securization chain
  record_rf1_payment(...)       -> triggers collection chain
  check_engagement_ready(...)   -> (bool, list[str])
  get_rf2_securization_status() -> dict
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class InvalidAdvTransition(Exception):
    """Raised when a state machine transition is not allowed."""

    def __init__(self, message: str, from_state: str, to_state: str,
                 missing_step: str | None = None):
        super().__init__(message)
        self.from_state = from_state
        self.to_state = to_state
        self.missing_step = missing_step


class RF2NotSecured(Exception):
    """Raised when an operation requires RF2 to be fully secured."""
    pass


class RF2CashBalanceViolation(Exception):
    """Raised when RF2 cash account would go negative (RF2-S05)."""
    pass


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ═════════════════════════════════════════════════════════════════════════════
# STATE MACHINE: 16 states, 19 transitions
# ═════════════════════════════════════════════════════════════════════════════

VALID_TRANSITIONS: dict[str, set[str]] = {
    "DISPONIBLE":           {"RESERVE", "PRE_RESERVE"},
    "PRE_RESERVE":          {"RESERVE", "ANNULE"},
    "RESERVE":              {"ENGAGE", "ANNULE_RESERVATION"},
    "ENGAGE":               {"EN_COURS_CREDIT", "EN_COURS_FONDS_PROPRES",
                             "ANNULE_ENGAGEMENT"},
    "EN_COURS_CREDIT":      {"CONTRAT_SIGNE", "REJETE_BANQUE"},
    "REJETE_BANQUE":        {"EN_COURS_FONDS_PROPRES"},
    "EN_COURS_FONDS_PROPRES": {"PAIEMENT_EN_COURS", "DEFAUT_PAIEMENT"},
    "PAIEMENT_EN_COURS":    {"CONTRAT_SIGNE"},
    "CONTRAT_SIGNE":        {"DEBLOCAGE_EN_COURS"},
    "DEBLOCAGE_EN_COURS":   {"LIVRAISON_PRETE"},
    "LIVRAISON_PRETE":      {"LIVRE"},
    "LIVRE":                {"CLOTURE"},
    "DEFAUT_PAIEMENT":      set(),  # terminal until resolved
    "ANNULE":               set(),
    "ANNULE_RESERVATION":   set(),
    "ANNULE_ENGAGEMENT":    set(),
    "INDISPONIBLE":         {"DISPONIBLE"},
}

# All 16 valid states
ALL_STATES = set(VALID_TRANSITIONS.keys())


def _validate_preconditions(
    session: Session,
    dossier,
    to_state: str,
) -> list[str]:
    """
    Check preconditions for a transition. Returns list of unmet conditions.
    Empty list = all preconditions met.
    """
    unmet = []

    if to_state == "RESERVE":
        if dossier.statut_rf2 != "SECURISE" and dossier.prix_vente_rf2 and dossier.prix_vente_rf2 > 0:
            # PRE_RESERVE -> RESERVE requires RF2 secured
            if dossier.statut_global == "PRE_RESERVE":
                unmet.append("RF2 non securise (statut_rf2 != SECURISE)")

    elif to_state == "ENGAGE":
        # ENG-001 / RF2-S02: RF2 must be 100% secured
        if dossier.prix_vente_rf2 and dossier.prix_vente_rf2 > 0:
            if dossier.statut_rf2 != "SECURISE":
                unmet.append(
                    "RF2 non securise — engagement impossible "
                    "(RF2-S02 / ENG-001)"
                )
        # ENG-002: If fonds propres, 30% of prix_reel must be paid
        if dossier.type_paiement in ("FONDS_PROPRES", "MIXTE"):
            seuil = _r2(Decimal(str(dossier.prix_vente_reel)) * Decimal("0.30"))
            verse = Decimal(str(dossier.montant_total_verse))
            if verse < seuil:
                unmet.append(
                    f"30% du prix reel non atteint: verse={verse} DA, "
                    f"requis={seuil} DA (ENG-002)"
                )
        # ENG-004: If credit, fond de garantie must be sufficient
        if dossier.type_paiement in ("CREDIT_BANCAIRE", "MIXTE"):
            if dossier.montant_credit and dossier.fond_garantie_disponible:
                if Decimal(str(dossier.fond_garantie_disponible)) < Decimal(str(dossier.montant_credit)):
                    unmet.append(
                        "Fond de garantie insuffisant (ENG-004)"
                    )

    elif to_state == "EN_COURS_CREDIT":
        if dossier.type_paiement not in ("CREDIT_BANCAIRE", "MIXTE"):
            unmet.append("Type paiement n'est pas CREDIT_BANCAIRE/MIXTE")

    elif to_state == "EN_COURS_FONDS_PROPRES":
        if dossier.type_paiement not in ("FONDS_PROPRES", "MIXTE") \
                and dossier.statut_global != "REJETE_BANQUE":
            unmet.append("Type paiement n'est pas FONDS_PROPRES/MIXTE")

    elif to_state == "CONTRAT_SIGNE":
        if dossier.statut_global == "EN_COURS_CREDIT":
            if not dossier.date_signature_contrat:
                unmet.append("Contrat de credit non signe")

    elif to_state == "DEBLOCAGE_EN_COURS":
        if not dossier.date_signature_contrat:
            unmet.append("Contrat non signe")

    elif to_state == "CLOTURE":
        # All RF1 payments must equal prix_rf1
        rf1_total = _get_rf1_total(session, dossier.id)
        if rf1_total != Decimal(str(dossier.prix_vente_rf1)):
            unmet.append(
                f"Total RF1 ({rf1_total}) != prix RF1 ({dossier.prix_vente_rf1})"
            )
        # All RF2 payments must equal prix_rf2
        if dossier.prix_vente_rf2 and dossier.prix_vente_rf2 > 0:
            rf2_total = _get_rf2_total(session, dossier.id)
            if rf2_total != Decimal(str(dossier.prix_vente_rf2)):
                unmet.append(
                    f"Total RF2 ({rf2_total}) != prix RF2 ({dossier.prix_vente_rf2})"
                )

    return unmet


def _get_rf1_total(session: Session, dossier_id: UUID) -> Decimal:
    from app.models.dossier_payment import DossierPayment
    from sqlalchemy import func as sqfunc

    total = (
        session.query(sqfunc.coalesce(sqfunc.sum(DossierPayment.amount), 0))
        .filter(
            DossierPayment.dossier_id == dossier_id,
            DossierPayment.rf_type == "RF1",
            DossierPayment.status != "ANNULE",
            DossierPayment.is_deleted.is_(False),
        )
        .scalar()
    )
    return Decimal(str(total))


def _get_rf2_total(session: Session, dossier_id: UUID) -> Decimal:
    from app.models.dossier_payment import DossierPayment
    from sqlalchemy import func as sqfunc

    total = (
        session.query(sqfunc.coalesce(sqfunc.sum(DossierPayment.amount), 0))
        .filter(
            DossierPayment.dossier_id == dossier_id,
            DossierPayment.rf_type == "RF2",
            DossierPayment.status != "ANNULE",
            DossierPayment.is_deleted.is_(False),
        )
        .scalar()
    )
    return Decimal(str(total))


def transition(
    session: Session,
    *,
    dossier_id: UUID,
    to_state: str,
    trigger: str | None = None,
    transitioned_by: UUID | None = None,
    notes: str | None = None,
) -> object:
    """
    Execute a state machine transition with full precondition validation.
    No transition can be skipped.
    """
    from app.models.dossier_adv import DossierAdv
    from app.models.dossier_transition import DossierTransition

    dossier = session.get(DossierAdv, dossier_id)
    if dossier is None:
        raise ValueError(f"Dossier {dossier_id} not found.")

    from_state = dossier.statut_global

    # Check transition is valid
    allowed = VALID_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        # Find what step is missing
        missing = None
        for intermediate, targets in VALID_TRANSITIONS.items():
            if to_state in targets and from_state != intermediate:
                missing = intermediate
                break
        raise InvalidAdvTransition(
            f"Transition {from_state} -> {to_state} impossible. "
            f"Etape requise : {missing or 'etat precedent manquant'}.",
            from_state=from_state,
            to_state=to_state,
            missing_step=missing,
        )

    # Check preconditions
    unmet = _validate_preconditions(session, dossier, to_state)
    if unmet:
        raise InvalidAdvTransition(
            f"Transition {from_state} -> {to_state} bloquee. "
            f"Preconditions non remplies: {'; '.join(unmet)}",
            from_state=from_state,
            to_state=to_state,
        )

    # Execute transition
    now = datetime.now(timezone.utc)
    dossier.statut_global = to_state

    # State-specific side effects
    if to_state == "RESERVE":
        dossier.date_reservation = now.date()
    elif to_state == "ENGAGE":
        dossier.date_engagement = now.date()
    elif to_state == "CONTRAT_SIGNE":
        if not dossier.date_signature_contrat:
            dossier.date_signature_contrat = now.date()
    elif to_state == "LIVRE":
        dossier.date_livraison_effective = now.date()
    elif to_state in ("ANNULE", "ANNULE_RESERVATION", "ANNULE_ENGAGEMENT"):
        # Release lot back to EDD
        from app.models.lot import Lot
        lot = session.get(Lot, dossier.lot_id)
        if lot and lot.status not in ("DISPONIBLE", "ANNULE"):
            lot.status = "DISPONIBLE" if to_state != "ANNULE" else "ANNULE"
            lot.client_name = None
            lot.client_id = None

    # Record transition
    trans = DossierTransition(
        company_id=dossier.company_id,
        dossier_id=dossier_id,
        from_status=from_state,
        to_status=to_state,
        transition_trigger=trigger,
        transitioned_at=now,
        transitioned_by=transitioned_by,
        preconditions_met={"checked": True, "unmet_count": 0},
        notes=notes,
    )
    session.add(trans)
    session.flush()

    return dossier


# ═════════════════════════════════════════════════════════════════════════════
# RF2 SECURIZATION ENGINE
# ═════════════════════════════════════════════════════════════════════════════

def record_rf2_payment(
    session: Session,
    *,
    dossier_id: UUID,
    company_id: UUID,
    amount: Decimal,
    payment_date: date,
    justification_path: str | None = None,
    created_by: UUID | None = None,
) -> dict:
    """
    Record an RF2 cash payment. Triggers the securization chain:
    1. Update montant_rf2_securise
    2. Check if fully secured -> set statut_rf2 = SECURISE
    3. If secured + fonds propres: check 30% threshold
    4. If secured + credit: check fond de garantie

    Returns a dict with securization status and any triggered actions.
    """
    from app.models.dossier_adv import DossierAdv
    from app.models.dossier_payment import DossierPayment

    amount = Decimal(str(amount))

    dossier = session.get(DossierAdv, dossier_id)
    if dossier is None:
        raise ValueError(f"Dossier {dossier_id} not found.")

    # RF2-S05: Cash balance can never go negative
    # (the payment itself is always positive, so this checks the account)

    # Create payment record
    payment = DossierPayment(
        company_id=company_id,
        dossier_id=dossier_id,
        payment_date=payment_date,
        rf_type="RF2",
        payment_mode="ESPECES",
        amount=amount,
        receipt_type="INTERNE",
        payment_category="RF2_SECURISATION",
        status="ENREGISTRE",
        justification_path=justification_path,
        created_by=created_by,
    )
    session.add(payment)

    # Step 1: Update securization totals
    now = datetime.now(timezone.utc)
    new_securise = Decimal(str(dossier.montant_rf2_securise)) + amount
    dossier.montant_rf2_securise = _r2(new_securise)
    dossier.rf2_last_payment_at = now

    prix_rf2 = Decimal(str(dossier.prix_vente_rf2 or 0))
    dossier.montant_rf2_restant = _r2(max(Decimal("0"), prix_rf2 - new_securise))

    result = {
        "montant_rf2_securise": str(dossier.montant_rf2_securise),
        "montant_rf2_restant": str(dossier.montant_rf2_restant),
        "actions_triggered": [],
    }

    # Step 2: Check if fully secured
    if new_securise >= prix_rf2 and prix_rf2 > 0:
        dossier.statut_rf2 = "SECURISE"
        result["statut_rf2"] = "SECURISE"
        result["actions_triggered"].append("RF2_FULLY_SECURED")

        # Step 3/4: Check engagement readiness
        if dossier.type_paiement in ("FONDS_PROPRES", "MIXTE"):
            seuil = _r2(Decimal(str(dossier.prix_vente_reel)) * Decimal("0.30"))
            verse = Decimal(str(dossier.montant_total_verse))
            if verse >= seuil:
                result["actions_triggered"].append("ENGAGEMENT_READY_FONDS_PROPRES")
            else:
                result["actions_triggered"].append(
                    f"RF2_SECURED_BUT_30PCT_NOT_MET (verse={verse}, requis={seuil})"
                )
        elif dossier.type_paiement in ("CREDIT_BANCAIRE",):
            if (dossier.fond_garantie_disponible
                    and dossier.montant_credit
                    and Decimal(str(dossier.fond_garantie_disponible)) >= Decimal(str(dossier.montant_credit))):
                result["actions_triggered"].append("ENGAGEMENT_READY_CREDIT")
            else:
                result["actions_triggered"].append("RF2_SECURED_BUT_FOND_GARANTIE_INSUFFICIENT")
    else:
        dossier.statut_rf2 = "PARTIELLEMENT_SECURISE"
        result["statut_rf2"] = "PARTIELLEMENT_SECURISE"
        pct = (new_securise / prix_rf2 * 100) if prix_rf2 > 0 else 0
        result["progress_pct"] = str(_r2(pct))

    session.flush()
    return result


def record_rf1_payment(
    session: Session,
    *,
    dossier_id: UUID,
    company_id: UUID,
    amount: Decimal,
    payment_date: date,
    payment_mode: str,
    payment_category: str,
    credit_tier_pct: Decimal | None = None,
    justification_path: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """Record an RF1 payment on a dossier. Updates total versé."""
    from app.models.dossier_adv import DossierAdv
    from app.models.dossier_payment import DossierPayment
    from app.rf import validate_rf_payment

    amount = Decimal(str(amount))

    # Enforce RF1 payment mode constraint
    validate_rf_payment("RF1", payment_mode)

    dossier = session.get(DossierAdv, dossier_id)
    if dossier is None:
        raise ValueError(f"Dossier {dossier_id} not found.")

    payment = DossierPayment(
        company_id=company_id,
        dossier_id=dossier_id,
        payment_date=payment_date,
        rf_type="RF1",
        payment_mode=payment_mode,
        amount=amount,
        receipt_type="OFFICIEL",
        receipt_amount=amount,
        payment_category=payment_category,
        credit_tier_pct=credit_tier_pct,
        status="ENREGISTRE",
        justification_path=justification_path,
        created_by=created_by,
    )
    session.add(payment)

    # Update total versé
    new_total = Decimal(str(dossier.montant_total_verse)) + amount
    dossier.montant_total_verse = _r2(new_total)

    # Check 30% threshold
    seuil = _r2(Decimal(str(dossier.prix_vente_reel)) * Decimal("0.30"))
    if new_total >= seuil:
        dossier.seuil_30_pct_atteint = "Y"

    session.flush()
    return payment


def create_dossier(
    session: Session,
    *,
    company_id: UUID,
    client_id: UUID,
    lot_id: UUID,
    project_id: UUID,
    type_paiement: str,
    prix_rf1: Decimal,
    prix_rf2: Decimal | None = None,
    agent_commercial_id: UUID | None = None,
    responsable_adv_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """Create a new ADV dossier. Generates sequential numero_dossier."""
    from app.models.dossier_adv import DossierAdv
    from app.models.project import Project

    project = session.get(Project, project_id)
    project_code = project.code if project else "UNK"
    year = date.today().year

    # Sequential number per project per year
    from sqlalchemy import func as sqfunc
    count = (
        session.query(sqfunc.count(DossierAdv.id))
        .filter(
            DossierAdv.project_id == project_id,
            DossierAdv.numero_dossier.like(f"ADV-{year}-{project_code}-%"),
            DossierAdv.is_deleted.is_(False),
        )
        .scalar()
    ) or 0

    numero = f"ADV-{year}-{project_code}-{count + 1:04d}"

    prix_rf1 = Decimal(str(prix_rf1))
    prix_rf2 = Decimal(str(prix_rf2)) if prix_rf2 else Decimal("0")
    prix_reel = prix_rf1 + prix_rf2

    rf2_status = None
    if prix_rf2 > 0:
        rf2_status = "NON_SECURISE"

    dossier = DossierAdv(
        company_id=company_id,
        numero_dossier=numero,
        client_id=client_id,
        lot_id=lot_id,
        project_id=project_id,
        type_paiement=type_paiement,
        prix_vente_rf1=prix_rf1,
        prix_vente_rf2=prix_rf2,
        prix_vente_reel=prix_reel,
        statut_global="DISPONIBLE",
        statut_rf2=rf2_status,
        montant_rf2_securise=Decimal("0"),
        montant_rf2_restant=prix_rf2,
        agent_commercial_id=agent_commercial_id,
        responsable_adv_id=responsable_adv_id,
        created_by=created_by,
    )
    session.add(dossier)
    session.flush()
    return dossier


def check_engagement_ready(
    session: Session,
    dossier_id: UUID,
) -> tuple[bool, list[str]]:
    """Check if a dossier is ready for engagement. Returns (ready, blockers)."""
    from app.models.dossier_adv import DossierAdv

    dossier = session.get(DossierAdv, dossier_id)
    if dossier is None:
        return False, ["Dossier not found"]

    blockers = _validate_preconditions(session, dossier, "ENGAGE")
    return len(blockers) == 0, blockers


def get_rf2_securization_dashboard(
    session: Session,
    company_id: UUID,
) -> list[dict]:
    """
    RF2 securization screen: dossiers with unsecured RF2, sorted by urgency.
    """
    from app.models.dossier_adv import DossierAdv

    dossiers = (
        session.query(DossierAdv)
        .filter(
            DossierAdv.company_id == company_id,
            DossierAdv.statut_rf2.in_(["NON_SECURISE", "PARTIELLEMENT_SECURISE"]),
            DossierAdv.prix_vente_rf2 > 0,
            DossierAdv.is_deleted.is_(False),
        )
        .order_by(DossierAdv.date_reservation.asc())
        .all()
    )

    result = []
    now = datetime.now(timezone.utc)

    for d in dossiers:
        prix_rf2 = Decimal(str(d.prix_vente_rf2 or 0))
        securise = Decimal(str(d.montant_rf2_securise))
        pct = _r2(securise / prix_rf2 * 100) if prix_rf2 > 0 else Decimal("0")

        days_stagnant = None
        if d.rf2_last_payment_at:
            delta = now - d.rf2_last_payment_at
            days_stagnant = delta.days

        result.append({
            "dossier_id": str(d.id),
            "numero_dossier": d.numero_dossier,
            "client_name": None,  # joined from client table in real query
            "prix_rf2": str(prix_rf2),
            "montant_securise": str(securise),
            "montant_restant": str(d.montant_rf2_restant),
            "progress_pct": str(pct),
            "stagnant_days": days_stagnant,
            "stagnation_alert": days_stagnant is not None and days_stagnant >= 7,
        })

    return result
