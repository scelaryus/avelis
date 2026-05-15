"""GFI Platform - IngestDocumentsAgent.

Accepts files, hashes them, stores in object storage, registers DocumentArtifact.
"""
import uuid
import structlog

from app.schemas.artifacts import (
    WorkflowState, NodeResult, DocumentArtifact
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)

ALLOWED_MIMES = {
    "application/pdf", "image/png", "image/jpeg", "image/tiff",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
}


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """
    Ingest documents: hash, detect mime, store, create DocumentArtifact.
    Expects doc_ids in state to be pre-registered document IDs after upload.
    """
    from sqlalchemy import select
    from app.models.core import Document, Artifact, ArtifactType

    artifacts_created = []
    warnings = []
    errors = []

    for doc_id in state.doc_ids:
        try:
            # Fetch document record
            result = await ctx.db_session.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()

            if not doc:
                errors.append({"code": "DOC_NOT_FOUND", "message": f"Document {doc_id} not found"})
                continue

            # Build document artifact
            doc_artifact = DocumentArtifact(
                doc_id=str(doc.id),
                filename=doc.filename,
                mime_type=doc.mime_type or "application/octet-stream",
                file_size=doc.file_size or 0,
                sha256=doc.sha256,
                storage_key=doc.storage_key,
                page_count=doc.page_count,
                doc_type_guess=doc.doc_type.value if doc.doc_type else "OTHER",
                doc_type_confidence=doc.doc_type_confidence or 0.0,
            )

            # Check for existing cached artifact (same sha256)
            cache_result = await ctx.db_session.execute(
                select(Artifact).where(
                    Artifact.doc_id == doc.id,
                    Artifact.artifact_type == ArtifactType.DOCUMENT,
                )
            )
            existing = cache_result.scalar_one_or_none()

            if existing:
                artifacts_created.append(str(existing.id))
                logger.info("using_cached_document_artifact", doc_id=doc_id, artifact_id=str(existing.id))
                continue

            # Store new artifact
            artifact = Artifact(
                id=uuid.uuid4(),
                tenant_id=state.tenant_id,
                workflow_id=state.workflow_id,
                doc_id=doc.id,
                artifact_type=ArtifactType.DOCUMENT,
                data=doc_artifact.model_dump(),
                sha256=doc.sha256,
                algo_version="v3.0",
                inputs_hash=doc.sha256,
            )
            ctx.db_session.add(artifact)
            artifacts_created.append(str(artifact.id))

            logger.info("document_ingested", doc_id=doc_id, artifact_id=str(artifact.id))

        except Exception as e:
            errors.append({
                "code": "INGEST_ERROR",
                "message": f"Failed to ingest document {doc_id}: {str(e)}"
            })

    await ctx.db_session.flush()

    if errors and not artifacts_created:
        return NodeResult(status="ERROR", artifacts_created=[], warnings=warnings, errors=errors)

    return NodeResult(
        status="OK",
        artifacts_created=artifacts_created,
        warnings=warnings,
        errors=errors,
    )
