# GAP 8.D — BIM / EDD API — api/bim.py
"""BIM import, IDS validation, EDD pipeline, pricing, and unit editing endpoints."""
from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.core import User, Document
from app.models.bim_edd import (
    REProject,
    REBlock,
    RELevel,
    REUnit,
    REValidation,
    REDoc,
    BIMImportJob,
    EddState,
    ImportJobStatus,
    DocType,
)
from app.services.blocking_rules import BlockingError
from app.services.rbac import require_permission

router = APIRouter(tags=["BIM / EDD"])


# ── Helpers ────────────────────────────────────────────────────────────────

def _blocking_to_422(exc: BlockingError):
    raise HTTPException(status_code=422, detail=str(exc))


# ════════════════════════════════════════════════════════════════════════════
# BIM Import (IFC / RVT file upload)
# ════════════════════════════════════════════════════════════════════════════

@router.post("/import", status_code=201)
async def bim_import(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bim:import")),
):
    """Upload an IFC or RVT file for BIM import.

    Creates a BIMImportJob in PENDING status.
    Actual IFC parsing is not available — sets status PENDING with message.
    """
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].upper() if "." in filename else ""
    if ext not in ("IFC", "RVT"):
        raise HTTPException(status_code=400, detail="Only IFC or RVT files accepted")

    content = await file.read()
    sha = hashlib.sha256(content).hexdigest()

    # Store document record
    doc = Document(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        filename=filename,
        sha256=sha,
        storage_key=f"bim/{sha[:12]}_{filename}",
        doc_type="BIM_IMPORT",
        file_size=len(content),
        uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()

    job = BIMImportJob(
        id=str(uuid.uuid4()),
        project_id=project_id,
        filename=filename,
        file_format=ext,
        file_id=doc.id,
        status=ImportJobStatus.PENDING,
        error_message="Parser IFC non disponible — validation manuelle requise",
        created_by=user.id,
    )
    db.add(job)
    await db.commit()

    return {
        "import_id": job.id,
        "filename": filename,
        "file_format": ext,
        "status": job.status.value,
        "message": job.error_message,
    }


# ════════════════════════════════════════════════════════════════════════════
# IDS Validation
# ════════════════════════════════════════════════════════════════════════════

@router.get("/validate/{import_id}")
async def validate_import(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bim:read")),
):
    """Validate IDS fields on a BIM import job."""
    from app.services.edd_service import validate_ids

    result = await validate_ids(import_id, db)
    await db.commit()
    return result


# ════════════════════════════════════════════════════════════════════════════
# Extract & Map Units
# ════════════════════════════════════════════════════════════════════════════

@router.post("/extract/{import_id}", status_code=201)
async def extract_units(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bim:write")),
):
    """Extract and map units from a validated import job."""
    from app.services.edd_service import extract_and_map_units

    try:
        units = await extract_and_map_units(import_id, db)
        await db.commit()
        return {"extracted": len(units), "unit_ids": [u.id for u in units]}
    except BlockingError as e:
        _blocking_to_422(e)


# ════════════════════════════════════════════════════════════════════════════
# EDD Generation
# ════════════════════════════════════════════════════════════════════════════

@router.post("/edd/generate")
async def generate_edd_endpoint(
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("edd:generate")),
):
    """Generate EDD report for a project and return JSON + PDF download URL."""
    from app.services.edd_service import generate_edd

    project_code = data.get("project_code")
    if not project_code:
        raise HTTPException(status_code=400, detail="project_code required")

    report = await generate_edd(project_code, db)
    await db.commit()
    report["pdf_url"] = f"/api/v1/bim/edd/{project_code}/pdf"
    return report


