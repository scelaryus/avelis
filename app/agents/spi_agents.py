"""GFI Platform – SPI AI Agents (GFI v7.0 integration).

Four specialised agents using the shared LangGraph runtime:
  1. HRConsistencyAgent    – validates employee hierarchy + SPI readiness
  2. OrgHierarchyAgent     – validates organization structure
  3. SPIComputationAgent   – computes monthly SPI via GFI v7 engine (SPIMensuel)
  4. PayrollProposalAgent  – generates payroll proposals using compute_paie_employe
"""
from __future__ import annotations

import uuid
import structlog
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hr import Employee, PayrollProposal, EmploymentStatus, PayrollStatus
from app.models.spi import (
    Department, HierarchyRelation,
)
from app.models.planification import (
    SPIMensuel, TacheSPI, StatutTache, AlerteRH,
)
from app.services.spi_engine import (
    compute_spi_mensuel, compute_spi_batch_mensuel,
    compute_paie_employe, check_sous_performance,
    validate_employee_hierarchy, validate_shareholder_percentages,
)

logger = structlog.get_logger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# 1. HR Consistency Agent
# ────────────────────────────────────────────────────────────────────────────

async def hr_consistency_agent(
    db: AsyncSession,
    tenant_id: str,
) -> dict[str, Any]:
    """Validate employee hierarchy, data consistency, and SPI readiness.

    Checks:
      - Every employee must belong to a department
      - Employee manager must exist and be active
      - No circular management chains
      - SPI readiness: avenant_spi_signe, prime_spi_plafond set
      - No orphan hierarchy relations
    """
    errors: list[dict] = []
    warnings: list[dict] = []

    # 1. Basic hierarchy validation
    hierarchy_errors = await validate_employee_hierarchy(db, tenant_id)
    errors.extend(hierarchy_errors)

    # 2. Department assignment + SPI readiness check
    result = await db.execute(
        select(Employee).where(
            Employee.tenant_id == tenant_id,
            Employee.status == EmploymentStatus.ACTIVE,
        )
    )
    employees = result.scalars().all()

    spi_ready_count = 0
    for emp in employees:
        if not emp.department and not emp.department_id:
            warnings.append({
                "code": "NO_DEPARTMENT",
                "employee_id": emp.id,
                "message": f"{emp.first_name} {emp.last_name} has no department assigned",
            })

        if not emp.position:
            warnings.append({
                "code": "NO_POSITION",
                "employee_id": emp.id,
                "message": f"{emp.first_name} {emp.last_name} has no position defined",
            })

        # GFI v7: SPI readiness checks
        if not getattr(emp, 'avenant_spi_signe', False):
            warnings.append({
                "code": "NO_AVENANT_SPI",
                "employee_id": emp.id,
                "message": f"{emp.first_name} {emp.last_name} — avenant SPI non signé, prime SPI ne sera pas comptabilisée",
            })
        elif not getattr(emp, 'prime_spi_plafond', None) or float(emp.prime_spi_plafond or 0) <= 0:
            warnings.append({
                "code": "NO_PRIME_PLAFOND",
                "employee_id": emp.id,
                "message": f"{emp.first_name} {emp.last_name} — prime SPI plafond non défini (avenant signé mais plafond = 0)",
            })
        else:
            spi_ready_count += 1

    # 3. Check hierarchy relations consistency
    hr_result = await db.execute(
        select(HierarchyRelation).where(
            HierarchyRelation.tenant_id == tenant_id,
            HierarchyRelation.is_active == True,
        )
    )
    relations = hr_result.scalars().all()
    emp_ids = {e.id for e in employees}

    for rel in relations:
        if rel.manager_id not in emp_ids:
            errors.append({
                "code": "ORPHAN_MANAGER_RELATION",
                "message": f"Hierarchy relation {rel.id} references non-existent manager {rel.manager_id}",
            })
        if rel.subordinate_id not in emp_ids:
            errors.append({
                "code": "ORPHAN_SUBORDINATE_RELATION",
                "message": f"Hierarchy relation {rel.id} references non-existent subordinate {rel.subordinate_id}",
            })

    status = "OK" if not errors else "ISSUES_FOUND"
    logger.info("hr_consistency_check", status=status, errors=len(errors), warnings=len(warnings))

    return {
        "agent": "HRConsistencyAgent",
        "status": status,
        "total_employees": len(employees),
        "spi_ready_employees": spi_ready_count,
        "total_relations": len(relations),
        "errors": errors,
        "warnings": warnings,
        "checked_at": datetime.utcnow().isoformat(),
    }


