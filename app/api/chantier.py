"""Gestion de Projets & Chantiers API — Section 10.

Endpoints for:
  - Planning tasks with progress tracking (EX-PROJ-101)
  - Sous-traitants CRUD + performance scoring (EX-PROJ-103)
  - Situations de travaux with auto-debt generation (EX-PROJ-102)
  - Expert reports for VSP releases
"""
import uuid as _uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy import select, func as sa_func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User, AuditLog, JournalEntry, JournalLine, JournalEntryStatus
from app.models.financial import Projet
from app.models.chantier import (
    TacheChantier, StatutTache,
    SousTraitant,
    SituationTravaux, StatutSituation,
    RapportExpert,
)

router = APIRouter(tags=["Projets & Chantiers"])


async def _require_proof(
    file: Optional[UploadFile],
    action: str,
    context: dict,
    user: User,
    db: AsyncSession,
) -> dict:
    """Verify proof document via AI. Raises HTTPException if invalid."""
    if not file or not file.filename:
        raise HTTPException(400, "Document justificatif obligatoire pour cette action")
    from app.services.proof_verifier import verify_proof
    proof = await verify_proof(file, action, context, user.tenant_id, user.id, db)
    if not proof["verified"]:
        raise HTTPException(400, f"BLOCAGE : Document non conforme — {proof['rejection_reason']}")
    return proof


# ═══════════════════════════════════════════════════════════════════════════
# TACHES CHANTIER (EX-PROJ-101)
# ═══════════════════════════════════════════════════════════════════════════

class TacheCreate(BaseModel):
    projet_id: str
    code: str
    libelle: str
    categorie: Optional[str] = None
    date_debut_prevue: Optional[date] = None
    date_fin_prevue: Optional[date] = None
    budget_prevu: float = 0
    responsable_id: Optional[str] = None
    sous_traitant_id: Optional[str] = None
    tache_parent_id: Optional[str] = None


class TacheUpdate(BaseModel):
    avancement_pct: Optional[float] = None
    statut: Optional[str] = None
    date_debut_reelle: Optional[date] = None
    date_fin_reelle: Optional[date] = None
    cout_reel: Optional[float] = None
    notes: Optional[str] = None


