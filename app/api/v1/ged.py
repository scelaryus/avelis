"""Router — GED: document upload, search, detail.
Documents stored in PostgreSQL with full-text search."""
import hashlib
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.api.v1.deps import get_current_user, CurrentUser, get_db
from app.api.v1.schemas import ApiResponse, Meta
from app.models.core import Document, Company, Project, AuditTrail

router = APIRouter(prefix="/ged", tags=["GED"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "uploads")


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    entity_code: str = Form(default=""),
    project_code: str = Form(default=""),
    doc_type: str = Form(default=""),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Upload a document. Layer 1-3 of the 7-layer pipeline."""
    # Layer 1: Reception
    content = await file.read()
    file_size = len(content)

    # Layer 3: Dedup via SHA-256
    file_hash = hashlib.sha256(content).hexdigest()
    existing = db.query(Document).filter(Document.file_hash == file_hash, Document.is_deleted == False).first()
    if existing:
        raise HTTPException(409, f"Document duplique (KT-01). Hash {file_hash[:16]}... identique a {existing.filename}")

    # Save file
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    fpath = os.path.join(UPLOAD_DIR, f"{file_hash[:16]}_{file.filename}")
    with open(fpath, "wb") as f:
        f.write(content)

    # Layer 4-7: Create record (OCR/classification/indexing would happen async in production)
    doc = Document(
        filename=file.filename, file_path=fpath, file_size=file_size,
        file_hash=file_hash, doc_type=doc_type or None,
        entity_code=entity_code or None, project_code=project_code or None,
        pipeline_status="INDEXED", pipeline_layer=7,
        uploaded_by=user.name,
    )
    db.add(doc)
    # Audit trail
    db.add(AuditTrail(
        user_id=user.email or user.user_id, user_role=user.role,
        action="UPLOAD", resource_type="DOCUMENT", resource_id=file.filename,
        module="GED", data_after={"filename": file.filename, "size": file_size, "hash": file_hash[:16]},
    ))
    db.commit()
    db.refresh(doc)
    return ApiResponse(data={
        "document_id": str(doc.id), "filename": doc.filename,
        "size": file_size, "hash": file_hash[:16],
        "pipeline_status": "INDEXED",
    })


@router.get("/documents")
async def search_documents(q: str = "", doc_type: str | None = None,
                            entity_code: str | None = None, project_code: str | None = None,
                            limit: int = 50, offset: int = 0,
                            db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    query = db.query(Document).filter(Document.is_deleted == False)
    if q:
        query = query.filter(
            Document.filename.ilike(f"%{q}%") |
            Document.extracted_text.ilike(f"%{q}%") |
            Document.entity_code.ilike(f"%{q}%") |
            Document.project_code.ilike(f"%{q}%")
        )
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
    if entity_code:
        query = query.filter(Document.entity_code == entity_code)
    if project_code:
        query = query.filter(Document.project_code == project_code)
    total = query.count()
    rows = query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
    return ApiResponse(data=[{
        "id": str(d.id), "filename": d.filename, "doc_type": d.doc_type,
        "entity": d.entity_code, "project": d.project_code,
        "size": d.file_size, "pipeline_status": d.pipeline_status,
        "uploaded_by": d.uploaded_by, "date": str(d.created_at.date()) if d.created_at else "",
    } for d in rows], meta=Meta(total=total, limit=limit, offset=offset))


@router.get("/documents/{doc_id}")
async def document_detail(doc_id: str, db: Session = Depends(get_db),
                            user: CurrentUser = Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document introuvable")
    return ApiResponse(data={
        "id": str(doc.id), "filename": doc.filename, "file_path": doc.file_path,
        "doc_type": doc.doc_type, "file_size": doc.file_size,
        "file_hash": doc.file_hash, "entity": doc.entity_code,
        "project": doc.project_code, "extracted_text": doc.extracted_text,
        "extracted_metadata": doc.extracted_metadata,
        "pipeline_status": doc.pipeline_status, "pipeline_layer": doc.pipeline_layer,
        "uploaded_by": doc.uploaded_by, "date": str(doc.created_at),
    })


@router.get("/pipeline/status")
async def pipeline_status(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    by_status = {}
    for status in ["UPLOADED", "OCR", "CLASSIFIED", "INDEXED"]:
        by_status[status] = db.query(Document).filter(Document.pipeline_status == status).count()
    return ApiResponse(data={
        "total": db.query(Document).filter(Document.is_deleted == False).count(),
        "by_status": by_status,
    })
