"""GAP 8 — Integration tests for BIM/EDD v2 pipeline.

17 test cases covering:
  - IDS validation (pass / reject / fallback)
  - Extraction & mapping
  - Surface computation & tolerance (1%)
  - Orientation computation
  - EDD generation
  - Publish blocking checks
  - Frozen state / freeze-check
  - Pricing coefficient engine
  - Rollback
  - Nomenclature & incoherence detection
  - Unit editing (allowed / blocked)
  - Commission calculation
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.core import Tenant, Document
from app.models.bim_edd import (
    REProject,
    REBlock,
    RELevel,
    REUnit,
    REUnitAnnex,
    REDoc,
    BIMImportJob,
    REPricingRule,
    AnnexType,
    EddState,
    PricingRuleType,
    DocType,
)
from app.services.blocking_rules import BlockingError


# ══════════════════════════════════════════════════════════════════════════
# Shared fixtures
# ══════════════════════════════════════════════════════════════════════════

async def _setup_project(db, tenant_id, *, project_code="PROJ1", north_angle=180):
    """Create tenant + project + block + level."""
    tenant = Tenant(
        id=tenant_id, name="BIM-TEST", code="BT", description="Test", settings={}
    )
    db.add(tenant)
    await db.flush()

    project = REProject(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        code=project_code,
        name="Test Project",
        lat=Decimal("33.5731"),
        lon=Decimal("-7.5898"),
        north_angle=Decimal(str(north_angle)),
    )
    db.add(project)
    await db.flush()

    block = REBlock(
        id=str(uuid.uuid4()),
        project_id=project.id,
        code="BLKA",
        name="Bloc A",
    )
    db.add(block)
    await db.flush()

    level = RELevel(
        id=str(uuid.uuid4()),
        block_id=block.id,
        code="L03",
        elevation=Decimal("9.00"),
    )
    db.add(level)
    await db.flush()

    return {"project": project, "block": block, "level": level}


async def _add_unit(db, level_id, *, code="PROJ1-BLKA-STA-L03-UNIT-AAA", **kwargs):
    """Add a unit to a level with sensible defaults."""
    defaults = dict(
        id=str(uuid.uuid4()),
        level_id=level_id,
        code=code,
        typology="F3",
        bedrooms=2,
        area_sh=Decimal("85.00"),
        area_su=Decimal("72.00"),
        area_net_bim=Decimal("85.50"),
        area_gross_bim=Decimal("110.00"),
        price_base=Decimal("15000"),
    )
    defaults.update(kwargs)
    unit = REUnit(**defaults)
    db.add(unit)
    await db.flush()
    return unit


async def _add_expert_foncier_doc(db, project_id, tenant_id):
    """Create a Document + REDoc expert foncier for publish checks."""
    doc = Document(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        filename="expert_foncier_test.pdf",
        sha256="a" * 64,
        storage_key="ef/test.pdf",
        doc_type="EXPERT_FONCIER",
        file_size=1024,
        uploaded_by=str(uuid.uuid4()),
    )
    db.add(doc)
    await db.flush()

    re_doc = REDoc(
        id=str(uuid.uuid4()),
        project_id=project_id,
        doc_type=DocType.EXPERT_FONCIER,
        file_id=doc.id,
        hash="a" * 64,
    )
    db.add(re_doc)
    await db.flush()
    return re_doc


# ══════════════════════════════════════════════════════════════════════════
# 1. IDS Validation — valid units pass
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ids_validation_pass(db, tenant_id):
    """IDS validation with complete units → VALIDATED."""
    from app.services.edd_service import validate_ids

    data = await _setup_project(db, tenant_id)

    job = BIMImportJob(
        id=str(uuid.uuid4()),
        project_id=data["project"].id,
        filename="model.ifc",
        file_format="IFC",
        ids_report={
            "site": {"Lat": 33.57, "Lon": -7.58, "NorthAngle": 180},
            "units": [
                {"ProjectCode": "PROJ1", "BlockCode": "BLKA", "LevelCode": "L03",
                 "UnitCode": "PROJ1-BLKA-STA-L03-UNIT-AAA",
                 "Area_Net": 85, "Area_Gross": 110, "UsageType": "habitation", "IsAnnex": False},
            ],
        },
    )
    db.add(job)
    await db.flush()

    result = await validate_ids(job.id, db)
    assert result["status"] == "VALIDATED"
    assert result["units_valid"] == 1
    assert result["units_rejected"] == 0


# ══════════════════════════════════════════════════════════════════════════
# 2. IDS Validation — missing fields → REJECTED
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ids_validation_rejected(db, tenant_id):
    """IDS validation with missing UnitCode → REJECTED."""
    from app.services.edd_service import validate_ids

    data = await _setup_project(db, tenant_id)

    job = BIMImportJob(
        id=str(uuid.uuid4()),
        project_id=data["project"].id,
        filename="bad.ifc",
        file_format="IFC",
        ids_report={
            "site": {"Lat": 33.57, "Lon": -7.58, "NorthAngle": 180},
            "units": [
                {"ProjectCode": "PROJ1", "BlockCode": "BLKA", "LevelCode": "L03",
                 "Area_Net": 85, "Area_Gross": 110, "UsageType": "habitation",
                 "IsAnnex": False},  # Missing UnitCode
            ],
        },
    )
    db.add(job)
    await db.flush()

    result = await validate_ids(job.id, db)
    assert result["status"] == "REJECTED"
    assert result["units_rejected"] == 1


# ══════════════════════════════════════════════════════════════════════════
# 3. IDS Validation — no parser fallback → PENDING
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ids_validation_fallback_pending(db, tenant_id):
    """IDS validation with empty units list → PENDING (parser unavailable)."""
    from app.services.edd_service import validate_ids

    data = await _setup_project(db, tenant_id)

    job = BIMImportJob(
        id=str(uuid.uuid4()),
        project_id=data["project"].id,
        filename="empty.ifc",
        file_format="IFC",
        ids_report={"units": []},
    )
    db.add(job)
    await db.flush()

    result = await validate_ids(job.id, db)
    assert result["status"] == "PENDING"


# ══════════════════════════════════════════════════════════════════════════
# 4. Extract & map units
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_extract_and_map_units(db, tenant_id):
    """From validated job, extract creates project/block/level/unit."""
    from app.services.edd_service import validate_ids, extract_and_map_units

    data = await _setup_project(db, tenant_id)

    job = BIMImportJob(
        id=str(uuid.uuid4()),
        project_id=data["project"].id,
        filename="model.ifc",
        file_format="IFC",
        ids_report={
            "site": {"Lat": 33.57, "Lon": -7.58, "NorthAngle": 180},
            "units": [
                {"ProjectCode": "PROJ1", "BlockCode": "BLKA", "LevelCode": "L03",
                 "UnitCode": "PROJ1-BLKA-STA-L03-UNIT-BBB",
                 "Area_Net": 90, "Area_Gross": 120, "UsageType": "habitation",
                 "IsAnnex": False, "Typology": "F4", "Bedrooms": 3},
            ],
        },
    )
    db.add(job)
    await db.flush()

    await validate_ids(job.id, db)
    units = await extract_and_map_units(job.id, db)

    assert len(units) == 1
    assert units[0].code == "PROJ1-BLKA-STA-L03-UNIT-BBB"
    assert float(units[0].area_net_bim) == 90.0


# ══════════════════════════════════════════════════════════════════════════
# 5. Surface computation & tolerance PASS (< 1%)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_surface_tolerance_pass(db, tenant_id):
    """Surface tolerance within 1% → PASSED."""
    from app.services.edd_service import compute_surfaces

    data = await _setup_project(db, tenant_id)
    unit = await _add_unit(db, data["level"].id, area_sh=Decimal("85.00"), area_net_bim=Decimal("85.50"))

    # Add annexes
    db.add(REUnitAnnex(id=str(uuid.uuid4()), unit_id=unit.id, type=AnnexType.B, area=Decimal("6.0")))
    db.add(REUnitAnnex(id=str(uuid.uuid4()), unit_id=unit.id, type=AnnexType.T, area=Decimal("12.5")))
    await db.flush()

    result = await compute_surfaces(unit.id, db)
    assert result["tolerance_status"] == "PASSED"
    assert float(result["area_sb"]) == 6.0
    assert float(result["area_st"]) == 12.5


# ══════════════════════════════════════════════════════════════════════════
# 6. Surface tolerance FAIL (> 1%)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_surface_tolerance_fail(db, tenant_id):
    """Surface tolerance exceeds 1% → FAILED."""
    from app.services.edd_service import compute_surfaces

    data = await _setup_project(db, tenant_id)
    # area_sh=85, area_net_bim=100 → ecart = 15% → FAILED
    unit = await _add_unit(db, data["level"].id, area_sh=Decimal("85.00"), area_net_bim=Decimal("100.00"))

    result = await compute_surfaces(unit.id, db)
    assert result["tolerance_status"] == "FAILED"


# ══════════════════════════════════════════════════════════════════════════
# 7. Orientation computation
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_orientation_south(db, tenant_id):
    """North angle 180 + facade 0 → S."""
    from app.services.edd_service import compute_orientation

    data = await _setup_project(db, tenant_id, north_angle=180)
    unit = await _add_unit(db, data["level"].id)

    exposure = await compute_orientation(unit.id, db, facade_angle=0)
    assert exposure == "S"


# ══════════════════════════════════════════════════════════════════════════
# 8. EDD generation
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_generate_edd(db, tenant_id):
    """Generate EDD report → contains project/blocks/units structure."""
    from app.services.edd_service import generate_edd

    data = await _setup_project(db, tenant_id)
    await _add_unit(db, data["level"].id)

    report = await generate_edd("PROJ1", db)
    assert report["project"]["code"] == "PROJ1"
    assert report["summary"]["total_units"] == 1
    assert len(report["blocks"]) == 1
    assert len(report["blocks"][0]["levels"]) == 1


# ══════════════════════════════════════════════════════════════════════════
# 9. Publish — missing expert foncier → BlockingError
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_publish_blocked_no_expert_foncier(db, tenant_id):
    """Publish blocked when expert foncier document is missing."""
    from app.services.edd_service import publish_edd

    data = await _setup_project(db, tenant_id)
    await _add_unit(db, data["level"].id, price_total=Decimal("1200000"))

    with pytest.raises(BlockingError, match="expert foncier"):
        await publish_edd("PROJ1", "BIM", db)


# ══════════════════════════════════════════════════════════════════════════
# 10. Publish — success (all checks pass)
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_publish_success(db, tenant_id):
    """Full publish succeeds when all blocking checks pass."""
    from app.services.edd_service import publish_edd, compute_surfaces

    data = await _setup_project(db, tenant_id)
    unit = await _add_unit(
        db, data["level"].id,
        price_total=Decimal("1200000"),
        area_sh=Decimal("85.00"),
        area_net_bim=Decimal("85.50"),
    )
    # Run surface compute to create tolerance validation (PASSED)
    await compute_surfaces(unit.id, db)

    # Add expert foncier
    await _add_expert_foncier_doc(db, data["project"].id, tenant_id)

    result = await publish_edd("PROJ1", "BIM", db)
    assert result["units_frozen"] == 1

    # Verify unit is frozen
    r = await db.execute(select(REUnit).where(REUnit.id == unit.id))
    refreshed = r.scalar_one()
    assert refreshed.edd_state == EddState.FROZEN.value


# ══════════════════════════════════════════════════════════════════════════
# 11. Frozen state — freeze-check returns is_frozen=True
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_freeze_check(db, tenant_id):
    """After publish, freeze-check says unit is frozen."""
    from app.services.edd_service import publish_edd, compute_surfaces, check_unit_editable

    data = await _setup_project(db, tenant_id)
    unit = await _add_unit(db, data["level"].id, price_total=Decimal("1200000"))
    await compute_surfaces(unit.id, db)
    await _add_expert_foncier_doc(db, data["project"].id, tenant_id)
    await publish_edd("PROJ1", "BIM", db)

    with pytest.raises(BlockingError, match="gelé"):
        await check_unit_editable(unit.id, db)


# ══════════════════════════════════════════════════════════════════════════
# 12. Pricing — coefficient engine
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_pricing_coefficient(db, tenant_id):
    """Pricing engine applies coefficient and computes price_total."""
    from app.services.pricing_service import compute_unit_price

    data = await _setup_project(db, tenant_id)
    unit = await _add_unit(
        db, data["level"].id,
        price_base=Decimal("15000"),
        area_su=Decimal("72"),
        exposure="S",
        view_class="mer",
    )

    # Add a simple facade rule: +10% for S exposure
    db.add(REPricingRule(
        id=str(uuid.uuid4()),
        code="test_facade_s",
        rule_type=PricingRuleType.FACADE,
        label="S facade +10%",
        value=Decimal("0.10"),
        scope="ALL",
        condition_field="exposure",
        condition_value="S",
    ))
    await db.flush()

    result = await compute_unit_price(unit.id, db)
    # 15000 × 72 × 1.10 = 1,188,000
    assert result["price_total"] == pytest.approx(1188000, abs=1)
    assert len(result["coefficients"]) == 1


# ══════════════════════════════════════════════════════════════════════════
# 13. Pricing — per-level with cap
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_pricing_per_level_cap(db, tenant_id):
    """Per-level coefficient is capped."""
    from app.services.pricing_service import compute_unit_price

    data = await _setup_project(db, tenant_id)
    unit = await _add_unit(
        db, data["level"].id,  # level code = L03
        price_base=Decimal("10000"),
        area_su=Decimal("100"),
        view_class="mer",
    )

    # +5% per level, capped at 10%
    db.add(REPricingRule(
        id=str(uuid.uuid4()),
        code="test_etage_cap",
        rule_type=PricingRuleType.VERTICAL,
        value=Decimal("0.05"),
        scope="ALL",
        condition_field="view_class",
        condition_value="mer",
        is_per_level=True,
        cap_value=Decimal("0.10"),
    ))
    await db.flush()

    result = await compute_unit_price(unit.id, db)
    # L03 → level 3, coeff = 0.05 × 3 = 0.15 but capped at 0.10
    # total = 10000 × 100 × 1.10 = 1,100,000
    assert result["price_total"] == pytest.approx(1100000, abs=1)


# ══════════════════════════════════════════════════════════════════════════
# 14. Rollback — unfreeze units
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_rollback(db, tenant_id):
    """Rollback unfreezes units back to DRAFT."""
    from app.services.edd_service import publish_edd, compute_surfaces, create_new_edd_version

    data = await _setup_project(db, tenant_id)
    unit = await _add_unit(db, data["level"].id, price_total=Decimal("1200000"))
    await compute_surfaces(unit.id, db)
    await _add_expert_foncier_doc(db, data["project"].id, tenant_id)

    await publish_edd("PROJ1", "BIM", db)

    # Rollback
    await create_new_edd_version("PROJ1", "correction surfaces", "BIM", db)

    r = await db.execute(select(REUnit).where(REUnit.id == unit.id))
    refreshed = r.scalar_one()
    assert refreshed.edd_state == EddState.DRAFT.value


# ══════════════════════════════════════════════════════════════════════════
# 15. Nomenclature correction
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_nomenclature_correction(db, tenant_id):
    """Bad nomenclature gets a correction suggestion."""
    from app.services.edd_ocr_service import suggest_nomenclature_correction

    suggestion = suggest_nomenclature_correction("PROJ1-A-STA-L03")
    assert suggestion is not None
    assert "UNIT" in suggestion


# ══════════════════════════════════════════════════════════════════════════
# 16. Incoherence detection — typology vs bedrooms
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_incoherence_typology(db, tenant_id):
    """F3 with 0 bedrooms → incoherence warning."""
    from app.services.edd_ocr_service import detect_edd_incoherences

    data = await _setup_project(db, tenant_id)
    unit = await _add_unit(db, data["level"].id, typology="F3", bedrooms=0)

    issues = await detect_edd_incoherences(unit.id, db)
    assert any(i["check"] == "typology_vs_bedrooms" for i in issues)


# ══════════════════════════════════════════════════════════════════════════
# 17. Unit editing — allowed when DRAFT, blocked when FROZEN
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_edit_unit_allowed_draft(db, tenant_id):
    """Editing a DRAFT unit succeeds."""
    from app.services.edd_service import update_unit

    data = await _setup_project(db, tenant_id)
    unit = await _add_unit(db, data["level"].id)

    updated = await update_unit(unit.id, {"typology": "F4", "bedrooms": 3}, db)
    assert updated.typology == "F4"
    assert updated.bedrooms == 3


@pytest.mark.asyncio
async def test_edit_unit_blocked_frozen(db, tenant_id):
    """Editing a FROZEN unit raises BlockingError."""
    from app.services.edd_service import update_unit, publish_edd, compute_surfaces

    data = await _setup_project(db, tenant_id)
    unit = await _add_unit(db, data["level"].id, price_total=Decimal("1200000"))
    await compute_surfaces(unit.id, db)
    await _add_expert_foncier_doc(db, data["project"].id, tenant_id)
    await publish_edd("PROJ1", "BIM", db)

    with pytest.raises(BlockingError):
        await update_unit(unit.id, {"typology": "F4"}, db)


# ══════════════════════════════════════════════════════════════════════════
# 18. Commission calculation
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_commission_cash(db, tenant_id):
    """Cash client commission = 1% base."""
    from app.services.pricing_service import compute_commission

    result = await compute_commission(
        sale_amount=1000000,
        client_type="CASH",
        agent_id="agent1",
        sales_count_agent=3,
        db=db,
    )
    assert result["base_rate"] == 0.01
    assert result["base_commission"] == 10000.0
    assert result["split"]["agent"] > 0
