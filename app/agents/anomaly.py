"""GFI Platform - AnomalyAgent (fraud/incoherence detection).

Detects anomalies: duplicates, mismatches, implausible values.
"""
import uuid
import structlog
from app.schemas.artifacts import (
    WorkflowState, NodeResult, AnomalyReport, AnomalyItem,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Detect anomalies in proposed ledger packages."""
    from sqlalchemy import select, func
    from app.models.core import Artifact, ArtifactType, Document, JournalEntry

    artifacts_created = []

    # Get proposed ledger packages
    ledger_ids = state.artifacts.get("ledger_structuring", [])

    for lid in ledger_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == lid)
        )
        artifact = result.scalar_one_or_none()
        if not artifact:
            continue

        data = artifact.data
        doc_id = data.get("doc_id", "")
        entries = data.get("entries", [])

        anomalies = []

        # 1. Balance check
        total_debit = data.get("total_debit", 0)
        total_credit = data.get("total_credit", 0)
        if not data.get("is_balanced", True):
            anomalies.append(AnomalyItem(
                anomaly_code="UNBALANCED_ENTRY",
                severity="BLOCKING",
                description=f"Journal entries unbalanced: debit={total_debit}, credit={total_credit}",
                details={"debit": total_debit, "credit": total_credit, "diff": abs(total_debit - total_credit)},
            ))

        # 2. Missing evidence anchors on lines
        for i, entry in enumerate(entries):
            for j, line in enumerate(entry.get("lines", [])):
                if not line.get("evidence_anchors"):
                    amount = line.get("debit", 0) or line.get("credit", 0)
                    if amount > 0:
                        anomalies.append(AnomalyItem(
                            anomaly_code="LINE_NO_EVIDENCE",
                            severity="WARNING",
                            description=f"Journal line {j+1} in entry {i+1} has no evidence anchor",
                            details={"entry_index": i, "line_index": j, "account": line.get("account_code")},
                        ))

        # 3. Duplicate invoice check
        dup_anomaly = await _check_duplicate_invoice(doc_id, entries, ctx, state)
        if dup_anomaly:
            anomalies.append(dup_anomaly)

        # 4. Negative amounts where forbidden
        for i, entry in enumerate(entries):
            for j, line in enumerate(entry.get("lines", [])):
                if line.get("debit", 0) < 0 or line.get("credit", 0) < 0:
                    anomalies.append(AnomalyItem(
                        anomaly_code="NEGATIVE_AMOUNT",
                        severity="BLOCKING",
                        description=f"Negative amount on line {j+1} entry {i+1}",
                        details={"debit": line.get("debit"), "credit": line.get("credit")},
                    ))

        # 5. Abnormally large amounts
        for entry in entries:
            for line in entry.get("lines", []):
                amount = max(line.get("debit", 0), line.get("credit", 0))
                if amount > 1_000_000:
                    anomalies.append(AnomalyItem(
                        anomaly_code="LARGE_AMOUNT",
                        severity="WARNING",
                        description=f"Unusually large amount: {amount}",
                        details={"amount": amount, "account": line.get("account_code")},
                        suggested_fix="Verify amount with source document",
                    ))

        # 6. Empty entries
        for i, entry in enumerate(entries):
            if not entry.get("lines"):
                anomalies.append(AnomalyItem(
                    anomaly_code="EMPTY_ENTRY",
                    severity="WARNING",
                    description=f"Entry {i+1} has no journal lines",
                ))

        has_blocking = any(a.severity == "BLOCKING" for a in anomalies)

        report = AnomalyReport(
            doc_id=doc_id,
            workflow_id=state.workflow_id,
            anomalies=anomalies,
            has_blocking=has_blocking,
        )

        anomaly_artifact = Artifact(
            id=uuid.uuid4(),
            tenant_id=state.tenant_id,
            workflow_id=state.workflow_id,
            doc_id=doc_id,
            artifact_type=ArtifactType.ANOMALY_REPORT,
            data=report.model_dump(),
            algo_version="v3.0-anomaly",
        )
        ctx.db_session.add(anomaly_artifact)
        artifacts_created.append(str(anomaly_artifact.id))

        # Store individual anomaly records
        for item in anomalies:
            from app.models.core import AnomalyRecord, AnomalySeverity
            record = AnomalyRecord(
                id=uuid.uuid4(),
                tenant_id=state.tenant_id,
                workflow_id=state.workflow_id,
                doc_id=doc_id,
                anomaly_code=item.anomaly_code,
                severity=AnomalySeverity(item.severity),
                description=item.description,
                details=item.details,
            )
            ctx.db_session.add(record)

        logger.info("anomaly_check_complete", doc_id=doc_id,
                     anomalies=len(anomalies), blocking=has_blocking)

    await ctx.db_session.flush()

    # Block if any blocking anomalies found
    has_any_blocking = False
    for lid in ledger_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == lid)
        )
        a = result.scalar_one_or_none()
        if a and not a.data.get("is_balanced", True):
            has_any_blocking = True

    if has_any_blocking:
        return NodeResult(
            status="BLOCK",
            artifacts_created=artifacts_created,
            warnings=[],
            errors=[{"code": "ANOMALY_BLOCKING", "message": "Blocking anomalies detected"}],
        )

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=[])


async def _check_duplicate_invoice(
    doc_id: str, entries: list[dict], ctx: RunContext, state: WorkflowState
) -> AnomalyItem | None:
    """Check if an invoice with the same reference already exists."""
    from sqlalchemy import select
    from app.models.core import JournalEntry

    for entry in entries:
        ref = entry.get("reference")
        if not ref:
            continue

        result = await ctx.db_session.execute(
            select(JournalEntry).where(
                JournalEntry.tenant_id == state.tenant_id,
                JournalEntry.reference == ref,
                JournalEntry.status != "REJECTED",
            )
        )
        existing = result.scalars().all()
        if existing:
            return AnomalyItem(
                anomaly_code="DUPLICATE_INVOICE",
                severity="BLOCKING",
                description=f"Invoice reference '{ref}' already exists in journal",
                details={"existing_entry_ids": [str(e.id) for e in existing]},
                suggested_fix="Verify this is not a duplicate submission",
            )

    return None
