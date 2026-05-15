"""GFI Platform – SPI (Score de Performance Intégré) API router.

Endpoints for:
  - SPI score computation (daily/monthly/batch)
  - SPI rules management (CRUD)
  - Bonus/malus rules
  - SPI dashboard data
  - KPI management
  - Payroll with SPI integration
  - Validation agents
"""
from __future__ import annotations

from typing import Optional
from datetime import date, datetime

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.core import User, AuditLog
from app.models.hr import Employee
from app.models.spi import (
    SPIScore, SPIScorePeriod, SPIRule, SPIKpi, SPIBonusMalusRule,
    SPICategory, BonusMalusType, FunctionCategory,
    RemunerationBareme, Department, HierarchyRelation,
    OwnershipRelation,
)
from app.models.planification import SPIMensuel, AlerteRH
from app.auth.dependencies import get_current_user, require_role
from app.services.spi_engine import compute_commission
from app.agents.spi_agents import (
    hr_consistency_agent, org_hierarchy_agent,
    spi_computation_agent, payroll_proposal_agent,
)

router = APIRouter(tags=["SPI"])


# ── Request/Response schemas ────────────────────────────────────────────────

class SPIComputeRequest(BaseModel):
    target_date: Optional[date] = None
    employee_id: Optional[str] = None
    period_type: str = "MONTHLY"  # GFI v7: monthly SPI is primary


class SPIRuleCreate(BaseModel):
    role_code: str
    role_label: str
    function_category: str = "SUPPORT"
    weight_planification: float = 30
    weight_qualite: float = 25
    weight_comportement: float = 25
    weight_performance: float = 20
    criteria_planification: list[dict] = []
    criteria_qualite: list[dict] = []
    criteria_comportement: list[dict] = []
    criteria_performance: list[dict] = []
    commission_cash_pct: float = 0
    commission_credit_pct: float = 0
    task_points_per_completion: float = 10
    inactivity_penalty_per_day: float = 10
    absence_penalty_per_day: float = 5


class BonusMalusRuleCreate(BaseModel):
    rule_type: str  # BONUS | MALUS
    label: str
    spi_min: Optional[float] = None
    spi_max: Optional[float] = None
    consecutive_months: int = 1
    salary_adjustment_pct: float
    triggers_hr_alert: bool = False
    triggers_termination: bool = False
    triggers_salary_freeze: bool = False


class KPICreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    category: str  # PLANIFICATION | QUALITE_EXECUTION | COMPORTEMENT | PERFORMANCE_METIER
    target_value: Optional[float] = None
    unit: str = "points"
    weight: float = 1.0
    applicable_roles: list[str] = []


class CommissionRequest(BaseModel):
    sale_amount: float
    is_cash: bool = True


class PayrollSPIRequest(BaseModel):
    period_label: str
    employee_ids: Optional[list[str]] = None


class DepartmentCreate(BaseModel):
    code: str
    name: str
    parent_id: Optional[str] = None
    description: Optional[str] = None


class HierarchyCreate(BaseModel):
    manager_id: str
    subordinate_id: str
    relation_type: str = "direct"


# ── SPI Score Endpoints ─────────────────────────────────────────────────────