@router.get("/edd/{project_code}/pdf")
async def download_edd_pdf(
    project_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("edd:read")),
):
    """Download the EDD report as a PDF."""
    from app.services.edd_service import generate_edd
    from app.services.pdf_generator import generate_edd_pdf

    try:
        report = await generate_edd(project_code, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    pdf_bytes = generate_edd_pdf(report)
    filename = f"EDD_{project_code}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ════════════════════════════════════════════════════════════════════════════
# EDD Publish
# ════════════════════════════════════════════════════════════════════════════

@router.post("/edd/publish")
async def publish_edd_endpoint(
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("edd:publish")),
):
    """Publish EDD: validates, freezes all units, logs event."""
    from app.services.edd_service import publish_edd

    project_code = data.get("project_code")
    if not project_code:
        raise HTTPException(status_code=400, detail="project_code required")

    try:
        result = await publish_edd(project_code, user.id, db)
        await db.commit()
        return result
    except BlockingError as e:
        _blocking_to_422(e)


# ════════════════════════════════════════════════════════════════════════════
# EDD Read
# ════════════════════════════════════════════════════════════════════════════

@router.get("/edd/{project_code}")
async def get_edd(
    project_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("edd:read")),
):
    """Get project info and validation history."""
    proj_r = await db.execute(
        select(REProject).where(REProject.code == project_code)
    )
    project = proj_r.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    val_r = await db.execute(
        select(REValidation)
        .where(REValidation.object_type == "re_project", REValidation.object_id == project.id)
        .order_by(REValidation.ts.desc())
    )
    validations = val_r.scalars().all()

    return {
        "project": {
            "code": project.code,
            "name": project.name,
            "status": project.status,
        },
        "validations": [
            {"stage": v.stage.value, "status": v.status.value, "ts": str(v.ts)}
            for v in validations
        ],
    }


# ════════════════════════════════════════════════════════════════════════════
# EDD Units listing (paginated + filtered)
# ════════════════════════════════════════════════════════════════════════════

@router.get("/edd/{project_code}/units")
async def list_edd_units(
    project_code: str,
    typology: Optional[str] = None,
    edd_state: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("edd:read")),
):
    """List units for a project with pagination and filters."""
    proj_r = await db.execute(
        select(REProject).where(REProject.code == project_code)
    )
    project = proj_r.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build subquery for units in this project
    level_ids_sq = (
        select(RELevel.id)
        .where(RELevel.block_id.in_(
            select(REBlock.id).where(REBlock.project_id == project.id)
        ))
    )

    query = select(REUnit).where(REUnit.level_id.in_(level_ids_sq))

    if typology:
        query = query.where(REUnit.typology == typology)
    if edd_state:
        query = query.where(REUnit.edd_state == edd_state)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    query = query.order_by(REUnit.code).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    units = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "units": [
            {
                "id": u.id,
                "code": u.code,
                "typology": u.typology,
                "area_sh": float(u.area_sh or 0),
                "area_su": float(u.area_su or 0),
                "exposure": u.exposure,
                "view_class": u.view_class,
                "price_base": float(u.price_base or 0),
                "price_total": float(u.price_total or 0),
                "edd_state": u.edd_state,
            }
            for u in units
        ],
    }


# ════════════════════════════════════════════════════════════════════════════
# EDD Rollback
# ════════════════════════════════════════════════════════════════════════════

@router.post("/edd/rollback")
async def rollback_edd_endpoint(
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("edd:publish")),
):
    """Rollback frozen EDD to DRAFT (blocked if sales exist)."""
    from app.services.edd_service import create_new_edd_version

    project_code = data.get("project_code")
    reason = data.get("reason", "")
    if not project_code:
        raise HTTPException(status_code=400, detail="project_code required")

    try:
        await create_new_edd_version(project_code, reason, user.id, db)
        await db.commit()
        return {"status": "rolled_back", "project_code": project_code}
    except BlockingError as e:
        _blocking_to_422(e)


# ════════════════════════════════════════════════════════════════════════════
# Freeze-check (single unit)
# ════════════════════════════════════════════════════════════════════════════

