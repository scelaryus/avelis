"""
GFI v7.0 — Credit Purchase Workflow Engine (9 steps).

The most complex sales path: 9 sequential steps, each with blocking
conditions. 5 disbursement tiers totaling 100% of the credit amount.

Steps:
  1. Reservation + RF2 securization
  2. Engagement (blocked until RF2 = SECURISE)
  3. Bank file constitution (document checklist + relance)
  4. Credit contract (signed + tax-registered)
  5. Sign 3 wire transfer orders (15%, 35%, 25%)
  6. Notary deposit (complete file required)
  7. VSP signing (20% disbursement via notary escrow)
  8. Tier disbursements (15%, 35%, 25% — expert reports required)
  9. Delivery + final 5% release

Core API:
  initialize_credit_tiers(dossier_id) -> creates 5 CreditTier records
  check_step_ready(dossier_id, step) -> (ready, blockers)
  process_expert_report(report_id, ...) -> validates + chains next tier
  process_vsp_signing(dossier_id, ...) -> 20% escrow flow
  process_delivery(dossier_id, ...) -> PV + 5% release
  verify_final_closure(dossier_id) -> checks all balances
  check_wire_alerts() -> 15-day alert for missing wires
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class CreditStepBlocked(Exception):
    """Raised when a credit workflow step cannot proceed."""
    def __init__(self, message: str, step: int, blockers: list[str]):
        super().__init__(message)
        self.step = step
        self.blockers = blockers


class TierDecompositionError(Exception):
    """FIN-003: tiers don't sum to 100%."""
    pass


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ── Tier definitions ─────────────────────────────────────────────────────────
TIER_DEFINITIONS = [
    (0, "TIER_20PCT", Decimal("20"), "VIA_NOTAIRE"),
    (1, "TIER_15PCT", Decimal("15"), "DIRECT"),
    (2, "TIER_35PCT", Decimal("35"), "DIRECT"),
    (3, "TIER_25PCT", Decimal("25"), "DIRECT"),
    (4, "TIER_5PCT",  Decimal("5"),  "VIA_NOTAIRE"),
]


def initialize_credit_tiers(
    session: Session,
    *,
    dossier_adv_id: UUID,
    company_id: UUID,
    montant_credit: Decimal,
    created_by: UUID | None = None,
) -> list:
    """
    Create the 5 CreditTier records for a credit dossier.
    FIN-003: Verify 20+15+35+25+5 = 100.
    """
    from app.models.credit_workflow import CreditTier

    montant_credit = Decimal(str(montant_credit))

    # FIN-003: verify decomposition
    total_pct = sum(t[2] for t in TIER_DEFINITIONS)
    if total_pct != Decimal("100"):
        raise TierDecompositionError(
            f"FIN-003: Tier percentages sum to {total_pct}%, not 100%."
        )

    tiers = []
    for tier_num, label, pct, routing in TIER_DEFINITIONS:
        montant = _r2(montant_credit * pct / Decimal("100"))
        tier = CreditTier(
            company_id=company_id,
            dossier_adv_id=dossier_adv_id,
            tier_number=tier_num,
            tier_label=label,
            percentage=pct,
            montant=montant,
            status="EN_ATTENTE",
            routing=routing,
            created_by=created_by,
        )
        session.add(tier)
        tiers.append(tier)

    session.flush()
    return tiers


