"""
GFI v7.0 — CCA (Compte Courant Associe) Treasury Engine.

Manages the 4 founders' CCAs across all entities they participate in.

Core rules:
  R-003 (KT-08): Double withdrawal rule — BOTH conditions must be met:
    1. Amount <= 50% of individual CCA balance
    2. Total sum of ALL CCAs in the entity is positive
  R-016 (S-17): CCA freeze on unpaid capital calls
  Every movement requires justification document

Core API:
  deposit(...)        -> CcaMovement
  withdraw(...)       -> CcaMovement (R-003 enforced)
  record_cff_deduction(...)  -> CcaMovement
  record_personal_debt(...)  -> CcaMovement
  record_commission(...)     -> CcaMovement
  get_balance(cca_account_id) -> Decimal
  get_entity_total(company_id) -> Decimal
  check_withdrawal_allowed(cca_account_id, amount) -> (bool, str)
  freeze_for_capital_call(...)  -> CcaFreeze
  unfreeze(...)               -> CcaFreeze
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from sqlalchemy import func as sqfunc


class CcaWithdrawalBlocked(Exception):
    """Raised when R-003 blocks a withdrawal."""

    def __init__(self, message: str, max_allowed: Decimal | None = None):
        super().__init__(message)
        self.max_allowed = max_allowed


class CcaFrozenError(Exception):
    """Raised when CCA is frozen (R-016)."""

    pass


class CcaJustificationMissing(Exception):
    """Raised when movement has no justification."""

    pass


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_balance(session: Session, cca_account_id: UUID) -> Decimal:
    """Get the current balance of a CCA account."""
    from app.models.cca_account import CcaAccount

    cca = session.get(CcaAccount, cca_account_id)
    if cca is None:
        raise ValueError(f"CCA account {cca_account_id} not found.")
    return Decimal(str(cca.balance))


def get_entity_total(session: Session, company_id: UUID) -> Decimal:
    """Get the sum of ALL CCA balances in an entity."""
    from app.models.cca_account import CcaAccount

    total = (
        session.query(sqfunc.coalesce(sqfunc.sum(CcaAccount.balance), 0))
        .filter(
            CcaAccount.company_id == company_id,
            CcaAccount.is_deleted.is_(False),
        )
        .scalar()
    )
    return Decimal(str(total))


def check_withdrawal_allowed(
    session: Session,
    cca_account_id: UUID,
    amount: Decimal,
) -> tuple[bool, str]:
    """
    Check R-003 double withdrawal rule.

    Returns (allowed: bool, message: str).
    Message explains why it's blocked if not allowed.
    """
    from app.models.cca_account import CcaAccount

    cca = session.get(CcaAccount, cca_account_id)
    if cca is None:
        return False, f"CCA account {cca_account_id} not found."

    if cca.status == "FROZEN":
        return False, (
            f"CCA gele — {cca.freeze_reason or 'capital call impaye'}. "
            f"Retrait interdit."
        )

    if cca.status == "CLOSED":
        return False, "CCA cloture — retrait interdit."

    amount = Decimal(str(amount))
    balance = Decimal(str(cca.balance))

    # Condition 1: amount <= 50% of individual balance
    if balance <= 0:
        return False, (
            f"Solde individuel CCA negatif ou nul ({balance} DA) — "
            f"retrait interdit."
        )

    max_individual = _r2(balance * Decimal("0.50"))
    if amount > max_individual:
        return False, (
            f"Montant maximum autorise : {max_individual} DA "
            f"(50% du solde individuel de {balance} DA)."
        )

    # Condition 2: total entity CCA balance must be positive
    entity_total = get_entity_total(session, cca.company_id)
    if entity_total <= 0:
        from app.models.company import Company
        company = session.get(Company, cca.company_id)
        company_name = company.legal_name if company else str(cca.company_id)
        return False, (
            f"Solde global CCA de {company_name} negatif — "
            f"retrait interdit."
        )

    return True, "OK"


def _require_justification(
    justification_type: str | None,
) -> None:
    """Enforce mandatory justification on every CCA movement."""
    if not justification_type:
        raise CcaJustificationMissing(
            "Tout mouvement CCA requiert une piece justificative."
        )


def _create_movement(
    session: Session,
    *,
    cca_account_id: UUID,
    company_id: UUID,
    movement_date: date,
    movement_type: str,
    label: str,
    amount: Decimal,
    justification_type: str,
    justification_ref: str | None = None,
    justification_path: str | None = None,
    rf_type: str | None = None,
    project_id: UUID | None = None,
    cc_category: str | None = None,
    source_document_type: str | None = None,
    source_document_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """Internal: create a movement and update balance."""
    from app.models.cca_account import CcaAccount
    from app.models.cca_movement import CcaMovement

    _require_justification(justification_type)

    cca = session.get(CcaAccount, cca_account_id)
    if cca is None:
        raise ValueError(f"CCA account {cca_account_id} not found.")

    amount = Decimal(str(amount))
    new_balance = Decimal(str(cca.balance)) + amount

    movement = CcaMovement(
        company_id=company_id,
        cca_account_id=cca_account_id,
        movement_date=movement_date,
        movement_type=movement_type,
        label=label,
        amount=amount,
        balance_after=_r2(new_balance),
        justification_type=justification_type,
        justification_ref=justification_ref,
        justification_path=justification_path,
        rf_type=rf_type,
        project_id=project_id,
        cc_category=cc_category,
        source_document_type=source_document_type,
        source_document_id=source_document_id,
        created_by=created_by,
    )
    session.add(movement)

    # Update running balance
    cca.balance = _r2(new_balance)
    session.flush()

    return movement


def deposit(
    session: Session,
    *,
    cca_account_id: UUID,
    company_id: UUID,
    movement_date: date,
    amount: Decimal,
    label: str = "Depot CCA",
    justification_type: str,
    justification_ref: str | None = None,
    justification_path: str | None = None,
    rf_type: str = "RF1",
    created_by: UUID | None = None,
) -> object:
    """Record a deposit into a CCA (positive movement)."""
    return _create_movement(
        session,
        cca_account_id=cca_account_id,
        company_id=company_id,
        movement_date=movement_date,
        movement_type="DEPOT",
        label=label,
        amount=abs(Decimal(str(amount))),  # always positive
        justification_type=justification_type,
        justification_ref=justification_ref,
        justification_path=justification_path,
        rf_type=rf_type,
        created_by=created_by,
    )


def withdraw(
    session: Session,
    *,
    cca_account_id: UUID,
    company_id: UUID,
    movement_date: date,
    amount: Decimal,
    label: str = "Retrait CCA",
    justification_type: str,
    justification_ref: str | None = None,
    justification_path: str | None = None,
    rf_type: str = "RF1",
    project_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Record a withdrawal from a CCA (negative movement).
    Enforces R-003 double withdrawal rule and R-016 freeze check.
    """
    amount = abs(Decimal(str(amount)))

    # R-003 + R-016 check
    allowed, message = check_withdrawal_allowed(
        session, cca_account_id, amount
    )
    if not allowed:
        max_allowed = None
        # Extract max from message if it's an individual limit
        from app.models.cca_account import CcaAccount
        cca = session.get(CcaAccount, cca_account_id)
        if cca and Decimal(str(cca.balance)) > 0:
            max_allowed = _r2(Decimal(str(cca.balance)) * Decimal("0.50"))
        raise CcaWithdrawalBlocked(message, max_allowed=max_allowed)

    return _create_movement(
        session,
        cca_account_id=cca_account_id,
        company_id=company_id,
        movement_date=movement_date,
        movement_type="RETRAIT",
        label=label,
        amount=-amount,  # negative for withdrawal
        justification_type=justification_type,
        justification_ref=justification_ref,
        justification_path=justification_path,
        rf_type=rf_type,
        project_id=project_id,
        cc_category="CC9",
        created_by=created_by,
    )


