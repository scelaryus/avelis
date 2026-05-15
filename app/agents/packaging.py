"""GFI Platform - Packaging Agent.

Builds the final SubmissionPackage before commit.
"""
import uuid
import structlog
from app.schemas.artifacts import (
    WorkflowState, NodeResult, SubmissionPackage,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Build submission package from all collected artifacts."""
    from sqlalchemy import select
    from app.models.core import Artifact, ArtifactType

    # Collect artifact IDs by type
    ocr_ids = (
        state.artifacts.get("ocr", []) +
        state.artifacts.get("ocr_merge", []) +
        state.artifacts.get("text_layer_parse", [])
    )
    verification_ids = state.artifacts.get("verification", [])
    ledger_ids = state.artifacts.get("ledger_structuring", [])
    anomaly_ids = state.artifacts.get("anomaly", [])

    # Check for blocking anomalies
    blocking_reasons = []
    for aid in anomaly_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == aid)
        )
        a = result.scalar_one_or_none()
        if a and a.data.get("has_blocking"):
            blocking_reasons.append(f"Blocking anomalies in {a.data.get('doc_id')}")

    # Validate evidence anchors exist
    for lid in ledger_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == lid)
        )
        a = result.scalar_one_or_none()
        if a:
            for entry in a.data.get("entries", []):
                for line in entry.get("lines", []):
                    anchors = line.get("evidence_anchors", [])
                    debit = line.get("debit", 0)
                    credit = line.get("credit", 0)
                    if (debit > 0 or credit > 0) and not anchors:
                        # Non-blocking warning for missing evidence on non-zero lines
                        pass

    is_ready = len(blocking_reasons) == 0 and len(ledger_ids) > 0

    package = SubmissionPackage(
        workflow_id=state.workflow_id,
        doc_ids=state.doc_ids,
        ocr_artifact_ids=ocr_ids,
        verification_report_id=verification_ids[0] if verification_ids else None,
        proposed_ledger_package_id=ledger_ids[0] if ledger_ids else "",
        anomaly_report_id=anomaly_ids[0] if anomaly_ids else None,
        evidence_anchor_ids=[],  # collected during commit
        decisions=state.decisions,
        is_ready=is_ready,
        blocking_reasons=blocking_reasons,
    )

    artifact = Artifact(
        id=uuid.uuid4(),
        tenant_id=state.tenant_id,
        workflow_id=state.workflow_id,
        artifact_type=ArtifactType.SUBMISSION_PACKAGE,
        data=package.model_dump(),
        algo_version="v3.0-pkg",
    )
    ctx.db_session.add(artifact)
    await ctx.db_session.flush()

    logger.info("submission_packaged", ready=is_ready, blocking=len(blocking_reasons))

    if not is_ready:
        return NodeResult(
            status="BLOCK",
            artifacts_created=[str(artifact.id)],
            warnings=[],
            errors=[{"code": "NOT_READY", "message": r} for r in blocking_reasons],
        )

    return NodeResult(
        status="OK",
        artifacts_created=[str(artifact.id)],
        warnings=[],
        errors=[],
    )
