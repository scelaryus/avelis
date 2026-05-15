"""Legal case tracking API."""
import hashlib
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.config import get_settings
from app.database import get_db
from app.models.core import Artifact, AuditLog, Document, User
from app.models.legal import LegalCase, LegalCaseDirection, LegalCaseFolder, LegalCaseStatus
from app.services.legal_case_summary import build_case_summary
from app.storage.service import get_storage_service

router = APIRouter(tags=["Legal"])
settings = get_settings()


class LegalCaseCreate(BaseModel):
    title: str
    reference: Optional[str] = None
    direction: LegalCaseDirection
    opposing_party: Optional[str] = None
    court_name: Optional[str] = None
    status: LegalCaseStatus = LegalCaseStatus.OPEN
    description: Optional[str] = None
    opened_on: Optional[date] = None


class LegalFolderCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_folder_id: Optional[str] = None
    sort_order: int = 0


def _serialize_case(case: LegalCase, folder_count: int = 0, document_count: int = 0) -> dict:
    return {
        "id": case.id,
        "title": case.title,
        "reference": case.reference,
        "direction": case.direction.value,
        "opposing_party": case.opposing_party,
        "court_name": case.court_name,
        "status": case.status.value,
        "description": case.description,
        "opened_on": case.opened_on.isoformat() if case.opened_on else None,
        "folder_count": folder_count,
        "document_count": document_count,
        "created_at": case.created_at.isoformat() if case.created_at else None,
    }


def _serialize_folder(folder: LegalCaseFolder, document_count: int = 0) -> dict:
    return {
        "id": folder.id,
        "case_id": folder.case_id,
        "parent_folder_id": folder.parent_folder_id,
        "name": folder.name,
        "description": folder.description,
        "sort_order": folder.sort_order,
        "document_count": document_count,
        "created_at": folder.created_at.isoformat() if folder.created_at else None,
    }


def _serialize_document(document: Document) -> dict:
    return {
        "id": document.id,
        "filename": document.filename,
        "mime_type": document.mime_type,
        "file_size": document.file_size,
        "doc_type": document.doc_type.value if document.doc_type else None,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "legal_case_id": getattr(document, "legal_case_id", None),
        "legal_folder_id": getattr(document, "legal_folder_id", None),
    }


async def _get_case_or_404(case_id: str, tenant_id: str, db: AsyncSession) -> LegalCase:
    result = await db.execute(select(LegalCase).where(LegalCase.id == case_id, LegalCase.tenant_id == tenant_id))
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Legal case not found")
    return case


async def _get_folder_or_404(folder_id: str, tenant_id: str, db: AsyncSession) -> LegalCaseFolder:
    result = await db.execute(select(LegalCaseFolder).where(LegalCaseFolder.id == folder_id, LegalCaseFolder.tenant_id == tenant_id))
    folder = result.scalar_one_or_none()
    if folder is None:
        raise HTTPException(status_code=404, detail="Legal folder not found")
    return folder


@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def create_case(
    body: LegalCaseCreate,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    legal_case = LegalCase(
        tenant_id=user.tenant_id,
        title=body.title,
        reference=body.reference,
        direction=body.direction,
        opposing_party=body.opposing_party,
        court_name=body.court_name,
        status=body.status,
        description=body.description,
        opened_on=body.opened_on,
        created_by=user.id,
    )
    db.add(legal_case)
    await db.flush()

    root_folder = LegalCaseFolder(
        tenant_id=user.tenant_id,
        case_id=legal_case.id,
        name="Dossier principal",
        description="Dossier racine du contentieux",
        sort_order=0,
        created_by=user.id,
    )
    db.add(root_folder)
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="legal_case_create",
        entity_type="legal_case",
        entity_id=legal_case.id,
    ))
    await db.commit()
    await db.refresh(legal_case)
    return _serialize_case(legal_case, folder_count=1, document_count=0)