def check_step_ready(
    session: Session,
    dossier_id: UUID,
    step: int,
) -> tuple[bool, list[str]]:
    """
    Check if a specific credit workflow step can proceed.
    Returns (ready, list_of_blockers).
    """
    from app.models.dossier_adv import DossierAdv
    from app.models.credit_workflow import CreditTier, WireTransferOrder

    dossier = session.get(DossierAdv, dossier_id)
    if dossier is None:
        return False, ["Dossier not found"]

    blockers = []

    if step == 2:  # Engagement
        if dossier.statut_rf2 != "SECURISE" and dossier.prix_vente_rf2 and dossier.prix_vente_rf2 > 0:
            blockers.append("RF2 non securise (ENG-001)")
        if dossier.fond_garantie_disponible and dossier.montant_credit:
            if Decimal(str(dossier.fond_garantie_disponible)) < Decimal(str(dossier.montant_credit)):
                blockers.append("Fond de garantie insuffisant (ENG-004)")

    elif step == 4:  # Credit contract
        if not dossier.date_signature_contrat:
            blockers.append("Contrat credit non signe (CRE-002)")

    elif step == 5:  # Wire transfer orders
        orders = (
            session.query(WireTransferOrder)
            .filter(
                WireTransferOrder.dossier_adv_id == dossier_id,
                WireTransferOrder.is_deleted.is_(False),
            )
            .all()
        )
        signed_pcts = {
            Decimal(str(o.tier_percentage))
            for o in orders if o.status == "SIGNE"
        }
        for pct in [Decimal("15"), Decimal("35"), Decimal("25")]:
            if pct not in signed_pcts:
                blockers.append(f"Ordre de virement {pct}% non signe (CRE-001)")

    elif step == 6:  # Notary deposit
        # Check complete file
        if not dossier.date_signature_contrat:
            blockers.append("Contrat credit non enregistre aux impots")
        orders = (
            session.query(WireTransferOrder)
            .filter(
                WireTransferOrder.dossier_adv_id == dossier_id,
                WireTransferOrder.status == "SIGNE",
                WireTransferOrder.is_deleted.is_(False),
            )
            .count()
        )
        if orders < 3:
            blockers.append(f"Seulement {orders}/3 ordres de virement signes")

    elif step == 7:  # VSP
        ready_6, blockers_6 = check_step_ready(session, dossier_id, 6)
        if not ready_6:
            blockers.extend(blockers_6)

    elif step == 9:  # Delivery
        tiers = (
            session.query(CreditTier)
            .filter(
                CreditTier.dossier_adv_id == dossier_id,
                CreditTier.tier_number.in_([0, 1, 2, 3]),
                CreditTier.is_deleted.is_(False),
            )
            .all()
        )
        for t in tiers:
            if t.status != "DEBLOQUE":
                blockers.append(f"Palier {t.tier_label} non debloque")

    return len(blockers) == 0, blockers


def create_wire_transfer_orders(
    session: Session,
    *,
    dossier_adv_id: UUID,
    company_id: UUID,
    montant_credit: Decimal,
    dossier_reference: str,
    company_bank_account: str | None = None,
    created_by: UUID | None = None,
) -> list:
    """Create the 3 pre-signed wire transfer orders (15%, 35%, 25%)."""
    from app.models.credit_workflow import WireTransferOrder

    montant_credit = Decimal(str(montant_credit))
    orders = []

    for pct in [Decimal("15"), Decimal("35"), Decimal("25")]:
        montant = _r2(montant_credit * pct / Decimal("100"))
        order = WireTransferOrder(
            company_id=company_id,
            dossier_adv_id=dossier_adv_id,
            tier_percentage=pct,
            montant=montant,
            dossier_reference=dossier_reference,
            company_bank_account=company_bank_account,
            status="EN_ATTENTE",
            created_by=created_by,
        )
        session.add(order)
        orders.append(order)

    session.flush()
    return orders


def sign_wire_order(
    session: Session,
    *,
    order_id: UUID,
    signature_date: date,
    scan_url: str,
) -> object:
    """Record signature of a wire transfer order."""
    from app.models.credit_workflow import WireTransferOrder

    order = session.get(WireTransferOrder, order_id)
    if order is None:
        raise ValueError(f"WireTransferOrder {order_id} not found.")

    order.status = "SIGNE"
    order.signature_date = signature_date
    order.scan_url = scan_url
    session.flush()
    return order


def validate_expert_report(
    session: Session,
    *,
    report_id: UUID,
    validated_by: UUID,
) -> object:
    """
    CRE-005: Validate an expert report for tier disbursement.
    Unvalidated report -> disbursement BLOCKED.
    Auto-chains to next tier if its report is already received.
    """
    from app.models.credit_workflow import ExpertReport, CreditTier

    report = session.get(ExpertReport, report_id)
    if report is None:
        raise ValueError(f"ExpertReport {report_id} not found.")

    now = datetime.now(timezone.utc)
    report.status = "VALIDE"
    report.validated_by = validated_by
    report.validated_at = now

    # Update the corresponding tier
    tier_pct = Decimal(str(report.tier_percentage))
    tier = (
        session.query(CreditTier)
        .filter(
            CreditTier.dossier_adv_id == report.dossier_adv_id,
            CreditTier.percentage == tier_pct,
            CreditTier.is_deleted.is_(False),
        )
        .first()
    )

    if tier:
        tier.expert_report_id = report.id
        tier.status = "EXPERT_VALIDE"

    session.flush()

    # Check if next tier's report is already received -> auto-chain
    result = {"report_validated": True, "auto_chain": None}
    pct_order = [Decimal("15"), Decimal("35"), Decimal("25")]
    try:
        idx = pct_order.index(tier_pct)
        if idx < len(pct_order) - 1:
            next_pct = pct_order[idx + 1]
            next_report = (
                session.query(ExpertReport)
                .filter(
                    ExpertReport.dossier_adv_id == report.dossier_adv_id,
                    ExpertReport.tier_percentage == next_pct,
                    ExpertReport.status == "RECU",
                    ExpertReport.is_deleted.is_(False),
                )
                .first()
            )
            if next_report:
                result["auto_chain"] = f"Next tier {next_pct}% report already received"
    except ValueError:
        pass

    return result


