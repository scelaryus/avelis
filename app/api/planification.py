"""GFI v7.0 — Planification, Tâches SPI, Offres Performance, Paie API.

Endpoints:
  /plans          — Strategic plans (propose, validate, decline)
  /taches         — Tasks with SPI tracking
  /offres         — Performance offers (bonus/malus)
  /paie           — Payroll computation
  /spi-mensuel    — Monthly SPI scores
  /dashboard      — Employee, manager, DAF dashboards
  /alertes        — HR alerts
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.core import User
from app.models.hr import Employee, EmploymentStatus
from app.models.planification import (
    PlanStrategique, StatutPlan, HorizonPlan,
    TacheSPI, StatutTache, PrioriteTache, SourceTache,
    OffrePerformance, StatutOffre, ResultatOffre,
    SPIMensuel, AlerteRH, TypeAlerte,
)
from app.auth.dependencies import get_current_user, require_role
from app.services.spi_engine import (
    compute_spi_mensuel, compute_spi_batch_mensuel,
    compute_paie_employe, check_sous_performance,
    get_dashboard_employe, get_dashboard_manager, get_dashboard_daf,
    calculate_plan_prime, process_offre_result, compute_commission,
)

router = APIRouter(tags=["Planification & SPI"])


# ── Schemas ────────────────────────────────────────────────────────────────

class PlanCreate(BaseModel):
    titre: str
    description: str
    objectif_mesurable: Optional[str] = None
    kpis_proposes: list[dict] = []
    horizon: str = "MOIS_3"
    benefice_estime: Optional[str] = None
    ressources_necessaires: Optional[str] = None
    projet_id: Optional[str] = None


class PlanValidation(BaseModel):
    decision: str  # VALIDE, DECLINE, CONTRE_PROPOSITION
    modifications: Optional[str] = None
    justification: Optional[str] = None


class TacheCreate(BaseModel):
    titre: str
    description: Optional[str] = None
    assignee_id: str
    date_fin_prevue: str  # ISO date
    priorite: str = "NORMALE"
    source_type: str = "OBJECTIF_MANAGER"
    plan_strategique_id: Optional[str] = None
    projet_id: Optional[str] = None
    criteres_acceptation: Optional[str] = None
    kpis: list[dict] = []


class OffreCreate(BaseModel):
    bonus_propose_pct: float
    delai_propose: Optional[str] = None
    justification: Optional[str] = None


class OffreContreOffre(BaseModel):
    bonus_contre_offre_pct: float
    justification: Optional[str] = None


class TacheValidation(BaseModel):
    decision: str  # VALIDEE, REJETEE
    commentaire: Optional[str] = None
    rating: Optional[int] = None  # 1-5


# ── Plans Stratégiques ─────────────────────────────────────────────────────

@router.post("/plans", status_code=status.HTTP_201_CREATED)
async def proposer_plan(
    body: PlanCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Any employee can propose a strategic plan."""
    # Get employee
    emp = await _get_employee_for_user(db, user)

    # Anti-abuse: max 3 plans/month
    month_start = date.today().replace(day=1)
    count_result = await db.execute(
        select(func.count(PlanStrategique.id)).where(
            PlanStrategique.proposeur_id == emp.id,
            PlanStrategique.date_proposition >= datetime.combine(month_start, datetime.min.time()),
        )
    )
    if (count_result.scalar() or 0) >= 3:
        raise HTTPException(status_code=400, detail="Maximum 3 plans par mois atteint")

    if len(body.description) < 50:
        raise HTTPException(status_code=400, detail="Description doit faire au moins 50 caractères")

    # Generate reference
    seq_result = await db.execute(
        select(func.count(PlanStrategique.id)).where(
            PlanStrategique.tenant_id == user.tenant_id,
        )
    )
    seq = (seq_result.scalar() or 0) + 1
    reference = f"PLAN-{date.today().year}-{seq:04d}"

    # AI SMART reformulation
    smart_goal = body.objectif_mesurable or ""
    ai_notes = None
    ai_score = 0
    try:
        from app.services.llm_graph import invoke_json_agent
        ai_result = await invoke_json_agent(
            system_prompt="""\
You are an expert business coach for Groupe Dendani, an Algerian real-estate group.
An employee is proposing a strategic plan. Your job:
1. Reformulate their objective into a SMART goal (Specific, Measurable, Achievable, Relevant, Time-bound)
2. Score the plan's relevance (0-100)
3. Score feasibility (0-100)
4. Suggest improvements

Reply JSON only:
{
  "smart_objective": "The reformulated SMART goal in French",
  "score_pertinence": 0-100,
  "faisabilite": 0-100,
  "ameliorations": "Suggestions in French"
}
No markdown fences.""",
            user_prompt=f"""Titre: {body.titre}
Description: {body.description}
Objectif proposé: {body.objectif_mesurable or 'Non spécifié'}
KPIs: {body.kpis_proposes or []}
Horizon: {body.horizon}
Bénéfice estimé: {body.benefice_estime or 'Non spécifié'}
Ressources: {body.ressources_necessaires or 'Non spécifié'}""",
            temperature=0.2,
            max_tokens=512,
        )
        parsed = ai_result.get("parsed_json", {})
        smart_goal = parsed.get("smart_objective", smart_goal)
        ai_score = parsed.get("score_pertinence", 0)
        ai_faisabilite = parsed.get("faisabilite", 0)
        ai_notes = parsed.get("ameliorations")
    except Exception:
        ai_faisabilite = 0

    plan = PlanStrategique(
        tenant_id=user.tenant_id,
        reference=reference,
        proposeur_id=emp.id,
        titre=body.titre,
        description=body.description,
        objectif_mesurable=smart_goal,
        kpis_proposes=body.kpis_proposes,
        horizon=HorizonPlan(body.horizon),
        benefice_estime=body.benefice_estime,
        ressources_necessaires=body.ressources_necessaires,
        projet_id=body.projet_id,
        statut=StatutPlan.SOUMIS,
        score_pertinence_ia=ai_score,
        faisabilite_score=ai_faisabilite,
        ameliorations_proposees=ai_notes,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    return {
        "id": plan.id,
        "reference": plan.reference,
        "titre": plan.titre,
        "statut": plan.statut.value,
        "objectif_smart": smart_goal,
        "score_pertinence": float(ai_score),
        "faisabilite": float(ai_faisabilite),
        "ameliorations": ai_notes,
        "message": "Plan soumis avec succès. L'IA a reformulé votre objectif en SMART.",
    }


@router.get("/plans")
async def list_plans(
    statut: Optional[str] = Query(None),
    proposeur_id: Optional[str] = Query(None),
    mine: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List strategic plans."""
    query = select(PlanStrategique).where(PlanStrategique.tenant_id == user.tenant_id)
    if mine and user.employee_id:
        query = query.where(PlanStrategique.proposeur_id == user.employee_id)
    if statut:
        query = query.where(PlanStrategique.statut == StatutPlan(statut))
    if proposeur_id:
        query = query.where(PlanStrategique.proposeur_id == proposeur_id)
    query = query.order_by(PlanStrategique.date_proposition.desc())

    result = await db.execute(query)
    plans = result.scalars().all()

    # Get proposer names
    emp_ids = list(set(p.proposeur_id for p in plans))
    emp_map = await _get_employee_map(db, emp_ids)

    return [
        {
            "id": p.id,
            "reference": p.reference,
            "titre": p.titre,
            "description": p.description[:200] if p.description else "",
            "objectif_smart": p.objectif_mesurable,
            "statut": p.statut.value,
            "horizon": p.horizon.value if p.horizon else None,
            "proposeur_id": p.proposeur_id,
            "proposeur_nom": _emp_name(emp_map, p.proposeur_id),
            "date_proposition": p.date_proposition.isoformat() if p.date_proposition else None,
            "avancement_pct": float(p.avancement_pct or 0),
            "score_pertinence": float(p.score_pertinence_ia or 0),
            "faisabilite": float(p.faisabilite_score or 0),
            "ameliorations": p.ameliorations_proposees,
            "prime_versee": p.prime_versee,
            "montant_prime": float(p.montant_prime or 0),
        }
        for p in plans
    ]


@router.put("/plans/{plan_id}/valider")
async def valider_plan(
    plan_id: str,
    body: PlanValidation,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """CEO/manager validates, declines, or counter-proposes a plan."""
    plan = await _get_plan(db, user.tenant_id, plan_id)
    valideur = await _get_employee_for_user(db, user)

    if body.decision == "VALIDE":
        plan.statut = StatutPlan.VALIDE
        plan.valideur_id = valideur.id
        plan.date_validation = datetime.utcnow()
        plan.modifications_valideur = body.modifications

        # Calculate 5% prime
        proposeur_result = await db.execute(
            select(Employee).where(Employee.id == plan.proposeur_id)
        )
        proposeur = proposeur_result.scalar_one_or_none()
        if proposeur:
            await calculate_plan_prime(db, plan, proposeur)

    elif body.decision == "DECLINE":
        if not body.justification:
            raise HTTPException(status_code=400, detail="Justification obligatoire pour un refus")
        plan.statut = StatutPlan.DECLINE
        plan.valideur_id = valideur.id
        plan.justification_refus = body.justification

    elif body.decision == "CONTRE_PROPOSITION":
        plan.statut = StatutPlan.CONTRE_PROPOSITION
        plan.valideur_id = valideur.id
        plan.modifications_valideur = body.modifications

    await db.commit()
    return {"id": plan.id, "statut": plan.statut.value}


# ── Tâches SPI ─────────────────────────────────────────────────────────────

@router.post("/taches", status_code=status.HTTP_201_CREATED)
async def creer_tache(
    body: TacheCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a task and assign to an employee."""
    assigneur = await _get_employee_for_user(db, user)

    # Generate reference
    seq_result = await db.execute(
        select(func.count(TacheSPI.id)).where(TacheSPI.tenant_id == user.tenant_id)
    )
    seq = (seq_result.scalar() or 0) + 1
    reference = f"TACHE-{date.today().year}-{seq:04d}"

    tache = TacheSPI(
        tenant_id=user.tenant_id,
        reference=reference,
        source_type=SourceTache(body.source_type),
        plan_strategique_id=body.plan_strategique_id,
        titre=body.titre,
        description=body.description,
        criteres_acceptation=body.criteres_acceptation,
        assignee_id=body.assignee_id,
        assigneur_id=assigneur.id,
        date_fin_prevue=date.fromisoformat(body.date_fin_prevue),
        priorite=PrioriteTache(body.priorite),
        kpis=body.kpis,
        projet_id=body.projet_id,
        statut=StatutTache.ASSIGNEE,
    )
    db.add(tache)
    await db.commit()
    await db.refresh(tache)

    return {
        "id": tache.id,
        "reference": tache.reference,
        "titre": tache.titre,
        "statut": tache.statut.value,
    }


@router.get("/taches")
async def list_taches(
    assignee_id: Optional[str] = Query(None),
    statut: Optional[str] = Query(None),
    plan_id: Optional[str] = Query(None),
    mine: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List tasks with filters."""
    query = select(TacheSPI).where(TacheSPI.tenant_id == user.tenant_id)

    if mine:
        emp = await _get_employee_for_user(db, user)
        query = query.where(TacheSPI.assignee_id == emp.id)
    elif assignee_id:
        query = query.where(TacheSPI.assignee_id == assignee_id)

    if statut:
        query = query.where(TacheSPI.statut == StatutTache(statut))
    if plan_id:
        query = query.where(TacheSPI.plan_strategique_id == plan_id)

    query = query.order_by(TacheSPI.date_fin_prevue.asc())
    result = await db.execute(query.limit(100))
    taches = result.scalars().all()

    emp_ids = list(set(t.assignee_id for t in taches))
    emp_map = await _get_employee_map(db, emp_ids)

    # Get offres for these tasks
    task_ids = [t.id for t in taches]
    offre_result = await db.execute(
        select(OffrePerformance).where(OffrePerformance.tache_id.in_(task_ids))
    ) if task_ids else None
    offre_map = {}
    if offre_result:
        for o in offre_result.scalars().all():
            offre_map[o.tache_id] = o

    return [
        {
            "id": t.id,
            "reference": t.reference,
            "titre": t.titre,
            "description": t.description,
            "statut": t.statut.value,
            "priorite": t.priorite.value if t.priorite else "NORMALE",
            "source_type": t.source_type.value if t.source_type else None,
            "assignee_id": t.assignee_id,
            "assignee_nom": _emp_name(emp_map, t.assignee_id),
            "date_fin_prevue": t.date_fin_prevue.isoformat() if t.date_fin_prevue else None,
            "date_fin_reelle": t.date_fin_reelle.isoformat() if t.date_fin_reelle else None,
            "jours_restants": (t.date_fin_prevue - date.today()).days if t.date_fin_prevue else None,
            "en_retard": t.date_fin_prevue < date.today() if t.date_fin_prevue and t.statut not in (StatutTache.VALIDEE, StatutTache.ANNULEE) else False,
            "score_execution": float(t.score_execution) if t.score_execution else None,
            "score_qualite": float(t.score_qualite) if t.score_qualite else None,
            "manager_rating": t.manager_rating,
            "offre": {
                "bonus_pct": float(offre_map[t.id].bonus_final_pct or offre_map[t.id].bonus_propose_pct),
                "bonus_da": float(offre_map[t.id].bonus_final_da or offre_map[t.id].bonus_propose_da or 0),
                "statut": offre_map[t.id].statut.value,
                "resultat": offre_map[t.id].resultat.value if offre_map[t.id].resultat else None,
            } if t.id in offre_map else None,
            "plan_strategique_id": t.plan_strategique_id,
            "projet_id": t.projet_id,
        }
        for t in taches
    ]


@router.get("/taches/{tache_id}")
async def get_tache(
    tache_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get task detail."""
    tache = await _get_tache(db, user.tenant_id, tache_id)
    emp_map = await _get_employee_map(db, [tache.assignee_id])

    offre_result = await db.execute(
        select(OffrePerformance).where(OffrePerformance.tache_id == tache.id)
    )
    offre = offre_result.scalar_one_or_none()

    return {
        "id": tache.id,
        "reference": tache.reference,
        "titre": tache.titre,
        "description": tache.description,
        "criteres_acceptation": tache.criteres_acceptation,
        "statut": tache.statut.value,
        "priorite": tache.priorite.value if tache.priorite else "NORMALE",
        "source_type": tache.source_type.value if tache.source_type else None,
        "assignee_id": tache.assignee_id,
        "assignee_nom": _emp_name(emp_map, tache.assignee_id),
        "date_fin_prevue": tache.date_fin_prevue.isoformat() if tache.date_fin_prevue else None,
        "date_fin_reelle": tache.date_fin_reelle.isoformat() if tache.date_fin_reelle else None,
        "score_execution": float(tache.score_execution) if tache.score_execution else None,
        "score_qualite": float(tache.score_qualite) if tache.score_qualite else None,
        "score_global_tache": float(tache.score_global_tache) if tache.score_global_tache else None,
        "manager_rating": tache.manager_rating,
        "commentaire_manager": tache.commentaire_manager,
        "valide_par_systeme": tache.valide_par_systeme,
        "valide_par_manager": tache.valide_par_manager,
        "kpis": tache.kpis,
        "preuves": tache.preuves,
        "est_contestee": tache.est_contestee,
        "offre": {
            "id": offre.id,
            "bonus_propose_pct": float(offre.bonus_propose_pct),
            "bonus_propose_da": float(offre.bonus_propose_da or 0),
            "bonus_contre_offre_pct": float(offre.bonus_contre_offre_pct) if offre.bonus_contre_offre_pct else None,
            "bonus_final_pct": float(offre.bonus_final_pct) if offre.bonus_final_pct else None,
            "bonus_final_da": float(offre.bonus_final_da) if offre.bonus_final_da else None,
            "malus_final_da": float(offre.malus_final_da) if offre.malus_final_da else None,
            "statut": offre.statut.value,
            "resultat": offre.resultat.value if offre.resultat else None,
            "montant_applique": float(offre.montant_applique) if offre.montant_applique else None,
        } if offre else None,
    }


@router.put("/taches/{tache_id}/demarrer")
async def demarrer_tache(
    tache_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Employee starts working on a task."""
    tache = await _get_tache(db, user.tenant_id, tache_id)
    if tache.statut not in (StatutTache.ASSIGNEE, StatutTache.VERROUILLEE, StatutTache.OFFRE_EN_COURS):
        raise HTTPException(status_code=400, detail=f"Impossible de démarrer — statut actuel: {tache.statut.value}")
    tache.statut = StatutTache.EN_COURS
    tache.date_debut_reelle = date.today()
    await db.commit()
    return {"id": tache.id, "statut": tache.statut.value}


@router.put("/taches/{tache_id}/livrer")
async def livrer_tache(
    tache_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Employee marks task as delivered — moves to review."""
    tache = await _get_tache(db, user.tenant_id, tache_id)
    if tache.statut not in (StatutTache.EN_COURS, StatutTache.VERROUILLEE):
        raise HTTPException(status_code=400, detail=f"Impossible de livrer — statut actuel: {tache.statut.value}")
    tache.statut = StatutTache.EN_REVUE
    tache.date_fin_reelle = date.today()
    # System auto-validation: check deadline
    if tache.date_fin_prevue:
        delta = (tache.date_fin_reelle - tache.date_fin_prevue).days
        if delta <= 0:
            tache.score_execution = 100
        elif delta <= 2:
            tache.score_execution = 75
        elif delta <= 7:
            tache.score_execution = 50
        else:
            tache.score_execution = 25
        tache.valide_par_systeme = delta <= 7
    await db.commit()
    return {"id": tache.id, "statut": tache.statut.value, "score_execution": float(tache.score_execution or 0)}


@router.post("/taches/{tache_id}/ai-evaluate")
async def ai_evaluate_tache_proof(
    tache_id: str,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI evaluation of proof submitted for a TacheSPI.

    Sets score_qualite and valide_par_systeme on the task,
    which feeds into the C2 (Quality) component of SPI.
    """
    tache = await _get_tache(db, user.tenant_id, tache_id)
    if tache.statut != StatutTache.EN_REVUE:
        raise HTTPException(status_code=400, detail=f"Task not in review — statut: {tache.statut.value}")

    if not tache.preuves:
        raise HTTPException(status_code=400, detail="No proof documents attached to this task")

    from app.services.proof_evaluator import evaluate_tache_spi_proof
    score, note, quality_score, system_validated = await evaluate_tache_spi_proof(tache, db)

    await db.commit()
    return {
        "tache_id": tache.id,
        "ai_score": score,
        "ai_note": note,
        "quality_score": quality_score,
        "system_validated": system_validated,
        "score_qualite": float(tache.score_qualite or 0),
    }


@router.put("/taches/{tache_id}/valider")
async def valider_tache(
    tache_id: str,
    body: TacheValidation,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manager validates or rejects a delivered task."""
    tache = await _get_tache(db, user.tenant_id, tache_id)
    if tache.statut != StatutTache.EN_REVUE:
        raise HTTPException(status_code=400, detail=f"Task not in review — statut: {tache.statut.value}")

    if body.decision == "VALIDEE":
        tache.statut = StatutTache.VALIDEE
        tache.valide_par_manager = True
        if body.rating:
            tache.manager_rating = body.rating
            tache.score_qualite = body.rating / 5.0 * 100
        else:
            tache.score_qualite = 80
        # Global score
        exec_score = float(tache.score_execution or 80)
        qual_score = float(tache.score_qualite or 80)
        tache.score_global_tache = round((exec_score * 0.5 + qual_score * 0.5), 2)
    elif body.decision == "REJETEE":
        tache.statut = StatutTache.REJETEE
        tache.valide_par_manager = False
        tache.score_qualite = 0
        tache.score_global_tache = 0

    tache.commentaire_manager = body.commentaire
    tache.date_validation = datetime.utcnow()

    # Process linked performance offer
    offre_result = await db.execute(
        select(OffrePerformance).where(
            OffrePerformance.tache_id == tache.id,
            OffrePerformance.statut == StatutOffre.VERROUILLEE,
        )
    )
    offre = offre_result.scalar_one_or_none()
    if offre:
        await process_offre_result(db, offre, tache)

    await db.commit()
    return {"id": tache.id, "statut": tache.statut.value, "score_global": float(tache.score_global_tache or 0)}


# ── Offres de Performance ─────────────────────────────────────────────────

@router.post("/taches/{tache_id}/offre", status_code=status.HTTP_201_CREATED)
async def proposer_offre(
    tache_id: str,
    body: OffreCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Employee proposes a bonus/malus offer for a task."""
    tache = await _get_tache(db, user.tenant_id, tache_id)
    emp = await _get_employee_for_user(db, user)

    if tache.assignee_id != emp.id:
        raise HTTPException(status_code=403, detail="Seul l'assigné peut proposer une offre")

    if not emp.avenant_spi_signe:
        raise HTTPException(status_code=400, detail="Avenant SPI non signé — impossible de proposer une offre")

    # Calculate amounts
    prime_plafond = float(emp.prime_spi_plafond or 0)
    bonus_da = round(prime_plafond * body.bonus_propose_pct / 100, 2)

    offre = OffrePerformance(
        tenant_id=user.tenant_id,
        tache_id=tache.id,
        employe_id=emp.id,
        bonus_propose_pct=body.bonus_propose_pct,
        bonus_propose_da=bonus_da,
        delai_propose=date.fromisoformat(body.delai_propose) if body.delai_propose else None,
        justification_employe=body.justification,
        statut=StatutOffre.PROPOSEE,
    )
    db.add(offre)
    tache.statut = StatutTache.OFFRE_EN_COURS
    await db.commit()
    await db.refresh(offre)

    return {
        "id": offre.id,
        "bonus_propose_pct": float(offre.bonus_propose_pct),
        "bonus_propose_da": float(offre.bonus_propose_da),
        "malus_identique_da": float(offre.bonus_propose_da),  # symmetric
        "statut": offre.statut.value,
    }


@router.put("/offres/{offre_id}/contre-offre")
async def contre_offre(
    offre_id: str,
    body: OffreContreOffre,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Manager makes a counter-offer."""
    result = await db.execute(
        select(OffrePerformance).where(
            OffrePerformance.id == offre_id,
            OffrePerformance.tenant_id == user.tenant_id,
        )
    )
    offre = result.scalar_one_or_none()
    if not offre:
        raise HTTPException(status_code=404, detail="Offre not found")

    offre.bonus_contre_offre_pct = body.bonus_contre_offre_pct
    offre.justification_manager = body.justification
    offre.date_contre_offre = datetime.utcnow()
    offre.statut = StatutOffre.CONTRE_OFFRE
    await db.commit()
    return {"id": offre.id, "statut": offre.statut.value}


@router.put("/offres/{offre_id}/accepter")
async def accepter_offre(
    offre_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Employee or manager accepts the offer — locks it."""
    result = await db.execute(
        select(OffrePerformance).where(
            OffrePerformance.id == offre_id,
            OffrePerformance.tenant_id == user.tenant_id,
        )
    )
    offre = result.scalar_one_or_none()
    if not offre:
        raise HTTPException(status_code=404, detail="Offre not found")

    # Determine final pct
    final_pct = float(offre.bonus_contre_offre_pct or offre.bonus_propose_pct)

    # Get employee to calculate amount
    emp_result = await db.execute(select(Employee).where(Employee.id == offre.employe_id))
    emp = emp_result.scalar_one_or_none()
    prime_plafond = float(emp.prime_spi_plafond or 0) if emp else 0
    final_da = round(prime_plafond * final_pct / 100, 2)

    offre.bonus_final_pct = final_pct
    offre.bonus_final_da = final_da
    offre.malus_final_da = final_da  # SYMMETRIC
    offre.statut = StatutOffre.VERROUILLEE
    offre.date_verrouillage = datetime.utcnow()
    offre.signature_employe = True
    offre.signature_manager = True

    # Update task status
    tache_result = await db.execute(select(TacheSPI).where(TacheSPI.id == offre.tache_id))
    tache = tache_result.scalar_one_or_none()
    if tache and tache.statut == StatutTache.OFFRE_EN_COURS:
        tache.statut = StatutTache.VERROUILLEE

    await db.commit()
    return {
        "id": offre.id,
        "bonus_final_pct": final_pct,
        "bonus_final_da": final_da,
        "malus_final_da": final_da,
        "statut": offre.statut.value,
    }


# ── SPI Mensuel ────────────────────────────────────────────────────────────

@router.post("/spi-mensuel/compute")
async def compute_spi_month(
    mois: str = Query(..., description="Format YYYY-MM"),
    employee_id: Optional[str] = Query(None),
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Compute monthly SPI for one or all employees."""
    if employee_id:
        emp_result = await db.execute(select(Employee).where(Employee.id == employee_id))
        emp = emp_result.scalar_one_or_none()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        spi = await compute_spi_mensuel(db, emp, mois)
        db.add(spi)
        await db.commit()
        return {"count": 1, "score": float(spi.score_spi)}
    else:
        scores = await compute_spi_batch_mensuel(db, user.tenant_id, mois)
        await db.commit()
        return {"count": len(scores)}


@router.get("/spi-mensuel")
async def list_spi_mensuel(
    mois: Optional[str] = Query(None),
    employee_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List monthly SPI scores."""
    query = select(SPIMensuel).where(SPIMensuel.tenant_id == user.tenant_id)
    if mois:
        query = query.where(SPIMensuel.mois == mois)
    if employee_id:
        query = query.where(SPIMensuel.employe_id == employee_id)
    query = query.order_by(SPIMensuel.mois.desc()).limit(100)

    result = await db.execute(query)
    spis = result.scalars().all()

    emp_ids = list(set(s.employe_id for s in spis))
    emp_map = await _get_employee_map(db, emp_ids)

    return [
        {
            "id": s.id,
            "employe_id": s.employe_id,
            "employe_nom": _emp_name(emp_map, s.employe_id),
            "mois": s.mois,
            "c1_execution": float(s.c1_execution),
            "c2_qualite": float(s.c2_qualite),
            "c3_comportement": float(s.c3_comportement),
            "c4_metier": float(s.c4_metier),
            "w1": float(s.w1), "w2": float(s.w2), "w3": float(s.w3), "w4": float(s.w4),
            "score_spi": float(s.score_spi),
            "fiabilite_score": float(s.fiabilite_score),
            "est_confirme": s.est_confirme,
            "prime_calculee": float(s.prime_calculee or 0),
            "solde_bm_mois": float(s.solde_bm_mois or 0),
            "taches_total": s.taches_total,
            "taches_validees": s.taches_validees,
            "taches_rejetees": s.taches_rejetees,
            "taches_en_retard": s.taches_en_retard,
            "valide_par_manager": s.valide_par_manager,
        }
        for s in spis
    ]


@router.put("/spi-mensuel/{spi_id}/confirmer")
async def confirmer_spi(
    spi_id: str,
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Manager confirms a monthly SPI score."""
    result = await db.execute(
        select(SPIMensuel).where(SPIMensuel.id == spi_id, SPIMensuel.tenant_id == user.tenant_id)
    )
    spi = result.scalar_one_or_none()
    if not spi:
        raise HTTPException(status_code=404, detail="SPI mensuel not found")

    manager = await _get_employee_for_user(db, user)
    spi.est_confirme = True
    spi.valide_par_manager = True
    spi.valideur_id = manager.id
    spi.date_validation = datetime.utcnow()

    # Check sub-performance after confirmation
    alerts = await check_sous_performance(db, user.tenant_id, spi.mois)

    await db.commit()
    return {"id": spi.id, "est_confirme": True, "alerts": alerts}


# ── Paie ───────────────────────────────────────────────────────────────────

@router.get("/paie/prevision")
async def prevision_paie(
    mois: str = Query(..., description="Format YYYY-MM"),
    employee_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get payroll preview for one or all employees."""
    if employee_id:
        emp_result = await db.execute(select(Employee).where(Employee.id == employee_id))
        emp = emp_result.scalar_one_or_none()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        return await compute_paie_employe(db, emp, mois)
    else:
        emps_result = await db.execute(
            select(Employee).where(
                Employee.tenant_id == user.tenant_id,
                Employee.status == EmploymentStatus.ACTIVE,
            )
        )
        employees = emps_result.scalars().all()
        results = []
        total_brut = 0
        total_net = 0
        for emp in employees:
            paie = await compute_paie_employe(db, emp, mois)
            results.append(paie)
            total_brut += paie["brut"]
            total_net += paie["net"]

        return {
            "mois": mois,
            "effectif": len(results),
            "total_brut": round(total_brut, 2),
            "total_net": round(total_net, 2),
            "fiches": results,
        }


# ── Dashboards ─────────────────────────────────────────────────────────────

@router.get("/dashboard/employe")
async def dashboard_employe(
    mois: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Employee personal dashboard."""
    emp = await _get_employee_for_user(db, user)
    mois = mois or date.today().strftime("%Y-%m")
    return await get_dashboard_employe(db, emp, mois)


@router.get("/dashboard/manager")
async def dashboard_manager(
    mois: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manager team dashboard."""
    emp = await _get_employee_for_user(db, user)
    mois = mois or date.today().strftime("%Y-%m")
    return await get_dashboard_manager(db, emp, mois)


@router.get("/dashboard/direction")
async def dashboard_direction(
    mois: Optional[str] = Query(None),
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """DAF/CEO company dashboard."""
    mois = mois or date.today().strftime("%Y-%m")
    return await get_dashboard_daf(db, user.tenant_id, mois)


# ── Alertes RH ─────────────────────────────────────────────────────────────

@router.get("/alertes")
async def list_alertes(
    mois: Optional[str] = Query(None),
    non_traitees: bool = Query(True),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List HR alerts."""
    query = select(AlerteRH).where(AlerteRH.tenant_id == user.tenant_id)
    if mois:
        query = query.where(AlerteRH.mois_reference == mois)
    if non_traitees:
        query = query.where(AlerteRH.est_traitee == False)
    query = query.order_by(AlerteRH.created_at.desc()).limit(50)

    result = await db.execute(query)
    alertes = result.scalars().all()

    emp_ids = list(set(a.employe_id for a in alertes))
    emp_map = await _get_employee_map(db, emp_ids)

    return [
        {
            "id": a.id,
            "type": a.type_alerte.value,
            "message": a.message,
            "severite": a.severite,
            "employe_id": a.employe_id,
            "employe_nom": _emp_name(emp_map, a.employe_id),
            "mois": a.mois_reference,
            "score_spi": float(a.score_spi) if a.score_spi else None,
            "est_traitee": a.est_traitee,
            "date": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alertes
    ]


@router.put("/alertes/{alerte_id}/traiter")
async def traiter_alerte(
    alerte_id: str,
    notes: Optional[str] = Query(None),
    user: User = Depends(require_role("admin", "hr_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Mark an alert as treated."""
    result = await db.execute(
        select(AlerteRH).where(AlerteRH.id == alerte_id, AlerteRH.tenant_id == user.tenant_id)
    )
    alerte = result.scalar_one_or_none()
    if not alerte:
        raise HTTPException(status_code=404, detail="Alerte not found")

    emp = await _get_employee_for_user(db, user)
    alerte.est_traitee = True
    alerte.traitee_par = emp.id
    alerte.date_traitement = datetime.utcnow()
    alerte.notes = notes
    await db.commit()
    return {"id": alerte.id, "est_traitee": True}


# ── Commissions ────────────────────────────────────────────────────────────

@router.post("/commissions/calculer")
async def calculer_commission(
    montant: float = Query(...),
    mode_paiement: str = Query("CASH_100"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Calculate commission split for a sale."""
    return compute_commission(montant, mode_paiement)


# ── Private helpers ────────────────────────────────────────────────────────

async def _get_employee_for_user(db: AsyncSession, user: User) -> Employee:
    """Get the Employee record linked to the current user."""
    result = await db.execute(
        select(Employee).where(Employee.user_id == user.id)
    )
    emp = result.scalar_one_or_none()
    if not emp:
        # Fallback: create a minimal employee record
        result = await db.execute(
            select(Employee).where(Employee.tenant_id == user.tenant_id).limit(1)
        )
        emp = result.scalar_one_or_none()
        if not emp:
            emp = Employee(
                id=str(uuid.uuid4()),
                tenant_id=user.tenant_id,
                employee_number="AUTO-" + user.id[:8],
                first_name=user.full_name.split()[0] if user.full_name else "Admin",
                last_name=" ".join(user.full_name.split()[1:]) if user.full_name and len(user.full_name.split()) > 1 else "",
                email=user.email,
                user_id=user.id,
                base_salary=0,
                status=EmploymentStatus.ACTIVE,
            )
            db.add(emp)
            await db.flush()
    return emp


async def _get_employee_map(db: AsyncSession, emp_ids: list[str]) -> dict:
    if not emp_ids:
        return {}
    result = await db.execute(select(Employee).where(Employee.id.in_(emp_ids)))
    return {e.id: e for e in result.scalars().all()}


def _emp_name(emp_map: dict, emp_id: str) -> str:
    emp = emp_map.get(emp_id)
    return f"{emp.first_name} {emp.last_name}" if emp else ""


async def _get_plan(db: AsyncSession, tenant_id: str, plan_id: str) -> PlanStrategique:
    result = await db.execute(
        select(PlanStrategique).where(
            PlanStrategique.id == plan_id,
            PlanStrategique.tenant_id == tenant_id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


async def _get_tache(db: AsyncSession, tenant_id: str, tache_id: str) -> TacheSPI:
    result = await db.execute(
        select(TacheSPI).where(
            TacheSPI.id == tache_id,
            TacheSPI.tenant_id == tenant_id,
        )
    )
    tache = result.scalar_one_or_none()
    if not tache:
        raise HTTPException(status_code=404, detail="Tâche not found")
    return tache