@router.get("/cases")
async def list_cases(
    direction: Optional[LegalCaseDirection] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(LegalCase).where(LegalCase.tenant_id == user.tenant_id)
    if direction:
        query = query.where(LegalCase.direction == direction)
    query = query.order_by(LegalCase.updated_at.desc(), LegalCase.created_at.desc())
    case_rows = (await db.execute(query)).scalars().all()

    folder_counts = dict(
        (await db.execute(
            select(LegalCaseFolder.case_id, func.count(LegalCaseFolder.id))
            .where(LegalCaseFolder.tenant_id == user.tenant_id)
            .group_by(LegalCaseFolder.case_id)
        )).all()
    )
    document_counts = dict(
        (await db.execute(
            select(Document.legal_case_id, func.count(Document.id))
            .where(Document.tenant_id == user.tenant_id, Document.legal_case_id.isnot(None))
            .group_by(Document.legal_case_id)
        )).all()
    )
    return [
        _serialize_case(case, folder_counts.get(case.id, 0), document_counts.get(case.id, 0))
        for case in case_rows
    ]


@router.get("/cases/{case_id}")
async def get_case(
    case_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    legal_case = await _get_case_or_404(case_id, user.tenant_id, db)
    folder_rows = (await db.execute(
        select(LegalCaseFolder)
        .where(LegalCaseFolder.case_id == case_id, LegalCaseFolder.tenant_id == user.tenant_id)
        .order_by(LegalCaseFolder.sort_order, LegalCaseFolder.created_at)
    )).scalars().all()
    document_rows = (await db.execute(
        select(Document)
        .where(Document.tenant_id == user.tenant_id, Document.legal_case_id == case_id)
        .order_by(Document.created_at.desc())
    )).scalars().all()
    documents_per_folder = {
        row[0]: row[1]
        for row in (await db.execute(
            select(Document.legal_folder_id, func.count(Document.id))
            .where(Document.tenant_id == user.tenant_id, Document.legal_case_id == case_id)
            .group_by(Document.legal_folder_id)
        )).all()
    }
    return {
        "case": _serialize_case(legal_case, len(folder_rows), len(document_rows)),
        "folders": [_serialize_folder(folder, documents_per_folder.get(folder.id, 0)) for folder in folder_rows],
        "documents": [_serialize_document(document) for document in document_rows],
    }


@router.post("/cases/{case_id}/folders", status_code=status.HTTP_201_CREATED)
async def create_folder(
    case_id: str,
    body: LegalFolderCreate,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    await _get_case_or_404(case_id, user.tenant_id, db)
    if body.parent_folder_id:
        parent = await _get_folder_or_404(body.parent_folder_id, user.tenant_id, db)
        if parent.case_id != case_id:
            raise HTTPException(status_code=400, detail="Parent folder does not belong to this case")
    folder = LegalCaseFolder(
        tenant_id=user.tenant_id,
        case_id=case_id,
        parent_folder_id=body.parent_folder_id,
        name=body.name,
        description=body.description,
        sort_order=body.sort_order,
        created_by=user.id,
    )
    db.add(folder)
    await db.flush()
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="legal_folder_create",
        entity_type="legal_folder",
        entity_id=folder.id,
    ))
    await db.commit()
    await db.refresh(folder)
    return _serialize_folder(folder, document_count=0)


@router.get("/cases/{case_id}/summary")
async def get_case_summary(
    case_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    legal_case = await _get_case_or_404(case_id, user.tenant_id, db)
    folder_rows = (await db.execute(
        select(LegalCaseFolder)
        .where(LegalCaseFolder.case_id == case_id, LegalCaseFolder.tenant_id == user.tenant_id)
        .order_by(LegalCaseFolder.sort_order, LegalCaseFolder.created_at)
    )).scalars().all()
    document_rows = (await db.execute(
        select(Document)
        .where(Document.tenant_id == user.tenant_id, Document.legal_case_id == case_id)
        .order_by(Document.created_at.desc())
    )).scalars().all()
    document_ids = [document.id for document in document_rows]
    artifact_rows = []
    if document_ids:
        artifact_rows = (await db.execute(select(Artifact).where(Artifact.doc_id.in_(document_ids)))).scalars().all()
    return await build_case_summary(legal_case, folder_rows, document_rows, artifact_rows)


@router.get("/folders/{folder_id}")
async def get_folder(
    folder_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    folder = await _get_folder_or_404(folder_id, user.tenant_id, db)
    document_rows = (await db.execute(
        select(Document)
        .where(Document.tenant_id == user.tenant_id, Document.legal_folder_id == folder_id)
        .order_by(Document.created_at.desc())
    )).scalars().all()
    return {
        "folder": _serialize_folder(folder, len(document_rows)),
        "documents": [_serialize_document(document) for document in document_rows],
    }


@router.post("/folders/{folder_id}/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_case_document(
    folder_id: str,
    file: UploadFile = File(...),
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    folder = await _get_folder_or_404(folder_id, user.tenant_id, db)
    await _get_case_or_404(folder.case_id, user.tenant_id, db)

    allowed_types = {"application/pdf", "image/png", "image/jpeg", "image/tiff"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

    content = await file.read()
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB")

    file_hash = hashlib.sha256(content).hexdigest()
    storage = get_storage_service()
    storage_key = f"legal/{user.tenant_id}/{folder.case_id}/{folder.id}/{file_hash}/{file.filename}"
    await storage.upload(storage_key, content, file.content_type)

    document = Document(
        tenant_id=user.tenant_id,
        filename=file.filename,
        mime_type=file.content_type,
        file_size=len(content),
        sha256=file_hash,
        storage_key=storage_key,
        uploaded_by=user.id,
        legal_case_id=folder.case_id,
        legal_folder_id=folder.id,
    )
    db.add(document)
    await db.flush()
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="legal_document_upload",
        entity_type="document",
        entity_id=document.id,
        new_value={"case_id": folder.case_id, "folder_id": folder.id},
    ))
    await db.commit()
    await db.refresh(document)
    return _serialize_document(document)