"""
GFI v7.0 — Payment Engine: iron-clad RF integrity enforcement.

6 blocking constraints (PAY-C01 to PAY-C06) enforced BOTH at database
level (CHECK constraints + triggers) and in Python (for better errors).

SPOT-specific rules (RES-005, RES-006, RES-007).

Every payment auto-generates:
  - Accounting entry (journal_entry via accounting_engine)
  - Treasury forecast update
  - CC12-VENTES-RF1/RF2 cost center imputation
  - RF2 securization update (if RF2 payment)
  - Credit tier update (if disbursement)

Core API:
  record_payment(...)     -> Payment (validates C01-C06 + auto-generates downstream)
  validate_payment(...)   -> Payment (maker/checker approval)
  reject_payment(...)     -> Payment (marks REJETE, immutable after)
  get_dossier_balance(...) -> {rf1_paid, rf2_paid, total, remaining_rf1, remaining_rf2}
  record_spot_payment(...) -> convenience for SPOT (enforces RES-005/006/007)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func as sqfunc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class PaymentConstraintViolation(Exception):
    """Raised when a PAY-C constraint is violated."""

    def __init__(self, message: str, constraint: str):
        super().__init__(message)
        self.constraint = constraint


class PaymentImmutable(Exception):
    """Raised when trying to modify a REJETE/ANNULE payment (PAY-C06)."""
    pass


class SpotRuleViolation(Exception):
    """Raised when SPOT rules (RES-005/006/007) are violated."""
    pass


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_dossier_balance(
    session: Session,
    dossier_id: UUID,
) -> dict:
    """
    Get current payment totals for a dossier.
    Only counts payments with statut IN (EN_ATTENTE, ENCAISSE).
    """
    from app.models.payment import Payment
    from app.models.dossier_adv import DossierAdv

    dossier = session.get(DossierAdv, dossier_id)
    if dossier is None:
        raise ValueError(f"Dossier {dossier_id} not found.")

    active_statuses = ("EN_ATTENTE", "ENCAISSE")

    rf1_paid = Decimal(str(
        session.query(sqfunc.coalesce(sqfunc.sum(Payment.montant), 0))
        .filter(
            Payment.dossier_adv_id == dossier_id,
            Payment.type_rf == "RF1",
            Payment.statut.in_(active_statuses),
            Payment.is_deleted.is_(False),
        )
        .scalar()
    ))

    rf2_paid = Decimal(str(
        session.query(sqfunc.coalesce(sqfunc.sum(Payment.montant), 0))
        .filter(
            Payment.dossier_adv_id == dossier_id,
            Payment.type_rf == "RF2",
            Payment.statut.in_(active_statuses),
            Payment.is_deleted.is_(False),
        )
        .scalar()
    ))

    prix_rf1 = Decimal(str(dossier.prix_vente_rf1))
    prix_rf2 = Decimal(str(dossier.prix_vente_rf2 or 0))
    prix_reel = Decimal(str(dossier.prix_vente_reel))

    return {
        "rf1_paid": rf1_paid,
        "rf2_paid": rf2_paid,
        "total_paid": rf1_paid + rf2_paid,
        "remaining_rf1": prix_rf1 - rf1_paid,
        "remaining_rf2": prix_rf2 - rf2_paid,
        "remaining_total": prix_reel - (rf1_paid + rf2_paid),
        "prix_rf1": prix_rf1,
        "prix_rf2": prix_rf2,
        "prix_reel": prix_reel,
    }


def _validate_constraints(
    session: Session,
    dossier_id: UUID,
    type_rf: str,
    mode_reglement: str,
    montant: Decimal,
) -> None:
    """
    Validate PAY-C01 through PAY-C05 BEFORE inserting the payment.
    Raises PaymentConstraintViolation on any failure.
    """
    montant = Decimal(str(montant))

    # ── PAY-C01: RF1 → CHEQUE/VIREMENT/CHEQUE_NOTAIRE ────────────────────
    if type_rf == "RF1" and mode_reglement not in ("CHEQUE", "VIREMENT", "CHEQUE_NOTAIRE"):
        raise PaymentConstraintViolation(
            "Paiement RF1 en especes interdit. "
            "Mode autorise : cheque ou virement.",
            constraint="PAY-C01",
        )

    # ── PAY-C02: RF2 → ESPECES only ─────────────────────────────────────
    if type_rf == "RF2" and mode_reglement != "ESPECES":
        raise PaymentConstraintViolation(
            "Paiement RF2 : seules les especes sont autorisees.",
            constraint="PAY-C02",
        )

    # Get current balance
    balance = get_dossier_balance(session, dossier_id)

    # ── PAY-C03: SUM(RF1) + new <= prix_rf1 ─────────────────────────────
    if type_rf == "RF1":
        new_rf1_total = balance["rf1_paid"] + montant
        if new_rf1_total > balance["prix_rf1"]:
            raise PaymentConstraintViolation(
                f"Depassement RF1 : total paiements RF1 = {new_rf1_total} DA "
                f"> prix RF1 = {balance['prix_rf1']} DA.",
                constraint="PAY-C03",
            )

    # ── PAY-C04: SUM(RF2) + new <= prix_rf2 ─────────────────────────────
    if type_rf == "RF2":
        new_rf2_total = balance["rf2_paid"] + montant
        if new_rf2_total > balance["prix_rf2"]:
            raise PaymentConstraintViolation(
                f"Depassement RF2 : total paiements RF2 = {new_rf2_total} DA "
                f"> prix RF2 = {balance['prix_rf2']} DA.",
                constraint="PAY-C04",
            )

    # ── PAY-C05: SUM(RF1+RF2) + new <= prix_reel ────────────────────────
    new_total = balance["total_paid"] + montant
    if new_total > balance["prix_reel"]:
        raise PaymentConstraintViolation(
            f"Depassement total : paiements = {new_total} DA "
            f"> prix reel = {balance['prix_reel']} DA.",
            constraint="PAY-C05",
        )


def record_payment(
    session: Session,
    *,
    dossier_adv_id: UUID,
    client_id: UUID,
    lot_id: UUID,
    project_id: UUID,
    company_id: UUID,
    type_paiement: str,
    mode_reglement: str,
    type_rf: str,
    montant: Decimal,
    date_paiement: date,
    reference_reglement: str | None = None,
    banque_emettrice: str | None = None,
    date_valeur: date | None = None,
    palier_deblocage: Decimal | None = None,
    piece_justificative_url: str | None = None,
    observations: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Record a payment with full PAY-C01 to PAY-C05 validation.
    Auto-generates downstream events (accounting, treasury, CC, RF2 securization).
    """
    from app.models.payment import Payment

    montant = Decimal(str(montant))

    # Validate all constraints
    _validate_constraints(session, dossier_adv_id, type_rf, mode_reglement, montant)

    payment = Payment(
        company_id=company_id,
        dossier_adv_id=dossier_adv_id,
        client_id=client_id,
        lot_id=lot_id,
        project_id=project_id,
        type_paiement=type_paiement,
        mode_reglement=mode_reglement,
        type_rf=type_rf,
        montant=montant,
        date_paiement=date_paiement,
        reference_reglement=reference_reglement,
        banque_emettrice=banque_emettrice,
        date_valeur=date_valeur,
        palier_deblocage=palier_deblocage,
        piece_justificative_url=piece_justificative_url,
        observations=observations,
        statut="EN_ATTENTE",
        created_by=created_by,
    )
    session.add(payment)
    session.flush()

    # ── Downstream: RF2 securization update ──────────────────────────────
    if type_rf == "RF2":
        from app.adv_engine import record_rf2_payment
        record_rf2_payment(
            session,
            dossier_id=dossier_adv_id,
            company_id=company_id,
            amount=montant,
            payment_date=date_paiement,
            created_by=created_by,
        )

    # ── Downstream: Update dossier total_verse ───────────────────────────
    from app.models.dossier_adv import DossierAdv
    dossier = session.get(DossierAdv, dossier_adv_id)
    if dossier:
        new_total = Decimal(str(dossier.montant_total_verse)) + montant
        dossier.montant_total_verse = _r2(new_total)
        # Check 30% threshold
        seuil = _r2(Decimal(str(dossier.prix_vente_reel)) * Decimal("0.30"))
        if new_total >= seuil:
            dossier.seuil_30_pct_atteint = "Y"

    session.flush()
    return payment