@router.post("/edd/freeze-check/{unit_id}")
async def freeze_check_unit(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("edd:read")),
):
    """Check if a unit is frozen (cannot be edited)."""
    result = await db.execute(select(REUnit).where(REUnit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    return {
        "unit_id": unit.id,
        "code": unit.code,
        "edd_state": unit.edd_state,
        "is_frozen": unit.edd_state == EddState.FROZEN.value,
    }


# ════════════════════════════════════════════════════════════════════════════
# Expert Foncier Upload (multipart + OCR)
# ════════════════════════════════════════════════════════════════════════════

@router.post("/expert-foncier/upload", status_code=201)
async def upload_expert_foncier(
    file: UploadFile = File(...),
    project_code: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bim:write")),
):
    """Upload expert foncier report and optionally run OCR."""
    proj_r = await db.execute(
        select(REProject).where(REProject.code == project_code)
    )
    project = proj_r.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    sha = hashlib.sha256(content).hexdigest()
    filename = file.filename or "expert_foncier.pdf"

    doc = Document(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        filename=filename,
        sha256=sha,
        storage_key=f"expert_foncier/{sha[:12]}_{filename}",
        doc_type="EXPERT_FONCIER",
        file_size=len(content),
        uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()

    re_doc = REDoc(
        id=str(uuid.uuid4()),
        project_id=project.id,
        doc_type=DocType.EXPERT_FONCIER,
        file_id=doc.id,
        hash=sha,
        uploaded_by=user.id,
    )
    db.add(re_doc)

    # Mark previous expert foncier docs as obsolete
    old_docs_r = await db.execute(
        select(REDoc).where(
            REDoc.project_id == project.id,
            REDoc.doc_type == DocType.EXPERT_FONCIER,
            REDoc.id != re_doc.id,
        )
    )
    for old in old_docs_r.scalars().all():
        old.is_obsolete = True

    await db.commit()

    return {
        "doc_id": re_doc.id,
        "file_id": doc.id,
        "hash": sha,
        "project_code": project_code,
    }


# ════════════════════════════════════════════════════════════════════════════
# Unit Pricing
# ════════════════════════════════════════════════════════════════════════════

@router.get("/units/{unit_id}/pricing")
async def get_unit_pricing(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bim:read")),
):
    """Compute and return pricing breakdown for a unit."""
    from app.services.pricing_service import compute_unit_price

    result = await compute_unit_price(unit_id, db)
    await db.commit()
    return result


# ════════════════════════════════════════════════════════════════════════════
# Unit CRUD (create / edit EDD data — blocked when frozen for edits)
# ════════════════════════════════════════════════════════════════════════════

@router.post("/edd/{project_code}/units", status_code=201)
async def create_unit_for_edd(
    project_code: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("re_unit:write")),
):
    """Create a new EDD unit manually for a BIM project.

    Manual alternative to IFC import:
      - requires an existing REProject (by project_code)
      - requires block_code and level_code to position the unit
      - creates REBlock / RELevel if they do not already exist
      - creates a REUnit in DRAFT edd_state
    """
    block_code = data.get("block_code")
    level_code = data.get("level_code")
    unit_code = data.get("code")

    if not project_code:
        raise HTTPException(status_code=400, detail="project_code is required")
    if not block_code or not level_code or not unit_code:
        raise HTTPException(
            status_code=400,
            detail="block_code, level_code and code are required",
        )

    proj_r = await db.execute(
        select(REProject).where(
            REProject.code == project_code,
            REProject.tenant_id == user.tenant_id,
        )
    )
    project = proj_r.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Upsert block
    blk_r = await db.execute(
        select(REBlock).where(
            REBlock.project_id == project.id,
            REBlock.code == block_code,
        )
    )
    block = blk_r.scalar_one_or_none()
    if not block:
        block = REBlock(
            id=str(uuid.uuid4()),
            project_id=project.id,
            code=block_code,
            name=data.get("block_name") or block_code,
        )
        db.add(block)
        await db.flush()

    # Upsert level
    lvl_r = await db.execute(
        select(RELevel).where(
            RELevel.block_id == block.id,
            RELevel.code == level_code,
        )
    )
    level = lvl_r.scalar_one_or_none()
    if not level:
        level = RELevel(
            id=str(uuid.uuid4()),
            block_id=block.id,
            code=level_code,
        )
        db.add(level)
        await db.flush()

    # Ensure unit code is unique (global uniqueness enforced by model)
    existing_unit_r = await db.execute(
        select(REUnit).where(REUnit.code == unit_code)
    )
    if existing_unit_r.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="A unit with this code already exists",
        )

    unit = REUnit(
        id=str(uuid.uuid4()),
        level_id=level.id,
        code=unit_code,
        typology=data.get("typology"),
        bedrooms=data.get("bedrooms"),
        bathrooms=data.get("bathrooms"),
        area_sh=data.get("area_sh"),
        area_su=data.get("area_su"),
        area_net_bim=data.get("area_net_bim") or data.get("area_sh"),
        area_gross_bim=data.get("area_gross_bim"),
        price_base=data.get("price_base"),
        price_total=data.get("price_total"),
        exposure=data.get("exposure"),
        view_class=data.get("view_class"),
        usage_type=data.get("usage_type"),
        edd_state=EddState.DRAFT.value,
    )
    db.add(unit)
    await db.commit()

    return {
        "id": unit.id,
        "code": unit.code,
        "typology": unit.typology,
        "area_sh": float(unit.area_sh or 0),
        "area_su": float(unit.area_su or 0),
        "price_total": float(unit.price_total or 0),
        "edd_state": unit.edd_state,
    }


@router.put("/units/{unit_id}")
async def update_unit_endpoint(
    unit_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("re_unit:write")),
):
    """Update a unit's fields. Blocked if EDD is frozen."""
    from app.services.edd_service import update_unit

    try:
        unit = await update_unit(unit_id, data, db)
        await db.commit()
        return {
            "id": unit.id,
            "code": unit.code,
            "typology": unit.typology,
            "area_sh": float(unit.area_sh or 0),
            "price_total": float(unit.price_total or 0),
            "edd_state": unit.edd_state,
        }
    except BlockingError as e:
        _blocking_to_422(e)


