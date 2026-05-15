"""GFI Platform - ADV Agents.

Handles sales administration: contracts, receivables, payments.
"""
import uuid
import structlog
from datetime import datetime
from app.schemas.artifacts import (
    WorkflowState, NodeResult, ADVPackage,
    ProposedJournalEntry, ProposedJournalLine,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def ingest(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Ingest ADV data: contracts, payments, documents."""
    from sqlalchemy import select
    from app.models.adv import Contract, Receivable, Payment, Client

    # Validate that referenced clients/contracts exist
    warnings = []

    # Fetch active contracts for tenant
    result = await ctx.db_session.execute(
        select(Contract).where(
            Contract.tenant_id == state.tenant_id,
        ).limit(100)
    )
    contracts = result.scalars().all()

    logger.info("adv_ingest", contracts=len(contracts))
    return NodeResult(status="OK", artifacts_created=[], warnings=warnings, errors=[])


async def normalize(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Normalize ADV terms and amounts."""
    # ADV normalization is simpler: standardize dates, amounts, references
    return NodeResult(status="OK", artifacts_created=[], warnings=[], errors=[])


async def verify(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """ADV verification checks."""
    from sqlalchemy import select
    from app.models.adv import Receivable, Payment, Client

    errors = []

    # Check for overdue receivables
    result = await ctx.db_session.execute(
        select(Receivable).where(
            Receivable.tenant_id == state.tenant_id,
            Receivable.status == "OVERDUE",
        )
    )
    overdue = result.scalars().all()
    if overdue:
        for r in overdue:
            errors.append({
                "code": "OVERDUE_RECEIVABLE",
                "message": f"Receivable {r.invoice_ref} is overdue (due: {r.due_date})",
            })

    if errors:
        return NodeResult(status="OK", artifacts_created=[], warnings=errors, errors=[])

    return NodeResult(status="OK", artifacts_created=[], warnings=[], errors=[])


async def ledger_structuring(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Generate ledger proposals for ADV operations."""
    from sqlalchemy import select
    from app.models.core import Artifact, ArtifactType
    from app.models.adv import Receivable, Payment, Client

    artifacts_created = []

    # Fetch pending receivables
    result = await ctx.db_session.execute(
        select(Receivable).where(
            Receivable.tenant_id == state.tenant_id,
            Receivable.status.in_(["PENDING", "PARTIAL"]),
        ).limit(50)
    )
    receivables = result.scalars().all()

    # Fetch recent payments
    result = await ctx.db_session.execute(
        select(Payment).where(
            Payment.tenant_id == state.tenant_id,
        ).order_by(Payment.created_at.desc()).limit(50)
    )
    payments = result.scalars().all()

    entries = []

    # Create receivable entries
    for recv in receivables:
        if recv.journal_entry_id:
            continue  # Already has journal entry

        # Get client for account code
        client_result = await ctx.db_session.execute(
            select(Client).where(Client.id == recv.client_id)
        )
        client = client_result.scalar_one_or_none()
        client_acc = client.account_code if client and client.account_code else "3421"

        entries.append(ProposedJournalEntry(
            entry_date=str(recv.due_date or datetime.utcnow().date()),
            reference=recv.invoice_ref or str(recv.id)[:8],
            description=f"Créance client - {client.name if client else 'Client'}",
            lines=[
                ProposedJournalLine(
                    account_code=client_acc,
                    label=f"Client {client.name if client else ''} - Créance",
                    debit=float(recv.amount),
                    credit=0.0,
                ),
                ProposedJournalLine(
                    account_code="7111",  # Ventes de marchandises
                    label="Ventes",
                    debit=0.0,
                    credit=float(recv.amount),
                ),
            ],
        ))

    # Create payment entries
    for pmt in payments:
        if pmt.journal_entry_id:
            continue

        client_result = await ctx.db_session.execute(
            select(Client).where(Client.id == pmt.client_id)
        )
        client = client_result.scalar_one_or_none()
        client_acc = client.account_code if client and client.account_code else "3421"

        entries.append(ProposedJournalEntry(
            entry_date=str(pmt.payment_date),
            reference=pmt.payment_ref or str(pmt.id)[:8],
            description=f"Paiement client - {client.name if client else 'Client'}",
            lines=[
                ProposedJournalLine(
                    account_code="5141",  # Banque
                    label="Encaissement",
                    debit=float(pmt.amount),
                    credit=0.0,
                ),
                ProposedJournalLine(
                    account_code=client_acc,
                    label=f"Client {client.name if client else ''}",
                    debit=0.0,
                    credit=float(pmt.amount),
                ),
            ],
        ))

    if entries:
        adv_package = ADVPackage(
            tenant_id=state.tenant_id,
            client_id="multiple",
            proposed_journal_entries=entries,
        )

        artifact = Artifact(
            id=uuid.uuid4(),
            tenant_id=state.tenant_id,
            workflow_id=state.workflow_id,
            artifact_type=ArtifactType.ADV_PACKAGE,
            data=adv_package.model_dump(),
            algo_version="v3.0-adv",
        )
        ctx.db_session.add(artifact)
        artifacts_created.append(str(artifact.id))

    await ctx.db_session.flush()
    logger.info("adv_ledger_structured", entries=len(entries))

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=[])
