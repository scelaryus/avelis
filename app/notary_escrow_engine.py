"""
GFI v7.0 — Notary Escrow Engine.

Manages the transit of bank credit funds through the notary's escrow account.
Bank -> Notary Escrow -> Company. NEVER direct bank -> company (CRE-004).

Core rules:
  FIN-005:     solde_transitoire >= 0 always (DB trigger enforced)
  NOTAIRE-001: SUM(etat_detaille lines) == montant_global (exact)
  NOTAIRE-002: No treasury registration without etat detaille for global cheques
  CRE-004:     20% must transit via escrow
  CRE-006:     5% release requires PV remise des cles
  CRE-007:     Global cheque auto-requires etat detaille
  48h alert:   Positive balance above expected 5% reserves for >48h

Core API:
  credit_escrow(...)           -> EscrowMovement (money into escrow)
  debit_escrow(...)            -> EscrowMovement (money out of escrow)
  record_vsp_20pct(...)        -> credit 20% + debit 20% (transit)
  record_5pct_reserve(...)     -> credit 5% (held until delivery)
  release_5pct(...)            -> debit 5% (after PV remise des cles)
  create_etat_detaille(...)    -> EtatDetaille (ventilate global cheque)
  validate_etat_detaille(...)  -> validates sum == montant_global
  check_48h_alerts(...)        -> list of escrows with overdue balances
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class EscrowBalanceViolation(Exception):
    """FIN-005: escrow balance would go negative."""
    def __init__(self, message: str, current_balance: Decimal, attempted: Decimal):
        super().__init__(message)
        self.current_balance = current_balance
        self.attempted = attempted


class EtatDetailleDiscrepancy(Exception):
    """NOTAIRE-001: sum of lines != montant_global."""
    def __init__(self, message: str, sum_lignes: Decimal, montant_global: Decimal):
        super().__init__(message)
        self.sum_lignes = sum_lignes
        self.montant_global = montant_global


class EtatDetailleRequired(Exception):
    """NOTAIRE-002: global cheque requires etat detaille before treasury."""
    pass


class PvRemiseClesRequired(Exception):
    """CRE-006: PV remise des cles required before 5% release."""
    pass


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _get_or_create_escrow(
    session: Session,
    *,
    company_id: UUID,
    notaire_id: UUID,
    project_id: UUID,
    notaire_name: str | None = None,
) -> object:
    """Get or create a notary escrow account."""
    from app.models.notary_escrow import NotaryEscrow

    escrow = (
        session.query(NotaryEscrow)
        .filter(
            NotaryEscrow.company_id == company_id,
            NotaryEscrow.notaire_id == notaire_id,
            NotaryEscrow.project_id == project_id,
            NotaryEscrow.is_deleted.is_(False),
        )
        .first()
    )
    if escrow is None:
        escrow = NotaryEscrow(
            company_id=company_id,
            notaire_id=notaire_id,
            project_id=project_id,
            notaire_name=notaire_name,
            solde_transitoire=Decimal("0"),
            expected_5pct_reserve=Decimal("0"),
        )
        session.add(escrow)
        session.flush()
    return escrow


def credit_escrow(
    session: Session,
    *,
    escrow_id: UUID,
    company_id: UUID,
    montant: Decimal,
    source: str,
    motif: str,
    dossier_adv_id: UUID | None = None,
    reference_cheque: str | None = None,
    etat_detaille_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """Record money flowing INTO the escrow account."""
    from app.models.notary_escrow import NotaryEscrow
    from app.models.notary_escrow import EscrowMovement

    montant = Decimal(str(montant))
    escrow = session.get(NotaryEscrow, escrow_id)
    if escrow is None:
        raise ValueError(f"Escrow {escrow_id} not found.")

    now = datetime.now(timezone.utc)
    new_balance = Decimal(str(escrow.solde_transitoire)) + montant

    movement = EscrowMovement(
        company_id=company_id,
        escrow_id=escrow_id,
        movement_date=now,
        movement_type="CREDIT",
        montant=montant,
        balance_after=_r2(new_balance),
        source=source,
        destination="Compte sequestre notaire",
        dossier_adv_id=dossier_adv_id,
        motif=motif,
        reference_cheque=reference_cheque,
        etat_detaille_id=etat_detaille_id,
        created_by=created_by,
    )
    session.add(movement)
    escrow.solde_transitoire = _r2(new_balance)
    session.flush()
    return movement


def debit_escrow(
    session: Session,
    *,
    escrow_id: UUID,
    company_id: UUID,
    montant: Decimal,
    destination: str,
    motif: str,
    dossier_adv_id: UUID | None = None,
    reference_cheque: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Record money flowing OUT of the escrow account.
    FIN-005: blocks if balance would go negative.
    """
    from app.models.notary_escrow import NotaryEscrow
    from app.models.notary_escrow import EscrowMovement

    montant = Decimal(str(montant))
    escrow = session.get(NotaryEscrow, escrow_id)
    if escrow is None:
        raise ValueError(f"Escrow {escrow_id} not found.")

    current = Decimal(str(escrow.solde_transitoire))
    new_balance = current - montant

    # FIN-005: balance can NEVER be negative
    if new_balance < Decimal("0"):
        raise EscrowBalanceViolation(
            f"FIN-005: Solde sequestre deviendrait negatif. "
            f"Solde actuel = {current} DA, debit = {montant} DA, "
            f"resultat = {new_balance} DA.",
            current_balance=current,
            attempted=montant,
        )

    now = datetime.now(timezone.utc)

    movement = EscrowMovement(
        company_id=company_id,
        escrow_id=escrow_id,
        movement_date=now,
        movement_type="DEBIT",
        montant=montant,
        balance_after=_r2(new_balance),
        source="Compte sequestre notaire",
        destination=destination,
        dossier_adv_id=dossier_adv_id,
        motif=motif,
        reference_cheque=reference_cheque,
        created_by=created_by,
    )
    session.add(movement)
    escrow.solde_transitoire = _r2(new_balance)

    # Update 48h alert tracking
    if new_balance == Decimal("0"):
        escrow.last_zero_at = now
        escrow.alert_48h_active = "N"

    session.flush()
    return movement


