"""
GFI v7.0 — Legal + Governance Engine.

Contract lifecycle alerts, share transfers with preemption (R-017),
capital calls with CCA freeze (R-016).

Core API:
  check_contract_alerts(today)           -> expiration alerts 30/15/7 days
  initiate_share_transfer(...)           -> notifies all associates
  process_preemption_response(...)       -> records exercise/renounce
  complete_share_transfer(...)           -> updates ownership + KT-09
  issue_capital_call(...)                -> creates call + freeze if unpaid
  record_capital_call_payment(...)       -> unfreeze if fully covered
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class PreemptionPeriodActive(Exception):
    """Transfer blocked — preemption period still running."""
    pass


class OwnershipSumError(Exception):
    """KT-09: ownership doesn't sum to 100%."""
    pass


class TransferBlockedByCapitalCall(Exception):
    """Associate has unpaid capital call — transfers blocked."""
    pass


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def check_contract_alerts(
    session: Session,
    today: date | None = None,
) -> list[dict]:
    """Check for contracts expiring in 30/15/7 days. Send alerts."""
    from app.models.legal import ContractLifecycle

    if today is None:
        today = date.today()

    alerts = []

    for days, field in [(30, "alert_30d_sent"), (15, "alert_15d_sent"), (7, "alert_7d_sent")]:
        target = today + timedelta(days=days)
        contracts = (
            session.query(ContractLifecycle)
            .filter(
                ContractLifecycle.expiration_date == target,
                ContractLifecycle.status == "ACTIF",
                getattr(ContractLifecycle, field).is_(False),
                ContractLifecycle.is_deleted.is_(False),
            )
            .all()
        )
        for c in contracts:
            setattr(c, field, True)
            alerts.append({
                "contract_id": str(c.id),
                "title": c.title,
                "expiration": str(c.expiration_date),
                "days_remaining": days,
            })

    session.flush()
    return alerts


def initiate_share_transfer(
    session: Session,
    *,
    company_id: UUID,
    seller_associate_id: UUID,
    buyer_name: str,
    ownership_type: str,
    target_entity_id: UUID,
    percentage: Decimal,
    transfer_price: Decimal | None = None,
    preemption_days: int = 30,
    created_by: UUID | None = None,
) -> object:
    """
    R-017: Initiate share transfer. Notifies ALL other associates
    of their preemption right. 30-day response period.
    """
    from app.models.legal import ShareTransfer, PreemptionRight, CapitalCall
    from app.models.entreprise_associe import EntrepriseAssocie

    # Check seller has no unpaid capital calls
    unpaid = (
        session.query(CapitalCall)
        .filter(
            CapitalCall.company_id == company_id,
            CapitalCall.associate_id == seller_associate_id,
            CapitalCall.status.in_(["EMIS", "IMPAYE"]),
            CapitalCall.is_deleted.is_(False),
        )
        .first()
    )
    if unpaid:
        raise TransferBlockedByCapitalCall(
            f"Associate has unpaid capital call ({unpaid.call_ref}). "
            f"Share transfer blocked."
        )

    today = date.today()
    deadline = today + timedelta(days=preemption_days)

    transfer = ShareTransfer(
        company_id=company_id,
        seller_associate_id=seller_associate_id,
        buyer_name=buyer_name,
        ownership_type=ownership_type,
        target_entity_id=target_entity_id,
        percentage_transferred=Decimal(str(percentage)),
        transfer_price=Decimal(str(transfer_price)) if transfer_price else None,
        request_date=today,
        preemption_deadline=deadline,
        preemption_period_days=preemption_days,
        status="PREEMPTION_EN_COURS",
        created_by=created_by,
    )
    session.add(transfer)
    session.flush()

    # Notify all OTHER associates in this entity
    associates = (
        session.query(EntrepriseAssocie)
        .filter(
            EntrepriseAssocie.company_id == company_id,
            EntrepriseAssocie.associate_id != seller_associate_id,
            EntrepriseAssocie.is_deleted.is_(False),
        )
        .all()
    )

    now = datetime.now(timezone.utc)
    for ea in associates:
        pr = PreemptionRight(
            company_id=company_id,
            share_transfer_id=transfer.id,
            associate_id=ea.associate_id,
            notified_at=now,
            deadline=deadline,
            response="NOTIFIE",
            created_by=created_by,
        )
        session.add(pr)

    session.flush()
    return transfer


def process_preemption_response(
    session: Session,
    *,
    preemption_id: UUID,
    response: str,
    notes: str | None = None,
) -> object:
    """Record an associate's preemption response: EXERCE or RENONCE."""
    from app.models.legal import PreemptionRight, ShareTransfer

    pr = session.get(PreemptionRight, preemption_id)
    if pr is None:
        raise ValueError(f"PreemptionRight {preemption_id} not found.")

    pr.response = response
    pr.response_date = date.today()
    pr.notes = notes

    # If exercised, mark transfer accordingly
    if response == "EXERCE":
        transfer = session.get(ShareTransfer, pr.share_transfer_id)
        if transfer:
            transfer.status = "PREEMPTION_EXERCEE"
            transfer.buyer_associate_id = pr.associate_id
            transfer.is_internal_transfer = True

    session.flush()
    return pr


