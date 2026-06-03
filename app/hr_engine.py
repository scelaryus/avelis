"""
GFI v7.0 — HR Engine: employee lifecycle, contract validation, agent cascade.

22 DRH AI agents coordinate via event-driven architecture.
Contract triple validation: DRH -> DG -> PDG (sequential, no skip).
CDD requalification: auto-CDI if continues past end_date.

Core API:
  create_employee(...)         -> Employee + document checklist
  create_contract(...)         -> EmployeeContract + SNMG check
  validate_contract(step, ...) -> triple validation circuit
  check_cdd_requalification()  -> auto-CDI flagging
  trigger_onboarding(...)      -> 6-agent parallel cascade
  generate_matricule(...)      -> {company_code}-{year}-{seq}
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func as sqfunc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


SNMG = Decimal("20000")  # Salaire National Minimum Garanti


class SNMGViolation(Exception):
    """Salary below SNMG (20,000 DA)."""
    pass


class ContractValidationError(Exception):
    """Triple validation sequence violation."""
    pass


class CDDReasonMissing(Exception):
    """CDD without legal justification (Article 12, Loi 90-11)."""
    pass


class CDDRequalified(Exception):
    """CDD auto-requalified as CDI (continues past end_date)."""
    pass


def generate_matricule(
    session: Session,
    company_id: UUID,
) -> str:
    """Generate sequential matricule: {entity_code}-{year}-{seq:04d}."""
    from app.models.hr import Employee
    from app.models.company import Company

    company = session.get(Company, company_id)
    code = company.code.replace("-", "") if company else "UNK"
    year = date.today().year

    count = (
        session.query(sqfunc.count(Employee.id))
        .filter(
            Employee.company_id == company_id,
            Employee.matricule.like(f"{code}-{year}-%"),
            Employee.is_deleted.is_(False),
        )
        .scalar()
    ) or 0

    return f"{code}-{year}-{count + 1:04d}"


def create_employee(
    session: Session,
    *,
    company_id: UUID,
    first_name: str,
    last_name: str,
    birth_date: date,
    gender: str,
    national_id: str | None = None,
    created_by: UUID | None = None,
    **kwargs,
) -> object:
    """Create an employee record with document checklist."""
    from app.models.hr import Employee

    # Age check
    today = date.today()
    age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )
    if age < 16 or age > 70:
        raise ValueError(f"Employee age {age} outside allowed range (16-70).")

    matricule = generate_matricule(session, company_id)

    checklist = {
        "cni": "PENDING", "photo": "PENDING", "diplome": "PENDING",
        "medical": "PENDING", "rib": "PENDING", "casier": "PENDING",
        "cv": "PENDING",
    }

    employee = Employee(
        company_id=company_id,
        matricule=matricule,
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
        gender=gender,
        national_id=national_id,
        document_checklist_status=checklist,
        status="DRAFT",
        created_by=created_by,
        **kwargs,
    )
    session.add(employee)
    session.flush()
    return employee


def create_contract(
    session: Session,
    *,
    company_id: UUID,
    employee_id: UUID,
    contract_type: str,
    start_date: date,
    salary_base: Decimal,
    end_date: date | None = None,
    cdd_reason: str | None = None,
    created_by: UUID | None = None,
    **kwargs,
) -> object:
    """
    Create employment contract with validation checks:
    - SNMG: salary >= 20,000 DA
    - CDD: legal reason mandatory (Article 12, Loi 90-11)
    - CDD: end_date mandatory
    """
    from app.models.hr import EmployeeContract

    salary = Decimal(str(salary_base))
    if salary < SNMG:
        raise SNMGViolation(
            f"Salary {salary} DA below SNMG ({SNMG} DA)."
        )

    if contract_type == "CDD":
        if not cdd_reason or len(cdd_reason.strip()) < 30:
            raise CDDReasonMissing(
                "CDD requires legal justification >= 30 chars "
                "(Article 12, Loi 90-11)."
            )
        if not end_date:
            raise ValueError("CDD requires end_date.")

    contract = EmployeeContract(
        company_id=company_id,
        employee_id=employee_id,
        contract_type=contract_type,
        start_date=start_date,
        end_date=end_date,
        salary_base=salary,
        cdd_reason=cdd_reason,
        status="DRAFT",
        created_by=created_by,
        **kwargs,
    )
    session.add(contract)
    session.flush()
    return contract


# Contract validation states (sequential, no skip)
VALIDATION_SEQUENCE = [
    ("PENDING_VALIDATION", "VALIDATED_DRH", "validated_drh_by", "validated_drh_at"),
    ("VALIDATED_DRH", "VALIDATED_DG", "validated_dg_by", "validated_dg_at"),
    ("VALIDATED_DG", "VALIDATED_PDG", "validated_pdg_by", "validated_pdg_at"),
]


def validate_contract(
    session: Session,
    *,
    contract_id: UUID,
    validated_by: UUID,
) -> object:
    """
    Triple validation: DRH -> DG -> PDG. Sequential, no skip.
    Each step requires the previous to be complete.
    """
    from app.models.hr import EmployeeContract

    contract = session.get(EmployeeContract, contract_id)
    if contract is None:
        raise ValueError(f"Contract {contract_id} not found.")

    now = datetime.now(timezone.utc)

    for from_status, to_status, by_field, at_field in VALIDATION_SEQUENCE:
        if contract.status == from_status:
            setattr(contract, by_field, validated_by)
            setattr(contract, at_field, now)
            contract.status = to_status

            # If final validation -> activate
            if to_status == "VALIDATED_PDG":
                contract.status = "ACTIVE"
                # Update employee status
                from app.models.hr import Employee
                emp = session.get(Employee, contract.employee_id)
                if emp and emp.status in ("DRAFT", "ONBOARDING"):
                    emp.status = "ACTIVE"
                    if not emp.hire_date:
                        emp.hire_date = contract.start_date
                        emp.seniority_date = contract.start_date

            session.flush()
            return contract

    raise ContractValidationError(
        f"Contract status '{contract.status}' is not pending validation. "
        f"Expected one of: {[s[0] for s in VALIDATION_SEQUENCE]}"
    )


def submit_for_validation(
    session: Session,
    contract_id: UUID,
) -> object:
    """Submit a DRAFT contract for the triple validation circuit."""
    from app.models.hr import EmployeeContract

    contract = session.get(EmployeeContract, contract_id)
    if contract is None:
        raise ValueError(f"Contract {contract_id} not found.")

    if contract.status != "DRAFT":
        raise ContractValidationError(
            f"Only DRAFT contracts can be submitted. Current: {contract.status}"
        )

    contract.status = "PENDING_VALIDATION"
    session.flush()
    return contract


def check_cdd_requalification(
    session: Session,
    today: date | None = None,
) -> list[dict]:
    """
    Auto-requalify CDDs that continue past end_date without renewal.
    Cour Supreme algerienne, 09/07/2015.
    """
    from app.models.hr import EmployeeContract

    if today is None:
        today = date.today()

    expired_cdds = (
        session.query(EmployeeContract)
        .filter(
            EmployeeContract.contract_type == "CDD",
            EmployeeContract.status == "ACTIVE",
            EmployeeContract.end_date < today,
            EmployeeContract.requalified_as_cdi.is_(False),
            EmployeeContract.is_deleted.is_(False),
        )
        .all()
    )

    requalified = []
    for contract in expired_cdds:
        contract.requalified_as_cdi = True
        contract.requalification_date = today
        contract.contract_type = "CDI"
        contract.end_date = None

        requalified.append({
            "contract_id": str(contract.id),
            "employee_id": str(contract.employee_id),
            "original_end_date": str(contract.end_date),
            "requalified_date": str(today),
        })

    session.flush()
    return requalified


def trigger_onboarding_cascade(
    session: Session,
    employee_id: UUID,
    contract_id: UUID,
) -> dict:
    """
    Simulate the 6-agent parallel onboarding cascade.
    In production, this would be a LangGraph parallel fan-out.
    Returns status of each agent branch.
    """
    results = {
        "agent_acces": "PENDING",     # Badge + zones
        "agent_paie": "PENDING",      # Salary integration
        "agent_mgx": "PENDING",       # Equipment
        "agent_ged": "PENDING",       # Archive contract
        "agent_formation": "PENDING", # Training plan
        "agent_spi": "PENDING",       # Performance profile
    }

    # Each agent would execute independently
    # Here we just mark them as triggered
    for agent in results:
        results[agent] = "TRIGGERED"

    return {
        "employee_id": str(employee_id),
        "contract_id": str(contract_id),
        "agents": results,
        "all_complete": all(v == "TRIGGERED" for v in results.values()),
    }