def record_vsp_20pct(
    session: Session,
    *,
    escrow_id: UUID,
    company_id: UUID,
    dossier_adv_id: UUID,
    montant_20pct: Decimal,
    bank_name: str,
    company_name: str,
    reference_cheque: str | None = None,
    created_by: UUID | None = None,
) -> tuple:
    """
    Record the 20% VSP transit: bank -> escrow -> company.
    CRE-004: 20% MUST transit via escrow.
    Returns (credit_movement, debit_movement).
    """
    montant = Decimal(str(montant_20pct))

    # Step 1: Credit - bank sends to escrow
    credit_mv = credit_escrow(
        session,
        escrow_id=escrow_id,
        company_id=company_id,
        montant=montant,
        source=f"Banque {bank_name}",
        motif="VSP_20PCT",
        dossier_adv_id=dossier_adv_id,
        reference_cheque=reference_cheque,
        created_by=created_by,
    )

    # Step 2: Debit - escrow releases to company (immediate)
    debit_mv = debit_escrow(
        session,
        escrow_id=escrow_id,
        company_id=company_id,
        montant=montant,
        destination=f"Compte entreprise {company_name}",
        motif="LIBERATION_20PCT",
        dossier_adv_id=dossier_adv_id,
        created_by=created_by,
    )

    return credit_mv, debit_mv


def record_5pct_reserve(
    session: Session,
    *,
    escrow_id: UUID,
    company_id: UUID,
    dossier_adv_id: UUID,
    montant_5pct: Decimal,
    bank_name: str,
    created_by: UUID | None = None,
) -> object:
    """
    Record the 5% held reserve from credit establishment.
    This stays in escrow until PV remise des cles.
    Updates the expected_5pct_reserve on the escrow.
    """
    from app.models.notary_escrow import NotaryEscrow

    montant = Decimal(str(montant_5pct))

    credit_mv = credit_escrow(
        session,
        escrow_id=escrow_id,
        company_id=company_id,
        montant=montant,
        source=f"Banque {bank_name} (reserve 5%)",
        motif="PALIER_5PCT",
        dossier_adv_id=dossier_adv_id,
        created_by=created_by,
    )

    # Update expected 5% reserve total
    escrow = session.get(NotaryEscrow, escrow_id)
    current_reserve = Decimal(str(escrow.expected_5pct_reserve))
    escrow.expected_5pct_reserve = _r2(current_reserve + montant)
    session.flush()

    return credit_mv


