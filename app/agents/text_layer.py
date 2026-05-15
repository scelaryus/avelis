"""GFI Platform - TextLayerDetectorAgent & TextLayerParseAgent.

Detects and parses embedded text layers from PDFs.
"""
import uuid
import structlog
from app.schemas.artifacts import (
    WorkflowState, NodeResult, TextLayerDetectionResult,
    OCRTextArtifact, OCRBlock, OCRBlockProvenance,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def detect(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Determine if PDFs have reliable embedded text layers."""
    from sqlalchemy import select
    from app.models.core import Document, Artifact, ArtifactType

    artifacts_created = []
    _has_reliable_text = False

    for doc_id in state.doc_ids:
        result = await ctx.db_session.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            continue

        mime = doc.mime_type or ""
        if "pdf" not in mime:
            # Non-PDF: no text layer
            doc.has_text_layer = False
            doc.text_layer_confidence = 0
            continue

        # Check PDF for text layer
        has_text, confidence, reason = await _check_text_layer(doc, ctx)
        doc.has_text_layer = has_text
        doc.text_layer_confidence = confidence

        detection = TextLayerDetectionResult(
            doc_id=str(doc.id),
            has_text_layer=has_text,
            confidence=confidence,
            reason=reason,
        )

        if has_text and confidence > 0.8:
            _has_reliable_text = True

        # Store as artifact (using data field)
        artifact = Artifact(
            id=uuid.uuid4(),
            tenant_id=state.tenant_id,
            workflow_id=state.workflow_id,
            doc_id=doc.id,
            artifact_type=ArtifactType.OCR_TEXT,
            data={"text_layer_detection": detection.model_dump()},
            algo_version="v3.0",
        )
        ctx.db_session.add(artifact)
        artifacts_created.append(str(artifact.id))

    await ctx.db_session.flush()

    # Tag state for conditional routing
    if _has_reliable_text:
        state.artifacts["_text_layer_reliable"] = ["true"]
    else:
        state.artifacts["_text_layer_reliable"] = ["false"]

    logger.info("text_layer_detection_complete", has_reliable=_has_reliable_text)

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=[])


async def parse(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Parse embedded text from PDF into OCR-compatible blocks with bbox."""
    from sqlalchemy import select
    from app.models.core import Document, Artifact, ArtifactType

    artifacts_created = []

    for doc_id in state.doc_ids:
        result = await ctx.db_session.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if not doc or not doc.has_text_layer:
            continue

        blocks_by_page = await _extract_text_blocks(doc, ctx)

        for page_num, blocks in blocks_by_page.items():
            ocr_artifact = OCRTextArtifact(
                doc_id=str(doc.id),
                page=page_num,
                source="TEXT_LAYER",
                blocks=blocks,
            )

            artifact = Artifact(
                id=uuid.uuid4(),
                tenant_id=state.tenant_id,
                workflow_id=state.workflow_id,
                doc_id=doc.id,
                artifact_type=ArtifactType.OCR_TEXT,
                data=ocr_artifact.model_dump(),
                algo_version="v3.0",
            )
            ctx.db_session.add(artifact)
            artifacts_created.append(str(artifact.id))

    await ctx.db_session.flush()
    logger.info("text_layer_parsed", artifacts=len(artifacts_created))

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=[])


async def _check_text_layer(doc, ctx: RunContext) -> tuple[bool, float, str]:
    """Check if PDF has a reliable text layer using PyMuPDF."""
    import fitz

    try:
        file_bytes = await ctx.storage.download(doc.storage_key)
        pdf = fitz.open(stream=file_bytes, filetype="pdf")

        total_chars = 0
        total_pages = len(pdf)

        for page in pdf:
            text = page.get_text()
            total_chars += len(text.strip())

        pdf.close()

        if total_pages == 0:
            return False, 0.0, "No pages in PDF"

        avg_chars = total_chars / total_pages

        if avg_chars > 100:
            return True, 0.95, f"Avg {avg_chars:.0f} chars/page - reliable text layer"
        elif avg_chars > 20:
            return True, 0.5, f"Avg {avg_chars:.0f} chars/page - partial text layer"
        else:
            return False, 0.1, f"Avg {avg_chars:.0f} chars/page - no reliable text layer"

    except Exception as e:
        return False, 0.0, f"Error checking text layer: {str(e)}"


async def _extract_text_blocks(doc, ctx: RunContext) -> dict[int, list[OCRBlock]]:
    """Extract text blocks with bounding boxes from embedded PDF text."""
    import fitz

    file_bytes = await ctx.storage.download(doc.storage_key)
    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    blocks_by_page = {}

    for page_num in range(len(pdf)):
        page = pdf.load_page(page_num)
        rect = page.rect
        pw, ph = rect.width, rect.height

        text_dict = page.get_text("dict")
        blocks = []

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # text block
                continue

            block_bbox = block.get("bbox", [0, 0, 0, 0])
            block_text_parts = []

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    block_text_parts.append(span.get("text", ""))

            text = " ".join(block_text_parts).strip()
            if not text:
                continue

            # Normalize bbox to 0..1
            norm_bbox = [
                block_bbox[0] / pw if pw > 0 else 0,
                block_bbox[1] / ph if ph > 0 else 0,
                block_bbox[2] / pw if pw > 0 else 0,
                block_bbox[3] / ph if ph > 0 else 0,
            ]

            blocks.append(OCRBlock(
                text=text,
                bbox=norm_bbox,
                confidence=0.95,
                provenance=OCRBlockProvenance(engine="pymupdf", engine_version="1.23"),
                source="TEXT_LAYER",
            ))

        blocks_by_page[page_num + 1] = blocks

    pdf.close()
    return blocks_by_page