# ────────────────────────────────────────────────────────────────────────────
# 2. Org Hierarchy Agent
# ────────────────────────────────────────────────────────────────────────────

async def org_hierarchy_agent(
    db: AsyncSession,
    tenant_id: str,
) -> dict[str, Any]:
    """Validate organization structure integrity.

    Checks:
      - Department tree is acyclic (no circular parent refs)
      - Every department has at least one employee
      - Shareholder percentages must be coherent (<=100% per company)
      - Projects must belong to a valid company
    """
    errors: list[dict] = []
    warnings: list[dict] = []

    # 1. Department tree validation
    dept_result = await db.execute(
        select(Department).where(
            Department.tenant_id == tenant_id,
            Department.is_active == True,
        )
    )
    departments = dept_result.scalars().all()
    dept_map = {d.id: d for d in departments}

    for dept in departments:
        visited = set()
        current = dept
        while current and current.parent_id:
            if current.parent_id in visited:
                errors.append({
                    "code": "CIRCULAR_DEPARTMENT",
                    "department_id": dept.id,
                    "message": f"Department {dept.name} has circular parent reference",
                })
                break
            visited.add(current.id)
            current = dept_map.get(current.parent_id)

    # 2. Employees per department
    emp_result = await db.execute(
        select(Employee.department_id, func.count(Employee.id).label("cnt")).where(
            Employee.tenant_id == tenant_id,
            Employee.status == EmploymentStatus.ACTIVE,
            Employee.department_id != None,
        ).group_by(Employee.department_id)
    )
    dept_counts = {row.department_id: row.cnt for row in emp_result.all()}

    for dept in departments:
        if dept.id not in dept_counts:
            warnings.append({
                "code": "EMPTY_DEPARTMENT",
                "department_id": dept.id,
                "message": f"Department {dept.name} has no active employees",
            })

    # 3. Shareholder validation
    ownership_errors = await validate_shareholder_percentages(db, tenant_id)
    errors.extend(ownership_errors)

    # 4. Project-company validation
    from app.models.financial import Projet, Entreprise
    proj_result = await db.execute(
        select(Projet).where(Projet.tenant_id == tenant_id, Projet.is_active == True)
    )
    projects = proj_result.scalars().all()

    ent_result = await db.execute(
        select(Entreprise.id).where(Entreprise.tenant_id == tenant_id)
    )
    ent_ids = {row[0] for row in ent_result.all()}

    for proj in projects:
        if proj.entreprise_id not in ent_ids:
            errors.append({
                "code": "INVALID_PROJECT_COMPANY",
                "projet_id": proj.id,
                "message": f"Project {proj.nom} references non-existent company",
            })

    status = "OK" if not errors else "ISSUES_FOUND"
    logger.info("org_hierarchy_check", status=status, departments=len(departments), errors=len(errors))

    return {
        "agent": "OrgHierarchyAgent",
        "status": status,
        "total_departments": len(departments),
        "total_projects": len(projects),
        "errors": errors,
        "warnings": warnings,
        "checked_at": datetime.utcnow().isoformat(),
    }


# ────────────────────────────────────────────────────────────────────────────
# 3. SPI Computation Agent (GFI v7 — uses SPIMensuel)
# ────────────────────────────────────────────────────────────────────────────