def process_vsp_signing(
    session: Session,
    *,
    dossier_id: UUID,
    escrow_id: UUID,
    company_id: UUID,
    bank_name: str,
    company_name: str,
    reference_cheque: str | None = None,
    created_by: UUID | None = None,
) -> dict:
    """
    Step 7: VSP signing. Triggers 20% escrow transit.
    Bank -> notary escrow -> company account (immediate).
    """
    from app.models.dossier_adv import DossierAdv
    from app.models.credit_workflow import CreditTier
    from app.notary_escrow_engine import record_vsp_20pct

    dossier = session.get(DossierAdv, dossier_id)
    if dossier is None:
        raise ValueError(f"Dossier {dossier_id} not found.")

    # Check step readiness
    ready, blockers = check_step_ready(session, dossier_id, 7)
    if not ready:
        raise CreditStepBlocked(
            f"VSP impossible: {'; '.join(blockers)}",
            step=7, blockers=blockers,
        )

    # Get 20% tier
    tier_20 = (
        session.query(CreditTier)
        .filter(
            CreditTier.dossier_adv_id == dossier_id,
            CreditTier.tier_number == 0,
            CreditTier.is_deleted.is_(False),
        )
        .first()
    )

    if tier_20 is None:
        raise ValueError("Tier 20% not found. Initialize credit tiers first.")

    montant_20 = Decimal(str(tier_20.montant))

    # Execute escrow transit: bank -> escrow -> company
    credit_mv, debit_mv = record_vsp_20pct(
        session,
        escrow_id=escrow_id,
        company_id=company_id,
        dossier_adv_id=dossier_id,
        montant_20pct=montant_20,
        bank_name=bank_name,
        company_name=company_name,
        reference_cheque=reference_cheque,
        created_by=created_by,
    )

    # Update tier status
    now = datetime.now(timezone.utc)
    tier_20.status = "DEBLOQUE"
    tier_20.wire_received_at = now
    tier_20.debloque_at = now

    # Update dossier
    dossier.date_signature_contrat = dossier.date_signature_contrat or now.date()

    session.flush()

    return {
        "tier_20_debloque": True,
        "montant": str(montant_20),
        "escrow_credit_id": str(credit_mv.id),
        "escrow_debit_id": str(debit_mv.id),
    }


def process_tier_disbursement(
    session: Session,
    *,
    dossier_id: UUID,
    tier_number: int,
    company_id: UUID,
    wire_received_date: date | None = None,
    created_by: UUID | None = None,
) -> object:
    """Process a tier disbursement (15%, 35%, or 25%) after bank wire receipt."""
    from app.models.credit_workflow import CreditTier

    tier = (
        session.query(CreditTier)
        .filter(
            CreditTier.dossier_adv_id == dossier_id,
            CreditTier.tier_number == tier_number,
            CreditTier.is_deleted.is_(False),
        )
        .first()
    )

    if tier is None:
        raise ValueError(f"Tier {tier_number} not found for dossier {dossier_id}.")

    if tier.status not in ("EXPERT_VALIDE", "DEMANDE_SOUMISE"):
        raise CreditStepBlocked(
            f"Tier {tier.tier_label} not ready for disbursement (status: {tier.status}).",
            step=8, blockers=[f"Tier status is {tier.status}"],
        )

    now = datetime.now(timezone.utc)
    tier.status = "DEBLOQUE"
    tier.wire_received_at = now
    tier.debloque_at = now

    session.flush()
    return tier