# ════════════════════════════════════════════════════════════════════════════
# Surface computation trigger
# ════════════════════════════════════════════════════════════════════════════

@router.post("/units/{unit_id}/compute-surfaces")
async def compute_surfaces_endpoint(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bim:write")),
):
    """Compute aggregated surfaces and tolerance for a unit."""
    from app.services.edd_service import compute_surfaces

    result = await compute_surfaces(unit_id, db)
    await db.commit()
    return result


# ════════════════════════════════════════════════════════════════════════════
# Projects CRUD
# ════════════════════════════════════════════════════════════════════════════

@router.get("/projects")
async def list_re_projects(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bim:read")),
):
    result = await db.execute(
        select(REProject).where(REProject.tenant_id == user.tenant_id)
    )
    return [
        {"id": p.id, "code": p.code, "name": p.name, "status": p.status}
        for p in result.scalars().all()
    ]


@router.post("/projects", status_code=201)
async def create_re_project(
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bim:write")),
):
    project = REProject(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        code=data["code"],
        name=data["name"],
        lat=data.get("lat"),
        lon=data.get("lon"),
        north_angle=data.get("north_angle"),
    )
    db.add(project)
    await db.commit()
    return {"id": project.id, "code": project.code, "name": project.name}


# ════════════════════════════════════════════════════════════════════════════
# Validations history
# ════════════════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════════════════
# EDD Excel Import (AI-powered column mapping)
# ════════════════════════════════════════════════════════════════════════════

@router.post("/edd/import-excel", status_code=201)
async def import_edd_excel(
    file: UploadFile = File(...),
    project_code: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bim:write")),
):
    """Import EDD data from an Excel file.

    Uses an AI agent to understand column formats and map them
    to the canonical EDD schema. Supports various column naming
    conventions (French, Arabic, English, abbreviated).
    """
    filename = file.filename or "edd_import.xlsx"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("xlsx", "xls"):
        raise HTTPException(status_code=400, detail="Seuls les fichiers Excel (.xlsx, .xls) sont acceptes")

    content = await file.read()
    max_size = 50 * 1024 * 1024  # 50 MB
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 50 MB)")

    from app.services.edd_excel_import import import_edd_from_excel

    result = await import_edd_from_excel(
        file_content=content,
        filename=filename,
        tenant_id=user.tenant_id,
        user_id=str(user.id),
        project_code_override=project_code,
        db=db,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=422, detail=result)

    await db.commit()
    return result