async def spi_computation_agent(
    db: AsyncSession,
    tenant_id: str,
    target_date: Optional[date] = None,
    employee_id: Optional[str] = None,
) -> dict[str, Any]:
    """Compute monthly SPI scores using the GFI v7 engine.

    Uses compute_spi_mensuel (SPIMensuel model) with:
      - 4 components (C1-C4) with adaptive role weights
      - Fiabilité (reliability) scoring
      - Bonus/malus from OffrePerformance
      - 8 protection mechanisms (garde-fous)

    Optionally enhances with AI analysis for insights.
    """
    if target_date is None:
        target_date = date.today()

    mois = target_date.strftime("%Y-%m")
    scores_created: list[dict] = []

    if employee_id:
        # Single employee
        emp_result = await db.execute(
            select(Employee).where(Employee.id == employee_id, Employee.tenant_id == tenant_id)
        )
        emp = emp_result.scalar_one_or_none()
        if not emp:
            return {"agent": "SPIComputationAgent", "status": "ERROR", "message": "Employee not found"}

        # Check if already computed
        existing = await db.execute(
            select(SPIMensuel).where(
                SPIMensuel.employe_id == emp.id,
                SPIMensuel.mois == mois,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return {"agent": "SPIComputationAgent", "status": "ALREADY_COMPUTED",
                    "message": f"SPI for {mois} already exists for this employee"}

        spi = await compute_spi_mensuel(db, emp, mois)
        db.add(spi)
        await db.flush()
        scores_created.append(_serialize_spi_mensuel(spi, emp))
    else:
        # Batch all active employees
        spis = await compute_spi_batch_mensuel(db, tenant_id, mois)
        # Fetch employee data for serialization
        emp_ids = [s.employe_id for s in spis]
        if emp_ids:
            emp_result = await db.execute(select(Employee).where(Employee.id.in_(emp_ids)))
            emp_map = {e.id: e for e in emp_result.scalars().all()}
        else:
            emp_map = {}
        scores_created = [_serialize_spi_mensuel(s, emp_map.get(s.employe_id)) for s in spis]

    # Run sub-performance checks and create alerts
    alerts = await check_sous_performance(db, tenant_id, mois)

    # AI-enhanced analysis
    ai_analysis = None
    try:
        ai_analysis = await _ai_analyze_spi(scores_created)
    except Exception:
        logger.warning("spi_ai_analysis_skipped", reason="LLM unavailable")

    return {
        "agent": "SPIComputationAgent",
        "status": "OK",
        "mois": mois,
        "scores_computed": len(scores_created),
        "scores": scores_created,
        "alerts_generated": alerts,
        "ai_analysis": ai_analysis,
        "computed_at": datetime.utcnow().isoformat(),
    }


# ────────────────────────────────────────────────────────────────────────────
# 4. Payroll Proposal Agent (GFI v7 — uses compute_paie_employe)
# ────────────────────────────────────────────────────────────────────────────

async def payroll_proposal_agent(
    db: AsyncSession,
    tenant_id: str,
    period_label: str,
    employee_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Generate payroll proposals using GFI v7 formula.

    For each employee:
      NET = base_cnas (INTANGIBLE)
            + prime_SPI (from score)
            + solde_bonus_malus (from OffrePerformance)
            + commission (commercial only)
            + prime_plan (5% if validated plan)
            - CNAS salarial (9%)
            - IRG (progressive brackets)
    """
    query = select(Employee).where(
        Employee.tenant_id == tenant_id,
        Employee.status == EmploymentStatus.ACTIVE,
    )
    if employee_ids:
        query = query.where(Employee.id.in_(employee_ids))

    result = await db.execute(query)
    employees = result.scalars().all()

    if not employees:
        return {"agent": "PayrollProposalAgent", "status": "ERROR", "message": "No active employees"}

    # period_label is "YYYY-MM" format
    mois = period_label

    proposals = []
    for emp in employees:
        # Use GFI v7 payroll computation
        payroll = await compute_paie_employe(db, emp, mois)

        # Create PayrollProposal record
        proposal = PayrollProposal(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            employee_id=emp.id,
            period_label=period_label,
            status=PayrollStatus.PROPOSED,
            gross_salary=Decimal(str(payroll["brut"])),
            net_salary=Decimal(str(payroll["net"])),
            deductions={
                "cnas_salarial": payroll["cnas_salarial"],
                "cnas_patronal": payroll["cnas_patronal"],
                "irg": payroll["irg"],
            },
            contributions={
                "prime_spi": payroll["prime_spi"],
                "versement_bm": payroll["versement_bm"],
                "commission": payroll["commission"],
                "prime_plan": payroll["prime_plan"],
            },
            notes=f"SPI: {payroll['score_spi']} | Prime: {payroll['prime_spi']} DA | B/M: {payroll['versement_bm']} DA",
        )
        db.add(proposal)
        proposals.append({
            "employee_id": emp.id,
            "employee_name": payroll["employe_nom"],
            "proposal_id": proposal.id,
            **payroll,
        })

    await db.flush()

    logger.info("payroll_proposals_generated", count=len(proposals), period=period_label)

    return {
        "agent": "PayrollProposalAgent",
        "status": "OK",
        "period_label": period_label,
        "proposals_generated": len(proposals),
        "total_masse_salariale": round(sum(p["brut"] for p in proposals), 2),
        "total_cout_employeur": round(sum(p["cout_employeur"] for p in proposals), 2),
        "proposals": proposals,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ── Private helpers ─────────────────────────────────────────────────────────

def _serialize_spi_mensuel(spi: SPIMensuel, emp: Optional[Employee] = None) -> dict:
    """Serialize an SPIMensuel record for agent output."""
    return {
        "id": spi.id,
        "employe_id": spi.employe_id,
        "employe_nom": f"{emp.first_name} {emp.last_name}" if emp else None,
        "mois": spi.mois,
        "c1_execution": float(spi.c1_execution or 0),
        "c2_qualite": float(spi.c2_qualite or 0),
        "c3_comportement": float(spi.c3_comportement or 0),
        "c4_metier": float(spi.c4_metier or 0),
        "w1": float(spi.w1 or 30),
        "w2": float(spi.w2 or 25),
        "w3": float(spi.w3 or 25),
        "w4": float(spi.w4 or 20),
        "score_spi": float(spi.score_spi or 0),
        "fiabilite_score": float(spi.fiabilite_score or 0),
        "prime_calculee": float(spi.prime_calculee or 0),
        "solde_bm_mois": float(spi.solde_bm_mois or 0),
        "commission_mois": float(spi.commission_mois or 0),
        "prime_plan": float(spi.prime_plan or 0),
        "taches_total": spi.taches_total or 0,
        "taches_validees": spi.taches_validees or 0,
        "taches_rejetees": spi.taches_rejetees or 0,
        "taches_en_retard": spi.taches_en_retard or 0,
    }


async def _ai_analyze_spi(scores: list[dict]) -> Optional[dict]:
    """Use LangGraph AI to analyze SPI scores and provide insights."""
    if not scores:
        return None

    try:
        from app.services.llm_graph import invoke_json_agent

        top_performers = sorted(scores, key=lambda s: s["score_spi"], reverse=True)[:5]
        low_performers = sorted(scores, key=lambda s: s["score_spi"])[:5]

        # Build richer context with GFI v7 component data
        prompt = (
            "Analyze these monthly SPI (Score de Performance Intégré) scores and provide insights.\n"
            f"Total employees scored: {len(scores)}\n"
            f"Average SPI: {sum(s['score_spi'] for s in scores) / max(len(scores), 1):.1f}\n\n"
            f"Top performers:\n{_format_spi_list(top_performers)}\n\n"
            f"Low performers:\n{_format_spi_list(low_performers)}\n\n"
            "GFI v7 SPI Components: C1=Execution/Planning, C2=Quality, C3=Behavior, C4=Business KPI\n"
            "Fiabilité < 70% means the SPI is not reliable for that employee.\n\n"
            "Provide:\n"
            "- overall_assessment: brief summary of the team's performance health\n"
            "- component_analysis: which components are weakest across the team\n"
            "- risk_alerts: list of specific risks (e.g., employees near SPI < 50 threshold)\n"
            "- recommendations: actionable suggestions for HR/management"
        )

        result = await invoke_json_agent(
            system_prompt=(
                "You are an HR performance analyst specializing in the GFI v7 SPI system. "
                "Return JSON with keys: overall_assessment, component_analysis, risk_alerts (list), recommendations (list)."
            ),
            user_prompt=prompt,
            temperature=0.2,
        )
        return result.get("parsed_json")
    except Exception:
        return None


def _format_spi_list(scores: list[dict]) -> str:
    """Format SPI scores for AI prompt."""
    lines = []
    for s in scores:
        name = s.get("employe_nom") or s.get("employe_id", "?")
        lines.append(
            f"  - {name}: SPI={s['score_spi']}, "
            f"C1={s['c1_execution']}, C2={s['c2_qualite']}, "
            f"C3={s['c3_comportement']}, C4={s['c4_metier']}, "
            f"fiabilité={s['fiabilite_score']}%"
        )
    return "\n".join(lines)