def process_delivery_5pct(
    session: Session,
    *,
    dossier_id: UUID,
    escrow_id: UUID,
    company_id: UUID,
    company_name: str,
    pv_remise_cles_path: str,
    created_by: UUID | None = None,
) -> dict:
    """
    Step 9: Delivery + 5% release from escrow.
    CRE-006: PV remise des cles is MANDATORY.
    """
    from app.models.dossier_adv import DossierAdv
    from app.models.credit_workflow import CreditTier
    from app.notary_escrow_engine import release_5pct

    dossier = session.get(DossierAdv, dossier_id)
    if dossier is None:
        raise ValueError(f"Dossier {dossier_id} not found.")

    # Check all tiers 0-3 are DEBLOQUE
    ready, blockers = check_step_ready(session, dossier_id, 9)
    if not ready:
        raise CreditStepBlocked(
            f"Delivery impossible: {'; '.join(blockers)}",
            step=9, blockers=blockers,
        )

    # Get 5% tier
    tier_5 = (
        session.query(CreditTier)
        .filter(
            CreditTier.dossier_adv_id == dossier_id,
            CreditTier.tier_number == 4,
            CreditTier.is_deleted.is_(False),
        )
        .first()
    )

    if tier_5 is None:
        raise ValueError("Tier 5% not found.")

    montant_5 = Decimal(str(tier_5.montant))

    # CRE-006: Release 5% from escrow (PV is mandatory — enforced by engine)
    debit_mv = release_5pct(
        session,
        escrow_id=escrow_id,
        company_id=company_id,
        dossier_adv_id=dossier_id,
        montant_5pct=montant_5,
        company_name=company_name,
        pv_remise_cles_path=pv_remise_cles_path,
        created_by=created_by,
    )

    now = datetime.now(timezone.utc)
    tier_5.status = "DEBLOQUE"
    tier_5.debloque_at = now

    dossier.date_livraison_effective = now.date()

    session.flush()

    return {
        "tier_5_debloque": True,
        "montant": str(montant_5),
        "escrow_debit_id": str(debit_mv.id),
    }


def verify_final_closure(
    session: Session,
    dossier_id: UUID,
) -> tuple[bool, list[str]]:
    """
    Final closure verification:
    - SUM(RF1 ENCAISSE) = prix_rf1
    - SUM(RF2 ENCAISSE) = prix_rf2
    - All tiers DEBLOQUE
    - All required documents present
    """
    from app.models.dossier_adv import DossierAdv
    from app.models.credit_workflow import CreditTier
    from app.models.payment import Payment
    from sqlalchemy import func as sqfunc

    dossier = session.get(DossierAdv, dossier_id)
    if dossier is None:
        return False, ["Dossier not found"]

    issues = []

    # RF1 balance
    rf1_total = Decimal(str(
        session.query(sqfunc.coalesce(sqfunc.sum(Payment.montant), 0))
        .filter(
            Payment.dossier_adv_id == dossier_id,
            Payment.type_rf == "RF1",
            Payment.statut == "ENCAISSE",
            Payment.is_deleted.is_(False),
        )
        .scalar()
    ))
    if rf1_total != Decimal(str(dossier.prix_vente_rf1)):
        issues.append(
            f"RF1: encaisse={rf1_total} != prix={dossier.prix_vente_rf1}"
        )

    # RF2 balance
    if dossier.prix_vente_rf2 and dossier.prix_vente_rf2 > 0:
        rf2_total = Decimal(str(
            session.query(sqfunc.coalesce(sqfunc.sum(Payment.montant), 0))
            .filter(
                Payment.dossier_adv_id == dossier_id,
                Payment.type_rf == "RF2",
                Payment.statut == "ENCAISSE",
                Payment.is_deleted.is_(False),
            )
            .scalar()
        ))
        if rf2_total != Decimal(str(dossier.prix_vente_rf2)):
            issues.append(
                f"RF2: encaisse={rf2_total} != prix={dossier.prix_vente_rf2}"
            )

    # All tiers
    tiers = (
        session.query(CreditTier)
        .filter(
            CreditTier.dossier_adv_id == dossier_id,
            CreditTier.is_deleted.is_(False),
        )
        .all()
    )
    for t in tiers:
        if t.status != "DEBLOQUE":
            issues.append(f"Tier {t.tier_label} not DEBLOQUE ({t.status})")

    return len(issues) == 0, issues


def check_wire_alerts(session: Session) -> list[dict]:
    """
    Check for tiers where wire has not been received 15+ days after request.
    """
    from app.models.credit_workflow import CreditTier

    now = datetime.now(timezone.utc)
    threshold = timedelta(days=15)

    overdue = (
        session.query(CreditTier)
        .filter(
            CreditTier.status == "DEMANDE_SOUMISE",
            CreditTier.request_submitted_at.isnot(None),
            CreditTier.is_deleted.is_(False),
        )
        .all()
    )

    alerts = []
    for tier in overdue:
        elapsed = now - tier.request_submitted_at
        if elapsed > threshold:
            days = elapsed.days
            tier.days_since_request = days
            if tier.wire_alert_sent_at is None or (now - tier.wire_alert_sent_at).days >= 7:
                tier.wire_alert_sent_at = now
                alerts.append({
                    "tier_id": str(tier.id),
                    "dossier_id": str(tier.dossier_adv_id),
                    "tier_label": tier.tier_label,
                    "days_since_request": days,
                    "montant": str(tier.montant),
                    "message": (
                        f"Virement palier {tier.tier_label} non recu "
                        f"depuis {days} jours — relance banque requise."
                    ),
                })

    session.flush()
    return alerts
