# GAP 8.F — OCR & INCOHERENCE SERVICE — services/edd_ocr_service.py
"""OCR extraction from expert-foncier PDFs and EDD incoherence detection.

Provides:
  - ocr_expert_foncier_report  — extract structured data from PDF (stub)
  - detect_edd_incoherences     — 4 rule-based checks on unit data
  - suggest_nomenclature_correction — parse bad codes → suggest PROJ-BLK-STA-Lxx-UNIT-AAA
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bim_edd import (
    REUnit,
    REUnitAnnex,
)

logger = structlog.get_logger(__name__)

# Nomenclature pattern: PROJ-BLK-STA-Lxx-UNIT-AAA
NOMENCLATURE_RE = re.compile(
    r"^([A-Z0-9]+)-([A-Z0-9]{1,8})-([A-Z0-9]+)-L(\d{2})-UNIT-([A-Z]{3})$"
)


# ════════════════════════════════════════════════════════════════════════════
# OCR extraction (stub — real impl needs tesseract / cloud API)
# ════════════════════════════════════════════════════════════════════════════

async def ocr_expert_foncier_report(file_path: str) -> dict[str, Any]:
    """Extract structured fields from an expert-foncier PDF.

    Returns dict with:
      - surface_totale_cadastrale
      - date_rapport
      - nom_expert
      - reference_cadastrale
      - observations
      - sha256

    NOTE: Actual OCR requires tesseract/pdfplumber. This is a stub.
    """
    # Compute SHA-256 of file
    try:
        with open(file_path, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        sha = None

    return {
        "surface_totale_cadastrale": None,
        "date_rapport": None,
        "nom_expert": None,
        "reference_cadastrale": None,
        "observations": "OCR non disponible — extraction manuelle requise",
        "sha256": sha,
    }


# ════════════════════════════════════════════════════════════════════════════
# Incoherence detection
# ════════════════════════════════════════════════════════════════════════════

async def detect_edd_incoherences(
    unit_id: str,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Run 4 rule-based checks on a unit and return issues found.

    Checks:
      1. Typology vs surfaces — e.g. F2 should have 2 bedrooms
      2. Orientation vs facade — e.g. vue_mer + N exposure is suspect
      3. Orphan annexes — annexes not linked to a valid unit
      4. Nomenclature format — code should match PROJ-BLK-STA-Lxx-UNIT-AAA
    """
    result = await db.execute(select(REUnit).where(REUnit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        return [{"check": "unit_exists", "severity": "error", "message": f"Unit {unit_id} not found"}]

    issues: list[dict[str, Any]] = []

    # Check 1: Typology vs surfaces
    typology = (unit.typology or "").upper()
    if typology.startswith("F") and len(typology) >= 2:
        try:
            expected_bedrooms = int(typology[1]) - 1  # F3 = 2 bedrooms
            if unit.bedrooms is not None and unit.bedrooms != expected_bedrooms:
                issues.append({
                    "check": "typology_vs_bedrooms",
                    "severity": "warning",
                    "message": f"Typology {typology} expects {expected_bedrooms} bedrooms, found {unit.bedrooms}",
                    "unit_code": unit.code,
                })
        except ValueError:
            pass

    if typology == "STUDIO" and unit.bedrooms and unit.bedrooms > 0:
        issues.append({
            "check": "typology_vs_bedrooms",
            "severity": "warning",
            "message": f"Studio should have 0 bedrooms, found {unit.bedrooms}",
            "unit_code": unit.code,
        })

    # Check 2: Orientation vs facade
    if unit.view_class == "mer" and unit.exposure in ("N", "NO"):
        issues.append({
            "check": "orientation_vs_facade",
            "severity": "warning",
            "message": f"Vue mer declared but exposure is {unit.exposure} (unexpected for sea view)",
            "unit_code": unit.code,
        })

    # Check 3: Orphan annexes
    annex_r = await db.execute(
        select(REUnitAnnex).where(REUnitAnnex.unit_id == unit.id)
    )
    annexes = annex_r.scalars().all()
    for annex in annexes:
        if not annex.area or annex.area <= 0:
            issues.append({
                "check": "orphan_annex",
                "severity": "warning",
                "message": f"Annex {annex.type.value} has zero or null area",
                "unit_code": unit.code,
                "annex_id": annex.id,
            })

    # Check 4: Nomenclature format
    if unit.code and not NOMENCLATURE_RE.match(unit.code):
        issues.append({
            "check": "nomenclature_format",
            "severity": "info",
            "message": f"Code '{unit.code}' does not match PROJ-BLK-STA-Lxx-UNIT-AAA",
            "unit_code": unit.code,
            "suggestion": suggest_nomenclature_correction(unit.code),
        })

    return issues


# ════════════════════════════════════════════════════════════════════════════
# Nomenclature correction
# ════════════════════════════════════════════════════════════════════════════

def suggest_nomenclature_correction(code: str) -> str | None:
    """Parse a potentially bad unit code and suggest the canonical format.

    Expected: PROJ-BLK-STA-Lxx-UNIT-AAA
    """
    if not code:
        return None

    # Try to extract parts
    parts = code.upper().replace("_", "-").split("-")

    if len(parts) >= 3:
        proj = parts[0][:10]
        blk = parts[1][:8] if len(parts) > 1 else "BLK"
        sta = parts[2][:3] if len(parts) > 2 else "STA"
        lvl = "L00"
        unit_suffix = "AAA"

        # Try to find level info
        for p in parts:
            if p.startswith("L") and len(p) >= 2 and p[1:].isdigit():
                lvl = f"L{int(p[1:]):02d}"
                break

        # Last part could be unit suffix
        if len(parts) > 3:
            last = parts[-1]
            if last.isalpha() and len(last) <= 3:
                unit_suffix = last.ljust(3, "A")

        return f"{proj}-{blk}-{sta}-{lvl}-UNIT-{unit_suffix}"

    return f"{code}-BLK-STA-L00-UNIT-AAA"
