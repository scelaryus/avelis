"""GFI v7.0 — SPI Computation Engine (rebuilt per MODULE_PLANIFICATION_SALAIRE_SPI spec).

Core principles:
  - Contract triggers everything — base CNAS is INTANGIBLE
  - SPI only affects the variable prime (prime_spi_plafond)
  - 4 components: C1 Execution (30%), C2 Quality (25%), C3 Behavior (25%), C4 Business KPI (20%)
  - Weights adapt per role/position
  - Bonus/malus is per-task via OffrePerformance (employee proposes, symmetric)
  - Double verification: system + human
  - 8 protection mechanisms (garde-fous)
  - Monthly SPI drives prime calculation + sub-performance tracking
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hr import Employee, EmploymentStatus
from app.models.spi import SPIRule, SPIScore, SPIScorePeriod
from app.models.planification import (
    TacheSPI, StatutTache, OffrePerformance, StatutOffre, ResultatOffre,
    SPIMensuel, AlerteRH, TypeAlerte, PlanStrategique, StatutPlan,
)

logger = structlog.get_logger(__name__)

# ── Default weights by role ────────────────────────────────────────────────

ROLE_WEIGHTS = {
    "COMMERCIAL": {"c1": 15, "c2": 10, "c3": 10, "c4": 65},
    "TELECONSEILLERE": {"c1": 15, "c2": 10, "c3": 10, "c4": 65},
    "MARKETING": {"c1": 20, "c2": 25, "c3": 20, "c4": 35},
    "CHEF_CHANTIER": {"c1": 40, "c2": 20, "c3": 15, "c4": 25},
    "OPERATIONS_TECH": {"c1": 40, "c2": 20, "c3": 15, "c4": 25},
    "DAF": {"c1": 25, "c2": 35, "c3": 20, "c4": 20},
    "CHARGE_FINANCE": {"c1": 25, "c2": 35, "c3": 20, "c4": 20},
    "RH": {"c1": 20, "c2": 20, "c3": 35, "c4": 25},
    "ARCHIVISTE": {"c1": 20, "c2": 30, "c3": 30, "c4": 20},
    "MAGASINIER": {"c1": 30, "c2": 30, "c3": 20, "c4": 20},
    "ARCHITECTE": {"c1": 25, "c2": 35, "c3": 15, "c4": 25},
    "ACHATS": {"c1": 30, "c2": 25, "c3": 20, "c4": 25},
    "SECURITE": {"c1": 20, "c2": 15, "c3": 40, "c4": 25},
}

DEFAULT_WEIGHTS = {"c1": 30, "c2": 25, "c3": 25, "c4": 20}

# ── Commission rates by payment mode ──────────────────────────────────────

COMMISSION_RATES = {
    "CASH_100": Decimal("1.00"),
    "APPORT_75": Decimal("0.75"),
    "APPORT_50": Decimal("0.60"),
    "APPORT_30": Decimal("0.40"),
    "CREDIT": Decimal("0.20"),
}

COMMISSION_SPLIT = {
    "commercial": Decimal("70"),
    "manager": Decimal("15"),
    "marketing": Decimal("10"),
    "adv": Decimal("2.5"),
    "teleoperateur": Decimal("2.5"),
}

# ── Prime SPI calculation from score ───────────────────────────────────────

def compute_prime_spi(score_spi: float, prime_plafond: float) -> float:
    """Calculate the SPI prime based on score.

    SPI >= 95: 110% of plafond
    SPI >= 75: 105% of plafond
    SPI >= 60: 80% of plafond
    SPI >= 50: 50% of plafond
    SPI < 50:  0 DA (base only, malus goes to B/M balance)
    """
    if prime_plafond <= 0:
        return 0.0
    if score_spi >= 95:
        return round(prime_plafond * 1.10, 2)
    elif score_spi >= 75:
        return round(prime_plafond * 1.05, 2)
    elif score_spi >= 60:
        return round(prime_plafond * 0.80, 2)
    elif score_spi >= 50:
        return round(prime_plafond * 0.50, 2)
    else:
        return 0.0


# ── C1: Execution / Planning ──────────────────────────────────────────────

def compute_c1(tasks: list[TacheSPI]) -> float:
    """C1 — Execution score (0-100).

    - Delivered before deadline + validated: 100pts + 10pts precocity (cap 100)
    - Delivered on time + validated: 100pts
    - 1-2 days late, validated: 75pts
    - 3-7 days late, validated: 50pts
    - Not delivered or > 7 days late: 0pts
    """
    if not tasks:
        return 0.0

    total_score = 0.0
    evaluated = 0

    for t in tasks:
        if t.statut in (StatutTache.ANNULEE,):
            continue
        evaluated += 1

        if t.statut == StatutTache.VALIDEE and t.date_fin_reelle and t.date_fin_prevue:
            delta_days = (t.date_fin_reelle - t.date_fin_prevue).days
            if delta_days < 0:
                # Early delivery
                total_score += min(100 + 10, 100)  # precocity bonus capped
            elif delta_days == 0:
                total_score += 100
            elif delta_days <= 2:
                total_score += 75
            elif delta_days <= 7:
                total_score += 50
            else:
                total_score += 0
        elif t.statut == StatutTache.VALIDEE:
            total_score += 80  # validated but no date tracking
        elif t.statut == StatutTache.REJETEE:
            total_score += 0
        elif t.statut in (StatutTache.EN_COURS, StatutTache.EN_REVUE, StatutTache.VERROUILLEE):
            # In progress — check if overdue
            if t.date_fin_prevue and date.today() > t.date_fin_prevue:
                overdue = (date.today() - t.date_fin_prevue).days
                if overdue <= 2:
                    total_score += 60
                elif overdue <= 7:
                    total_score += 30
                else:
                    total_score += 0
            else:
                total_score += 70  # on track

    return round(total_score / max(evaluated, 1), 2)


# ── C2: Quality ───────────────────────────────────────────────────────────

def compute_c2(tasks: list[TacheSPI]) -> float:
    """C2 — Quality score (0-100).

    - Validated by system + manager without revision: 100pts
    - Validated after 1 minor correction: 80pts
    - Validated after major corrections: 60pts
    - System refused but manager validated (human override): 70pts
    - Manager refused: 0pts
    """
    if not tasks:
        return 50.0  # neutral when no tasks

    total_score = 0.0
    evaluated = 0

    for t in tasks:
        if t.statut in (StatutTache.ANNULEE, StatutTache.ASSIGNEE, StatutTache.PROPOSEE):
            continue
        evaluated += 1

        if t.statut == StatutTache.VALIDEE:
            if t.valide_par_systeme and t.valide_par_manager:
                score = 100.0
            elif not t.valide_par_systeme and t.valide_par_manager:
                score = 70.0  # human override
            else:
                score = 80.0  # validated with some corrections

            # Adjust by manager rating if available
            if t.manager_rating:
                score = min(score, t.manager_rating / 5.0 * 100)

            total_score += score
        elif t.statut == StatutTache.REJETEE:
            total_score += 0
        elif t.statut == StatutTache.EN_REVUE:
            total_score += 50  # pending review
        else:
            total_score += 50  # in progress

    return round(total_score / max(evaluated, 1), 2)


# ── C3: Behavior & Availability ───────────────────────────────────────────

def compute_c3(employee: Employee, absences: int = 0, retards: int = 0,
               avertissements: int = 0) -> float:
    """C3 — Behavior score (0-100).

    Starts at 100, deductions:
    - Late (>3/month): -10pts per extra
    - Unjustified absence 1 day: -15pts
    - Unjustified absence 2-3 days: -30pts
    - Unjustified absence >3 days: C3 = 0
    - Verbal warning: -5pts
    - Written warning: -15pts
    """
    score = 100.0

    # Absences
    if absences > 3:
        return 0.0
    elif absences >= 2:
        score -= 30
    elif absences >= 1:
        score -= 15

    # Lateness (penalty after 3 per month)
    if retards > 3:
        score -= (retards - 3) * 10

    # Warnings
    score -= avertissements * 15

    return max(round(score, 2), 0.0)


# ── C4: Business KPI ──────────────────────────────────────────────────────

def compute_c4(tasks: list[TacheSPI], employee: Employee) -> float:
    """C4 — Business performance (0-100).

    For commercial: based on sales KPIs in tasks
    For others: completion rate + quality of output
    """
    if not tasks:
        return 0.0

    evaluated_tasks = [t for t in tasks if t.statut not in (StatutTache.ANNULEE,)]
    if not evaluated_tasks:
        return 0.0

    # Check task KPIs
    kpi_scores = []
    for t in evaluated_tasks:
        if t.kpis and isinstance(t.kpis, list):
            for kpi in t.kpis:
                if isinstance(kpi, dict) and kpi.get("score_kpi") is not None:
                    kpi_scores.append(float(kpi["score_kpi"]))

    if kpi_scores:
        return round(sum(kpi_scores) / len(kpi_scores), 2)

    # Fallback: completion rate with quality weighting
    completed = sum(1 for t in evaluated_tasks if t.statut == StatutTache.VALIDEE)
    high_quality = sum(1 for t in evaluated_tasks
                       if t.statut == StatutTache.VALIDEE and t.manager_rating and t.manager_rating >= 4)

    ratio = (completed / len(evaluated_tasks)) * 80
    quality_bonus = (high_quality / len(evaluated_tasks)) * 20 if evaluated_tasks else 0

    return min(round(ratio + quality_bonus, 2), 100.0)


# ── Get weights for employee ──────────────────────────────────────────────

async def get_employee_weights(db: AsyncSession, employee: Employee) -> dict:
    """Get SPI weights adapted to the employee's role."""
    # Try DB rule first
    if employee.position:
        result = await db.execute(
            select(SPIRule).where(
                SPIRule.tenant_id == employee.tenant_id,
                SPIRule.role_code == employee.position,
                SPIRule.is_active == True,
            ).order_by(SPIRule.version.desc()).limit(1)
        )
        rule = result.scalar_one_or_none()
        if rule:
            return {
                "c1": float(rule.weight_planification),
                "c2": float(rule.weight_qualite),
                "c3": float(rule.weight_comportement),
                "c4": float(rule.weight_performance),
            }

    # Try role-based defaults
    cat = (employee.function_category or "").upper()
    if cat in ROLE_WEIGHTS:
        return ROLE_WEIGHTS[cat]

    return DEFAULT_WEIGHTS.copy()


