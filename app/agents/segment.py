"""GFI Platform - SegmentDocumentsAgent.

Detects segments (header, table, footer, line items, signature blocks) on rendered pages.
"""
import uuid
import structlog
from app.schemas.artifacts import WorkflowState, NodeResult, SegmentArtifact, SegmentRegion
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Detect segments/regions on document pages."""
    from sqlalchemy import select
    from app.models.core import Artifact, ArtifactType

    artifacts_created = []
    warnings = []

    # Get render artifacts from previous node
    render_artifact_ids = state.artifacts.get("render", [])
    if not render_artifact_ids:
        return NodeResult(
            status="OK",
            artifacts_created=[],
            warnings=[{"code": "NO_RENDERS", "message": "No render artifacts to segment"}],
            errors=[],
        )

    for render_id in render_artifact_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == render_id)
        )
        render_artifact = result.scalar_one_or_none()
        if not render_artifact:
            continue

        render_data = render_artifact.data
        doc_id = render_data.get("doc_id")
        page = render_data.get("page", 1)
        width = render_data.get("width", 1)
        height = render_data.get("height", 1)

        # Heuristic segmentation: divide page into regions
        # In production, this would use a layout analysis model (LayoutLM, etc.)
        regions = _heuristic_segment(width, height)

        segment = SegmentArtifact(
            doc_id=doc_id,
            page=page,
            regions=regions,
        )

        artifact = Artifact(
            id=uuid.uuid4(),
            tenant_id=state.tenant_id,
            workflow_id=state.workflow_id,
            doc_id=doc_id,
            artifact_type=ArtifactType.SEGMENT,
            data=segment.model_dump(),
            algo_version="v3.0-heuristic",
        )
        ctx.db_session.add(artifact)
        artifacts_created.append(str(artifact.id))

    await ctx.db_session.flush()
    logger.info("segments_detected", count=len(artifacts_created))

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=warnings, errors=[])


def _heuristic_segment(width: int, height: int) -> list[SegmentRegion]:
    """
    Basic heuristic segmentation: header (top 15%), body/table (middle 70%), footer (bottom 15%).
    Production would use ML layout detection.
    """
    return [
        SegmentRegion(segment_type="header", bbox=[0.0, 0.0, 1.0, 0.15], confidence=0.7),
        SegmentRegion(segment_type="table", bbox=[0.0, 0.15, 1.0, 0.85], confidence=0.6),
        SegmentRegion(segment_type="footer", bbox=[0.0, 0.85, 1.0, 1.0], confidence=0.7),
    ]
