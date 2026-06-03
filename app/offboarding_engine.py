"""
GFI v7.0 — Offboarding + Disciplinary Engine.

3 triggers: resignation, termination, end of CDD.
STC blocked until ALL prerequisites met — NO override, not even PDG.
Disciplinary: PV constat -> convocation (48h rule) -> audition -> sanction.

Core API:
  initiate_resignation(employee_id, ...) -> OffboardingProcess
  initiate_termination(employee_id, disciplinary_case_id) -> OffboardingProcess
  check_cdd_expiring(today) -> alerts at J-30/15/7/1
  record_disciplinary_step(case_id, step, ...) -> DisciplinaryCase
  calculate_stc(offboarding_id) -> StcCalculation
  check_stc_prerequisites(offboarding_id) -> (ready, blockers)
  process_stc_payment(offboarding_id) -> raises if ANY prerequisite missing
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func as sqfunc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class StcBlocked(Exception):
    """STC payment blocked — prerequisites not met. NO override."""
    def __init__(self, message: str, blockers: list[str]):
        super().__init__(message)
        self.blockers = blockers


class DisciplinaryRuleViolation(Exception):
    """Disciplinary procedure rule violated (e.g., 48h rule)."""
    pass


def _r2(v): return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def initiate_resignation(
    session: Session,
    *,
    company_id: UUID,
    employee_id: UUID,
    resignation_date: date,
    proposed_last_day: date,
    notice_waived: bool = False,
    created_by: UUID | None = None,
) -> object:
    """Start offboarding for resignation."""
    from app.models.offboarding import OffboardingProcess
    from app.models.hr import Employee, EmployeeContract

    emp = session.get(Employee, employee_id)
    if emp:
        emp.status = "OFFBOARDING"

    contract = (
        session.query(EmployeeContract)
        .filter(EmployeeContract.employee_id == employee_id,
                EmployeeContract.status == "ACTIVE",
                EmployeeContract.is_deleted.is_(False))
        .first()
    )
    if contract:
        contract.status = "TERMINATED"
        contract.termination_date = proposed_last_day
        contract.termination_reason = "DEMISSION"

    process = OffboardingProcess(
        company_id=company_id,
        employee_id=employee_id,
        contract_id=contract.id if contract else None,
        trigger_type="DEMISSION",
        trigger_date=resignation_date,
        last_working_day=proposed_last_day,
        notice_period_waived=notice_waived,
        status="INITIE",
        created_by=created_by,
    )
    session.add(process)
    session.flush()
    return process


def initiate_termination(
    session: Session,
    *,
    company_id: UUID,
    employee_id: UUID,
    reason: str,
    last_day: date | None = None,
    disciplinary_case_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """Start offboarding for termination (disciplinary or economic)."""
    from app.models.offboarding import OffboardingProcess
    from app.models.hr import Employee, EmployeeContract

    emp = session.get(Employee, employee_id)
    if emp:
        emp.status = "OFFBOARDING"

    contract = (
        session.query(EmployeeContract)
        .filter(EmployeeContract.employee_id == employee_id,
                EmployeeContract.status == "ACTIVE",
                EmployeeContract.is_deleted.is_(False))
        .first()
    )
    if contract:
        contract.status = "TERMINATED"
        contract.termination_date = last_day or date.today()
        contract.termination_reason = reason

    process = OffboardingProcess(
        company_id=company_id,
        employee_id=employee_id,
        contract_id=contract.id if contract else None,
        trigger_type=reason,
        trigger_date=date.today(),
        last_working_day=last_day or date.today(),
        status="INITIE",
        created_by=created_by,
    )
    session.add(process)
    session.flush()

    # For termination for cause: immediate badge deactivation
    if reason == "LICENCIEMENT_FAUTE":
        from app.access_control_engine import deactivate_all_for_employee
        deactivate_all_for_employee(session, employee_id, "TERMINATION")
        process.badge_deactivated = True
        process.badge_deactivated_at = datetime.now(timezone.utc)

    session.flush()
    return process


def check_cdd_expiring(
    session: Session,
    today: date | None = None,
) -> list[dict]:
    """Daily check: CDD/chantier contracts expiring in 30/15/7/1 days."""
    from app.models.hr import EmployeeContract

    if today is None:
        today = date.today()

    alerts = []
    for days in [30, 15, 7, 1]:
        target = today + timedelta(days=days)
        contracts = (
            session.query(EmployeeContract)
            .filter(
                EmployeeContract.contract_type.in_(["CDD", "CHANTIER"]),
                EmployeeContract.end_date == target,
                EmployeeContract.status == "ACTIVE",
                EmployeeContract.is_deleted.is_(False),
            )
            .all()
        )
        for c in contracts:
            alerts.append({
                "contract_id": str(c.id),
                "employee_id": str(c.employee_id),
                "end_date": str(c.end_date),
                "days_remaining": days,
                "contract_type": c.contract_type,
            })

    return alerts


def record_disciplinary_step(
    session: Session,
    *,
    case_id: UUID,
    step: str,
    **kwargs,
) -> object:
    """Record a step in the disciplinary workflow. Enforces 48h rule."""
    from app.models.offboarding import DisciplinaryCase

    case = session.get(DisciplinaryCase, case_id)
    if case is None:
        raise ValueError(f"DisciplinaryCase {case_id} not found.")

    if step == "CONVOCATION":
        # 48h rule: audition must be >= 48h after PV constat
        if kwargs.get("audition_date"):
            aud = kwargs["audition_date"]
            if isinstance(aud, datetime):
                aud_date = aud.date() if hasattr(aud, 'date') else aud
            else:
                aud_date = aud
            pv_plus_48h = case.pv_constat_date + timedelta(days=2)
            if aud_date < pv_plus_48h:
                raise DisciplinaryRuleViolation(
                    f"Audition date {aud_date} < PV + 48h ({pv_plus_48h}). "
                    f"Rule: audition must be >= 48h after PV constat."
                )
        case.convocation_date = date.today()
        case.audition_date = kwargs.get("audition_date")
        case.audition_location = kwargs.get("location")
        case.rights_statement_included = kwargs.get("rights_included", True)
        case.status = "CONVOQUE"

    elif step == "AUDITION":
        case.employee_statements = kwargs.get("statements")
        case.questions_answers = kwargs.get("qa")
        case.assistant_name = kwargs.get("assistant_name")
        case.assistant_role = kwargs.get("assistant_role")
        case.status = "AUDITION_FAITE"

    elif step == "DECISION":
        case.sanction = kwargs.get("sanction")
        case.mise_a_pied_days = kwargs.get("suspension_days")
        case.decision_date = date.today()
        case.decision_justification = kwargs.get("justification")
        case.status = "DECISION_PRISE"

    session.flush()
    return case


def calculate_stc(
    session: Session,
    *,
    offboarding_id: UUID,
    created_by: UUID | None = None,
) -> object:
    """Calculate Solde de Tout Compte (6 components)."""
    from app.models.offboarding import OffboardingProcess, StcCalculation
    from app.models.hr import Employee, EmployeeContract
    from app.models.leave import LeaveBalance

    process = session.get(OffboardingProcess, offboarding_id)
    if process is None:
        raise ValueError(f"OffboardingProcess {offboarding_id} not found.")

    emp = session.get(Employee, process.employee_id)
    contract = session.get(EmployeeContract, process.contract_id) if process.contract_id else None
    salary_base = Decimal(str(contract.salary_base)) if contract else Decimal("0")
    daily = _r2(salary_base / Decimal("30"))

    # 1. Last month salary (prorata)
    days_worked = 30  # simplified; in production: calculate from last_working_day
    if process.last_working_day and process.last_working_day.day < 28:
        days_worked = process.last_working_day.day
    last_month = _r2(daily * Decimal(str(days_worked)))

    # 2. Leave compensation
    leave_bal = (
        session.query(LeaveBalance)
        .filter(
            LeaveBalance.employee_id == process.employee_id,
            LeaveBalance.leave_type == "ANNUEL",
            LeaveBalance.year == date.today().year,
            LeaveBalance.is_deleted.is_(False),
        )
        .first()
    )
    unused_days = Decimal(str(leave_bal.remaining_days)) if leave_bal else Decimal("0")
    leave_comp = _r2(unused_days * daily)

    # 3. Notice indemnity
    notice_ind = Decimal("0")
    if process.notice_period_waived and contract and contract.notice_period_days:
        notice_ind = _r2(Decimal(str(contract.notice_period_days)) * daily)

    # 4. Severance (if applicable)
    severance = Decimal("0")
    seniority_months = 0
    if process.trigger_type in ("LICENCIEMENT_ECONOMIQUE", "ACCORD_MUTUEL"):
        if emp and emp.seniority_date:
            delta = date.today() - emp.seniority_date
            seniority_months = delta.days // 30
            severance = _r2(Decimal(str(seniority_months)) * salary_base * Decimal("0.02"))
            min_severance = salary_base * 6
            if severance < min_severance:
                severance = min_severance

    # 5. 13th month prorated
    months_this_year = date.today().month
    thirteenth = _r2(salary_base * Decimal(str(months_this_year)) / Decimal("12"))

    # 6. Deductions
    advance = Decimal("0")  # from payroll
    loan = Decimal("0")     # from loan records
    equipment = Decimal("0")  # from restitution

    gross = last_month + leave_comp + notice_ind + severance + thirteenth
    total_ded = advance + loan + equipment
    net = _r2(gross - total_ded)

    stc = StcCalculation(
        company_id=process.company_id,
        employee_id=process.employee_id,
        offboarding_id=offboarding_id,
        calculation_date=date.today(),
        last_month_salary=last_month,
        days_worked=days_worked,
        leave_compensation=leave_comp,
        leave_days_unused=unused_days,
        notice_indemnity=notice_ind,
        severance_pay=severance,
        seniority_months=seniority_months,
        thirteenth_month_prorated=thirteenth,
        advance_repayment=advance,
        loan_balance=loan,
        equipment_deduction=equipment,
        other_deductions=Decimal("0"),
        gross_stc=gross,
        total_deductions=total_ded,
        net_stc=net,
        status="CALCULATED",
        created_by=created_by,
    )
    session.add(stc)
    session.flush()

    process.stc_calculation_id = stc.id
    session.flush()
    return stc


def check_stc_prerequisites(
    session: Session,
    offboarding_id: UUID,
) -> tuple[bool, list[str]]:
    """
    ABSOLUTE CHECK: ALL prerequisites must be True for STC payment.
    NO override mechanism exists, not even for the PDG.
    """
    from app.models.offboarding import OffboardingProcess

    process = session.get(OffboardingProcess, offboarding_id)
    if process is None:
        return False, ["OffboardingProcess not found"]

    blockers = []

    if not process.handover_pv_signed:
        blockers.append("PV de passation non signe")
    if not process.equipment_quitus_signed:
        blockers.append("Quitus equipement non signe (tous items non resolus)")
    if not process.badge_deactivated:
        blockers.append("Badge non desactive sur tous les controleurs")
    if not process.digital_access_revoked:
        blockers.append("Acces numeriques non revoques")
    if not process.stc_verified_l6:
        blockers.append("STC non verifie L1-L6")
    if not process.stc_approved_triple:
        blockers.append("STC non approuve DRH/DG/PDG")

    return len(blockers) == 0, blockers


def process_stc_payment(
    session: Session,
    offboarding_id: UUID,
) -> object:
    """
    Execute STC payment. BLOCKED if ANY prerequisite is missing.
    No override. Then: generate certificates, archive, set archived.
    """
    from app.models.offboarding import OffboardingProcess
    from app.models.hr import Employee

    ready, blockers = check_stc_prerequisites(session, offboarding_id)
    if not ready:
        raise StcBlocked(
            f"STC bloque: {'; '.join(blockers)}. Aucune derogation possible.",
            blockers=blockers,
        )

    process = session.get(OffboardingProcess, offboarding_id)
    now = datetime.now(timezone.utc)

    process.stc_paid = True
    process.stc_paid_at = now
    process.status = "STC_PAYE"

    # Archive employee
    emp = session.get(Employee, process.employee_id)
    if emp:
        emp.status = "ARCHIVED"

    # Generate certificates (in production: PDF from templates)
    process.certificat_travail_url = f"/docs/certificat_{process.employee_id}.pdf"
    process.attestation_travail_url = f"/docs/attestation_{process.employee_id}.pdf"
    process.status = "ARCHIVE"

    session.flush()
    return process