# ── Compute monthly SPI ───────────────────────────────────────────────────

async def compute_spi_mensuel(
    db: AsyncSession,
    employee: Employee,
    mois: str,  # "2026-03"
) -> SPIMensuel:
    """Compute the full monthly SPI for an employee.

    Steps:
    1. Fetch all tasks for the month
    2. Compute C1-C4 component scores
    3. Apply adaptive weights
    4. Calculate reliability score (fiabilité)
    5. Compute prime from SPI
    6. Compute bonus/malus balance from OffrePerformance
    7. Check protection mechanisms (garde-fous)
    """
    year, month = int(mois[:4]), int(mois[5:7])
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    # 1. Fetch tasks for the month
    task_result = await db.execute(
        select(TacheSPI).where(
            TacheSPI.assignee_id == employee.id,
            TacheSPI.tenant_id == employee.tenant_id,
            TacheSPI.date_fin_prevue >= month_start,
            TacheSPI.date_fin_prevue <= month_end,
        )
    )
    tasks = list(task_result.scalars().all())

    # 2. Compute C1-C4
    c1 = compute_c1(tasks)
    c2 = compute_c2(tasks)
    c3 = compute_c3(employee)
    c4 = compute_c4(tasks, employee)

    # 3. Adaptive weights
    weights = await get_employee_weights(db, employee)
    w1, w2, w3, w4 = weights["c1"], weights["c2"], weights["c3"], weights["c4"]

    # 4. Compute weighted SPI
    score_spi = (c1 * w1 + c2 * w2 + c3 * w3 + c4 * w4) / 100.0
    score_spi = round(min(max(score_spi, 0), 100), 2)

    # 5. Reliability score
    fiabilite = _compute_fiabilite(tasks, employee)

    # 6. Bonus/malus from OffrePerformance
    offre_result = await db.execute(
        select(OffrePerformance).where(
            OffrePerformance.employe_id == employee.id,
            OffrePerformance.tenant_id == employee.tenant_id,
            OffrePerformance.statut == StatutOffre.EXECUTEE,
        )
    )
    offres = offre_result.scalars().all()

    # Filter offres for tasks in this month
    task_ids = {t.id for t in tasks}
    month_offres = [o for o in offres if o.tache_id in task_ids]

    bonus_total = sum(float(o.montant_applique or 0) for o in month_offres if o.resultat == ResultatOffre.BONUS_VERSE)
    malus_total = abs(sum(float(o.montant_applique or 0) for o in month_offres if o.resultat == ResultatOffre.MALUS_APPLIQUE))

    # 7. Prime SPI based on score
    prime_plafond = float(employee.prime_spi_plafond or 0)
    prime_calculee = compute_prime_spi(score_spi, prime_plafond)

    # Check for plan strategique primes this month
    plan_result = await db.execute(
        select(PlanStrategique).where(
            PlanStrategique.proposeur_id == employee.id,
            PlanStrategique.tenant_id == employee.tenant_id,
            PlanStrategique.statut == StatutPlan.VALIDE,
            PlanStrategique.prime_versee == True,
        )
    )
    plans = plan_result.scalars().all()
    prime_plan = sum(float(p.montant_prime or 0) for p in plans)

    # Task metrics
    taches_validees = sum(1 for t in tasks if t.statut == StatutTache.VALIDEE)
    taches_rejetees = sum(1 for t in tasks if t.statut == StatutTache.REJETEE)
    taches_en_retard = sum(1 for t in tasks
                           if t.date_fin_prevue and date.today() > t.date_fin_prevue
                           and t.statut not in (StatutTache.VALIDEE, StatutTache.ANNULEE))

    solde_bm = bonus_total - malus_total

    # Build record
    spi_record = SPIMensuel(
        id=str(uuid.uuid4()),
        tenant_id=employee.tenant_id,
        employe_id=employee.id,
        mois=mois,
        c1_execution=c1,
        c2_qualite=c2,
        c3_comportement=c3,
        c4_metier=c4,
        w1=w1, w2=w2, w3=w3, w4=w4,
        score_spi=score_spi,
        fiabilite_score=fiabilite,
        prime_calculee=prime_calculee,
        malus_calcule=malus_total,
        solde_bm_mois=solde_bm,
        commission_mois=0,  # set by commercial logic
        prime_plan=prime_plan,
        taches_total=len(tasks),
        taches_validees=taches_validees,
        taches_rejetees=taches_rejetees,
        taches_en_retard=taches_en_retard,
        details={
            "tasks_evaluated": len(tasks),
            "weights": weights,
            "offres_count": len(month_offres),
        },
    )

    logger.info("spi_mensuel_computed",
                employee_id=employee.id, mois=mois,
                score_spi=score_spi, c1=c1, c2=c2, c3=c3, c4=c4,
                prime=prime_calculee, solde_bm=solde_bm)

    return spi_record