def complete_share_transfer(
    session: Session,
    transfer_id: UUID,
) -> object:
    """
    Execute the share transfer. Updates ownership matrix.
    KT-09: Verifies sum = 100.0000% after update.
    """
    from app.models.legal import ShareTransfer, PreemptionRight
    from app.models.entreprise_associe import EntrepriseAssocie
    from sqlalchemy import func as sqfunc

    transfer = session.get(ShareTransfer, transfer_id)
    if transfer is None:
        raise ValueError(f"ShareTransfer {transfer_id} not found.")

    # Check preemption period is over or exercised
    if transfer.status == "PREEMPTION_EN_COURS":
        today = date.today()
        if today < transfer.preemption_deadline:
            # Check if all have responded
            pending = (
                session.query(PreemptionRight)
                .filter(
                    PreemptionRight.share_transfer_id == transfer_id,
                    PreemptionRight.response == "NOTIFIE",
                    PreemptionRight.is_deleted.is_(False),
                )
                .count()
            )
            if pending > 0:
                raise PreemptionPeriodActive(
                    f"Preemption period active until {transfer.preemption_deadline}. "
                    f"{pending} associates haven't responded."
                )

    pct = Decimal(str(transfer.percentage_transferred))

    if transfer.ownership_type == "ENTREPRISE":
        # Update entreprise_associe
        seller_ea = (
            session.query(EntrepriseAssocie)
            .filter(
                EntrepriseAssocie.company_id == transfer.target_entity_id,
                EntrepriseAssocie.associate_id == transfer.seller_associate_id,
                EntrepriseAssocie.is_deleted.is_(False),
            )
            .first()
        )
        if seller_ea:
            seller_ea.percentage = _r2(Decimal(str(seller_ea.percentage)) - pct)

        # Add to buyer (if internal)
        if transfer.buyer_associate_id:
            buyer_ea = (
                session.query(EntrepriseAssocie)
                .filter(
                    EntrepriseAssocie.company_id == transfer.target_entity_id,
                    EntrepriseAssocie.associate_id == transfer.buyer_associate_id,
                    EntrepriseAssocie.is_deleted.is_(False),
                )
                .first()
            )
            if buyer_ea:
                buyer_ea.percentage = _r2(Decimal(str(buyer_ea.percentage)) + pct)

        # KT-09: verify sum = 100%
        total = Decimal(str(
            session.query(sqfunc.coalesce(sqfunc.sum(EntrepriseAssocie.percentage), 0))
            .filter(
                EntrepriseAssocie.company_id == transfer.target_entity_id,
                EntrepriseAssocie.is_deleted.is_(False),
            )
            .scalar()
        ))

        if _r2(total) != Decimal("100.0000"):
            raise OwnershipSumError(
                f"KT-09: Ownership sum = {total}% != 100.0000% "
                f"after transfer. ROLLBACK."
            )

        transfer.sum_verified_100pct = True

    transfer.status = "EXECUTE"
    transfer.completion_date = date.today()
    session.flush()
    return transfer


def issue_capital_call(
    session: Session,
    *,
    company_id: UUID,
    associate_id: UUID,
    montant: Decimal,
    due_date: date,
    call_ref: str | None = None,
    description: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """Issue a capital call. If unpaid by due_date, auto-freeze CCA."""
    from app.models.legal import CapitalCall

    montant = Decimal(str(montant))

    call = CapitalCall(
        company_id=company_id,
        associate_id=associate_id,
        call_date=date.today(),
        call_ref=call_ref,
        montant=montant,
        due_date=due_date,
        montant_restant=montant,
        description=description,
        status="EMIS",
        created_by=created_by,
    )
    session.add(call)
    session.flush()
    return call


def check_overdue_capital_calls(
    session: Session,
    today: date | None = None,
) -> list[dict]:
    """Check for overdue capital calls and freeze CCAs."""
    from app.models.legal import CapitalCall
    from app.cca_engine import freeze_for_capital_call

    if today is None:
        today = date.today()

    overdue = (
        session.query(CapitalCall)
        .filter(
            CapitalCall.status.in_(["EMIS", "PARTIELLEMENT_PAYE"]),
            CapitalCall.due_date < today,
            CapitalCall.montant_restant > 0,
            CapitalCall.is_deleted.is_(False),
        )
        .all()
    )

    frozen = []
    for call in overdue:
        call.status = "IMPAYE"

        # Find and freeze CCA
        from app.models.cca_account import CcaAccount
        cca = (
            session.query(CcaAccount)
            .filter(
                CcaAccount.company_id == call.company_id,
                CcaAccount.associate_id == call.associate_id,
                CcaAccount.status == "ACTIVE",
                CcaAccount.is_deleted.is_(False),
            )
            .first()
        )

        if cca:
            freeze = freeze_for_capital_call(
                session,
                cca_account_id=cca.id,
                company_id=call.company_id,
                freeze_date=today,
                capital_call_amount=Decimal(str(call.montant_restant)),
                capital_call_ref=call.call_ref,
            )
            call.cca_freeze_id = freeze.id
            frozen.append({
                "call_id": str(call.id),
                "associate_id": str(call.associate_id),
                "montant_restant": str(call.montant_restant),
            })

    session.flush()
    return frozen


def record_capital_call_payment(
    session: Session,
    *,
    call_id: UUID,
    montant_paye: Decimal,
) -> object:
    """Record payment on a capital call. Unfreeze CCA if fully covered."""
    from app.models.legal import CapitalCall

    call = session.get(CapitalCall, call_id)
    if call is None:
        raise ValueError(f"CapitalCall {call_id} not found.")

    montant = Decimal(str(montant_paye))
    call.montant_paye = _r2(Decimal(str(call.montant_paye)) + montant)
    call.montant_restant = _r2(Decimal(str(call.montant)) - Decimal(str(call.montant_paye)))

    if call.montant_restant <= 0:
        call.status = "PAYE"
        call.montant_restant = Decimal("0")

        # Unfreeze CCA
        if call.cca_freeze_id:
            from app.cca_engine import unfreeze
            unfreeze(session, cca_freeze_id=call.cca_freeze_id,
                     resolved_date=date.today())
    else:
        call.status = "PARTIELLEMENT_PAYE"

    session.flush()
    return call
