"""GFI Platform - OCRAgent (FIRST-CLASS).

Runs OCR on page images, returns text blocks with normalized bbox.
Supports PaddleOCR/Tesseract/EasyOCR.
"""
import io
import uuid
import structlog
from app.schemas.artifacts import (
    WorkflowState, NodeResult, OCRTextArtifact, OCRBlock, OCRBlockProvenance,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Run OCR on all rendered page images."""
    from sqlalchemy import select
    from app.models.core import Artifact, ArtifactType

    artifacts_created = []
    errors = []

    # Get render artifacts
    render_ids = state.artifacts.get("render", [])
    if not render_ids:
        return NodeResult(
            status="OK",
            artifacts_created=[],
            warnings=[{"code": "NO_RENDERS", "message": "No render artifacts for OCR"}],
            errors=[],
        )

    for render_id in render_ids:
        try:
            result = await ctx.db_session.execute(
                select(Artifact).where(Artifact.id == render_id)
            )
            render_artifact = result.scalar_one_or_none()
            if not render_artifact:
                continue

            render_data = render_artifact.data
            doc_id = render_data["doc_id"]
            page = render_data["page"]
            storage_key = render_data["storage_key"]

            # Check cache
            cache_result = await ctx.db_session.execute(
                select(Artifact).where(
                    Artifact.doc_id == doc_id,
                    Artifact.artifact_type == ArtifactType.OCR_TEXT,
                    Artifact.inputs_hash == f"ocr_{storage_key}",
                )
            )
            cached = cache_result.scalar_one_or_none()
            if cached:
                artifacts_created.append(str(cached.id))
                logger.info("using_cached_ocr", doc_id=doc_id, page=page)
                continue

            # Download page image
            img_bytes = await ctx.storage.download(storage_key)

            # Run OCR
            engine = ctx.settings.OCR_ENGINE
            langs = ctx.settings.OCR_DEFAULT_LANGS.split(",")
            width = render_data.get("width", 1)
            height = render_data.get("height", 1)

            blocks = await _run_ocr(img_bytes, engine, langs, width, height)

            ocr_artifact = OCRTextArtifact(
                doc_id=doc_id,
                page=page,
                source="OCR",
                blocks=blocks,
            )

            artifact = Artifact(
                id=uuid.uuid4(),
                tenant_id=state.tenant_id,
                workflow_id=state.workflow_id,
                doc_id=doc_id,
                artifact_type=ArtifactType.OCR_TEXT,
                data=ocr_artifact.model_dump(),
                algo_version=f"v3.0-{engine}",
                inputs_hash=f"ocr_{storage_key}",
            )
            ctx.db_session.add(artifact)
            artifacts_created.append(str(artifact.id))

            logger.info("ocr_complete", doc_id=doc_id, page=page, blocks=len(blocks))

        except Exception as e:
            errors.append({"code": "OCR_ERROR", "message": f"OCR failed: {str(e)}"})

    await ctx.db_session.flush()

    if errors and not artifacts_created:
        # OCR failure is non-blocking — continue pipeline with empty text
        return NodeResult(status="OK", artifacts_created=[], warnings=errors, errors=[])

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=errors)


async def _run_ocr(img_bytes: bytes, engine: str, langs: list[str], width: int, height: int) -> list[OCRBlock]:
    """Run OCR using the configured engine."""
    if engine == "paddleocr":
        return await _run_paddleocr(img_bytes, langs, width, height)
    elif engine == "tesseract":
        return await _run_tesseract(img_bytes, langs, width, height)
    else:
        return await _run_paddleocr(img_bytes, langs, width, height)


async def _run_paddleocr(img_bytes: bytes, langs: list[str], width: int, height: int) -> list[OCRBlock]:
    """Run PaddleOCR on image bytes."""
    import numpy as np
    from PIL import Image
    import asyncio

    def _do_ocr():
        from paddleocr import PaddleOCR

        # Map language codes
        lang = "fr" if "fr" in langs else "en"
        ocr_engine = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

        img = Image.open(io.BytesIO(img_bytes))
        img_array = np.array(img)

        results = ocr_engine.ocr(img_array, cls=True)
        blocks = []

        if results and results[0]:
            for line in results[0]:
                bbox_raw = line[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                text_info = line[1]  # (text, confidence)

                text = text_info[0]
                confidence = text_info[1]

                # Convert polygon to [x0, y0, x1, y1] normalized
                xs = [p[0] for p in bbox_raw]
                ys = [p[1] for p in bbox_raw]
                norm_bbox = [
                    min(xs) / width if width > 0 else 0,
                    min(ys) / height if height > 0 else 0,
                    max(xs) / width if width > 0 else 0,
                    max(ys) / height if height > 0 else 0,
                ]

                blocks.append(OCRBlock(
                    text=text,
                    bbox=norm_bbox,
                    confidence=confidence,
                    provenance=OCRBlockProvenance(engine="paddleocr", engine_version="2.7"),
                    source="OCR",
                ))

        return blocks

    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _do_ocr)


async def _run_tesseract(img_bytes: bytes, langs: list[str], width: int, height: int) -> list[OCRBlock]:
    """Run Tesseract OCR on image bytes."""
    import asyncio
    from PIL import Image

    def _do_ocr():
        try:
            import pytesseract
        except ImportError:
            logger.warning("tesseract_not_available, falling back to empty blocks")
            return []

        img = Image.open(io.BytesIO(img_bytes))
        lang_str = "+".join(langs)

        data = pytesseract.image_to_data(img, lang=lang_str, output_type=pytesseract.Output.DICT)

        blocks = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if not text:
                continue

            conf = float(data["conf"][i]) / 100.0
            if conf < 0:
                continue

            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            norm_bbox = [
                x / width if width > 0 else 0,
                y / height if height > 0 else 0,
                (x + w) / width if width > 0 else 0,
                (y + h) / height if height > 0 else 0,
            ]

            blocks.append(OCRBlock(
                text=text,
                bbox=norm_bbox,
                confidence=conf,
                provenance=OCRBlockProvenance(engine="tesseract", engine_version="5.0"),
                source="OCR",
            ))

        return blocks

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _do_ocr)