def _compute_fiabilite(tasks: list[TacheSPI], employee: Employee) -> float:
    """Compute reliability score for SPI measurement (0-100).

    30% — tasks with complete data / total tasks
    20% — no active contestation
    20% — no unresolved external factors
    20% — system-manager convergence
    10% — stable history (no unexplained drop)
    """
    if not tasks:
        return 50.0  # neutral when no tasks

    # Data completeness (30%)
    complete = sum(1 for t in tasks if t.score_execution is not None or t.statut in (StatutTache.VALIDEE, StatutTache.REJETEE))
    data_pct = (complete / len(tasks)) * 30

    # No contestation (20%)
    contested = sum(1 for t in tasks if t.est_contestee)
    contest_pct = 20 if contested == 0 else max(0, 20 - contested * 10)

    # No external factors (20%) — simplified: check if any blocked tasks
    blocked = sum(1 for t in tasks if t.est_bloquee)
    external_pct = 20 if blocked == 0 else max(0, 20 - blocked * 10)

    # Convergence (20%) — system vs manager agreement
    converged = sum(1 for t in tasks if t.valide_par_systeme is not None and t.valide_par_manager is not None
                    and t.valide_par_systeme == t.valide_par_manager)
    evaluable = sum(1 for t in tasks if t.valide_par_systeme is not None and t.valide_par_manager is not None)
    convergence_pct = (converged / max(evaluable, 1)) * 20

    # History stability (10%) — simplified
    history_pct = 10  # assume stable unless we have data saying otherwise

    return round(data_pct + contest_pct + external_pct + convergence_pct + history_pct, 2)


