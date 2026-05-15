# GAP 8.C — PRICING SERVICE — services/pricing_service.py
"""Coefficient-based pricing engine for BIM/EDD.

Provides:
  - compute_unit_price   — apply coefficient rules: price_total = price_base × area_su × coeff_final
  - compute_commission   — progressive commission calculation
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bim_edd import (
    REUnit,
    RELevel,
    REBlock,
    REProject,
    REPricingRule,
)

logger = structlog.get_logger(__name__)

Q2 = Decimal("0.01")


# ════════════════════════════════════════════════════════════════════════════
# Unit pricing
# ════════════════════════════════════════════════════════════════════════════

async def compute_unit_price(
    unit_id: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """Apply all active pricing rules to a unit.

    Formula: price_total = price_base × area_su × product(coeff_i)
    Coefficients from re_pricing_rules filtered by scope / condition / date.

    Returns dict with coefficient breakdown and final price.
    """
    result = await db.execute(select(REUnit).where(REUnit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise ValueError(f"Unit {unit_id} not found")

    # Walk up to project for scope resolution
    level_r = await db.execute(select(RELevel).where(RELevel.id == unit.level_id))
    level = level_r.scalar_one()
    block_r = await db.execute(select(REBlock).where(REBlock.id == level.block_id))
    block = block_r.scalar_one()
    proj_r = await db.execute(select(REProject).where(REProject.id == block.project_id))
    project = proj_r.scalar_one()

    # Fetch all active rules valid today
    today = date.today()
    rules_r = await db.execute(
        select(REPricingRule).where(
            REPricingRule.active == True,
        ).order_by(REPricingRule.rule_type, REPricingRule.code)
    )
    all_rules = rules_r.scalars().all()

    # Filter by date window
    active_rules = []
    for r in all_rules:
        if r.active_from and r.active_from > today:
            continue
        if r.active_to and r.active_to < today:
            continue
        active_rules.append(r)

    # Match rules by condition
    applied: list[dict] = []
    coefficient_total = Decimal("1.0")

    for rule in active_rules:
        # Scope check
        scope = (rule.scope or "ALL").upper()
        if scope not in ("ALL", ""):
            if not _scope_matches(scope, unit, level, block, project):
                continue

        # Condition field/value check
        if rule.condition_field and rule.condition_value:
            unit_val = _get_field_value(unit, level, block, project, rule.condition_field)
            if str(unit_val).upper() != str(rule.condition_value).upper():
                continue

        coeff = Decimal(str(rule.value))

        # Per-level rules: multiply coefficient by level index
        if rule.is_per_level:
            level_idx = _extract_level_index(level.code)
            coeff = coeff * Decimal(str(level_idx))
            # Apply cap
            if rule.cap_value:
                cap = Decimal(str(rule.cap_value))
                if coeff > cap:
                    coeff = cap

        coefficient_total *= (Decimal("1.0") + coeff)

        applied.append({
            "rule_code": rule.code,
            "rule_type": rule.rule_type.value,
            "label": rule.label,
            "raw_value": float(rule.value),
            "applied_coefficient": float(coeff),
        })

    # Final price
    price_base = Decimal(str(unit.price_base or 0))
    area_su = Decimal(str(unit.area_su or unit.area_sh or 0))

    price_total = (price_base * area_su * coefficient_total).quantize(Q2, ROUND_HALF_UP)

    unit.price_total = price_total
    await db.flush()

    logger.info("pricing_computed", unit=unit_id, total=float(price_total), coeffs=len(applied))

    return {
        "unit_id": unit_id,
        "price_base": float(price_base),
        "area_su": float(area_su),
        "coefficient_total": float(coefficient_total),
        "coefficients": applied,
        "price_total": float(price_total),
    }


def _scope_matches(
    scope: str, unit: REUnit, level: RELevel, block: REBlock, project: REProject
) -> bool:
    """Check if a rule scope applies to this unit."""
    scope_upper = scope.upper()
    if scope_upper == "UNIT":
        return not unit.is_annex
    if scope_upper == "VILLA":
        return (unit.typology or "").upper().startswith("VILLA")
    if scope_upper == "COMMERCE":
        return (unit.usage_type or "").upper() == "COMMERCE"
    if scope_upper == "ALL":
        return True
    return True


def _get_field_value(
    unit: REUnit, level: RELevel, block: REBlock, project: REProject,
    field_name: str,
) -> Any:
    """Resolve a condition field from unit/level/block/project."""
    if hasattr(unit, field_name):
        return getattr(unit, field_name)
    if hasattr(level, field_name):
        return getattr(level, field_name)
    if hasattr(block, field_name):
        return getattr(block, field_name)
    if hasattr(project, field_name):
        return getattr(project, field_name)
    return None


def _extract_level_index(level_code: str) -> int:
    """Extract numeric level from code like 'L01', 'L10'."""
    digits = "".join(c for c in level_code if c.isdigit())
    return int(digits) if digits else 0


# ════════════════════════════════════════════════════════════════════════════
# Commission calculation
# ════════════════════════════════════════════════════════════════════════════

async def compute_commission(
    sale_amount: float,
    client_type: str,
    agent_id: str,
    sales_count_agent: int,
    db: AsyncSession,
) -> dict[str, Any]:
    """Compute agent/agency commission on a sale.

    Rules:
      - Cash client → 1% base
      - Credit client → 0.5% base
      - Progressive: base 0.5% + bonus capped 1.5%
      - Split: 50% agent / 25% agency / 25% reserve
      - Performance bonus: capped 3%
    """
    amount = Decimal(str(sale_amount))
    client_t = client_type.upper()

    # Base rate
    if client_t == "CASH":
        base_rate = Decimal("0.01")  # 1%
    else:
        base_rate = Decimal("0.005")  # 0.5%

    base_commission = (amount * base_rate).quantize(Q2, ROUND_HALF_UP)

    # Progressive bonus
    progressive_base = Decimal("0.005")  # 0.5%
    bonus_rate = Decimal("0")
    if sales_count_agent >= 5:
        bonus_rate = Decimal("0.003")  # 0.3%
    if sales_count_agent >= 10:
        bonus_rate = Decimal("0.007")  # 0.7%
    if sales_count_agent >= 20:
        bonus_rate = Decimal("0.01")   # 1%

    # Cap bonus at 1.5%
    bonus_cap = Decimal("0.015")
    if bonus_rate > bonus_cap:
        bonus_rate = bonus_cap

    progressive_commission = (amount * (progressive_base + bonus_rate)).quantize(Q2, ROUND_HALF_UP)
    total_commission = base_commission + progressive_commission

    # Performance bonus (capped 3% of sale)
    performance_cap = (amount * Decimal("0.03")).quantize(Q2, ROUND_HALF_UP)
    if total_commission > performance_cap:
        total_commission = performance_cap

    # Split
    agent_share = (total_commission * Decimal("0.50")).quantize(Q2, ROUND_HALF_UP)
    agency_share = (total_commission * Decimal("0.25")).quantize(Q2, ROUND_HALF_UP)
    reserve_share = total_commission - agent_share - agency_share  # remainder

    return {
        "sale_amount": float(amount),
        "client_type": client_t,
        "base_rate": float(base_rate),
        "base_commission": float(base_commission),
        "progressive_rate": float(progressive_base + bonus_rate),
        "progressive_commission": float(progressive_commission),
        "total_commission": float(total_commission),
        "performance_cap": float(performance_cap),
        "split": {
            "agent": float(agent_share),
            "agency": float(agency_share),
            "reserve": float(reserve_share),
        },
        "agent_id": agent_id,
        "sales_count": sales_count_agent,
    }
