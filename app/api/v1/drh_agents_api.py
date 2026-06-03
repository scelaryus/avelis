"""API endpoints for all 21 DRH agents + supporting agents.
Each endpoint calls the real agent function and returns structured results."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.v1.deps import get_current_user, CurrentUser, get_db
from app.api.v1.schemas import ApiResponse
from app.agents.drh_agents import (
    agent_dossier_check, agent_contrats_generate, agent_temps_aggregate,
    agent_recrutement_generate_listing, agent_recrutement_generate_profile,
    agent_recrutement_score_cv, agent_recrutement_batch, agent_formation_plan,
    agent_ged_classify, agent_materiel_onboarding, agent_acces_configure,
    agent_disciplinaire_evaluate, agent_messagerie_send, agent_bi_generate,
    agent_declarations_prepare, agent_prets_eligibility, agent_vision_analyze,
    agent_carriere_suggest, agent_securite_check, agent_visiteurs_register,
)

router = APIRouter(prefix="/agents/drh", tags=["DRH Agents"])


@router.post("/dossier/check")
async def check_dossier(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Dossier: check employee file completeness."""
    return ApiResponse(data=agent_dossier_check(body))


@router.post("/contrats/generate")
async def generate_contract(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Contrats: generate contract from template."""
    return ApiResponse(data=agent_contrats_generate(body.get("employee", {}), body.get("contract_type", "CDI")))


@router.post("/temps/aggregate")
async def aggregate_time(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Temps: aggregate attendance for a month."""
    return ApiResponse(data=agent_temps_aggregate(body.get("employee_id", ""), body.get("month", "")))


@router.post("/recrutement/generate-listing")
async def generate_job_listing(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Generate a LinkedIn-style job listing ready to post.
    Body: {job_position, description?, contract_type?, location?}"""
    job_position = body.get("job_position", "")
    if not job_position:
        raise HTTPException(400, "job_position requis")
    return ApiResponse(data=agent_recrutement_generate_listing(
        job_position,
        body.get("description", ""),
        body.get("contract_type", "CDI"),
        body.get("location", "Bab Ezzouar, Alger"),
    ))


@router.post("/recrutement/generate-profile")
async def generate_job_profile(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Recrutement: generate required skills and criteria for a job position using AI.
    Body: {job_position: "Chef de chantier"}. Returns skills, experience, salary range."""
    job_position = body.get("job_position", "")
    if not job_position:
        raise HTTPException(400, "job_position requis")
    return ApiResponse(data=agent_recrutement_generate_profile(job_position))


@router.post("/recrutement/score-cv")
async def score_cv(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Recrutement: score a single CV for a job position using AI.
    Body: {cv_text, job_position, job_requirements?}"""
    cv_text = body.get("cv_text", "")
    job_position = body.get("job_position", body.get("requirements", ""))
    if not cv_text:
        raise HTTPException(400, "cv_text requis")
    if not job_position:
        raise HTTPException(400, "job_position requis (ex: 'Chef de chantier')")
    return ApiResponse(data=agent_recrutement_score_cv(cv_text, job_position, body.get("job_requirements", "")))


@router.post("/recrutement/batch")
async def batch_score_cvs(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Recrutement: score multiple CVs for the same position. Returns ranked list.
    Body: {cvs: [{text: "..."}], job_position: "...", job_requirements?: "..."}"""
    cvs = body.get("cvs", [])
    job_position = body.get("job_position", "")
    if not cvs:
        raise HTTPException(400, "cvs requis (liste de {text: '...'})")
    if not job_position:
        raise HTTPException(400, "job_position requis")
    cv_texts = [c.get("text", c) if isinstance(c, dict) else str(c) for c in cvs]
    results = agent_recrutement_batch(cv_texts, job_position, body.get("job_requirements", ""))
    return ApiResponse(data={
        "job_position": job_position,
        "total_candidates": len(results),
        "retained": sum(1 for r in results if r.get("recommendation") == "RETENU"),
        "reserved": sum(1 for r in results if r.get("recommendation") == "RESERVE"),
        "rejected": sum(1 for r in results if r.get("recommendation") == "REJETE"),
        "candidates": results,
    })


@router.post("/formation/plan")
async def training_plan(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Formation: create 30-day onboarding training plan."""
    return ApiResponse(data=agent_formation_plan(body.get("employee", {}), body.get("position", "")))


@router.post("/ged/classify")
async def classify_document(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent GED RH: classify and route HR document."""
    return ApiResponse(data=agent_ged_classify(body.get("document_text", "")))


@router.post("/materiel/onboarding")
async def equipment_list(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Materiel: generate equipment list for new hire."""
    return ApiResponse(data=agent_materiel_onboarding(body.get("position", "")))


@router.post("/acces/configure")
async def configure_access(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Acces: configure badge zones for employee."""
    return ApiResponse(data=agent_acces_configure(body.get("employee", {}), body.get("position", "")))


@router.post("/discipline/evaluate")
async def evaluate_infraction(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Disciplinaire: evaluate infraction severity using AI."""
    return ApiResponse(data=agent_disciplinaire_evaluate(body))


# ── Discipline CRUD + History ──────────────────────────────────────────────

@router.get("/discipline/cases")
async def list_discipline_cases(employee_id: str = None, status: str = None,
                                 db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """List all discipline cases with optional filters."""
    from app.models.core import DisciplineCase, Employee
    q = db.query(DisciplineCase).order_by(DisciplineCase.infraction_date.desc())
    if employee_id:
        q = q.filter(DisciplineCase.employee_id == employee_id)
    if status:
        q = q.filter(DisciplineCase.status == status)
    cases = q.limit(100).all()
    result = []
    for c in cases:
        emp = db.query(Employee).filter(Employee.id == c.employee_id).first()
        # Count total infractions for this employee
        total_for_emp = db.query(DisciplineCase).filter(DisciplineCase.employee_id == c.employee_id).count()
        result.append({
            "id": str(c.id),
            "employee_id": str(c.employee_id),
            "employee_name": f"{emp.last_name} {emp.first_name}" if emp else "?",
            "employee_matricule": emp.matricule if emp else "?",
            "employee_position": emp.position if emp else "?",
            "employee_total_infractions": total_for_emp,
            "infraction_date": str(c.infraction_date),
            "description": c.description,
            "severity_declared": c.severity_declared,
            "ai_severity": c.ai_severity,
            "ai_sanction_suggested": c.ai_sanction_suggested,
            "sanction_applied": c.sanction_applied,
            "sanction_duration_days": c.sanction_duration_days,
            "status": c.status,
            "reported_by": c.reported_by,
            "created_at": str(c.created_at),
        })
    return ApiResponse(data=result)


@router.get("/discipline/employee/{employee_id}/history")
async def employee_discipline_history(employee_id: str, db: Session = Depends(get_db),
                                       user: CurrentUser = Depends(get_current_user)):
    """Full discipline history for one employee."""
    from app.models.core import DisciplineCase, Employee
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employe introuvable")

    cases = db.query(DisciplineCase).filter(
        DisciplineCase.employee_id == employee_id
    ).order_by(DisciplineCase.infraction_date.desc()).all()

    history = []
    for c in cases:
        history.append({
            "id": str(c.id),
            "infraction_date": str(c.infraction_date),
            "infraction_time": c.infraction_time,
            "infraction_location": c.infraction_location,
            "description": c.description,
            "witnesses": c.witnesses or [],
            "severity_declared": c.severity_declared,
            "ai_severity": c.ai_severity,
            "ai_sanction_suggested": c.ai_sanction_suggested,
            "ai_justification": c.ai_justification,
            "convocation_date": str(c.convocation_date) if c.convocation_date else None,
            "audition_date": str(c.audition_date) if c.audition_date else None,
            "audition_pv": c.audition_pv,
            "sanction_applied": c.sanction_applied,
            "sanction_duration_days": c.sanction_duration_days,
            "sanction_decided_by": c.sanction_decided_by,
            "sanction_decided_at": str(c.sanction_decided_at) if c.sanction_decided_at else None,
            "sanction_comment": c.sanction_comment,
            "status": c.status,
            "reported_by": c.reported_by,
            "evidence_count": len(c.evidence_document_ids or []),
        })

    # Summary stats
    avertissements = sum(1 for c in cases if c.sanction_applied == "AVERTISSEMENT")
    blames = sum(1 for c in cases if c.sanction_applied == "BLAME")
    mises_a_pied = sum(1 for c in cases if c.sanction_applied == "MISE_A_PIED")
    classees = sum(1 for c in cases if c.sanction_applied == "CLASSEE_SANS_SUITE")
    en_cours = sum(1 for c in cases if c.status not in ("CLOTURE",))

    return ApiResponse(data={
        "employee": {
            "id": str(emp.id), "name": f"{emp.last_name} {emp.first_name}",
            "matricule": emp.matricule, "position": emp.position,
        },
        "summary": {
            "total": len(cases), "avertissements": avertissements, "blames": blames,
            "mises_a_pied": mises_a_pied, "classees": classees, "en_cours": en_cours,
            "risk_level": "CRITIQUE" if mises_a_pied > 0 or len(cases) >= 3 else "ALERTE" if blames > 0 or len(cases) >= 2 else "STANDARD" if len(cases) > 0 else "AUCUN",
        },
        "cases": history,
    })


@router.patch("/discipline/cases/{case_id}/decide")
async def decide_sanction(case_id: str, body: dict, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    """DRH/DG decides the final sanction on a discipline case."""
    from app.models.core import DisciplineCase
    case = db.query(DisciplineCase).filter(DisciplineCase.id == case_id).first()
    if not case:
        raise HTTPException(404, "Dossier disciplinaire introuvable")
    if case.status == "CLOTURE":
        raise HTTPException(400, "Dossier deja cloture")

    sanction = body.get("sanction")
    if sanction not in ("AVERTISSEMENT", "BLAME", "MISE_A_PIED", "LICENCIEMENT", "CLASSEE_SANS_SUITE"):
        raise HTTPException(400, "Sanction invalide")

    case.sanction_applied = sanction
    case.sanction_duration_days = body.get("duration_days")
    case.sanction_comment = body.get("comment", "")
    case.sanction_decided_by = user.email
    case.sanction_decided_at = datetime.now(timezone.utc)
    case.status = "CLOTURE"

    if body.get("validated_by_drh"):
        case.validated_by_drh = user.email
    if body.get("validated_by_dg"):
        case.validated_by_dg = user.email

    db.commit()
    return ApiResponse(data={"id": str(case.id), "status": "CLOTURE", "sanction": sanction})


@router.get("/discipline/cases/{case_id}")
async def get_discipline_case(case_id: str, db: Session = Depends(get_db),
                               user: CurrentUser = Depends(get_current_user)):
    """Get full detail of a discipline case."""
    from app.models.core import DisciplineCase, Employee
    case = db.query(DisciplineCase).filter(DisciplineCase.id == case_id).first()
    if not case:
        raise HTTPException(404, "Dossier introuvable")
    emp = db.query(Employee).filter(Employee.id == case.employee_id).first()
    total = db.query(DisciplineCase).filter(DisciplineCase.employee_id == case.employee_id).count()

    return ApiResponse(data={
        "id": str(case.id),
        "employee": {"id": str(emp.id), "name": f"{emp.last_name} {emp.first_name}", "matricule": emp.matricule, "position": emp.position} if emp else None,
        "employee_total_infractions": total,
        "infraction_date": str(case.infraction_date),
        "infraction_time": case.infraction_time,
        "infraction_location": case.infraction_location,
        "description": case.description,
        "witnesses": case.witnesses or [],
        "severity_declared": case.severity_declared,
        "evidence_document_ids": case.evidence_document_ids or [],
        "ai_severity": case.ai_severity,
        "ai_sanction_suggested": case.ai_sanction_suggested,
        "ai_justification": case.ai_justification,
        "ai_evaluated_at": str(case.ai_evaluated_at) if case.ai_evaluated_at else None,
        "convocation_date": str(case.convocation_date) if case.convocation_date else None,
        "convocation_sent": case.convocation_sent,
        "audition_date": str(case.audition_date) if case.audition_date else None,
        "audition_pv": case.audition_pv,
        "audition_assistant_name": case.audition_assistant_name,
        "sanction_applied": case.sanction_applied,
        "sanction_duration_days": case.sanction_duration_days,
        "sanction_decided_by": case.sanction_decided_by,
        "sanction_decided_at": str(case.sanction_decided_at) if case.sanction_decided_at else None,
        "sanction_comment": case.sanction_comment,
        "status": case.status,
        "reported_by": case.reported_by,
        "validated_by_drh": case.validated_by_drh,
        "validated_by_dg": case.validated_by_dg,
        "validated_by_pdg": case.validated_by_pdg,
        "created_at": str(case.created_at),
    })


@router.post("/discipline/cases")
async def create_discipline_case(body: dict, db: Session = Depends(get_db),
                                  user: CurrentUser = Depends(get_current_user)):
    """Create a new discipline case (F-DIS-001 PV de constat)."""
    from app.models.core import DisciplineCase, Employee
    from datetime import date as date_type

    employee_id = body.get("employee_id")
    if not employee_id:
        raise HTTPException(400, "employee_id requis")
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employe introuvable")

    description = body.get("description", "")
    if len(description) < 50:
        raise HTTPException(400, "Description min 50 caracteres")

    proof_ids = body.get("evidence_document_ids", [])
    if not proof_ids:
        raise HTTPException(400, "Au moins un document de preuve requis (PV, photo, temoignage)")

    from app.models.core import Company
    co = db.query(Company).first()

    case = DisciplineCase(
        company_id=co.id, employee_id=emp.id,
        infraction_date=date_type.fromisoformat(body.get("infraction_date", str(date_type.today()))),
        infraction_time=body.get("infraction_time", ""),
        infraction_location=body.get("infraction_location", ""),
        description=description,
        witnesses=body.get("witnesses", []),
        severity_declared=body.get("severity", "MOYENNE"),
        evidence_document_ids=proof_ids,
        reported_by=user.email,
        status="PV_CONSTAT",
    )

    # Auto-evaluate with AI
    ai_result = agent_disciplinaire_evaluate({
        "description": description,
        "severity": body.get("severity", "MOYENNE"),
        "history": f"{db.query(DisciplineCase).filter(DisciplineCase.employee_id == emp.id).count()} infractions precedentes",
    })
    case.ai_severity = ai_result.get("severity_confirmed", body.get("severity"))
    case.ai_sanction_suggested = ai_result.get("sanction_suggeree", "AVERTISSEMENT")
    case.ai_justification = ai_result.get("justification") or ai_result.get("raw", "")
    case.ai_evaluated_at = datetime.now(timezone.utc)

    db.add(case)
    db.commit()
    db.refresh(case)

    return ApiResponse(data={
        "id": str(case.id), "status": "PV_CONSTAT",
        "ai_severity": case.ai_severity,
        "ai_sanction_suggested": case.ai_sanction_suggested,
        "ai_justification": case.ai_justification,
        "message": f"Infraction enregistree. L'IA recommande: {case.ai_sanction_suggested}",
    })


@router.post("/messagerie/send")
async def send_notification(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Messagerie: send notification via email/SMS."""
    return ApiResponse(data=agent_messagerie_send(body.get("recipient", ""), body.get("template", ""), body))


@router.post("/bi/generate")
async def generate_bi(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent BI RH: generate HR analytics data."""
    return ApiResponse(data=agent_bi_generate(body.get("metric", ""), body.get("period", "")))


@router.post("/declarations/prepare")
async def prepare_declaration(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Declarations: prepare social declaration draft."""
    return ApiResponse(data=agent_declarations_prepare(body.get("entity_code", ""), body.get("type", "DAC"), body.get("period", "")))


@router.post("/prets/check-eligibility")
async def check_loan(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Prets: check employee loan eligibility."""
    return ApiResponse(data=agent_prets_eligibility(body.get("employee", {})))


@router.post("/vision/analyze")
async def vision_analyze(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Vision OCR: analyze document and extract data using AI."""
    return ApiResponse(data=agent_vision_analyze(body.get("document_text", ""), body.get("doc_type", "AUTRE")))


@router.post("/carriere/suggest")
async def career_suggestion(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Carriere: suggest career progression."""
    return ApiResponse(data=agent_carriere_suggest(body.get("employee", {}), body.get("spi_history", [])))


@router.post("/securite/check")
async def security_check(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Securite: analyze badge events for anomalies."""
    return ApiResponse(data=agent_securite_check(body.get("badge_events", [])))


@router.post("/visiteurs/register")
async def register_visitor(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Agent Visiteurs: register visitor and generate QR code."""
    return ApiResponse(data=agent_visiteurs_register(body))