# ── Batch monthly computation ─────────────────────────────────────────────

async def compute_spi_batch_mensuel(
    db: AsyncSession,
    tenant_id: str,
    mois: str,
) -> list[SPIMensuel]:
    """Compute monthly SPI for all active employees."""
    result = await db.execute(
        select(Employee).where(
            Employee.tenant_id == tenant_id,
            Employee.status == EmploymentStatus.ACTIVE,
        )
    )
    employees = result.scalars().all()

    scores = []
    for emp in employees:
        # Check if already computed
        existing = await db.execute(
            select(SPIMensuel).where(
                SPIMensuel.employe_id == emp.id,
                SPIMensuel.mois == mois,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        spi = await compute_spi_mensuel(db, emp, mois)
        db.add(spi)
        scores.append(spi)

    if scores:
        await db.flush()

    return scores


# ── Check sub-performance thresholds ───────────────────────────────────────

async def check_sous_performance(
    db: AsyncSession,
    tenant_id: str,
    mois: str,
) -> list[dict]:
    """Check all employees for sub-performance and create alerts."""
    result = await db.execute(
        select(SPIMensuel).where(
            SPIMensuel.tenant_id == tenant_id,
            SPIMensuel.mois == mois,
            SPIMensuel.est_confirme == True,
        )
    )
    spis = result.scalars().all()

    alerts = []
    for spi in spis:
        emp_result = await db.execute(
            select(Employee).where(Employee.id == spi.employe_id)
        )
        emp = emp_result.scalar_one_or_none()
        if not emp:
            continue

        score = float(spi.score_spi)
        fiabilite = float(spi.fiabilite_score)

        # Guard: only count if reliability >= 70%
        if fiabilite < 70:
            alert = AlerteRH(
                tenant_id=tenant_id,
                employe_id=emp.id,
                type_alerte=TypeAlerte.PROTECTION,
                message=f"SPI {score} non comptabilisé — fiabilité {fiabilite}% < 70%. Investigation requise.",
                severite="WARNING",
                mois_reference=mois,
                score_spi=score,
            )
            db.add(alert)
            alerts.append({"type": "PROTECTION", "employee_id": emp.id, "message": alert.message})
            continue

        if score < 50:
            emp.mois_consecutifs_sous_50 = (emp.mois_consecutifs_sous_50 or 0) + 1
            emp.mois_consecutifs_sous_70 = (emp.mois_consecutifs_sous_70 or 0) + 1

            if emp.mois_consecutifs_sous_50 >= 2:
                emp.statut_rh = "EN_PROCEDURE_RUPTURE"
                alert = AlerteRH(
                    tenant_id=tenant_id,
                    employe_id=emp.id,
                    type_alerte=TypeAlerte.RUPTURE_SPI,
                    message=f"2 mois consécutifs SPI < 50% — Procédure de rupture à initier",
                    severite="CRITICAL",
                    mois_reference=mois,
                    score_spi=score,
                )
            else:
                emp.statut_rh = "AVERTISSEMENT"
                alert = AlerteRH(
                    tenant_id=tenant_id,
                    employe_id=emp.id,
                    type_alerte=TypeAlerte.AVERTISSEMENT,
                    message=f"SPI {score}% < 50% — Avertissement + plan de redressement 30j",
                    severite="CRITICAL",
                    mois_reference=mois,
                    score_spi=score,
                )
            db.add(alert)
            alerts.append({"type": alert.type_alerte.value, "employee_id": emp.id, "message": alert.message})

        elif score < 70:
            emp.mois_consecutifs_sous_50 = 0
            emp.mois_consecutifs_sous_70 = (emp.mois_consecutifs_sous_70 or 0) + 1
            emp.statut_rh = "SURVEILLANCE"

            alert = AlerteRH(
                tenant_id=tenant_id,
                employe_id=emp.id,
                type_alerte=TypeAlerte.SURVEILLANCE,
                message=f"SPI {score}% < 70% — Sous surveillance",
                severite="WARNING",
                mois_reference=mois,
                score_spi=score,
            )
            db.add(alert)
            alerts.append({"type": "SURVEILLANCE", "employee_id": emp.id, "message": alert.message})
        else:
            emp.mois_consecutifs_sous_50 = 0
            emp.mois_consecutifs_sous_70 = 0
            if emp.statut_rh in ("AVERTISSEMENT", "SURVEILLANCE"):
                emp.statut_rh = "ACTIF"

        # Update employee current SPI
        emp.spi_courant = score

    await db.flush()
    return alerts


# ── Payroll computation ────────────────────────────────────────────────────

async def compute_paie_employe(
    db: AsyncSession,
    employee: Employee,
    mois: str,
) -> dict:
    """Compute payroll for an employee for a given month.

    Formula:
      NET = base_cnas (INTANGIBLE)
            + prime_SPI (from score)
            + solde_bonus_malus (from tasks, only if positive)
            + commission (commercial only)
            + prime_plan (5% if validated plan)
            - CNAS salarial (9%)
            - IRG (progressive brackets)
    """
    # Fetch SPI mensuel
    spi_result = await db.execute(
        select(SPIMensuel).where(
            SPIMensuel.employe_id == employee.id,
            SPIMensuel.mois == mois,
        )
    )
    spi = spi_result.scalar_one_or_none()

    base = float(employee.base_salary or 0)
    prime_plafond = float(employee.prime_spi_plafond or 0)

    # Prime SPI from score
    if spi:
        prime_spi = float(spi.prime_calculee or 0)
        solde_bm = float(spi.solde_bm_mois or 0)
        commission = float(spi.commission_mois or 0)
        prime_plan = float(spi.prime_plan or 0)
        score_spi = float(spi.score_spi)
    else:
        prime_spi = 0
        solde_bm = 0
        commission = 0
        prime_plan = 0
        score_spi = 0

    # Solde B/M: only pay if positive, negative carried forward
    cumul_bm = float(employee.solde_bonus_malus or 0) + solde_bm
    versement_bm = max(cumul_bm, 0)
    # Cap at 110% of prime plafond
    versement_bm = min(versement_bm, prime_plafond * 1.10) if prime_plafond > 0 else versement_bm

    # Gross calculation
    brut = base + prime_spi + versement_bm + commission + prime_plan

    # Algerian deductions
    cnas_salarial = round(brut * 0.09, 2)
    cnas_patronal = round(brut * 0.26, 2)
    taxable = brut - cnas_salarial
    irg = _compute_irg(taxable)
    net = round(brut - cnas_salarial - irg, 2)

    return {
        "employe_id": employee.id,
        "employe_nom": f"{employee.first_name} {employee.last_name}",
        "mois": mois,
        "salaire_base": base,
        "prime_spi_plafond": prime_plafond,
        "score_spi": score_spi,
        "prime_spi": prime_spi,
        "solde_bm_mois": solde_bm,
        "versement_bm": versement_bm,
        "cumul_bm": cumul_bm,
        "commission": commission,
        "prime_plan": prime_plan,
        "brut": round(brut, 2),
        "cnas_salarial": cnas_salarial,
        "cnas_patronal": cnas_patronal,
        "irg": irg,
        "net": net,
        "cout_employeur": round(brut + cnas_patronal, 2),
    }


def _compute_irg(taxable_monthly: float) -> float:
    """Algerian IRG (progressive brackets)."""
    if taxable_monthly <= 10_000:
        return 0.0
    elif taxable_monthly <= 30_000:
        return round((taxable_monthly - 10_000) * 0.20, 2)
    elif taxable_monthly <= 120_000:
        return round(4_000 + (taxable_monthly - 30_000) * 0.30, 2)
    else:
        return round(31_000 + (taxable_monthly - 120_000) * 0.35, 2)


# ── Commission calculation ─────────────────────────────────────────────────

def compute_commission(
    montant_encaisse: float,
    mode_paiement: str = "CASH_100",
) -> dict:
    """Compute sales commission with 5-actor split."""
    rate = COMMISSION_RATES.get(mode_paiement, Decimal("0.20"))
    total = float(Decimal(str(montant_encaisse)) * rate / 100)
    return {
        "total_commission": round(total, 2),
        "commercial": round(total * 0.70, 2),
        "manager": round(total * 0.15, 2),
        "marketing": round(total * 0.10, 2),
        "adv": round(total * 0.025, 2),
        "teleoperateur": round(total * 0.025, 2),
    }


# ── Process performance offer result ──────────────────────────────────────

async def process_offre_result(
    db: AsyncSession,
    offre: OffrePerformance,
    tache: TacheSPI,
) -> OffrePerformance:
    """Process the result of a performance offer based on task outcome."""
    if tache.statut == StatutTache.VALIDEE:
        offre.resultat = ResultatOffre.BONUS_VERSE
        offre.montant_applique = offre.bonus_final_da or offre.bonus_propose_da
    elif tache.statut == StatutTache.REJETEE:
        offre.resultat = ResultatOffre.MALUS_APPLIQUE
        offre.montant_applique = -(offre.malus_final_da or offre.bonus_propose_da)
    else:
        return offre

    offre.statut = StatutOffre.EXECUTEE

    # Update employee B/M balance
    emp_result = await db.execute(
        select(Employee).where(Employee.id == offre.employe_id)
    )
    emp = emp_result.scalar_one_or_none()
    if emp:
        current_balance = float(emp.solde_bonus_malus or 0)
        emp.solde_bonus_malus = current_balance + float(offre.montant_applique or 0)

    return offre


# ── Plan strategique prime ─────────────────────────────────────────────────

async def calculate_plan_prime(
    db: AsyncSession,
    plan: PlanStrategique,
    employee: Employee,
) -> float:
    """Calculate the 5% prime for a validated strategic plan."""
    base = float(employee.base_salary or 0)
    prime_spi = float(employee.prime_spi_plafond or 0)
    montant = round((base + prime_spi) * 0.05, 2)
    plan.montant_prime = montant
    plan.prime_versee = True
    return montant


# ── Dashboard data ─────────────────────────────────────────────────────────

async def get_dashboard_employe(
    db: AsyncSession,
    employee: Employee,
    mois: str,
) -> dict:
    """Get employee dashboard data for mobile/web."""
    # Current SPI
    spi_result = await db.execute(
        select(SPIMensuel).where(
            SPIMensuel.employe_id == employee.id,
            SPIMensuel.mois == mois,
        )
    )
    spi = spi_result.scalar_one_or_none()

    # Active tasks
    task_result = await db.execute(
        select(TacheSPI).where(
            TacheSPI.assignee_id == employee.id,
            TacheSPI.tenant_id == employee.tenant_id,
            TacheSPI.statut.not_in([StatutTache.VALIDEE, StatutTache.REJETEE, StatutTache.ANNULEE]),
        ).order_by(TacheSPI.date_fin_prevue)
    )
    active_tasks = task_result.scalars().all()

    # Pending offres
    offre_result = await db.execute(
        select(OffrePerformance).where(
            OffrePerformance.employe_id == employee.id,
            OffrePerformance.statut.in_([StatutOffre.PROPOSEE, StatutOffre.CONTRE_OFFRE]),
        )
    )
    pending_offres = offre_result.scalars().all()

    # Payroll preview
    paie = await compute_paie_employe(db, employee, mois)

    return {
        "employe": {
            "id": employee.id,
            "nom": f"{employee.first_name} {employee.last_name}",
            "poste": employee.position,
            "departement": employee.department,
            "statut_rh": employee.statut_rh or "ACTIF",
        },
        "spi": {
            "score": float(spi.score_spi) if spi else 0,
            "c1_execution": float(spi.c1_execution) if spi else 0,
            "c2_qualite": float(spi.c2_qualite) if spi else 0,
            "c3_comportement": float(spi.c3_comportement) if spi else 0,
            "c4_metier": float(spi.c4_metier) if spi else 0,
            "fiabilite": float(spi.fiabilite_score) if spi else 0,
            "est_confirme": spi.est_confirme if spi else False,
        } if spi else None,
        "taches_actives": [
            {
                "id": t.id,
                "titre": t.titre,
                "statut": t.statut.value,
                "priorite": t.priorite.value if t.priorite else "NORMALE",
                "date_fin_prevue": t.date_fin_prevue.isoformat() if t.date_fin_prevue else None,
                "jours_restants": (t.date_fin_prevue - date.today()).days if t.date_fin_prevue else None,
                "en_retard": t.date_fin_prevue < date.today() if t.date_fin_prevue else False,
            }
            for t in active_tasks
        ],
        "offres_en_attente": len(pending_offres),
        "prevision_paie": paie,
        "solde_bm": float(employee.solde_bonus_malus or 0),
    }


async def get_dashboard_manager(
    db: AsyncSession,
    manager: Employee,
    mois: str,
) -> dict:
    """Get manager dashboard — team SPI overview."""
    # Get team members
    team_result = await db.execute(
        select(Employee).where(
            Employee.manager_id == manager.id,
            Employee.status == EmploymentStatus.ACTIVE,
        )
    )
    team = team_result.scalars().all()

    team_data = []
    total_spi = 0
    count_spi = 0
    alerts_count = 0

    for emp in team:
        spi_result = await db.execute(
            select(SPIMensuel).where(
                SPIMensuel.employe_id == emp.id,
                SPIMensuel.mois == mois,
            )
        )
        spi = spi_result.scalar_one_or_none()
        score = float(spi.score_spi) if spi else 0

        # Pending validations
        pending_result = await db.execute(
            select(func.count(TacheSPI.id)).where(
                TacheSPI.assignee_id == emp.id,
                TacheSPI.statut == StatutTache.EN_REVUE,
            )
        )
        pending_count = pending_result.scalar() or 0

        if score > 0:
            total_spi += score
            count_spi += 1

        if score < 50:
            alerts_count += 1

        team_data.append({
            "id": emp.id,
            "nom": f"{emp.first_name} {emp.last_name}",
            "poste": emp.position,
            "spi": score,
            "statut_rh": emp.statut_rh or "ACTIF",
            "taches_en_attente": pending_count,
        })

    # Pending offres for manager review
    offre_pending = await db.execute(
        select(func.count(OffrePerformance.id)).where(
            OffrePerformance.tenant_id == manager.tenant_id,
            OffrePerformance.statut == StatutOffre.PROPOSEE,
        )
    )

    return {
        "equipe_size": len(team),
        "spi_moyen": round(total_spi / max(count_spi, 1), 2),
        "alertes": alerts_count,
        "equipe": sorted(team_data, key=lambda x: x["spi"], reverse=True),
        "offres_a_traiter": offre_pending.scalar() or 0,
    }


async def get_dashboard_daf(
    db: AsyncSession,
    tenant_id: str,
    mois: str,
) -> dict:
    """Get DAF/CEO dashboard — company-wide SPI and payroll overview."""
    # All monthly SPIs
    spi_result = await db.execute(
        select(SPIMensuel).where(
            SPIMensuel.tenant_id == tenant_id,
            SPIMensuel.mois == mois,
        )
    )
    spis = spi_result.scalars().all()

    # All employees
    emp_result = await db.execute(
        select(Employee).where(
            Employee.tenant_id == tenant_id,
            Employee.status == EmploymentStatus.ACTIVE,
        )
    )
    employees = emp_result.scalars().all()
    emp_map = {e.id: e for e in employees}

    total_spi = 0
    total_masse_sal = 0
    total_primes = 0
    distribution = {"excellent": 0, "performant": 0, "standard": 0, "sous_perf": 0, "critique": 0}

    employee_details = []
    for spi in spis:
        score = float(spi.score_spi)
        emp = emp_map.get(spi.employe_id)
        if not emp:
            continue

        total_spi += score
        base = float(emp.base_salary or 0)
        prime = float(spi.prime_calculee or 0)
        total_masse_sal += base + prime
        total_primes += prime

        if score >= 90:
            distribution["excellent"] += 1
        elif score >= 75:
            distribution["performant"] += 1
        elif score >= 60:
            distribution["standard"] += 1
        elif score >= 50:
            distribution["sous_perf"] += 1
        else:
            distribution["critique"] += 1

        employee_details.append({
            "id": emp.id,
            "nom": f"{emp.first_name} {emp.last_name}",
            "departement": emp.department,
            "spi": score,
            "base": base,
            "prime": prime,
            "statut_rh": emp.statut_rh or "ACTIF",
        })

    # Alerts
    alert_result = await db.execute(
        select(AlerteRH).where(
            AlerteRH.tenant_id == tenant_id,
            AlerteRH.mois_reference == mois,
            AlerteRH.est_traitee == False,
        )
    )
    alertes = alert_result.scalars().all()

    return {
        "mois": mois,
        "effectif_total": len(employees),
        "effectif_evalue": len(spis),
        "spi_moyen": round(total_spi / max(len(spis), 1), 2),
        "masse_salariale_totale": round(total_masse_sal, 2),
        "total_primes_spi": round(total_primes, 2),
        "distribution": distribution,
        "top_performers": sorted(employee_details, key=lambda x: x["spi"], reverse=True)[:5],
        "low_performers": sorted(employee_details, key=lambda x: x["spi"])[:5],
        "alertes": [
            {
                "id": a.id,
                "type": a.type_alerte.value,
                "message": a.message,
                "severite": a.severite,
                "employe_id": a.employe_id,
            }
            for a in alertes
        ],
        "employees": sorted(employee_details, key=lambda x: x["spi"], reverse=True),
    }


# ── Legacy compat — keep old function signatures working ──────────────────

async def compute_spi_for_employee(
    db: AsyncSession,
    employee: Employee,
    target_date: date,
    period_type: SPIScorePeriod = SPIScorePeriod.DAILY,
) -> SPIScore:
    """Legacy compat: compute daily SPI score using SPIScore model."""
    mois = target_date.strftime("%Y-%m")

    # Fetch tasks for this specific date
    task_result = await db.execute(
        select(TacheSPI).where(
            TacheSPI.assignee_id == employee.id,
            TacheSPI.tenant_id == employee.tenant_id,
            TacheSPI.date_fin_prevue == target_date,
        )
    )
    tasks = list(task_result.scalars().all())

    c1 = compute_c1(tasks)
    c2 = compute_c2(tasks)
    c3 = compute_c3(employee)
    c4 = compute_c4(tasks, employee)
    weights = await get_employee_weights(db, employee)

    spi_total = (c1 * weights["c1"] + c2 * weights["c2"] +
                 c3 * weights["c3"] + c4 * weights["c4"]) / 100.0
    spi_total = round(min(max(spi_total, 0), 100), 2)

    score = SPIScore(
        id=str(uuid.uuid4()),
        tenant_id=employee.tenant_id,
        employee_id=employee.id,
        period_type=period_type,
        period_date=target_date,
        period_label=target_date.isoformat() if period_type == SPIScorePeriod.DAILY else mois,
        score_planification=c1,
        score_qualite=c2,
        score_comportement=c3,
        score_performance=c4,
        spi_total=spi_total,
        tasks_planned=len(tasks),
        tasks_completed=sum(1 for t in tasks if t.statut == StatutTache.VALIDEE),
        tasks_validated=sum(1 for t in tasks if t.statut == StatutTache.VALIDEE),
        tasks_rejected=sum(1 for t in tasks if t.statut == StatutTache.REJETEE),
        base_salary=float(employee.base_salary or 0),
        adjusted_salary=float(employee.base_salary or 0),
        computed_by="system",
    )
    return score


async def compute_spi_batch(
    db: AsyncSession,
    tenant_id: str,
    target_date: date,
    period_type: SPIScorePeriod = SPIScorePeriod.DAILY,
) -> list[SPIScore]:
    """Legacy compat: batch compute daily SPI."""
    result = await db.execute(
        select(Employee).where(
            Employee.tenant_id == tenant_id,
            Employee.status == EmploymentStatus.ACTIVE,
        )
    )
    employees = result.scalars().all()
    scores = []
    for emp in employees:
        existing = await db.execute(
            select(SPIScore).where(
                SPIScore.employee_id == emp.id,
                SPIScore.period_type == period_type,
                SPIScore.period_date == target_date,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        score = await compute_spi_for_employee(db, emp, target_date, period_type)
        db.add(score)
        scores.append(score)
    if scores:
        await db.flush()
    return scores


def compute_payroll_with_spi(employee, spi_score, period_label):
    """Legacy compat wrapper."""
    base = float(employee.base_salary or 0)
    if base == 0:
        return {"gross": 0, "net": 0, "spi_bonus": 0, "spi_malus": 0}
    spi_bonus = float(spi_score.bonus_amount or 0) if spi_score else 0
    spi_malus = float(spi_score.malus_amount or 0) if spi_score else 0
    commission = float(spi_score.commission_amount or 0) if spi_score else 0
    gross = base + spi_bonus - spi_malus + commission
    cnas = round(gross * 0.09, 2)
    irg = _compute_irg(gross - cnas)
    net = round(gross - cnas - irg, 2)
    return {
        "period_label": period_label,
        "base_salary": base,
        "spi_bonus": spi_bonus,
        "spi_malus": spi_malus,
        "commission": commission,
        "gross": round(gross, 2),
        "cnas": cnas,
        "irg": irg,
        "net": net,
        "spi_total": float(spi_score.spi_total) if spi_score else None,
    }


# ── Validation helpers (for agents) ───────────────────────────────────────

async def validate_employee_hierarchy(db: AsyncSession, tenant_id: str) -> list[dict]:
    errors = []
    result = await db.execute(
        select(Employee).where(
            Employee.tenant_id == tenant_id,
            Employee.status == EmploymentStatus.ACTIVE,
        )
    )
    employees = result.scalars().all()
    emp_ids = {e.id for e in employees}
    for emp in employees:
        if emp.manager_id and emp.manager_id not in emp_ids:
            errors.append({"code": "INVALID_MANAGER", "employee_id": emp.id,
                           "message": f"Manager ID {emp.manager_id} not found"})
        if emp.manager_id == emp.id:
            errors.append({"code": "SELF_MANAGER", "employee_id": emp.id,
                           "message": f"{emp.first_name} {emp.last_name} is their own manager"})
    return errors


async def validate_spi_score_range(db, tenant_id, period_date):
    errors = []
    result = await db.execute(
        select(SPIScore).where(SPIScore.tenant_id == tenant_id, SPIScore.period_date == period_date)
    )
    for score in result.scalars().all():
        if float(score.spi_total) < 0:
            errors.append({"code": "NEGATIVE_SPI", "employee_id": score.employee_id})
        if float(score.spi_total) > 200:
            errors.append({"code": "SPI_EXCEEDS_MAX", "employee_id": score.employee_id})
    return errors


async def validate_shareholder_percentages(db, tenant_id):
    from app.models.spi import OwnershipRelation
    errors = []
    result = await db.execute(
        select(OwnershipRelation.entreprise_id, func.sum(OwnershipRelation.ownership_pct).label("total_pct"))
        .where(OwnershipRelation.tenant_id == tenant_id, OwnershipRelation.is_active == True,
               OwnershipRelation.projet_id == None)
        .group_by(OwnershipRelation.entreprise_id)
    )
    for row in result.all():
        if float(row.total_pct) > 100:
            errors.append({"code": "OWNERSHIP_EXCEEDS_100", "entreprise_id": row.entreprise_id})
    return errors
