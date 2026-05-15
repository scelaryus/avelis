"""GFI Platform - RenderPagesAgent.

Renders PDF pages to images for OCR and UI display.
"""
import io
import uuid
import structlog
from app.schemas.artifacts import WorkflowState, NodeResult, RenderArtifact
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Render pages from PDFs / normalize image inputs."""
    from sqlalchemy import select
    from app.models.core import Document, Artifact, ArtifactType

    artifacts_created = []
    warnings = []
    errors = []

    for doc_id in state.doc_ids:
        try:
            result = await ctx.db_session.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                errors.append({"code": "DOC_NOT_FOUND", "message": f"Document {doc_id} not found"})
                continue

            mime = doc.mime_type or ""

            if "pdf" in mime:
                # Render PDF pages using PyMuPDF
                renders = await _render_pdf_pages(doc, ctx)
            elif "image" in mime:
                # Single-page image: normalize
                renders = await _render_image(doc, ctx)
            else:
                warnings.append({"code": "UNSUPPORTED_RENDER", "message": f"Cannot render {mime}"})
                continue

            # Store render artifacts
            for r in renders:
                artifact = Artifact(
                    id=uuid.uuid4(),
                    tenant_id=state.tenant_id,
                    workflow_id=state.workflow_id,
                    doc_id=doc.id,
                    artifact_type=ArtifactType.RENDER,
                    data=r.model_dump(),
                    storage_key=r.storage_key,
                    algo_version="v3.0",
                )
                ctx.db_session.add(artifact)
                artifacts_created.append(str(artifact.id))

            # Update page count
            doc.page_count = len(renders)
            await ctx.db_session.flush()

            logger.info("pages_rendered", doc_id=doc_id, pages=len(renders))

        except Exception as e:
            errors.append({"code": "RENDER_ERROR", "message": f"Render failed for {doc_id}: {str(e)}"})

    if errors and not artifacts_created:
        return NodeResult(status="ERROR", artifacts_created=[], warnings=warnings, errors=errors)

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=warnings, errors=errors)


async def _render_pdf_pages(doc, ctx: RunContext) -> list[RenderArtifact]:
    """Render all pages of a PDF to PNG images."""
    import fitz  # PyMuPDF

    renders = []
    dpi = ctx.settings.RENDER_DPI

    # Download file from storage
    file_bytes = await ctx.storage.download(doc.storage_key)
    pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")

    for page_num in range(len(pdf_doc)):
        page = pdf_doc.load_page(page_num)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        img_bytes = pix.tobytes("png")

        # Upload to storage
        storage_key = f"renders/{doc.id}/page_{page_num + 1}.png"
        await ctx.storage.upload(storage_key, img_bytes, content_type="image/png")

        renders.append(RenderArtifact(
            doc_id=str(doc.id),
            page=page_num + 1,
            width=pix.width,
            height=pix.height,
            dpi=dpi,
            format="png",
            storage_key=storage_key,
        ))

    pdf_doc.close()
    return renders


async def _render_image(doc, ctx: RunContext) -> list[RenderArtifact]:
    """Normalize a single image input."""
    from PIL import Image

    file_bytes = await ctx.storage.download(doc.storage_key)
    img = Image.open(io.BytesIO(file_bytes))

    # Store as-is with metadata
    storage_key = f"renders/{doc.id}/page_1.png"
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    await ctx.storage.upload(storage_key, buf.read(), content_type="image/png")

    return [RenderArtifact(
        doc_id=str(doc.id),
        page=1,
        width=img.width,
        height=img.height,
        dpi=ctx.settings.RENDER_DPI,
        format="png",
        storage_key=storage_key,
    )]