def release_5pct(
    session: Session,
    *,
    escrow_id: UUID,
    company_id: UUID,
    dossier_adv_id: UUID,
    montant_5pct: Decimal,
    company_name: str,
    pv_remise_cles_path: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Release the 5% after PV remise des cles.
    CRE-006: PV is an ABSOLUTE precondition.
    """
    if not pv_remise_cles_path:
        raise PvRemiseClesRequired(
            "CRE-006: PV de remise des cles signe requis avant "
            "liberation du 5%. Aucun PV fourni."
        )

    montant = Decimal(str(montant_5pct))

    debit_mv = debit_escrow(
        session,
        escrow_id=escrow_id,
        company_id=company_id,
        montant=montant,
        destination=f"Compte entreprise {company_name}",
        motif="LIBERATION_5PCT",
        dossier_adv_id=dossier_adv_id,
        created_by=created_by,
    )

    # Reduce expected 5% reserve
    from app.models.notary_escrow import NotaryEscrow
    escrow = session.get(NotaryEscrow, escrow_id)
    current_reserve = Decimal(str(escrow.expected_5pct_reserve))
    escrow.expected_5pct_reserve = _r2(max(Decimal("0"), current_reserve - montant))
    session.flush()

    return debit_mv


# ═════════════════════════════════════════════════════════════════════════════
# ÉTAT DÉTAILLÉ (global cheque ventilation)
# ═════════════════════════════════════════════════════════════════════════════

def create_etat_detaille(
    session: Session,
    *,
    escrow_id: UUID,
    company_id: UUID,
    cheque_reference: str,
    montant_global: Decimal,
    date_cheque,
    notaire_id: UUID,
    lines: list[dict],
    created_by: UUID | None = None,
) -> object:
    """
    Create an etat detaille for a global notary cheque.
    Validates NOTAIRE-001: sum of lines == montant_global.

    Each line dict: {dossier_adv_id, client_nom, lot_reference, montant_impute, motif}
    """
    from app.models.notary_escrow import EtatDetaille, EtatDetailleLine

    montant_global = Decimal(str(montant_global))
    sum_lignes = sum(Decimal(str(l["montant_impute"])) for l in lines)

    # NOTAIRE-001: exact match required
    if _r2(sum_lignes) != _r2(montant_global):
        raise EtatDetailleDiscrepancy(
            f"Ecart etat detaille : somme des lignes = {sum_lignes} DA "
            f"!= montant cheque = {montant_global} DA. "
            f"Enregistrement en tresorerie bloque.",
            sum_lignes=sum_lignes,
            montant_global=montant_global,
        )

    etat = EtatDetaille(
        company_id=company_id,
        escrow_id=escrow_id,
        cheque_global_reference=cheque_reference,
        montant_global=montant_global,
        date_cheque=date_cheque,
        notaire_id=notaire_id,
        status="VALIDATED",
        sum_lignes=_r2(sum_lignes),
        created_by=created_by,
    )
    session.add(etat)
    session.flush()

    for line_data in lines:
        line = EtatDetailleLine(
            company_id=company_id,
            etat_detaille_id=etat.id,
            dossier_adv_id=line_data["dossier_adv_id"],
            client_nom=line_data["client_nom"],
            lot_reference=line_data["lot_reference"],
            montant_impute=Decimal(str(line_data["montant_impute"])),
            motif=line_data["motif"],
            created_by=created_by,
        )
        session.add(line)

    session.flush()
    return etat


# ═════════════════════════════════════════════════════════════════════════════
# 48-HOUR ALERT
# ═════════════════════════════════════════════════════════════════════════════

def check_48h_alerts(session: Session) -> list[dict]:
    """
    Check all escrow accounts for positive balances exceeding 48h
    ABOVE the expected 5% reserves.
    Returns list of alert dicts.
    """
    from app.models.notary_escrow import NotaryEscrow

    now = datetime.now(timezone.utc)
    threshold = timedelta(hours=48)

    escrows = (
        session.query(NotaryEscrow)
        .filter(
            NotaryEscrow.solde_transitoire > 0,
            NotaryEscrow.is_deleted.is_(False),
        )
        .all()
    )

    alerts = []
    for escrow in escrows:
        balance = Decimal(str(escrow.solde_transitoire))
        reserve = Decimal(str(escrow.expected_5pct_reserve))
        excess = balance - reserve

        if excess <= Decimal("0"):
            # Balance is entirely attributable to 5% reserves — legitimate
            escrow.alert_48h_active = "N"
            continue

        # Check how long the excess has persisted
        if escrow.last_zero_at:
            duration = now - escrow.last_zero_at
            if duration > threshold:
                escrow.alert_48h_active = "Y"
                alerts.append({
                    "escrow_id": str(escrow.id),
                    "project_id": str(escrow.project_id),
                    "solde": str(balance),
                    "reserve_5pct": str(reserve),
                    "excess": str(excess),
                    "hours_since_zero": int(duration.total_seconds() / 3600),
                    "message": (
                        f"Solde transitoire positif depuis "
                        f"{int(duration.total_seconds() / 3600)} heures — "
                        f"liberation en retard ?"
                    ),
                })
        else:
            # Never been at zero — check from creation
            if escrow.created_at:
                duration = now - escrow.created_at
                if duration > threshold and excess > Decimal("0"):
                    escrow.alert_48h_active = "Y"
                    alerts.append({
                        "escrow_id": str(escrow.id),
                        "project_id": str(escrow.project_id),
                        "solde": str(balance),
                        "excess": str(excess),
                        "message": "Solde transitoire positif depuis creation — verifier.",
                    })

    session.flush()
    return alerts