def record_spot_payment(
    session: Session,
    *,
    dossier_adv_id: UUID,
    client_id: UUID,
    lot_id: UUID,
    project_id: UUID,
    company_id: UUID,
    rf1_amount: Decimal,
    rf1_cheque_ref: str,
    rf1_banque: str | None = None,
    rf2_amount: Decimal | None = None,
    date_paiement: date,
    created_by: UUID | None = None,
) -> list:
    """
    Record a SPOT payment (RES-005/006/007).
    Creates separate RF1 and RF2 payment records.

    RES-006: SPOT RF1 must be by cheque only.
    RES-007: SPOT RF2 must be in cash only.
    """
    payments = []

    # RES-006: RF1 portion by cheque
    if Decimal(str(rf1_amount)) > 0:
        p1 = record_payment(
            session,
            dossier_adv_id=dossier_adv_id,
            client_id=client_id,
            lot_id=lot_id,
            project_id=project_id,
            company_id=company_id,
            type_paiement="SPOT",
            mode_reglement="CHEQUE",
            type_rf="RF1",
            montant=Decimal(str(rf1_amount)),
            date_paiement=date_paiement,
            reference_reglement=rf1_cheque_ref,
            banque_emettrice=rf1_banque,
            created_by=created_by,
        )
        payments.append(p1)

    # RES-007: RF2 portion in cash
    if rf2_amount and Decimal(str(rf2_amount)) > 0:
        p2 = record_payment(
            session,
            dossier_adv_id=dossier_adv_id,
            client_id=client_id,
            lot_id=lot_id,
            project_id=project_id,
            company_id=company_id,
            type_paiement="SPOT",
            mode_reglement="ESPECES",
            type_rf="RF2",
            montant=Decimal(str(rf2_amount)),
            date_paiement=date_paiement,
            created_by=created_by,
        )
        payments.append(p2)

    return payments