@router.post("/compute", status_code=status.HTTP_201_CREATED)
async def compute_spi(
    body: SPIComputeRequest,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Trigger SPI computation for an employee or batch."""
    result = await spi_computation_agent(
        db, user.tenant_id,
        target_date=body.target_date or date.today(),
        employee_id=body.employee_id,
    )

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="spi_compute",
        entity_type="spi_score",
    ))
    await db.commit()
    return result


@router.get("/scores")
async def list_spi_scores(
    employee_id: Optional[str] = Query(None),
    mois: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List SPI scores (GFI v7 SPIMensuel records)."""
    query = select(SPIMensuel).where(SPIMensuel.tenant_id == user.tenant_id)
    if employee_id:
        query = query.where(SPIMensuel.employe_id == employee_id)
    if mois:
        query = query.where(SPIMensuel.mois == mois)

    query = query.order_by(SPIMensuel.mois.desc()).limit(limit)
    result = await db.execute(query)
    scores = result.scalars().all()

    # Get employee names
    emp_ids = list(set(s.employe_id for s in scores))
    emp_result = await db.execute(select(Employee).where(Employee.id.in_(emp_ids))) if emp_ids else None
    emp_map = {e.id: e for e in emp_result.scalars().all()} if emp_result else {}

    return [
        {
            "id": s.id,
            "employee_id": s.employe_id,
            "employee_name": f"{emp_map[s.employe_id].first_name} {emp_map[s.employe_id].last_name}" if s.employe_id in emp_map else None,
            "department": emp_map[s.employe_id].department if s.employe_id in emp_map else None,
            "mois": s.mois,
            "c1_execution": float(s.c1_execution or 0),
            "c2_qualite": float(s.c2_qualite or 0),
            "c3_comportement": float(s.c3_comportement or 0),
            "c4_metier": float(s.c4_metier or 0),
            "w1": float(s.w1 or 30),
            "w2": float(s.w2 or 25),
            "w3": float(s.w3 or 25),
            "w4": float(s.w4 or 20),
            "score_spi": float(s.score_spi or 0),
            "fiabilite_score": float(s.fiabilite_score or 0),
            "prime_calculee": float(s.prime_calculee or 0),
            "solde_bm_mois": float(s.solde_bm_mois or 0),
            "taches_total": s.taches_total or 0,
            "taches_validees": s.taches_validees or 0,
            "taches_rejetees": s.taches_rejetees or 0,
            "est_confirme": s.est_confirme if hasattr(s, 'est_confirme') else False,
        }
        for s in scores
    ]


@router.get("/scores/{score_id}")
async def get_spi_score(
    score_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed SPI score by ID (GFI v7 SPIMensuel)."""
    result = await db.execute(
        select(SPIMensuel).where(SPIMensuel.id == score_id, SPIMensuel.tenant_id == user.tenant_id)
    )
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=404, detail="SPI score not found")

    emp_result = await db.execute(select(Employee).where(Employee.id == score.employe_id))
    emp = emp_result.scalar_one_or_none()

    return {
        "id": score.id,
        "employee_id": score.employe_id,
        "employee_name": f"{emp.first_name} {emp.last_name}" if emp else None,
        "mois": score.mois,
        "c1_execution": float(score.c1_execution or 0),
        "c2_qualite": float(score.c2_qualite or 0),
        "c3_comportement": float(score.c3_comportement or 0),
        "c4_metier": float(score.c4_metier or 0),
        "w1": float(score.w1 or 30),
        "w2": float(score.w2 or 25),
        "w3": float(score.w3 or 25),
        "w4": float(score.w4 or 20),
        "score_spi": float(score.score_spi or 0),
        "fiabilite_score": float(score.fiabilite_score or 0),
        "prime_calculee": float(score.prime_calculee or 0),
        "malus_calcule": float(score.malus_calcule or 0),
        "solde_bm_mois": float(score.solde_bm_mois or 0),
        "commission_mois": float(score.commission_mois or 0),
        "prime_plan": float(score.prime_plan or 0),
        "taches_total": score.taches_total or 0,
        "taches_validees": score.taches_validees or 0,
        "taches_rejetees": score.taches_rejetees or 0,
        "taches_en_retard": score.taches_en_retard or 0,
        "est_confirme": getattr(score, 'est_confirme', False),
        "details": score.details,
    }


@router.post("/scores/{score_id}/validate")
async def validate_spi_score(
    score_id: str,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Manager confirms/validates a monthly SPI score."""
    result = await db.execute(
        select(SPIMensuel).where(SPIMensuel.id == score_id, SPIMensuel.tenant_id == user.tenant_id)
    )
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=404, detail="SPI score not found")

    score.est_confirme = True
    score.valide_par_manager = True
    score.valideur_id = user.id
    score.date_validation = datetime.utcnow()
    await db.commit()
    return {"id": score.id, "est_confirme": True}


# ── SPI Dashboard ───────────────────────────────────────────────────────────

@router.get("/dashboard")
async def spi_dashboard(
    mois: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SPI dashboard overview (GFI v7): averages, top/low performers, alerts."""
    target_mois = mois or date.today().strftime("%Y-%m")

    # Get monthly SPI scores
    score_result = await db.execute(
        select(SPIMensuel).where(
            SPIMensuel.tenant_id == user.tenant_id,
            SPIMensuel.mois == target_mois,
        ).order_by(SPIMensuel.score_spi.desc())
    )
    scores = score_result.scalars().all()

    if not scores:
        return {
            "mois": target_mois,
            "total_employees": 0,
            "average_spi": 0,
            "top_performers": [],
            "low_performers": [],
            "alerts": [],
            "distribution": {},
        }

    # Employee map
    emp_ids = [s.employe_id for s in scores]
    emp_result = await db.execute(select(Employee).where(Employee.id.in_(emp_ids)))
    emp_map = {e.id: e for e in emp_result.scalars().all()}

    evaluated_scores = [s for s in scores if (s.taches_total or 0) > 0]
    avg_source = evaluated_scores or scores
    avg_spi = sum(float(s.score_spi) for s in avg_source) / len(avg_source)
    top = sorted(
        [s for s in scores if (s.taches_total or 0) > 0],
        key=lambda s: float(s.score_spi), reverse=True,
    )[:5]
    low = sorted(
        [s for s in scores if (s.taches_total or 0) > 0 and float(s.score_spi) < 70],
        key=lambda s: float(s.score_spi),
    )[:5]

    # Alerts from AlerteRH
    alert_result = await db.execute(
        select(AlerteRH).where(
            AlerteRH.tenant_id == user.tenant_id,
            AlerteRH.mois_reference == target_mois,
        )
    )
    db_alerts = alert_result.scalars().all()
    alerts = [
        {
            "type": a.severite or "WARNING",
            "alerte_type": a.type_alerte.value if a.type_alerte else None,
            "message": a.message,
            "employee_id": a.employe_id,
        }
        for a in db_alerts
    ]

    # Distribution buckets
    dist = {"0-29": 0, "30-49": 0, "50-69": 0, "70-89": 0, "90-100": 0}
    for s in evaluated_scores:
        spi = float(s.score_spi)
        if spi < 30:
            dist["0-29"] += 1
        elif spi < 50:
            dist["30-49"] += 1
        elif spi < 70:
            dist["50-69"] += 1
        elif spi < 90:
            dist["70-89"] += 1
        else:
            dist["90-100"] += 1

    def _score_item(s):
        emp = emp_map.get(s.employe_id)
        return {
            "employee_id": s.employe_id,
            "employee_name": f"{emp.first_name} {emp.last_name}" if emp else None,
            "score_spi": float(s.score_spi),
            "c1": float(s.c1_execution or 0),
            "c2": float(s.c2_qualite or 0),
            "c3": float(s.c3_comportement or 0),
            "c4": float(s.c4_metier or 0),
            "fiabilite": float(s.fiabilite_score or 0),
            "department": emp.department if emp else None,
        }

    return {
        "mois": target_mois,
        "total_employees": len(scores),
        "average_spi": round(avg_spi, 2),
        "top_performers": [_score_item(s) for s in top],
        "low_performers": [_score_item(s) for s in low],
        "alerts": alerts,
        "distribution": dist,
    }


# ── SPI Rules CRUD ──────────────────────────────────────────────────────────

@router.post("/rules", status_code=status.HTTP_201_CREATED)
async def create_spi_rule(
    body: SPIRuleCreate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create an SPI scoring rule for a role."""
    # Validate weights sum to 100
    total = body.weight_planification + body.weight_qualite + body.weight_comportement + body.weight_performance
    if abs(total - 100) > 0.01:
        raise HTTPException(status_code=400, detail=f"Weights must sum to 100, got {total}")

    rule = SPIRule(
        tenant_id=user.tenant_id,
        role_code=body.role_code,
        role_label=body.role_label,
        function_category=FunctionCategory(body.function_category),
        weight_planification=body.weight_planification,
        weight_qualite=body.weight_qualite,
        weight_comportement=body.weight_comportement,
        weight_performance=body.weight_performance,
        criteria_planification=body.criteria_planification,
        criteria_qualite=body.criteria_qualite,
        criteria_comportement=body.criteria_comportement,
        criteria_performance=body.criteria_performance,
        commission_cash_pct=body.commission_cash_pct,
        commission_credit_pct=body.commission_credit_pct,
        task_points_per_completion=body.task_points_per_completion,
        inactivity_penalty_per_day=body.inactivity_penalty_per_day,
        absence_penalty_per_day=body.absence_penalty_per_day,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {"id": rule.id, "role_code": rule.role_code, "role_label": rule.role_label}


@router.get("/rules")
async def list_spi_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all SPI rules."""
    result = await db.execute(
        select(SPIRule).where(SPIRule.tenant_id == user.tenant_id, SPIRule.is_active == True)
        .order_by(SPIRule.role_code)
    )
    rules = result.scalars().all()
    return [
        {
            "id": r.id,
            "role_code": r.role_code,
            "role_label": r.role_label,
            "function_category": r.function_category.value if r.function_category else None,
            "weight_planification": float(r.weight_planification),
            "weight_qualite": float(r.weight_qualite),
            "weight_comportement": float(r.weight_comportement),
            "weight_performance": float(r.weight_performance),
            "commission_cash_pct": float(r.commission_cash_pct or 0),
            "commission_credit_pct": float(r.commission_credit_pct or 0),
            "version": r.version,
        }
        for r in rules
    ]


# ── Bonus/Malus Rules ──────────────────────────────────────────────────────

@router.post("/bonus-malus-rules", status_code=status.HTTP_201_CREATED)
async def create_bonus_malus_rule(
    body: BonusMalusRuleCreate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a bonus/malus threshold rule."""
    rule = SPIBonusMalusRule(
        tenant_id=user.tenant_id,
        rule_type=BonusMalusType(body.rule_type),
        label=body.label,
        spi_min=body.spi_min,
        spi_max=body.spi_max,
        consecutive_months=body.consecutive_months,
        salary_adjustment_pct=body.salary_adjustment_pct,
        triggers_hr_alert=body.triggers_hr_alert,
        triggers_termination=body.triggers_termination,
        triggers_salary_freeze=body.triggers_salary_freeze,
    )
    db.add(rule)
    await db.commit()
    return {"id": rule.id, "label": rule.label}


@router.get("/bonus-malus-rules")
async def list_bonus_malus_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List bonus/malus rules."""
    result = await db.execute(
        select(SPIBonusMalusRule).where(
            SPIBonusMalusRule.tenant_id == user.tenant_id,
            SPIBonusMalusRule.is_active == True,
        ).order_by(SPIBonusMalusRule.sort_order)
    )
    rules = result.scalars().all()
    return [
        {
            "id": r.id,
            "rule_type": r.rule_type.value,
            "label": r.label,
            "spi_min": float(r.spi_min) if r.spi_min else None,
            "spi_max": float(r.spi_max) if r.spi_max else None,
            "consecutive_months": r.consecutive_months,
            "salary_adjustment_pct": float(r.salary_adjustment_pct),
            "triggers_hr_alert": r.triggers_hr_alert,
            "triggers_termination": r.triggers_termination,
        }
        for r in rules
    ]


# ── KPIs ────────────────────────────────────────────────────────────────────

@router.post("/kpis", status_code=status.HTTP_201_CREATED)
async def create_kpi(
    body: KPICreate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a KPI definition."""
    kpi = SPIKpi(
        tenant_id=user.tenant_id,
        code=body.code,
        name=body.name,
        description=body.description,
        category=SPICategory(body.category),
        target_value=body.target_value,
        unit=body.unit,
        weight=body.weight,
        applicable_roles=body.applicable_roles,
    )
    db.add(kpi)
    await db.commit()
    return {"id": kpi.id, "code": kpi.code, "name": kpi.name}


@router.get("/kpis")
async def list_kpis(
    category: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List KPI definitions."""
    query = select(SPIKpi).where(SPIKpi.tenant_id == user.tenant_id, SPIKpi.is_active == True)
    if category:
        query = query.where(SPIKpi.category == SPICategory(category))
    result = await db.execute(query.order_by(SPIKpi.category, SPIKpi.code))
    kpis = result.scalars().all()
    return [
        {
            "id": k.id,
            "code": k.code,
            "name": k.name,
            "description": k.description,
            "category": k.category.value,
            "target_value": float(k.target_value) if k.target_value else None,
            "unit": k.unit,
            "weight": float(k.weight),
            "applicable_roles": k.applicable_roles,
        }
        for k in kpis
    ]


# ── Commissions ─────────────────────────────────────────────────────────────

@router.post("/commissions/calculate")
async def calculate_commission(
    body: CommissionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Calculate sales commission with split."""
    return compute_commission(body.sale_amount, body.is_cash)


# ── Payroll with SPI ────────────────────────────────────────────────────────

@router.post("/payroll/generate-with-spi")
async def generate_payroll_with_spi(
    body: PayrollSPIRequest,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Generate payroll proposals integrating SPI bonus/malus."""
    result = await payroll_proposal_agent(
        db, user.tenant_id,
        period_label=body.period_label,
        employee_ids=body.employee_ids,
    )

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="payroll_spi_generate",
        entity_type="payroll",
    ))
    await db.commit()
    return result


# ── Validation Agents ───────────────────────────────────────────────────────

@router.get("/validate/hr-consistency")
async def run_hr_consistency(
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Run HR consistency validation agent."""
    return await hr_consistency_agent(db, user.tenant_id)


@router.get("/validate/org-hierarchy")
async def run_org_hierarchy(
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Run organization hierarchy validation agent."""
    return await org_hierarchy_agent(db, user.tenant_id)


# ── Departments ─────────────────────────────────────────────────────────────

@router.post("/departments", status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentCreate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a department."""
    dept = Department(
        tenant_id=user.tenant_id,
        code=body.code,
        name=body.name,
        parent_id=body.parent_id,
        description=body.description,
    )
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    return {"id": dept.id, "code": dept.code, "name": dept.name}


@router.get("/departments")
async def list_departments(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List departments with hierarchy."""
    result = await db.execute(
        select(Department).where(
            Department.tenant_id == user.tenant_id,
            Department.is_active == True,
        ).order_by(Department.sort_order)
    )
    departments = result.scalars().all()

    # Count employees per department
    emp_counts = {}
    if departments:
        for dept in departments:
            count_result = await db.execute(
                select(func.count(Employee.id)).where(Employee.department_id == dept.id)
            )
            emp_counts[dept.id] = count_result.scalar() or 0

    return [
        {
            "id": d.id,
            "code": d.code,
            "name": d.name,
            "parent_id": d.parent_id,
            "description": d.description,
            "employee_count": emp_counts.get(d.id, 0),
        }
        for d in departments
    ]


# ── Hierarchy Relations ─────────────────────────────────────────────────────

@router.post("/hierarchy", status_code=status.HTTP_201_CREATED)
async def create_hierarchy_relation(
    body: HierarchyCreate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a manager-subordinate hierarchy relation."""
    if body.manager_id == body.subordinate_id:
        raise HTTPException(status_code=400, detail="Manager and subordinate cannot be the same")

    rel = HierarchyRelation(
        tenant_id=user.tenant_id,
        manager_id=body.manager_id,
        subordinate_id=body.subordinate_id,
        relation_type=body.relation_type,
    )
    db.add(rel)
    await db.commit()
    return {"id": rel.id}


@router.get("/hierarchy")
async def list_hierarchy(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List hierarchy relations."""
    result = await db.execute(
        select(HierarchyRelation).where(
            HierarchyRelation.tenant_id == user.tenant_id,
            HierarchyRelation.is_active == True,
        )
    )
    relations = result.scalars().all()

    emp_ids = list(set(
        [r.manager_id for r in relations] + [r.subordinate_id for r in relations]
    ))
    emp_result = await db.execute(select(Employee).where(Employee.id.in_(emp_ids))) if emp_ids else None
    emp_map = {e.id: e for e in emp_result.scalars().all()} if emp_result else {}

    return [
        {
            "id": r.id,
            "manager_id": r.manager_id,
            "manager_name": f"{emp_map[r.manager_id].first_name} {emp_map[r.manager_id].last_name}" if r.manager_id in emp_map else None,
            "subordinate_id": r.subordinate_id,
            "subordinate_name": f"{emp_map[r.subordinate_id].first_name} {emp_map[r.subordinate_id].last_name}" if r.subordinate_id in emp_map else None,
            "relation_type": r.relation_type,
        }
        for r in relations
    ]


# ── Seed Import ─────────────────────────────────────────────────────────────

@router.post("/seed", status_code=status.HTTP_201_CREATED)
async def run_seed_import(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Run full seed import from Markdown data sources (admin only)."""
    from app.services.seed_import import run_full_seed
    summary = await run_full_seed(db, user.tenant_id)
    return {"status": "ok", "summary": summary}

# ── Ownership Relations ─────────────────────────────────────────────────────

@router.get("/ownership")
async def list_ownership_relations(
    entreprise_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List company-shareholder ownership relations."""
    query = select(OwnershipRelation).where(
        OwnershipRelation.tenant_id == user.tenant_id,
        OwnershipRelation.is_active == True,
    )
    if entreprise_id:
        query = query.where(OwnershipRelation.entreprise_id == entreprise_id)

    result = await db.execute(query)
    relations = result.scalars().all()
    return [
        {
            "id": r.id,
            "entreprise_id": r.entreprise_id,
            "projet_id": r.projet_id,
            "shareholder_name": r.shareholder_name,
            "ownership_pct": float(r.ownership_pct),
            "status": r.status,
        }
        for r in relations
    ]