# ════════════════════════════════════════════════════════════════════════════
# EDD Document Import (AI-powered PDF/image → EDD extraction)
# ════════════════════════════════════════════════════════════════════════════

@router.post("/edd/import-document", status_code=201)
async def import_edd_document(
    file: UploadFile = File(...),
    project_code: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bim:write")),
):
    """Import EDD data from a scanned PDF or image document.

    Uses AI vision to analyze the document (état descriptif et divisif,
    tableau de lots, plan de masse, etc.) and extract unit data including:
    lot codes, typologies, surfaces (SH/SU), floors, prices.
    Then creates/updates the EDD structure from the extracted data.
    """
    import base64
    from app.services.llm_graph import invoke_json_agent

    allowed_types = {"application/pdf", "image/png", "image/jpeg", "image/tiff"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Format non supporté: {file.content_type}. Acceptés: PDF, PNG, JPG, TIFF")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 50 MB)")

    # Extract text from PDF or encode image
    extracted_text = ""
    image_b64 = None
    image_mime = None

    if file.content_type == "application/pdf":
        try:
            import fitz
            pdf = fitz.open(stream=content, filetype="pdf")
            pages = []
            for i in range(min(pdf.page_count, 10)):
                pages.append(pdf.load_page(i).get_text())
            pdf.close()
            extracted_text = "\n---PAGE---\n".join(pages)[:12000]
        except Exception:
            pass
        # If no text, try first page as image for vision
        if not extracted_text.strip():
            try:
                import fitz
                pdf = fitz.open(stream=content, filetype="pdf")
                page = pdf.load_page(0)
                pix = page.get_pixmap(dpi=200)
                image_b64 = base64.b64encode(pix.tobytes("png")).decode()
                image_mime = "image/png"
                pdf.close()
            except Exception:
                pass
    else:
        image_b64 = base64.b64encode(content).decode()
        image_mime = file.content_type

    if not extracted_text and not image_b64:
        raise HTTPException(status_code=422, detail="Impossible d'extraire le contenu du document")

    system_prompt = """\
You are an EDD (État Descriptif et Divisif) data extractor for a real-estate group in Algeria.
You receive a scanned document or PDF containing information about property lots/units.

Your task: Extract ALL units/lots visible in the document into a structured JSON array.

For each unit, extract:
- block_code: building/block identifier (e.g. "BLKA", "Bloc A", "Bat 1")
- level_code: floor/level (e.g. "RDC", "1er", "2ème", "SS1", "L03")
- code: unique lot/unit code if visible
- typology: apartment type (e.g. "F2", "F3", "F4", "STUDIO", "DUPLEX", "LOCAL")
- bedrooms: number of bedrooms (integer, null if unknown)
- area_sh: surface habitable in m² (number)
- area_su: surface utile in m² (number, null if not shown)
- area_sb: surface balcon (number, null)
- area_st: surface terrasse (number, null)
- area_sj: surface jardin (number, null)
- area_sp: surface parking (number, null)
- price_base: price per m² if shown (number, null)
- price_total: total unit price if shown (number, null)
- exposure: orientation (N, S, E, O, NE, NO, SE, SO, null)
- usage_type: HABITATION, COMMERCIAL, PARKING, CAVE (default HABITATION)

Also extract project-level info if visible:
- project_name: name of the project/residence
- project_code: project code if shown
- total_units: total number of units mentioned

Reply with JSON:
{
  "project_name": "...",
  "project_code": "...",
  "total_units": ...,
  "units": [
    { "block_code": "...", "level_code": "...", "code": "...", ... },
    ...
  ],
  "notes": "any observations about data quality or missing information"
}
No markdown fences. No extra text. Return ALL visible units."""

    user_prompt = f"Document filename: {file.filename}\n"
    if project_code:
        user_prompt += f"Project code (override): {project_code}\n"
    if extracted_text:
        user_prompt += f"\nExtracted text:\n\"\"\"\n{extracted_text}\n\"\"\""
    if image_b64:
        user_prompt += "\nI am attaching the scanned document image. Analyze it to extract all lot/unit data visible."

    try:
        result = await invoke_json_agent(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=4096,
            image_b64=image_b64,
            image_mime=image_mime,
        )
        ai_data = result["parsed_json"]
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Erreur IA lors de l'analyse: {str(exc)}")

    # Use the project_code from override or AI detection
    effective_project_code = project_code or ai_data.get("project_code")
    if not effective_project_code:
        return {
            "status": "needs_project_code",
            "message": "Le code projet n'a pas pu être détecté. Veuillez le spécifier.",
            "ai_result": ai_data,
        }

    # Create or get the project
    proj_r = await db.execute(
        select(REProject).where(REProject.code == effective_project_code)
    )
    project = proj_r.scalar_one_or_none()
    if not project:
        project = REProject(
            code=effective_project_code,
            name=ai_data.get("project_name") or effective_project_code,
        )
        db.add(project)
        await db.flush()

    # Process extracted units
    units = ai_data.get("units") or []
    created = 0
    skipped = 0
    warnings = []

    for u in units:
        block_code = (u.get("block_code") or "BLKA").strip().upper()
        level_code = (u.get("level_code") or "L00").strip().upper()
        unit_code = u.get("code") or f"{effective_project_code}-{block_code}-{level_code}-{created+1:03d}"

        # Get or create block
        blk_r = await db.execute(
            select(REBlock).where(
                REBlock.project_id == project.id,
                REBlock.code == block_code,
            )
        )
        block = blk_r.scalar_one_or_none()
        if not block:
            block = REBlock(project_id=project.id, code=block_code, name=block_code)
            db.add(block)
            await db.flush()

        # Get or create level
        lvl_r = await db.execute(
            select(RELevel).where(
                RELevel.block_id == block.id,
                RELevel.code == level_code,
            )
        )
        level = lvl_r.scalar_one_or_none()
        if not level:
            level = RELevel(block_id=block.id, code=level_code, label=level_code)
            db.add(level)
            await db.flush()

        # Check for existing unit
        existing_r = await db.execute(
            select(REUnit).where(REUnit.code == unit_code)
        )
        if existing_r.scalar_one_or_none():
            skipped += 1
            warnings.append(f"Unité {unit_code} existe déjà, ignorée.")
            continue

        def safe_float(v):
            if v is None:
                return 0.0
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0.0

        new_unit = REUnit(
            level_id=level.id,
            code=unit_code,
            typology=u.get("typology"),
            bedrooms=u.get("bedrooms"),
            area_sh=safe_float(u.get("area_sh")),
            area_su=safe_float(u.get("area_su")),
            area_sb=safe_float(u.get("area_sb")),
            area_st=safe_float(u.get("area_st")),
            area_sj=safe_float(u.get("area_sj")),
            area_sp=safe_float(u.get("area_sp")),
            price_base=safe_float(u.get("price_base")),
            price_total=safe_float(u.get("price_total")),
            exposure=u.get("exposure"),
            usage_type=u.get("usage_type") or "HABITATION",
            edd_state="DRAFT",
        )
        db.add(new_unit)
        created += 1

    await db.commit()

    return {
        "status": "success",
        "project_code": effective_project_code,
        "project_name": ai_data.get("project_name"),
        "ai_units_detected": len(units),
        "created": created,
        "skipped": skipped,
        "warnings": warnings,
        "notes": ai_data.get("notes"),
    }


@router.get("/validations/{project_code}")
async def list_validations(
    project_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bim:read")),
):
    proj_r = await db.execute(
        select(REProject).where(REProject.code == project_code)
    )
    project = proj_r.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(REValidation)
        .where(REValidation.object_id == project.id)
        .order_by(REValidation.ts.desc())
    )
    return [
        {
            "id": v.id,
            "stage": v.stage.value,
            "status": v.status.value,
            "payload": v.payload,
            "ts": str(v.ts),
        }
        for v in result.scalars().all()
    ]