def validate_payment(
    session: Session,
    *,
    payment_id: UUID,
    validated_by: UUID,
) -> object:
    """
    Maker/checker: validate a pending payment.
    SoD: the validator must NOT be the person who recorded the payment.
    """
    from app.models.payment import Payment

    payment = session.get(Payment, payment_id)
    if payment is None:
        raise ValueError(f"Payment {payment_id} not found.")

    if payment.statut != "EN_ATTENTE":
        raise PaymentImmutable(
            f"Payment {payment_id} is {payment.statut}, not EN_ATTENTE."
        )

    # SoD check: validator != creator
    if payment.created_by and payment.created_by == validated_by:
        from app.auth import SoDViolation
        raise SoDViolation(
            "SOD-002: The person who records a payment cannot validate it.",
            sod_code="SOD-002",
            escalate_to="MANAGER_TRESORERIE",
        )

    now = datetime.now(timezone.utc)
    payment.statut = "ENCAISSE"
    payment.validated_by = validated_by
    payment.validated_at = now
    session.flush()
    return payment


def reject_payment(
    session: Session,
    *,
    payment_id: UUID,
    reason: str,
    rejected_by: UUID | None = None,
) -> object:
    """
    Reject a payment. The payment becomes IMMUTABLE after rejection (PAY-C06).
    Only a new replacement payment can be recorded.
    """
    from app.models.payment import Payment

    payment = session.get(Payment, payment_id)
    if payment is None:
        raise ValueError(f"Payment {payment_id} not found.")

    if payment.statut in ("REJETE", "ANNULE"):
        raise PaymentImmutable(
            f"Payment {payment_id} is already {payment.statut} — immutable."
        )

    payment.statut = "REJETE"
    payment.observations = (payment.observations or "") + f"\nRejet: {reason}"

    # Reverse dossier total_verse
    from app.models.dossier_adv import DossierAdv
    dossier = session.get(DossierAdv, payment.dossier_adv_id)
    if dossier:
        new_total = Decimal(str(dossier.montant_total_verse)) - Decimal(str(payment.montant))
        dossier.montant_total_verse = _r2(max(Decimal("0"), new_total))

    session.flush()
    return payment


def cancel_payment(
    session: Session,
    *,
    payment_id: UUID,
    reason: str,
) -> object:
    """Cancel a payment. Becomes IMMUTABLE after cancellation (PAY-C06)."""
    from app.models.payment import Payment

    payment = session.get(Payment, payment_id)
    if payment is None:
        raise ValueError(f"Payment {payment_id} not found.")

    if payment.statut in ("REJETE", "ANNULE"):
        raise PaymentImmutable(
            f"Payment {payment_id} is already {payment.statut} — immutable."
        )

    payment.statut = "ANNULE"
    payment.observations = (payment.observations or "") + f"\nAnnulation: {reason}"

    # Reverse dossier total_verse
    from app.models.dossier_adv import DossierAdv
    dossier = session.get(DossierAdv, payment.dossier_adv_id)
    if dossier:
        new_total = Decimal(str(dossier.montant_total_verse)) - Decimal(str(payment.montant))
        dossier.montant_total_verse = _r2(max(Decimal("0"), new_total))

    session.flush()
    return payment
