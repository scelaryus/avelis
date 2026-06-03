"""
GFI v7.0 — Project + Construction Site Management Engine.

Advancement tracking drives credit disbursement eligibility.
Work situation validation feeds CC2 in cost center.

Core API:
  record_advancement(task_id, new_pct, ...) -> TaskAdvancement + tier check
  validate_work_situation(situation_id, ...) -> CC2 + accounting
  get_project_advancement(project_id) -> overall % + per-task breakdown
  check_tier_eligibility(project_id) -> which credit tiers are unlocked
  score_subcontractor(contract_id, ...) -> updated performance score
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func as sqfunc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# Tier thresholds: when project advancement crosses these, tiers unlock
TIER_THRESHOLDS = {
    Decimal("30"):  "TIER_15PCT",   # 30% completion -> 15% disbursement
    Decimal("65"):  "TIER_35PCT",   # 65% -> 35%
    Decimal("90"):  "TIER_25PCT",   # 90% -> 25%
}


def record_advancement(
    session: Session,
    *,
    task_id: UUID,
    company_id: UUID,
    new_pct: Decimal,
    observations: str | None = None,
    photo_urls: list[str] | None = None,
    recorded_by: UUID | None = None,
) -> object:
    """
    Record task advancement. Checks if a tier threshold is crossed.
    Updates project overall advancement.
    """
    from app.models.project_management import ProjectTask, TaskAdvancement

    task = session.get(ProjectTask, task_id)
    if task is None:
        raise ValueError(f"ProjectTask {task_id} not found.")

    new_pct = Decimal(str(new_pct))
    prev_pct = Decimal(str(task.completion_pct))

    # Check for tier threshold crossing
    tier_triggered = None
    for threshold, tier_label in TIER_THRESHOLDS.items():
        if prev_pct < threshold <= new_pct:
            tier_triggered = tier_label

    adv = TaskAdvancement(
        company_id=company_id,
        task_id=task_id,
        project_id=task.project_id,
        record_date=date.today(),
        previous_pct=prev_pct,
        new_pct=new_pct,
        observations=observations,
        photo_urls=photo_urls,
        recorded_by=recorded_by,
        tier_triggered=tier_triggered,
    )
    session.add(adv)

    # Update task
    task.completion_pct = new_pct
    if new_pct > 0 and task.status == "A_FAIRE":
        task.status = "EN_COURS"
        if not task.actual_start:
            task.actual_start = date.today()
    if new_pct >= Decimal("100"):
        task.status = "TERMINE"
        task.actual_end = date.today()

    session.flush()
    return adv


def validate_work_situation(
    session: Session,
    *,
    situation_id: UUID,
    validated_by: UUID,
) -> object:
    """
    Validate a work situation. Triggers:
    - CC2 imputation (gross amount)
    - CC8 imputation (deductions, if any, with impact_tresorerie=false)
    - Accounting entry (D 612 / C 401)
    """
    from app.models.gaceb import WorkSituation

    sit = session.get(WorkSituation, situation_id)
    if sit is None:
        raise ValueError(f"WorkSituation {situation_id} not found.")

    now = datetime.now(timezone.utc)
    sit.status = "VALIDEE"
    sit.validated_by = validated_by
    sit.validated_at = now

    # CC2: gross construction amount
    from app.cc_category_engine import impute_to_category

    impute_to_category(
        session,
        category="CONSTR",
        company_id=sit.company_id,
        project_id=sit.project_id,
        rf_type="RF1",
        montant=Decimal(str(sit.montant_brut)),
        entry_date=sit.situation_date,
        libelle=f"Situation #{sit.situation_number} {sit.subcontractor_name} (brut)",
        source_type="work_situation",
        source_id=sit.id,
    )

    # CC8: deductions (in-kind, no treasury impact)
    total_deductions = (
        Decimal(str(sit.deduction_avance))
        + Decimal(str(sit.deduction_vehicules))
        + Decimal(str(sit.deduction_appartements))
    )
    if total_deductions > 0:
        impute_to_category(
            session,
            category="COMPENSATION",
            company_id=sit.company_id,
            project_id=sit.project_id,
            rf_type="RF1",
            montant=-total_deductions,  # negative = deduction
            entry_date=sit.situation_date,
            libelle=f"Deductions situation #{sit.situation_number} (avance+vehicules)",
            source_type="work_situation_deduction",
            source_id=sit.id,
        )

    session.flush()
    return sit


def get_project_advancement(
    session: Session,
    project_id: UUID,
) -> dict:
    """Get overall project advancement and per-task breakdown."""
    from app.models.project_management import ProjectTask

    tasks = (
        session.query(ProjectTask)
        .filter(
            ProjectTask.project_id == project_id,
            ProjectTask.is_deleted.is_(False),
        )
        .order_by(ProjectTask.code)
        .all()
    )

    if not tasks:
        return {"project_id": str(project_id), "overall_pct": "0", "tasks": []}

    # Weighted average by budget (or equal weight if no budget)
    total_weight = Decimal("0")
    weighted_sum = Decimal("0")

    task_list = []
    for t in tasks:
        weight = Decimal(str(t.budget_amount)) if t.budget_amount else Decimal("1")
        total_weight += weight
        weighted_sum += weight * Decimal(str(t.completion_pct))

        task_list.append({
            "code": t.code,
            "name": t.name,
            "completion_pct": str(t.completion_pct),
            "status": t.status,
            "budget": str(t.budget_amount) if t.budget_amount else None,
        })

    overall = _r2(weighted_sum / total_weight) if total_weight > 0 else Decimal("0")

    return {
        "project_id": str(project_id),
        "overall_pct": str(overall),
        "task_count": len(tasks),
        "tasks": task_list,
    }


def check_tier_eligibility(
    session: Session,
    project_id: UUID,
) -> list[dict]:
    """Check which credit tiers are unlocked based on project advancement."""
    adv = get_project_advancement(session, project_id)
    overall = Decimal(adv["overall_pct"])

    result = []
    for threshold, tier_label in sorted(TIER_THRESHOLDS.items()):
        result.append({
            "tier": tier_label,
            "threshold_pct": str(threshold),
            "current_pct": str(overall),
            "eligible": overall >= threshold,
        })

    return result


def score_subcontractor(
    session: Session,
    contract_id: UUID,
    quality: int,
    deadlines: int,
    safety: int,
) -> object:
    """Score a subcontractor (0-100 per criterion)."""
    from app.models.project_management import SubcontractorContract

    contract = session.get(SubcontractorContract, contract_id)
    if contract is None:
        raise ValueError(f"SubcontractorContract {contract_id} not found.")

    contract.score_quality = Decimal(str(quality))
    contract.score_deadlines = Decimal(str(deadlines))
    contract.score_safety = Decimal(str(safety))
    contract.score_overall = _r2(
        Decimal(str(quality)) * Decimal("0.40")
        + Decimal(str(deadlines)) * Decimal("0.35")
        + Decimal(str(safety)) * Decimal("0.25")
    )

    # Propagate to supplier if linked
    if contract.supplier_id:
        from app.procurement_engine import update_supplier_score
        update_supplier_score(
            session, contract.supplier_id,
            delivery_quality=quality,
            delay_score=deadlines,
            pricing_score=safety,
        )

    session.flush()
    return contract
