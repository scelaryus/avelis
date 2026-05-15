"""GFI Platform - OCRMergeAndAlignAgent.

Merges TEXT_LAYER blocks and OCR blocks into one coherent OCRTextArtifact.
"""
import uuid
import structlog
from app.schemas.artifacts import (
    WorkflowState, NodeResult, OCRTextArtifact, OCRBlock,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Merge text layer blocks + OCR blocks; deduplicate; keep highest confidence."""
    from sqlalchemy import select
    from app.models.core import Artifact, ArtifactType

    artifacts_created = []

    # Collect all OCR_TEXT artifacts from this workflow
    ocr_ids = (
        state.artifacts.get("ocr", []) +
        state.artifacts.get("text_layer_parse", []) +
        state.artifacts.get("text_layer_detect", [])
    )

    # Group blocks by (doc_id, page)
    page_blocks: dict[tuple[str, int], list[OCRBlock]] = {}

    for ocr_id in ocr_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == ocr_id)
        )
        artifact = result.scalar_one_or_none()
        if not artifact:
            continue

        data = artifact.data
        # Skip detection-only artifacts
        if "text_layer_detection" in data:
            continue

        doc_id = data.get("doc_id", "")
        page = data.get("page", 1)
        blocks_data = data.get("blocks", [])

        key = (doc_id, page)
        if key not in page_blocks:
            page_blocks[key] = []

        for b in blocks_data:
            page_blocks[key].append(OCRBlock(**b))

    # Merge and deduplicate per page
    for (doc_id, page), blocks in page_blocks.items():
        merged_blocks = _merge_blocks(blocks)

        merged_artifact = OCRTextArtifact(
            doc_id=doc_id,
            page=page,
            source="MERGED",
            blocks=merged_blocks,
        )

        artifact = Artifact(
            id=uuid.uuid4(),
            tenant_id=state.tenant_id,
            workflow_id=state.workflow_id,
            doc_id=doc_id,
            artifact_type=ArtifactType.OCR_TEXT,
            data=merged_artifact.model_dump(),
            algo_version="v3.0-merge",
        )
        ctx.db_session.add(artifact)
        artifacts_created.append(str(artifact.id))

    await ctx.db_session.flush()
    logger.info("ocr_merged", pages=len(page_blocks))

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=[])


def _merge_blocks(blocks: list[OCRBlock]) -> list[OCRBlock]:
    """Merge blocks, deduplicating overlapping regions and keeping highest confidence."""
    if not blocks:
        return []

    # Sort by position (top-left)
    blocks.sort(key=lambda b: (b.bbox[1], b.bbox[0]))

    merged = []
    used = set()

    for i, block in enumerate(blocks):
        if i in used:
            continue

        best = block
        for j in range(i + 1, len(blocks)):
            if j in used:
                continue

            other = blocks[j]
            if _bbox_overlap(best.bbox, other.bbox) > 0.5:
                # Keep the one with higher confidence
                if other.confidence > best.confidence:
                    best = other
                used.add(j)

        merged.append(best)
        used.add(i)

    return merged


def _bbox_overlap(a: list[float], b: list[float]) -> float:
    """Compute IoU (intersection over union) of two normalized bboxes."""
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])

    if x2 <= x1 or y2 <= y1:
        return 0.0

    intersection = (x2 - x1) * (y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - intersection

    return intersection / union if union > 0 else 0.0