def record_cff_deduction(
    session: Session,
    *,
    cca_account_id: UUID,
    company_id: UUID,
    movement_date: date,
    amount: Decimal,
    cff_calculation_id: UUID,
    label: str = "Deduction CFF",
    created_by: UUID | None = None,
) -> object:
    """Record a CFF deduction on an associate's CCA (negative movement)."""
    return _create_movement(
        session,
        cca_account_id=cca_account_id,
        company_id=company_id,
        movement_date=movement_date,
        movement_type="CFF_DEDUCTION",
        label=label,
        amount=-abs(Decimal(str(amount))),
        justification_type="CFF_CALCULATION",
        justification_ref=str(cff_calculation_id),
        source_document_type="cff_calculation",
        source_document_id=cff_calculation_id,
        created_by=created_by,
    )


def record_personal_debt(
    session: Session,
    *,
    cca_account_id: UUID,
    company_id: UUID,
    movement_date: date,
    amount: Decimal,
    label: str,
    justification_type: str,
    justification_ref: str | None = None,
    project_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """Record a personal debt on an associate's CCA (negative = debt)."""
    return _create_movement(
        session,
        cca_account_id=cca_account_id,
        company_id=company_id,
        movement_date=movement_date,
        movement_type="DETTE_PERSONNELLE",
        label=label,
        amount=-abs(Decimal(str(amount))),
        justification_type=justification_type,
        justification_ref=justification_ref,
        project_id=project_id,
        cc_category="CC10",
        created_by=created_by,
    )


def record_commission(
    session: Session,
    *,
    cca_account_id: UUID,
    company_id: UUID,
    movement_date: date,
    amount: Decimal,
    label: str,
    direction: str,
    justification_type: str,
    justification_ref: str | None = None,
    project_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """Record commission income (CREDIT) or expense (DEBIT) on CCA."""
    amt = Decimal(str(amount))
    if direction == "DEBIT":
        amt = -abs(amt)
    else:
        amt = abs(amt)

    return _create_movement(
        session,
        cca_account_id=cca_account_id,
        company_id=company_id,
        movement_date=movement_date,
        movement_type="COMMISSION",
        label=label,
        amount=amt,
        justification_type=justification_type,
        justification_ref=justification_ref,
        project_id=project_id,
        cc_category="CC10",
        created_by=created_by,
    )


def record_distribution(
    session: Session,
    *,
    cca_account_id: UUID,
    company_id: UUID,
    movement_date: date,
    amount: Decimal,
    label: str = "Distribution de dividendes",
    justification_type: str = "PV_DISTRIBUTION",
    justification_ref: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """Record profit distribution credited to CCA (positive movement)."""
    return _create_movement(
        session,
        cca_account_id=cca_account_id,
        company_id=company_id,
        movement_date=movement_date,
        movement_type="DISTRIBUTION",
        label=label,
        amount=abs(Decimal(str(amount))),
        justification_type=justification_type,
        justification_ref=justification_ref,
        created_by=created_by,
    )


def freeze_for_capital_call(
    session: Session,
    *,
    cca_account_id: UUID,
    company_id: UUID,
    freeze_date: date,
    capital_call_amount: Decimal,
    capital_call_ref: str | None = None,
    description: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """R-016: Freeze CCA due to unpaid capital call."""
    from app.models.cca_account import CcaAccount
    from app.models.cca_freeze import CcaFreeze

    cca = session.get(CcaAccount, cca_account_id)
    if cca is None:
        raise ValueError(f"CCA account {cca_account_id} not found.")

    cca.status = "FROZEN"
    cca.freeze_reason = f"Capital call impaye: {capital_call_ref or 'N/A'}"

    freeze = CcaFreeze(
        company_id=company_id,
        cca_account_id=cca_account_id,
        freeze_date=freeze_date,
        reason="CAPITAL_CALL_UNPAID",
        description=description,
        capital_call_amount=Decimal(str(capital_call_amount)),
        capital_call_ref=capital_call_ref,
        status="ACTIVE",
        created_by=created_by,
    )
    session.add(freeze)
    session.flush()
    return freeze


def unfreeze(
    session: Session,
    *,
    cca_freeze_id: UUID,
    resolved_date: date,
    resolved_by_movement_id: UUID | None = None,
) -> None:
    """Unfreeze a CCA after capital call is covered."""
    from app.models.cca_account import CcaAccount
    from app.models.cca_freeze import CcaFreeze

    freeze = session.get(CcaFreeze, cca_freeze_id)
    if freeze is None:
        raise ValueError(f"CCA freeze {cca_freeze_id} not found.")

    freeze.status = "RESOLVED"
    freeze.resolved_date = resolved_date
    freeze.resolved_by_movement_id = resolved_by_movement_id

    # Check if there are other active freezes on this CCA
    active_freezes = (
        session.query(CcaFreeze)
        .filter(
            CcaFreeze.cca_account_id == freeze.cca_account_id,
            CcaFreeze.status == "ACTIVE",
            CcaFreeze.id != cca_freeze_id,
            CcaFreeze.is_deleted.is_(False),
        )
        .count()
    )

    if active_freezes == 0:
        cca = session.get(CcaAccount, freeze.cca_account_id)
        if cca:
            cca.status = "ACTIVE"
            cca.freeze_reason = None

    session.flush()


def get_associate_ccas(
    session: Session,
    associate_id: UUID,
) -> list:
    """Get all CCA accounts for an associate across all entities."""
    from app.models.cca_account import CcaAccount

    return (
        session.query(CcaAccount)
        .filter(
            CcaAccount.associate_id == associate_id,
            CcaAccount.is_deleted.is_(False),
        )
        .all()
    )


def get_movement_history(
    session: Session,
    cca_account_id: UUID,
    *,
    limit: int = 100,
) -> list:
    """Get recent movements for a CCA account."""
    from app.models.cca_movement import CcaMovement

    return (
        session.query(CcaMovement)
        .filter(
            CcaMovement.cca_account_id == cca_account_id,
            CcaMovement.is_deleted.is_(False),
        )
        .order_by(CcaMovement.movement_date.desc())
        .limit(limit)
        .all()
    )
