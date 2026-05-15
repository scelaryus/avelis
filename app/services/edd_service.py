# GAP 8.B — EDD SERVICE — services/edd_service.py
"""End-to-end EDD pipeline.

Steps:
  1. validate_ids           – IDS field-level checks on BIM import
  2. extract_and_map_units  – map IFC data to DB entities
  3. compute_surfaces       – SH/SU/annexes + tolerance
  4. compute_orientation    – cardinal exposure from north angle
  5. generate_edd           – structured JSON EDD report
  6. validate_before_publish – blocking checks
  7. publish_edd            – freeze units + log + event
  8. create_new_edd_version – rollback if no sales
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bim_edd import (
    REProject,
    REBlock,
    RELevel,
    REUnit,
    REUnitAnnex,
    REValidation,
    REDoc,
    BIMImportJob,
    AnnexType,
    EddState,
    ValidationStage,
    ValidationStatus,
    ImportJobStatus,
    DocType,
)
from app.services.blocking_rules import BlockingError

logger = structlog.get_logger(__name__)

Q2 = Decimal("0.01")

# ── Configurable usage types for SH computation ───────────────────────────
SURFACE_SH_USAGE_TYPES = {"chambre", "sejour", "cuisine", "bureau", "salle_a_manger"}
SURFACE_SU_EXTRA_TYPES = {"degagement", "rangement", "couloir", "entree"}


# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 1 — Validation IDS
# ════════════════════════════════════════════════════════════════════════════

async def validate_ids(
    import_job_id: str,
    db: AsyncSession,
) -> dict:
    """Validate IDS fields on a BIM import job.

    Checks each unit record in ids_report for required fields.
    Updates bim_import_job.status to VALIDATED or REJECTED.
    """
    result = await db.execute(
        select(BIMImportJob).where(BIMImportJob.id == import_job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise ValueError(f"Import job {import_job_id} not found")

    ids_report: dict[str, Any] = job.ids_report or {}
    units_data = ids_report.get("units", [])

    if not units_data:
        job.status = ImportJobStatus.PENDING
        job.error_message = "Parser IFC non disponible — validation manuelle requise"
        await db.flush()
        return {"status": "PENDING", "message": job.error_message}

    required_unit = ["ProjectCode", "BlockCode", "LevelCode", "UnitCode",
                     "Area_Net", "Area_Gross", "UsageType", "IsAnnex"]
    required_site = ["Lat", "Lon", "NorthAngle"]

    errors: list[dict] = []
    site_data = ids_report.get("site", {})
    for field in required_site:
        if not site_data.get(field):
            errors.append({"scope": "site", "field": field, "message": f"{field} missing"})

    valid_count = 0
    rejected_count = 0
    for idx, unit in enumerate(units_data):
        unit_code = unit.get("UnitCode", f"unit_{idx}")
        unit_errors = []
        for field in required_unit:
            if not unit.get(field) and unit.get(field) != 0:
                unit_errors.append({"field": field, "message": f"{field} missing"})
        if unit.get("IsAnnex") and not unit.get("AnnexType"):
            unit_errors.append({"field": "AnnexType", "message": "AnnexType required when IsAnnex=True"})
        if unit.get("AnnexType") and unit["AnnexType"] not in ("B", "T", "J", "P", "C"):
            unit_errors.append({"field": "AnnexType", "message": f"Invalid AnnexType: {unit['AnnexType']}"})
        if unit_errors:
            rejected_count += 1
            for e in unit_errors:
                errors.append({"scope": "unit", "unit_code": unit_code, **e})
        else:
            valid_count += 1

    bcf_report = [e for e in errors if e["scope"] == "unit"]

    job.ids_report = {"units": units_data, "site": site_data, "validation": errors}
    job.bcf_report = bcf_report or None
    job.units_found = len(units_data)
    job.units_valid = valid_count
    job.units_rejected = rejected_count

    critical = any(e["scope"] == "unit" and e.get("field") in ("UnitCode", "Area_Net") for e in errors)
    if critical or rejected_count > 0:
        job.status = ImportJobStatus.REJECTED
    else:
        job.status = ImportJobStatus.VALIDATED

    await db.flush()
    return {
        "status": job.status.value,
        "units_found": job.units_found,
        "units_valid": valid_count,
        "units_rejected": rejected_count,
        "errors": errors,
    }


# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 2 — Mapping / extraction
# ════════════════════════════════════════════════════════════════════════════

async def extract_and_map_units(
    import_job_id: str,
    db: AsyncSession,
) -> list[REUnit]:
    """From a VALIDATED import job, create/update project→block→level→unit."""
    result = await db.execute(
        select(BIMImportJob).where(BIMImportJob.id == import_job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise ValueError(f"Import job {import_job_id} not found")
    if job.status != ImportJobStatus.VALIDATED:
        raise BlockingError("Import job must be VALIDATED before extraction")

    ids = job.ids_report or {}
    site = ids.get("site", {})
    units_data = ids.get("units", [])

    created_units: list[REUnit] = []

    for u in units_data:
        project_code = u["ProjectCode"]
        block_code = u["BlockCode"]
        level_code = u["LevelCode"]
        unit_code = u["UnitCode"]

        # Upsert project
        proj_r = await db.execute(
            select(REProject).where(REProject.code == project_code)
        )
        project = proj_r.scalar_one_or_none()
        if not project:
            project = REProject(
                id=str(uuid.uuid4()),
                tenant_id=job.project_id or str(uuid.uuid4()),
                code=project_code,
                name=project_code,
                lat=site.get("Lat"),
                lon=site.get("Lon"),
                north_angle=site.get("NorthAngle"),
            )
            db.add(project)
            await db.flush()

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
                name=u.get("BlockName", block_code),
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

        # Upsert unit
        unit_r = await db.execute(
            select(REUnit).where(REUnit.code == unit_code)
        )
        unit = unit_r.scalar_one_or_none()
        is_annex = bool(u.get("IsAnnex"))
        if not unit:
            unit = REUnit(
                id=str(uuid.uuid4()),
                level_id=level.id,
                code=unit_code,
                typology=u.get("Typology"),
                bedrooms=u.get("Bedrooms"),
                area_sh=u.get("Area_Net"),
                area_su=u.get("AreaUseful"),
                area_net_bim=u.get("Area_Net"),
                area_gross_bim=u.get("Area_Gross"),
                is_annex=is_annex,
                annex_type=u.get("AnnexType") if is_annex else None,
                usage_type=u.get("UsageType"),
                ifc_space_id=u.get("IfcSpaceNumber"),
            )
            db.add(unit)
            await db.flush()
        else:
            unit.area_net_bim = u.get("Area_Net")
            unit.area_gross_bim = u.get("Area_Gross")
            unit.typology = u.get("Typology") or unit.typology

        # Create annex row if applicable
        if is_annex and u.get("AnnexType"):
            annex = REUnitAnnex(
                id=str(uuid.uuid4()),
                unit_id=unit.id,
                type=AnnexType(u["AnnexType"]),
                area=Decimal(str(u.get("Area_Net", 0))),
                ifc_space_id=u.get("IfcSpaceNumber"),
            )
            db.add(annex)

        created_units.append(unit)

    await db.flush()
    logger.info("extract_and_map_done", job=import_job_id, units=len(created_units))
    return created_units


# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 3 — Calcul des surfaces
# ════════════════════════════════════════════════════════════════════════════

async def compute_surfaces(
    unit_id: str,
    db: AsyncSession,
) -> dict:
    """Compute and update aggregate surface fields on a unit.

    Also performs tolerance check (1% threshold) and creates re_validation.
    """
    result = await db.execute(select(REUnit).where(REUnit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise ValueError(f"Unit {unit_id} not found")

    # Sum annexes by type
    annex_r = await db.execute(
        select(REUnitAnnex).where(REUnitAnnex.unit_id == unit.id)
    )
    annexes = annex_r.scalars().all()

    sums: dict[str, Decimal] = {"B": Decimal(0), "T": Decimal(0), "J": Decimal(0),
                                 "P": Decimal(0), "C": Decimal(0)}
    for a in annexes:
        sums[a.type.value] = sums.get(a.type.value, Decimal(0)) + Decimal(str(a.area or 0))

    unit.area_sb = sums["B"].quantize(Q2, ROUND_HALF_UP)
    unit.area_st = sums["T"].quantize(Q2, ROUND_HALF_UP)
    unit.area_sj = sums["J"].quantize(Q2, ROUND_HALF_UP)
    unit.area_sp = sums["P"].quantize(Q2, ROUND_HALF_UP)
    unit.area_sc = sums["C"].quantize(Q2, ROUND_HALF_UP)

    # Surface tolerance check (1%)
    tolerance_status = ValidationStatus.PASSED
    payload: dict[str, Any] = {}
    if unit.area_sh and unit.area_net_bim:
        sh = Decimal(str(unit.area_sh))
        bim = Decimal(str(unit.area_net_bim))
        if bim > 0:
            ecart_pct = abs(sh - bim) / bim * 100
            payload = {
                "ecart_pct": float(ecart_pct.quantize(Q2)),
                "area_sh": float(sh),
                "area_net_bim": float(bim),
            }
            if ecart_pct > Decimal("1.0"):
                tolerance_status = ValidationStatus.FAILED

    validation = REValidation(
        id=str(uuid.uuid4()),
        object_type="re_unit",
        object_id=unit.id,
        stage=ValidationStage.SURFACE_TOLERANCE,
        status=tolerance_status,
        payload=payload,
    )
    db.add(validation)
    await db.flush()

    return {
        "unit_id": unit.id,
        "area_sb": float(unit.area_sb),
        "area_st": float(unit.area_st),
        "area_sj": float(unit.area_sj),
        "area_sp": float(unit.area_sp),
        "area_sc": float(unit.area_sc),
        "tolerance_status": tolerance_status.value,
        "tolerance_payload": payload,
    }


# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 4 — Calcul orientation
# ════════════════════════════════════════════════════════════════════════════

CARDINAL_RANGES = [
    (0, 22.5, "N"), (22.5, 67.5, "NE"), (67.5, 112.5, "E"),
    (112.5, 157.5, "SE"), (157.5, 202.5, "S"), (202.5, 247.5, "SO"),
    (247.5, 292.5, "O"), (292.5, 337.5, "NO"), (337.5, 360, "N"),
]


async def compute_orientation(
    unit_id: str,
    db: AsyncSession,
    facade_angle: float | None = None,
) -> str:
    """Compute cardinal exposure from north_angle + facade angle."""
    result = await db.execute(select(REUnit).where(REUnit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise ValueError(f"Unit {unit_id} not found")

    # Walk up to project for north_angle
    level_r = await db.execute(select(RELevel).where(RELevel.id == unit.level_id))
    level = level_r.scalar_one()
    block_r = await db.execute(select(REBlock).where(REBlock.id == level.block_id))
    block = block_r.scalar_one()
    proj_r = await db.execute(select(REProject).where(REProject.id == block.project_id))
    project = proj_r.scalar_one()

    north = float(project.north_angle or 0)
    angle = (facade_angle or 0) + north
    angle = angle % 360

    exposure = "N"
    for lo, hi, card in CARDINAL_RANGES:
        if lo <= angle < hi:
            exposure = card
            break

    unit.exposure = exposure
    # Auto-validate view_class for mer exposures
    if unit.view_class == "mer" and exposure in ("N", "NO", "NE"):
        pass  # keep declared value — detect_incoherences will warn

    await db.flush()
    return exposure


# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 5 — Génération EDD
# ════════════════════════════════════════════════════════════════════════════

def _validate_unit_completeness(unit: REUnit) -> list[str]:
    """Return list of missing critical fields on a unit."""
    missing = []
    if not unit.code:
        missing.append("code")
    if not unit.typology:
        missing.append("typology")
    if not unit.area_sh or unit.area_sh <= 0:
        missing.append("area_sh")
    if not unit.price_base and not unit.price_total:
        missing.append("price_base or price_total")
    return missing


async def generate_edd(
    project_code: str,
    db: AsyncSession,
) -> dict:
    """Build full EDD structured report for a project."""
    proj_r = await db.execute(
        select(REProject).where(REProject.code == project_code)
    )
    project = proj_r.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project {project_code} not found")

    blocks_r = await db.execute(
        select(REBlock).where(REBlock.project_id == project.id).order_by(REBlock.code)
    )
    blocks = blocks_r.scalars().all()

    blocks_data = []
    total_units = 0
    total_sh = Decimal(0)
    total_su = Decimal(0)

    for block in blocks:
        levels_r = await db.execute(
            select(RELevel).where(RELevel.block_id == block.id).order_by(RELevel.code)
        )
        levels = levels_r.scalars().all()

        levels_data = []
        for level in levels:
            units_r = await db.execute(
                select(REUnit).where(
                    REUnit.level_id == level.id,
                    REUnit.is_annex.is_not(True),
                ).order_by(REUnit.code)
            )
            units = units_r.scalars().all()

            units_data = []
            for u in units:
                completeness = _validate_unit_completeness(u)
                units_data.append({
                    "code": u.code,
                    "typology": u.typology,
                    "area_sh": float(u.area_sh or 0),
                    "area_su": float(u.area_su or 0),
                    "area_sb": float(u.area_sb or 0),
                    "area_st": float(u.area_st or 0),
                    "area_sj": float(u.area_sj or 0),
                    "area_sp": float(u.area_sp or 0),
                    "area_sc": float(u.area_sc or 0),
                    "area_scom": float(u.area_scom or 0),
                    "exposure": u.exposure,
                    "view_class": u.view_class,
                    "price_base": float(u.price_base or 0),
                    "price_total": float(u.price_total or 0),
                    "coefficients_applied": [],
                    "observations": ", ".join(completeness) if completeness else "",
                })
                total_units += 1
                total_sh += Decimal(str(u.area_sh or 0))
                total_su += Decimal(str(u.area_su or 0))

            levels_data.append({
                "level": {"code": level.code, "elevation": float(level.elevation or 0)},
                "units": units_data,
            })

        blocks_data.append({
            "block": {"code": block.code, "name": block.name},
            "levels": levels_data,
        })

    now = datetime.now(timezone.utc).isoformat()

    edd_report = {
        "project": {
            "code": project.code,
            "name": project.name,
            "lat": float(project.lat or 0),
            "lon": float(project.lon or 0),
        },
        "blocks": blocks_data,
        "summary": {
            "total_units": total_units,
            "total_sh": float(total_sh),
            "total_su": float(total_su),
            "generated_at": now,
        },
    }

    # Save as re_docs JSON (no PDF/Excel generation without optional deps)
    doc_hash = hashlib.sha256(str(edd_report).encode()).hexdigest()

    return edd_report


# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 6 — Validations bloquantes avant publication
# ════════════════════════════════════════════════════════════════════════════

async def validate_before_publish(
    project_code: str,
    db: AsyncSession,
) -> None:
    """Run all blocking checks. Raises BlockingError on failure."""
    proj_r = await db.execute(
        select(REProject).where(REProject.code == project_code)
    )
    project = proj_r.scalar_one_or_none()
    if not project:
        raise BlockingError(f"Project {project_code} not found")

    # Get all non-annex units
    units_r = await db.execute(
        select(REUnit).where(
            REUnit.level_id.in_(
                select(RELevel.id).where(
                    RELevel.block_id.in_(
                        select(REBlock.id).where(REBlock.project_id == project.id)
                    )
                )
            )
        )
    )
    units = units_r.scalars().all()

    if not units:
        raise BlockingError("Aucune unité trouvée pour ce projet")

    # Blocage 1 — champs critiques manquants
    for unit in units:
        manquants = _validate_unit_completeness(unit)
        if manquants:
            raise BlockingError(
                f"Unité {unit.code} : champs critiques manquants : {', '.join(manquants)}"
            )

    # Blocage 2 — tolérance surfaces
    for unit in units:
        tol_r = await db.execute(
            select(REValidation).where(
                REValidation.object_id == unit.id,
                REValidation.stage == ValidationStage.SURFACE_TOLERANCE,
                REValidation.status == ValidationStatus.FAILED,
            )
        )
        failed = tol_r.scalars().all()
        if failed:
            payload = failed[0].payload or {}
            raise BlockingError(
                f"Unité {unit.code} : écart surface > 1% : {payload}"
            )

    # Blocage 3 — rapport expert foncier
    doc_r = await db.execute(
        select(REDoc).where(
            REDoc.project_id == project.id,
            REDoc.doc_type == DocType.EXPERT_FONCIER,
            REDoc.is_obsolete == False,
        )
    )
    if not doc_r.scalar_one_or_none():
        raise BlockingError(
            "Rapport expert foncier absent ou obsolète pour ce projet"
        )


# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 7 — Publication et gel EDD
# ════════════════════════════════════════════════════════════════════════════

async def publish_edd(
    project_code: str,
    published_by: str,
    db: AsyncSession,
) -> dict:
    """Validate, freeze all units, log validations, return summary."""
    # Step 1: blocking checks
    await validate_before_publish(project_code, db)

    proj_r = await db.execute(
        select(REProject).where(REProject.code == project_code)
    )
    project = proj_r.scalar_one()

    # Step 2: freeze all units
    units_r = await db.execute(
        select(REUnit).where(
            REUnit.level_id.in_(
                select(RELevel.id).where(
                    RELevel.block_id.in_(
                        select(REBlock.id).where(REBlock.project_id == project.id)
                    )
                )
            )
        )
    )
    units = units_r.scalars().all()

    now = datetime.now(timezone.utc)
    for unit in units:
        unit.edd_state = EddState.FROZEN.value

        # Step 3: per-unit freeze validation
        db.add(REValidation(
            id=str(uuid.uuid4()),
            object_type="re_unit",
            object_id=unit.id,
            stage=ValidationStage.FREEZE,
            status=ValidationStatus.PASSED,
            validator_role=published_by,
        ))

    # Step 4: project-level publication validation
    db.add(REValidation(
        id=str(uuid.uuid4()),
        object_type="re_project",
        object_id=project.id,
        stage=ValidationStage.PUBLICATION,
        status=ValidationStatus.PASSED,
        validator_role=published_by,
    ))

    project.status = "FROZEN"
    await db.flush()

    # Step 5: event would be emitted here (edd.published)
    logger.info("edd_published", project=project_code, units_frozen=len(units))

    return {
        "project_code": project_code,
        "units_frozen": len(units),
        "published_at": now.isoformat(),
    }


# ════════════════════════════════════════════════════════════════════════════
# ÉTAPE 8 — Versioning / rollback
# ════════════════════════════════════════════════════════════════════════════

async def create_new_edd_version(
    project_code: str,
    reason: str,
    created_by: str,
    db: AsyncSession,
) -> None:
    """Rollback FROZEN units to DRAFT. Blocked if adv sales exist."""
    proj_r = await db.execute(
        select(REProject).where(REProject.code == project_code)
    )
    project = proj_r.scalar_one_or_none()
    if not project:
        raise BlockingError(f"Project {project_code} not found")

    # Get all frozen units
    units_r = await db.execute(
        select(REUnit).where(
            REUnit.edd_state == EddState.FROZEN.value,
            REUnit.level_id.in_(
                select(RELevel.id).where(
                    RELevel.block_id.in_(
                        select(REBlock.id).where(REBlock.project_id == project.id)
                    )
                )
            ),
        )
    )
    units = units_r.scalars().all()

    if not units:
        raise BlockingError("Aucune unité gelée pour ce projet")

    # Check for linked sales (Contract model in adv.py)
    from app.models.adv import Contract
    for unit in units:
        sale_r = await db.execute(
            select(func.count(Contract.id)).where(
                Contract.notes.contains(unit.code)
            )
        )
        if (sale_r.scalar() or 0) > 0:
            raise BlockingError(
                "Rollback impossible : des ventes sont déjà enregistrées sur ce projet"
            )

    # Rollback
    for unit in units:
        unit.edd_state = EddState.DRAFT.value

    db.add(REValidation(
        id=str(uuid.uuid4()),
        object_type="re_project",
        object_id=project.id,
        stage=ValidationStage.ROLLBACK,
        status=ValidationStatus.PASSED,
        payload={"reason": reason, "created_by": created_by},
    ))

    # Mark all EDD_REPORT docs as obsolete
    docs_r = await db.execute(
        select(REDoc).where(
            REDoc.project_id == project.id,
            REDoc.doc_type == DocType.EDD_REPORT,
        )
    )
    for doc in docs_r.scalars().all():
        doc.is_obsolete = True

    project.status = "DRAFT"
    await db.flush()
    logger.info("edd_rollback", project=project_code, units=len(units))


# ════════════════════════════════════════════════════════════════════════════
# Helpers for unit modification (EDD must be non-frozen)
# ════════════════════════════════════════════════════════════════════════════

async def check_unit_editable(unit_id: str, db: AsyncSession) -> REUnit:
    """Return unit if editable. Raise BlockingError if FROZEN."""
    result = await db.execute(select(REUnit).where(REUnit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise ValueError(f"Unit {unit_id} not found")
    if unit.edd_state == EddState.FROZEN.value:
        raise BlockingError("EDD non gelé. Décision d'affectation impossible.")
    return unit


async def update_unit(
    unit_id: str,
    data: dict,
    db: AsyncSession,
) -> REUnit:
    """Update a unit's fields if EDD is not frozen."""
    unit = await check_unit_editable(unit_id, db)
    editable_fields = {
        "typology", "bedrooms", "bathrooms", "height_clear",
        "area_sh", "area_su", "area_sb", "area_st", "area_sj",
        "area_sp", "area_sc", "area_scom", "exposure", "view_class",
        "price_base", "price_total", "usage_type", "is_annex", "annex_type",
    }
    for key, val in data.items():
        if key in editable_fields:
            setattr(unit, key, val)
    await db.flush()
    return unit
