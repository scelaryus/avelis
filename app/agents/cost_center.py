"""GFI Platform - CostCenterAgent.

Computes centre de coût snapshots and dashboard datasets.
"""
import uuid
import structlog
from app.schemas.artifacts import (
    WorkflowState, NodeResult, CostCenterSnapshot, CostCenterLineItem,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Compute cost center snapshots from committed/proposed ledger entries."""
    from sqlalchemy import select
    from app.models.core import (
        Artifact, ArtifactType, CostCenter, CostCenterAllocation,
        JournalEntry, JournalLine, JournalEntryStatus,
    )

    artifacts_created = []

    # Get ledger packages
    ledger_ids = state.artifacts.get("ledger_structuring", [])

    # Collect cost center allocations from proposed entries
    cc_data: dict[str, dict] = {}  # {cc_code: {account: {debit, credit}}}

    for lid in ledger_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == lid)
        )
        artifact = result.scalar_one_or_none()
        if not artifact:
            continue

        data = artifact.data
        for entry in data.get("entries", []):
            for line in entry.get("lines", []):
                cc_code = line.get("cost_center_code")
                if not cc_code:
                    cc_code = "GENERAL"

                if cc_code not in cc_data:
                    cc_data[cc_code] = {}

                acc = line.get("account_code", "0000")
                if acc not in cc_data[cc_code]:
                    cc_data[cc_code][acc] = {"debit": 0.0, "credit": 0.0, "label": line.get("label", "")}

                cc_data[cc_code][acc]["debit"] += line.get("debit", 0.0)
                cc_data[cc_code][acc]["credit"] += line.get("credit", 0.0)

    # Build snapshots
    for cc_code, accounts in cc_data.items():
        # Look up cost center name
        result = await ctx.db_session.execute(
            select(CostCenter).where(
                CostCenter.tenant_id == state.tenant_id,
                CostCenter.code == cc_code,
            )
        )
        cc = result.scalar_one_or_none()
        cc_name = cc.name if cc else cc_code

        line_items = []
        total_debit = 0.0
        total_credit = 0.0

        for acc_code, vals in accounts.items():
            line_items.append(CostCenterLineItem(
                account_code=acc_code,
                account_label=vals.get("label", ""),
                debit=round(vals["debit"], 2),
                credit=round(vals["credit"], 2),
            ))
            total_debit += vals["debit"]
            total_credit += vals["credit"]

        snapshot = CostCenterSnapshot(
            cost_center_code=cc_code,
            cost_center_name=cc_name,
            period_label="current",
            total_debit=round(total_debit, 2),
            total_credit=round(total_credit, 2),
            balance=round(total_debit - total_credit, 2),
            line_items=line_items,
        )

        artifact = Artifact(
            id=uuid.uuid4(),
            tenant_id=state.tenant_id,
            workflow_id=state.workflow_id,
            artifact_type=ArtifactType.COST_CENTER_SNAPSHOT,
            data=snapshot.model_dump(),
            algo_version="v3.0-cc",
        )
        ctx.db_session.add(artifact)
        artifacts_created.append(str(artifact.id))

    await ctx.db_session.flush()
    logger.info("cost_center_snapshots", count=len(artifacts_created))

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=[])
