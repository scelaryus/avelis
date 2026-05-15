"""GFI Platform - HR Agents.

Employee operations, payroll proposals, and HR verification.
"""
import uuid
import structlog
from datetime import datetime
from app.schemas.artifacts import (
    WorkflowState, NodeResult, HRPackage, HRPayrollPackage,
    PayrollLineItem, ProposedJournalEntry, ProposedJournalLine,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def employee_ops(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """HR employee operations - validate employee data."""
    from sqlalchemy import select
    from app.models.hr import Employee, EmploymentStatus

    # Validate all active employees for the tenant
    result = await ctx.db_session.execute(
        select(Employee).where(
            Employee.tenant_id == state.tenant_id,
            Employee.status == EmploymentStatus.ACTIVE,
        )
    )
    employees = result.scalars().all()

    if not employees:
        return NodeResult(
            status="BLOCK",
            artifacts_created=[],
            warnings=[],
            errors=[{"code": "NO_EMPLOYEES", "message": "No active employees found"}],
        )

    logger.info("hr_employee_ops", active_count=len(employees))
    return NodeResult(status="OK", artifacts_created=[], warnings=[], errors=[])


async def payroll_proposal(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Generate payroll proposals for active employees."""
    from sqlalchemy import select
    from app.models.core import Artifact, ArtifactType
    from app.models.hr import Employee, EmploymentStatus

    result = await ctx.db_session.execute(
        select(Employee).where(
            Employee.tenant_id == state.tenant_id,
            Employee.status == EmploymentStatus.ACTIVE,
        )
    )
    employees = result.scalars().all()

    payroll_proposals = []
    for emp in employees:
        gross = float(emp.base_salary or 0)
        if gross == 0:
            continue

        # Algerian deductions (CNAS + IRG)
        cnas_salarial = round(gross * 0.09, 2)  # CNAS employee share 9%
        cnas_patronal = round(gross * 0.26, 2)  # CNAS employer share 26%
        taxable = gross - cnas_salarial
        irg = _compute_irg(taxable)

        net = gross - cnas_salarial - irg

        items = [
            PayrollLineItem(label="Salaire de base", type="earning", amount=gross),
            PayrollLineItem(label="CNAS salarial", type="deduction", amount=cnas_salarial),
            PayrollLineItem(label="IRG", type="deduction", amount=round(irg, 2)),
            PayrollLineItem(label="CNAS patronal", type="employer_contribution",
                            amount=cnas_patronal),
        ]

        # Build proposed journal entry
        journal_entry = ProposedJournalEntry(
            entry_date=datetime.utcnow().strftime("%Y-%m-%d"),
            reference=f"PAIE-{emp.employee_number}",
            description=f"Paie {emp.first_name} {emp.last_name}",
            lines=[
                ProposedJournalLine(
                    account_code="6171", label="Salaire brut",
                    debit=round(gross, 2), credit=0.0,
                ),
                ProposedJournalLine(
                    account_code="4441", label="CNAS salarial",
                    debit=0.0, credit=cnas_salarial,
                ),
                ProposedJournalLine(
                    account_code="4457", label="IRG retenu",
                    debit=0.0, credit=round(irg, 2),
                ),
                ProposedJournalLine(
                    account_code="4432", label="Net a payer",
                    debit=0.0, credit=round(net, 2),
                ),
            ],
        )

        payroll_proposals.append(HRPayrollPackage(
            employee_id=str(emp.id),
            employee_name=f"{emp.first_name} {emp.last_name}",
            period_label=datetime.utcnow().strftime("%Y-%m"),
            gross_salary=gross,
            items=items,
            net_salary=round(net, 2),
            proposed_journal_entry=journal_entry,
        ))

    hr_package = HRPackage(
        tenant_id=state.tenant_id,
        period_label=datetime.utcnow().strftime("%Y-%m"),
        payroll_proposals=payroll_proposals,
    )

    artifact = Artifact(
        id=uuid.uuid4(),
        tenant_id=state.tenant_id,
        workflow_id=state.workflow_id,
        artifact_type=ArtifactType.HR_PACKAGE,
        data=hr_package.model_dump(),
        algo_version="v3.0-hr",
    )
    ctx.db_session.add(artifact)
    await ctx.db_session.flush()

    logger.info("payroll_proposals_generated", count=len(payroll_proposals))
    return NodeResult(status="OK", artifacts_created=[str(artifact.id)], warnings=[], errors=[])


async def verify(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Verify HR payroll proposals for consistency."""
    from sqlalchemy import select
    from app.models.core import Artifact, ArtifactType

    hr_ids = state.artifacts.get("hr_payroll", [])
    errors = []

    for hid in hr_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == hid)
        )
        artifact = result.scalar_one_or_none()
        if not artifact:
            continue

        data = artifact.data
        for proposal in data.get("payroll_proposals", []):
            gross = proposal.get("gross_salary", 0)
            net = proposal.get("net_salary", 0)

            if net > gross:
                errors.append({
                    "code": "NET_GT_GROSS",
                    "message": f"Net ({net}) > Gross ({gross}) for {proposal.get('employee_name')}",
                })

            if net < 0:
                errors.append({
                    "code": "NEGATIVE_NET",
                    "message": f"Negative net salary for {proposal.get('employee_name')}",
                })

    if errors:
        return NodeResult(status="BLOCK", artifacts_created=[], warnings=[], errors=errors)

    return NodeResult(status="OK", artifacts_created=[], warnings=[], errors=[])


def _compute_irg(taxable_monthly: float) -> float:
    """Algerian IRG (progressive brackets)."""
    if taxable_monthly <= 10_000:
        return 0.0
    elif taxable_monthly <= 30_000:
        return round((taxable_monthly - 10_000) * 0.20, 2)
    elif taxable_monthly <= 120_000:
        return round(4_000 + (taxable_monthly - 30_000) * 0.30, 2)
    else:
        return round(31_000 + (taxable_monthly - 120_000) * 0.35, 2)
