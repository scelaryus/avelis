"""
GFI v7.0 — Fonds Propres (Own-Funds) Payment Workflow Engine.

3 conditional cases for the 30% initial payment:
  Case 1: 30% <= RF2 price → all cash, RF2 partial, no engagement yet
  Case 2: 30% > RF2 and < total → auto RF1/RF2 split, engagement if OK
  Case 3: 30% >= total → full upfront, fast-track

Installment schedule for remaining 70% RF1 balance.
Daily monitoring job with escalation ladder.
Penalty calculation: montant * (taux/365) * jours_retard.

Core API:
  calculate_initial_payment(prix_rf1, prix_rf2) -> case + amounts
  process_initial_payment(dossier_id, amount, ...) -> auto-split RF1/RF2
  generate_echeancier(dossier_id, ...) -> creates schedule
  run_daily_monitoring(date) -> processes all due/late installments
  calculate_penalty(echeance_id) -> computes accumulated penalty
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class FPEngagementBlocked(Exception):
    """FP-001: total paid < 30% of prix_reel."""
    def __init__(self, message: str, paid: Decimal, required: Decimal):
        super().__init__(message)
        self.paid = paid
        self.required = required


class FPDefaultBlocked(Exception):
    """FP-005: dossier in DEFAUT_PAIEMENT — all operations blocked."""
    pass


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ═════════════════════════════════════════════════════════════════════════════
# 3-CASE INITIAL PAYMENT ALGORITHM
# ═════════════════════════════════════════════════════════════════════════════

def calculate_initial_payment(
    prix_rf1: Decimal,
    prix_rf2: Decimal,
) -> dict:
    """
    Determine which case applies and compute the RF1/RF2 split.
    Returns: {case, seuil_30pct, rf2_portion, rf1_portion, engagement_possible}
    """
    prix_rf1 = Decimal(str(prix_rf1))
    prix_rf2 = Decimal(str(prix_rf2))
    prix_reel = prix_rf1 + prix_rf2
    seuil = _r2(prix_reel * Decimal("0.30"))

    if seuil <= prix_rf2:
        # CASE 1: 30% entirely within RF2
        return {
            "case": 1,
            "seuil_30pct": seuil,
            "rf2_portion": seuil,
            "rf1_portion": Decimal("0"),
            "total_initial": seuil,
            "engagement_possible": False,
            "description": (
                "30% <= prix RF2. Tout en especes. RF2 partiellement "
                "securise. Pas d'engagement tant que RF2 non complet."
            ),
        }

    elif seuil < prix_reel:
        # CASE 2: 30% exceeds RF2 but less than total
        rf2_portion = prix_rf2
        rf1_portion = seuil - prix_rf2
        return {
            "case": 2,
            "seuil_30pct": seuil,
            "rf2_portion": rf2_portion,
            "rf1_portion": rf1_portion,
            "total_initial": seuil,
            "engagement_possible": True,
            "description": (
                f"30% > prix RF2. Split: RF2={rf2_portion} DA (especes) "
                f"+ RF1={rf1_portion} DA (cheque). Engagement possible."
            ),
        }

    else:
        # CASE 3: 30% >= total (full upfront)
        return {
            "case": 3,
            "seuil_30pct": seuil,
            "rf2_portion": prix_rf2,
            "rf1_portion": prix_rf1,
            "total_initial": prix_reel,
            "engagement_possible": True,
            "description": (
                "Paiement integral. RF2 en especes, RF1 par cheque. "
                "Engagement immediat + cloture acceleree."
            ),
        }


def process_initial_payment(
    session: Session,
    *,
    dossier_id: UUID,
    total_amount: Decimal,
    date_paiement: date,
    rf1_cheque_ref: str | None = None,
    rf1_banque: str | None = None,
    created_by: UUID | None = None,
) -> dict:
    """
    Process the initial payment with automatic RF1/RF2 split.
    Calls the payment engine for each portion.
    """
    from app.models.dossier_adv import DossierAdv
    from app.payment_engine import record_payment

    dossier = session.get(DossierAdv, dossier_id)
    if dossier is None:
        raise ValueError(f"Dossier {dossier_id} not found.")

    total_amount = Decimal(str(total_amount))
    prix_rf1 = Decimal(str(dossier.prix_vente_rf1))
    prix_rf2 = Decimal(str(dossier.prix_vente_rf2 or 0))

    calc = calculate_initial_payment(prix_rf1, prix_rf2)
    result = {"case": calc["case"], "payments": []}

    rf2_to_pay = min(total_amount, calc["rf2_portion"])
    rf1_to_pay = total_amount - rf2_to_pay

    # RF2 portion (cash)
    if rf2_to_pay > 0:
        p_rf2 = record_payment(
            session,
            dossier_adv_id=dossier_id,
            client_id=dossier.client_id,
            lot_id=dossier.lot_id,
            project_id=dossier.project_id,
            company_id=dossier.company_id,
            type_paiement="SPOT",
            mode_reglement="ESPECES",
            type_rf="RF2",
            montant=rf2_to_pay,
            date_paiement=date_paiement,
            created_by=created_by,
        )
        result["payments"].append({
            "rf_type": "RF2", "amount": str(rf2_to_pay),
            "mode": "ESPECES", "receipt": "AUCUN",
        })

    # RF1 portion (cheque)
    if rf1_to_pay > 0:
        p_rf1 = record_payment(
            session,
            dossier_adv_id=dossier_id,
            client_id=dossier.client_id,
            lot_id=dossier.lot_id,
            project_id=dossier.project_id,
            company_id=dossier.company_id,
            type_paiement="SPOT",
            mode_reglement="CHEQUE",
            type_rf="RF1",
            montant=rf1_to_pay,
            date_paiement=date_paiement,
            reference_reglement=rf1_cheque_ref,
            banque_emettrice=rf1_banque,
            created_by=created_by,
        )
        result["payments"].append({
            "rf_type": "RF1", "amount": str(rf1_to_pay),
            "mode": "CHEQUE", "receipt": "OFFICIEL",
        })

    result["engagement_possible"] = calc["engagement_possible"]
    return result


# ═════════════════════════════════════════════════════════════════════════════
# INSTALLMENT SCHEDULE GENERATION
# ═════════════════════════════════════════════════════════════════════════════

def generate_echeancier(
    session: Session,
    *,
    dossier_id: UUID,
    company_id: UUID,
    project_id: UUID,
    solde_rf1: Decimal,
    date_engagement: date,
    date_livraison_prevue: date,
    frequence: str = "MENSUEL",
    taux_penalite_annuel: Decimal = Decimal("5.00"),
    created_by: UUID | None = None,
) -> object:
    """
    Generate the installment schedule for the remaining RF1 balance.
    Each installment is RF1, cheque only (FP-003).
    Last installment absorbs rounding difference.
    """
    from app.models.echeancier import Echeancier, Echeance

    solde = Decimal(str(solde_rf1))
    if solde <= 0:
        raise ValueError("Solde RF1 must be positive to generate echeancier.")

    # Calculate duration
    months = (
        (date_livraison_prevue.year - date_engagement.year) * 12
        + (date_livraison_prevue.month - date_engagement.month)
    )
    if months < 1:
        months = 1

    nb = months if frequence == "MENSUEL" else months * 2
    if nb < 1:
        nb = 1

    montant_ech = _r2(solde / Decimal(str(nb)))
    montant_derniere = solde - (montant_ech * (nb - 1))

    ech = Echeancier(
        company_id=company_id,
        dossier_adv_id=dossier_id,
        project_id=project_id,
        solde_rf1=solde,
        date_engagement=date_engagement,
        date_livraison_prevue=date_livraison_prevue,
        duree_mois=months,
        frequence=frequence,
        nb_echeances=nb,
        montant_echeance=montant_ech,
        montant_derniere=montant_derniere,
        taux_penalite_annuel=taux_penalite_annuel,
        status="ACTIF",
        created_by=created_by,
    )
    session.add(ech)
    session.flush()

    # Generate individual installments
    current_date = date_engagement
    step_months = 1 if frequence == "MENSUEL" else 0
    step_days = 15 if frequence == "BIMENSUEL" else 0

    for i in range(1, nb + 1):
        # Advance date
        if frequence == "MENSUEL":
            month = current_date.month + 1
            year = current_date.year
            if month > 12:
                month = 1
                year += 1
            _, last_day = monthrange(year, month)
            day = min(current_date.day, last_day)
            current_date = date(year, month, day)
        else:
            current_date = current_date + timedelta(days=15)

        montant = montant_derniere if i == nb else montant_ech

        installment = Echeance(
            company_id=company_id,
            echeancier_id=ech.id,
            numero=i,
            date_echeance=current_date,
            montant=montant,
            status="A_VENIR",
            created_by=created_by,
        )
        session.add(installment)

    session.flush()

    # Link echeancier to dossier
    from app.models.dossier_adv import DossierAdv
    dossier = session.get(DossierAdv, dossier_id)
    if dossier:
        dossier.echeancier_id = ech.id

    session.flush()
    return ech


# ═════════════════════════════════════════════════════════════════════════════
# DAILY MONITORING JOB (runs at 07:00)
# ═════════════════════════════════════════════════════════════════════════════

def run_daily_monitoring(
    session: Session,
    today: date | None = None,
) -> dict:
    """
    Process all installments: mark DUE, EN_RETARD, send relances,
    calculate penalties, trigger DEFAUT_PAIEMENT at J+60.
    """
    from app.models.echeancier import Echeancier, Echeance
    from app.models.dossier_adv import DossierAdv

    if today is None:
        today = date.today()

    stats = {
        "due_today": 0,
        "newly_late": 0,
        "penalties_calculated": 0,
        "defaults_triggered": 0,
        "reminders_sent": 0,
    }

    # Get all active echeanciers
    echeanciers = (
        session.query(Echeancier)
        .filter(
            Echeancier.status == "ACTIF",
            Echeancier.is_deleted.is_(False),
        )
        .all()
    )

    for ech in echeanciers:
        installments = (
            session.query(Echeance)
            .filter(
                Echeance.echeancier_id == ech.id,
                Echeance.status.in_(["A_VENIR", "DUE", "EN_RETARD"]),
                Echeance.is_deleted.is_(False),
            )
            .order_by(Echeance.date_echeance)
            .all()
        )

        for inst in installments:
            due_date = inst.date_echeance
            days_diff = (today - due_date).days

            # ── Preventive reminders (before due date) ───────────────
            if days_diff == -7 and inst.relance_j7_sent == "N":
                inst.relance_j7_sent = "Y"
                stats["reminders_sent"] += 1

            if days_diff == -3 and inst.relance_j3_sent == "N":
                inst.relance_j3_sent = "Y"
                stats["reminders_sent"] += 1

            # ── Due today ────────────────────────────────────────────
            if days_diff == 0 and inst.status == "A_VENIR":
                inst.status = "DUE"
                stats["due_today"] += 1

            # ── Late ─────────────────────────────────────────────────
            if days_diff >= 1 and inst.status in ("A_VENIR", "DUE"):
                inst.status = "EN_RETARD"
                stats["newly_late"] += 1

            if inst.status == "EN_RETARD":
                inst.jours_retard = max(0, days_diff)

                # Calculate penalty (FP-004)
                taux = Decimal(str(ech.taux_penalite_annuel))
                montant = Decimal(str(inst.montant))
                jours = Decimal(str(inst.jours_retard))
                penalty = _r2(montant * taux / Decimal("365") / Decimal("100") * jours)
                inst.penalite_montant = penalty
                stats["penalties_calculated"] += 1

                # Relance escalation
                if days_diff >= 7 and inst.relance_j7r_sent == "N":
                    inst.relance_j7r_sent = "Y"
                    stats["reminders_sent"] += 1
                if days_diff >= 15 and inst.relance_j15r_sent == "N":
                    inst.relance_j15r_sent = "Y"
                    stats["reminders_sent"] += 1
                if days_diff >= 30 and inst.relance_j30r_sent == "N":
                    inst.relance_j30r_sent = "Y"
                    inst.mise_en_demeure_sent = "Y"
                    stats["reminders_sent"] += 1

                # FP-005: DEFAUT_PAIEMENT at J+60
                if days_diff >= 60 and inst.status != "DEFAUT":
                    inst.status = "DEFAUT"
                    ech.status = "DEFAUT"
                    ech.nb_retards += 1

                    # Block the dossier
                    dossier = session.get(DossierAdv, ech.dossier_adv_id)
                    if dossier and dossier.statut_global != "DEFAUT_PAIEMENT":
                        dossier.statut_global = "DEFAUT_PAIEMENT"
                        stats["defaults_triggered"] += 1

        # Update echeancier totals
        total_penalites = sum(
            Decimal(str(i.penalite_montant))
            for i in installments if i.penalite_montant
        )
        ech.total_penalites = _r2(total_penalites)

    session.flush()
    return stats


def record_installment_payment(
    session: Session,
    *,
    echeance_id: UUID,
    payment_id: UUID,
    date_paiement: date,
    montant_paye: Decimal,
) -> object:
    """Record payment of an installment. Updates echeancier totals."""
    from app.models.echeancier import Echeance, Echeancier

    inst = session.get(Echeance, echeance_id)
    if inst is None:
        raise ValueError(f"Echeance {echeance_id} not found.")

    inst.status = "PAYEE"
    inst.date_paiement = date_paiement
    inst.montant_paye = Decimal(str(montant_paye))
    inst.payment_id = payment_id

    # Update echeancier total
    ech = session.get(Echeancier, inst.echeancier_id)
    if ech:
        ech.total_paye = _r2(
            Decimal(str(ech.total_paye)) + Decimal(str(montant_paye))
        )
        # Check if all installments paid
        from app.models.echeancier import Echeance as EchModel
        remaining = (
            session.query(EchModel)
            .filter(
                EchModel.echeancier_id == ech.id,
                EchModel.status.in_(["A_VENIR", "DUE", "EN_RETARD"]),
                EchModel.is_deleted.is_(False),
            )
            .count()
        )
        if remaining == 0:
            ech.status = "TERMINE"

    session.flush()
    return inst