@router.get("/taches")
async def list_taches(
    projet_id: Optional[str] = None,
    statut: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(TacheChantier).where(TacheChantier.tenant_id == user.tenant_id)
    if projet_id:
        q = q.where(TacheChantier.projet_id == projet_id)
    if statut:
        q = q.where(TacheChantier.statut == statut)
    q = q.order_by(TacheChantier.ordre, TacheChantier.code)
    result = await db.execute(q)
    return [_tache_dict(t) for t in result.scalars().all()]


@router.post("/taches", status_code=201)
async def create_tache(
    body: TacheCreate,
    file: Optional[UploadFile] = File(None, description="Justificatif (planning, bon de commande, contrat ST)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file and file.filename:
        await _require_proof(file, "creer_tache_chantier", {"action_detail": f"Tâche {body.code}: {body.libelle}", "montant": body.budget_prevu}, user, db)

    t = TacheChantier(
        tenant_id=user.tenant_id,
        projet_id=body.projet_id,
        code=body.code,
        libelle=body.libelle,
        categorie=body.categorie,
        date_debut_prevue=body.date_debut_prevue,
        date_fin_prevue=body.date_fin_prevue,
        budget_prevu=body.budget_prevu,
        responsable_id=body.responsable_id,
        sous_traitant_id=body.sous_traitant_id,
        tache_parent_id=body.tache_parent_id,
        created_by=user.id,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return _tache_dict(t)


@router.put("/taches/{tache_id}")
async def update_tache(
    tache_id: str,
    body: TacheUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update task progress. EX-PROJ-101: advancement drives VSP releases."""

    result = await db.execute(
        select(TacheChantier).where(TacheChantier.id == tache_id, TacheChantier.tenant_id == user.tenant_id)
    )
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Tâche introuvable")

    if body.avancement_pct is not None:
        t.avancement_pct = body.avancement_pct
        if body.avancement_pct >= 100:
            t.statut = StatutTache.TERMINE
            t.date_fin_reelle = t.date_fin_reelle or date.today()
        elif body.avancement_pct > 0 and t.statut == StatutTache.A_FAIRE:
            t.statut = StatutTache.EN_COURS
            t.date_debut_reelle = t.date_debut_reelle or date.today()
    if body.statut:
        t.statut = StatutTache(body.statut)
    if body.date_debut_reelle:
        t.date_debut_reelle = body.date_debut_reelle
    if body.date_fin_reelle:
        t.date_fin_reelle = body.date_fin_reelle
    if body.cout_reel is not None:
        t.cout_reel = body.cout_reel
    if body.notes is not None:
        t.notes = body.notes

    # Recalculate project-level advancement
    await _recalc_project_avancement(t.projet_id, db)

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="tache_update", entity_type="tache_chantier", entity_id=tache_id,
    ))
    await db.commit()
    return _tache_dict(t)


async def _recalc_project_avancement(projet_id: str, db: AsyncSession):
    """Recalculate project overall advancement from its tasks."""
    result = await db.execute(
        select(
            sa_func.avg(TacheChantier.avancement_pct),
            sa_func.count(TacheChantier.id),
        ).where(
            TacheChantier.projet_id == projet_id,
            TacheChantier.statut != StatutTache.ANNULE,
        )
    )
    row = result.one()
    avg = float(row[0] or 0)

    await db.execute(
        update(Projet).where(Projet.id == projet_id).values(taux_avancement=round(avg, 2))
    )


def _tache_dict(t: TacheChantier) -> dict:
    return {
        "id": t.id, "projet_id": t.projet_id, "code": t.code,
        "libelle": t.libelle, "categorie": t.categorie,
        "avancement_pct": float(t.avancement_pct or 0),
        "statut": t.statut.value if t.statut else None,
        "date_debut_prevue": str(t.date_debut_prevue) if t.date_debut_prevue else None,
        "date_fin_prevue": str(t.date_fin_prevue) if t.date_fin_prevue else None,
        "date_debut_reelle": str(t.date_debut_reelle) if t.date_debut_reelle else None,
        "date_fin_reelle": str(t.date_fin_reelle) if t.date_fin_reelle else None,
        "budget_prevu": float(t.budget_prevu or 0),
        "cout_reel": float(t.cout_reel or 0),
        "responsable_id": t.responsable_id,
        "sous_traitant_id": t.sous_traitant_id,
        "notes": t.notes,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SOUS-TRAITANTS (EX-PROJ-103)
# ═══════════════════════════════════════════════════════════════════════════

class STCreate(BaseModel):
    raison_sociale: str
    specialite: Optional[str] = None
    nif: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None


class STEvaluation(BaseModel):
    score_qualite: float = Field(ge=0, le=100)
    score_delais: float = Field(ge=0, le=100)
    score_securite: float = Field(ge=0, le=100)


@router.get("/sous-traitants")
async def list_sous_traitants(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SousTraitant)
        .where(SousTraitant.tenant_id == user.tenant_id)
        .order_by(SousTraitant.score_global.desc())
    )
    return [_st_dict(s) for s in result.scalars().all()]


@router.post("/sous-traitants", status_code=201)
async def create_sous_traitant(
    body: STCreate,
    file: UploadFile = File(..., description="Justificatif obligatoire (RC, NIF, attestation agrément, CACOBATPH)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file or not file.filename:
        raise HTTPException(400, "Un justificatif (registre commerce, NIF, agrément) est obligatoire.")
    await _require_proof(file, "creer_sous_traitant", {"action_detail": f"ST: {body.raison_sociale}"}, user, db)

    st = SousTraitant(
        tenant_id=user.tenant_id,
        raison_sociale=body.raison_sociale,
        specialite=body.specialite,
        nif=body.nif,
        telephone=body.telephone,
        email=body.email,
    )
    db.add(st)
    await db.commit()
    await db.refresh(st)
    return _st_dict(st)


@router.post("/sous-traitants/{st_id}/evaluer")
async def evaluer_sous_traitant(
    st_id: str,
    body: STEvaluation,
    file: Optional[UploadFile] = File(None, description="Rapport d'évaluation, PV de réception, photos"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Score a subcontractor. EX-PROJ-103: quality, deadlines, safety. Proof verified by AI."""
    if file and file.filename:
        await _require_proof(file, "evaluer_sous_traitant", {"action_detail": f"Évaluation ST {st_id}"}, user, db)

    result = await db.execute(
        select(SousTraitant).where(SousTraitant.id == st_id, SousTraitant.tenant_id == user.tenant_id)
    )
    st = result.scalar_one_or_none()
    if not st:
        raise HTTPException(404, "Sous-traitant introuvable")

    n = (st.nb_evaluations or 0)
    # Running average
    st.score_qualite = _running_avg(float(st.score_qualite or 50), body.score_qualite, n)
    st.score_delais = _running_avg(float(st.score_delais or 50), body.score_delais, n)
    st.score_securite = _running_avg(float(st.score_securite or 50), body.score_securite, n)
    st.score_global = round(st.score_qualite * 0.4 + st.score_delais * 0.35 + st.score_securite * 0.25, 2)
    st.nb_evaluations = n + 1

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="st_evaluation", entity_type="sous_traitant", entity_id=st_id,
    ))
    await db.commit()
    return _st_dict(st)


def _running_avg(old: float, new: float, n: int) -> float:
    if n == 0:
        return new
    return round((old * n + new) / (n + 1), 2)


def _st_dict(s: SousTraitant) -> dict:
    return {
        "id": s.id, "raison_sociale": s.raison_sociale,
        "specialite": s.specialite, "nif": s.nif,
        "telephone": s.telephone, "email": s.email,
        "score_qualite": float(s.score_qualite or 0),
        "score_delais": float(s.score_delais or 0),
        "score_securite": float(s.score_securite or 0),
        "score_global": float(s.score_global or 0),
        "nb_evaluations": s.nb_evaluations,
        "est_agree": s.est_agree, "is_active": s.is_active,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SITUATIONS DE TRAVAUX (EX-PROJ-102)
# ═══════════════════════════════════════════════════════════════════════════

class SituationCreate(BaseModel):
    projet_id: str
    entreprise_id: str
    sous_traitant_id: str
    numero: str
    periode: Optional[str] = None
    montant_ht: float = Field(gt=0)
    avancement_cumule_pct: float = Field(ge=0, le=100)
    avancement_periode_pct: float = Field(ge=0, le=100)
    realite_financiere: str = "RF1"
    notes: Optional[str] = None


@router.get("/situations")
async def list_situations(
    projet_id: Optional[str] = None,
    sous_traitant_id: Optional[str] = None,
    statut: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(SituationTravaux).where(SituationTravaux.tenant_id == user.tenant_id)
    if projet_id:
        q = q.where(SituationTravaux.projet_id == projet_id)
    if sous_traitant_id:
        q = q.where(SituationTravaux.sous_traitant_id == sous_traitant_id)
    if statut:
        q = q.where(SituationTravaux.statut == statut)
    q = q.order_by(SituationTravaux.created_at.desc())
    result = await db.execute(q)
    return [_sit_dict(s) for s in result.scalars().all()]


@router.post("/situations", status_code=201)
async def create_situation(
    body: SituationCreate,
    file: UploadFile = File(..., description="Document situation de travaux (PDF signé, attachement)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proof = await _require_proof(file, "situation_travaux", {"montant": body.montant_ht, "action_detail": f"Situation {body.numero}"}, user, db)

    ht = Decimal(str(body.montant_ht))
    tva = ht * Decimal("0.19")
    ttc = ht + tva
    retenue = ttc * Decimal("0.05")
    net = ttc - retenue

    sit = SituationTravaux(
        tenant_id=user.tenant_id,
        projet_id=body.projet_id,
        entreprise_id=body.entreprise_id,
        sous_traitant_id=body.sous_traitant_id,
        numero=body.numero,
        periode=body.periode,
        montant_ht=ht,
        montant_tva=tva,
        montant_ttc=ttc,
        retenue_garantie=retenue,
        montant_net=net,
        avancement_cumule_pct=body.avancement_cumule_pct,
        avancement_periode_pct=body.avancement_periode_pct,
        realite_financiere=body.realite_financiere,
        notes=body.notes,
        created_by=user.id,
    )
    db.add(sit)
    await db.commit()
    await db.refresh(sit)
    return _sit_dict(sit)


@router.post("/situations/{situation_id}/valider")
async def valider_situation(
    situation_id: str,
    file: UploadFile = File(..., description="PV de validation signé, attachement de situation approuvé"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate a work situation. EX-PROJ-102: auto-generates debt + cost center charge.

    Creates journal entry: D 605 (travaux ST) / C 401 (fournisseur).
    Requires signed validation proof.
    """
    result = await db.execute(
        select(SituationTravaux).where(
            SituationTravaux.id == situation_id,
            SituationTravaux.tenant_id == user.tenant_id,
        )
    )
    sit = result.scalar_one_or_none()
    if not sit:
        raise HTTPException(404, "Situation introuvable")
    if sit.statut != StatutSituation.SOUMISE and sit.statut != StatutSituation.BROUILLON:
        raise HTTPException(400, f"Impossible de valider : statut {sit.statut.value}")

    await _require_proof(file, "valider_situation_travaux", {"montant": float(sit.montant_ht or 0), "action_detail": f"Validation situation {sit.numero}"}, user, db)

    sit.statut = StatutSituation.VALIDEE
    sit.validee_par = user.id
    sit.date_validation = datetime.utcnow()

    # Auto-generate journal entry (EX-PROJ-102)
    je = JournalEntry(
        id=str(_uuid.uuid4()),
        tenant_id=user.tenant_id,
        entreprise_id=sit.entreprise_id,
        entry_date=datetime.utcnow(),
        reference=f"SIT-{sit.numero}",
        description=f"Situation travaux {sit.numero} — ST validée",
        status=JournalEntryStatus.COMMITTED,
        realite_financiere=sit.realite_financiere,
        auto_generated=True,
    )
    db.add(je)
    await db.flush()
    sit.journal_entry_id = je.id

    # D 605 (travaux) + D 4456 (TVA déductible) / C 401 (fournisseur)
    lines = [
        ("605", f"Travaux ST — {sit.numero}", sit.montant_ht, Decimal(0)),
        ("4456", f"TVA déductible — {sit.numero}", sit.montant_tva, Decimal(0)),
        ("401", f"Fournisseur ST — {sit.numero}", Decimal(0), sit.montant_ttc),
    ]
    for i, (acc, label, d, c) in enumerate(lines, 1):
        db.add(JournalLine(
            id=str(_uuid.uuid4()),
            entry_id=je.id, line_no=i,
            account_code=acc, label=label,
            debit=d, credit=c,
        ))

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="situation_validee", entity_type="situation_travaux", entity_id=situation_id,
    ))
    await db.commit()
    return {
        "statut": "VALIDEE",
        "journal_entry_id": je.id,
        "message": f"Situation {sit.numero} validée — écriture comptable générée automatiquement",
    }


@router.post("/situations/{situation_id}/rejeter")
async def rejeter_situation(
    situation_id: str,
    motif: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SituationTravaux).where(
            SituationTravaux.id == situation_id,
            SituationTravaux.tenant_id == user.tenant_id,
        )
    )
    sit = result.scalar_one_or_none()
    if not sit:
        raise HTTPException(404, "Situation introuvable")

    sit.statut = StatutSituation.REJETEE
    sit.motif_rejet = motif
    await db.commit()
    return {"statut": "REJETEE", "motif": motif}


def _sit_dict(s: SituationTravaux) -> dict:
    return {
        "id": s.id, "projet_id": s.projet_id,
        "sous_traitant_id": s.sous_traitant_id,
        "numero": s.numero, "periode": s.periode,
        "montant_ht": float(s.montant_ht or 0),
        "montant_tva": float(s.montant_tva or 0),
        "montant_ttc": float(s.montant_ttc or 0),
        "retenue_garantie": float(s.retenue_garantie or 0),
        "montant_net": float(s.montant_net or 0),
        "avancement_cumule_pct": float(s.avancement_cumule_pct or 0),
        "avancement_periode_pct": float(s.avancement_periode_pct or 0),
        "statut": s.statut.value if s.statut else None,
        "realite_financiere": s.realite_financiere,
        "journal_entry_id": s.journal_entry_id,
        "notes": s.notes,
    }


# ═══════════════════════════════════════════════════════════════════════════
# RAPPORTS D'EXPERT (VSP fund releases)
# ═══════════════════════════════════════════════════════════════════════════

class RapportCreate(BaseModel):
    projet_id: str
    numero: str
    date_visite: date
    avancement_constate_pct: float = Field(ge=0, le=100)
    palier_vsp: Optional[int] = None
    observations: Optional[str] = None


@router.get("/rapports-expert")
async def list_rapports(
    projet_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(RapportExpert).where(RapportExpert.tenant_id == user.tenant_id)
    if projet_id:
        q = q.where(RapportExpert.projet_id == projet_id)
    q = q.order_by(RapportExpert.date_visite.desc())
    result = await db.execute(q)
    return [
        {
            "id": r.id, "projet_id": r.projet_id, "numero": r.numero,
            "date_visite": str(r.date_visite),
            "avancement_constate_pct": float(r.avancement_constate_pct or 0),
            "palier_vsp": r.palier_vsp, "observations": r.observations,
            "est_valide": r.est_valide,
        }
        for r in result.scalars().all()
    ]


@router.post("/rapports-expert", status_code=201)
async def create_rapport(
    body: RapportCreate,
    file: UploadFile = File(..., description="Rapport d'expert (PDF signé)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proof = await _require_proof(file, "rapport_expert", {"action_detail": f"Rapport expert {body.numero}, avancement {body.avancement_constate_pct}%"}, user, db)

    r = RapportExpert(
        tenant_id=user.tenant_id,
        projet_id=body.projet_id,
        numero=body.numero,
        date_visite=body.date_visite,
        avancement_constate_pct=body.avancement_constate_pct,
        palier_vsp=body.palier_vsp,
        observations=body.observations,
        document_id=proof.get("document_id"),
        created_by=user.id,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return {"id": r.id, "numero": r.numero, "avancement_constate_pct": float(r.avancement_constate_pct)}


@router.post("/rapports-expert/{rapport_id}/valider")
async def valider_rapport(
    rapport_id: str,
    file: UploadFile = File(..., description="Preuve de validation (PV signé, attestation)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate an expert report. Triggers VSP fund release (EX-ADV-003). Proof required."""
    result = await db.execute(
        select(RapportExpert).where(RapportExpert.id == rapport_id, RapportExpert.tenant_id == user.tenant_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Rapport introuvable")

    await _require_proof(file, "valider_rapport_expert", {"action_detail": f"Validation rapport {r.numero}, avancement {r.avancement_constate_pct}%"}, user, db)

    r.est_valide = True
    r.valide_par = user.id

    # Update project advancement
    await db.execute(
        update(Projet).where(Projet.id == r.projet_id).values(taux_avancement=r.avancement_constate_pct)
    )

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="rapport_expert_valide", entity_type="rapport_expert", entity_id=rapport_id,
    ))
    await db.commit()
    return {
        "statut": "VALIDE",
        "avancement_constate_pct": float(r.avancement_constate_pct),
        "palier_vsp": r.palier_vsp,
        "message": "Rapport validé — avancement projet mis à jour",
    }


# ═══════════════════════════════════════════════════════════════════════════
# ── AI PLANNING AGENT ─────────────────────────────────────────────────────

@router.post("/taches/ai-plan")
async def ai_plan_task(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI agent that creates a project plan from a task description.

    Asks the user for any missing information (budget, dates, resources).
    Returns a structured plan with subtasks.
    """
    description = body.get("description", "").strip()
    budget = body.get("budget")
    date_debut = body.get("date_debut")
    date_fin = body.get("date_fin")
    projet_id = body.get("projet_id")

    if not description or len(description) < 10:
        raise HTTPException(400, "Description trop courte (min 10 caractères)")

    # Build context about existing project tasks
    existing_tasks = []
    if projet_id:
        result = await db.execute(
            select(TacheChantier.code, TacheChantier.libelle, TacheChantier.statut, TacheChantier.avancement_pct)
            .where(TacheChantier.projet_id == projet_id)
            .limit(20)
        )
        existing_tasks = [{"code": r[0], "libelle": r[1], "statut": r[2], "avancement": float(r[3] or 0)} for r in result.all()]

    system_prompt = """\
Tu es un planificateur de chantier expert pour Groupe Dendani (promotion immobilière en Algérie).

RÈGLES:
1. Analyse la description de la tâche et crée un plan détaillé
2. Si des informations manquent (budget, dates, ressources), liste-les dans "missing_info"
3. Décompose en sous-tâches logiques avec des codes structurés
4. Estime les durées et budgets si possible
5. Réponds toujours en français

Réponds en JSON:
{
  "plan_title": "Titre du plan",
  "missing_info": ["liste des informations manquantes à demander à l'utilisateur"],
  "tasks": [
    {
      "code": "TCH-001",
      "libelle": "Description de la sous-tâche",
      "categorie": "GROS_OEUVRE|SECOND_OEUVRE|VRD|ELECTRICITE|PLOMBERIE|FINITIONS|ADMIN",
      "duree_jours": nombre estimé,
      "budget_estime": montant en DA ou null,
      "dependances": ["codes des tâches précédentes"],
      "priorite": "HAUTE|NORMALE|BASSE"
    }
  ],
  "budget_total_estime": montant total estimé ou null,
  "duree_totale_jours": durée totale estimée,
  "recommandations": "Conseils et points d'attention"
}
Pas de blocs markdown."""

    context_parts = [f"Description: {description}"]
    if budget:
        context_parts.append(f"Budget alloué: {budget} DA")
    if date_debut:
        context_parts.append(f"Date début prévue: {date_debut}")
    if date_fin:
        context_parts.append(f"Date fin prévue: {date_fin}")
    if existing_tasks:
        context_parts.append(f"Tâches existantes du projet: {existing_tasks}")

    try:
        from app.services.llm_graph import invoke_json_agent
        ai_result = await invoke_json_agent(
            system_prompt=system_prompt,
            user_prompt="\n".join(context_parts),
            temperature=0.2,
            max_tokens=1500,
        )
        return ai_result.get("parsed_json", {"error": "Réponse IA invalide"})
    except Exception as exc:
        return {
            "plan_title": "Plan non disponible",
            "missing_info": [],
            "tasks": [],
            "recommandations": f"Service IA indisponible: {exc}",
        }


# PROJECT DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def chantier_dashboard(
    projet_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Project/construction dashboard with KPIs."""
    conditions = [TacheChantier.tenant_id == user.tenant_id]
    if projet_id:
        conditions.append(TacheChantier.projet_id == projet_id)

    # Task stats
    task_r = await db.execute(
        select(
            sa_func.count(TacheChantier.id),
            sa_func.avg(TacheChantier.avancement_pct),
            sa_func.sum(TacheChantier.budget_prevu),
            sa_func.sum(TacheChantier.cout_reel),
        ).where(*conditions)
    )
    row = task_r.one()

    # Situation stats
    sit_conditions = [SituationTravaux.tenant_id == user.tenant_id]
    if projet_id:
        sit_conditions.append(SituationTravaux.projet_id == projet_id)
    sit_r = await db.execute(
        select(
            sa_func.count(SituationTravaux.id),
            sa_func.coalesce(sa_func.sum(SituationTravaux.montant_ttc), 0),
        ).where(*sit_conditions, SituationTravaux.statut == StatutSituation.VALIDEE)
    )
    sit_row = sit_r.one()

    return {
        "taches_total": row[0] or 0,
        "avancement_moyen": round(float(row[1] or 0), 1),
        "budget_prevu_total": float(row[2] or 0),
        "cout_reel_total": float(row[3] or 0),
        "ecart_budget": float((row[2] or 0) - (row[3] or 0)),
        "situations_validees": sit_row[0] or 0,
        "montant_situations_ttc": float(sit_row[1] or 0),
    }
