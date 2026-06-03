"""Router 10 — Juridique: contracts, cases, compliance.
Cases and events from PostgreSQL. Contracts still partially static (to be migrated)."""
from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.v1.deps import get_current_user, CurrentUser, get_db
from app.api.v1.schemas import ApiResponse, Meta
from app.models.core import LegalCase, LegalCaseEvent, LegalContract, LegalAiFeedback, Company, Project

router = APIRouter(prefix="/juridique", tags=["Juridique"])

VALID_STAGES = ["ouvert", "mise_en_demeure", "negociation", "audience_programmee", "en_delibere", "jugement", "appel", "cloture"]


# ═══ CASES — from database ═══

@router.get("/cases")
async def list_cases(case_type: str = None, stage: str = None,
                     db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    q = db.query(LegalCase).order_by(LegalCase.date_open.desc())
    if case_type:
        q = q.filter(LegalCase.case_type == case_type)
    if stage:
        q = q.filter(LegalCase.stage == stage)
    # NC-C3: Confidentiality filter — only DAF and assigned juriste see confidential cases
    if user.role not in ("DAF", "ADMIN_SYS"):
        q = q.filter(
            (LegalCase.is_confidential == False) |
            (LegalCase.assigned_juriste == user.email)
        )
    cases = q.all()
    today = date.today()
    return ApiResponse(data=[{
        "id": str(c.id), "name": c.name, "type": c.case_type, "title": c.title,
        "stage": c.stage, "priority": c.priority,
        "amount_claimed": str(c.amount_claimed), "amount_recovered": str(c.amount_recovered or 0),
        "partner": c.partner_name, "assigned_to": c.assigned_juriste,
        "project": c.project_code, "employee": c.employee_name,
        "days_open": (today - c.date_open).days if c.date_open else 0,
        "ai_risk_score": float(c.ai_risk_score) if c.ai_risk_score else None,
        "result": c.result, "is_confidential": c.is_confidential,
        "cost_total": str(c.cost_total or 0),
        "date_deadline": str(c.date_deadline) if c.date_deadline else None,
        "events_count": len(c.events),
    } for c in cases], meta=Meta(total=len(cases)))


@router.get("/cases/{case_id}")
async def case_detail(case_id: str, db: Session = Depends(get_db),
                      user: CurrentUser = Depends(get_current_user)):
    case = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not case:
        raise HTTPException(404, "Dossier introuvable")
    today = date.today()
    events = db.query(LegalCaseEvent).filter(LegalCaseEvent.case_id == case.id).order_by(LegalCaseEvent.event_date.desc()).all()
    return ApiResponse(data={
        "id": str(case.id), "name": case.name, "type": case.case_type, "title": case.title,
        "description": case.description, "stage": case.stage, "priority": case.priority,
        "partner_name": case.partner_name, "partner_lawyer": case.partner_lawyer,
        "company_lawyer": case.company_lawyer, "assigned_juriste": case.assigned_juriste,
        "assigned_manager": case.assigned_manager,
        "contract_ref": case.contract_ref, "invoice_ref": case.invoice_ref,
        "employee_name": case.employee_name, "project_code": case.project_code,
        "amount_claimed": str(case.amount_claimed), "amount_recovered": str(case.amount_recovered or 0),
        "cost_honoraires": str(case.cost_honoraires or 0),
        "cost_frais_justice": str(case.cost_frais_justice or 0),
        "cost_expertise": str(case.cost_expertise or 0),
        "cost_total": str(case.cost_total or 0),
        "ai_risk_score": float(case.ai_risk_score) if case.ai_risk_score else None,
        "ai_summary": case.ai_summary, "ai_suggested_actions": case.ai_suggested_actions,
        "result": case.result, "result_comment": case.result_comment,
        "date_open": str(case.date_open), "date_deadline": str(case.date_deadline) if case.date_deadline else None,
        "date_close": str(case.date_close) if case.date_close else None,
        "is_confidential": case.is_confidential,
        "days_open": (today - case.date_open).days if case.date_open else 0,
        "events": [{
            "id": str(e.id), "date": str(e.event_date), "type": e.event_type,
            "title": e.title, "description": e.description,
            "old_stage": e.old_stage, "new_stage": e.new_stage,
            "amount": str(e.amount) if e.amount else None,
            "document_id": e.document_id, "created_by": e.created_by,
        } for e in events],
        "available_stages": [s for s in VALID_STAGES if VALID_STAGES.index(s) > VALID_STAGES.index(case.stage)] if case.stage in VALID_STAGES else [],
    })


@router.post("/cases")
async def create_case(body: dict, db: Session = Depends(get_db),
                      user: CurrentUser = Depends(get_current_user)):
    co = db.query(Company).first()
    seq = db.query(LegalCase).count() + 1
    year = date.today().year
    case = LegalCase(
        company_id=co.id, name=f"LGL/{year}/{seq:05d}",
        case_type=body.get("case_type", "precontentieux"),
        title=body.get("title", ""), description=body.get("description", ""),
        stage="ouvert", priority=body.get("priority", "normal"),
        partner_name=body.get("partner_name"), partner_lawyer=body.get("partner_lawyer"),
        company_lawyer=body.get("company_lawyer"), assigned_juriste=body.get("assigned_juriste"),
        project_code=body.get("project_code"), employee_name=body.get("employee_name"),
        contract_ref=body.get("contract_ref"), invoice_ref=body.get("invoice_ref"),
        amount_claimed=Decimal(str(body["amount_claimed"])) if body.get("amount_claimed") else Decimal("0"),
        date_open=date.today(), date_deadline=date.fromisoformat(body["date_deadline"]) if body.get("date_deadline") else None,
    )
    db.add(case)
    db.flush()
    db.add(LegalCaseEvent(case_id=case.id, event_type="CREATION", title="Ouverture du dossier",
                          description=body.get("description", ""), created_by=user.email))
    db.commit()
    db.refresh(case)
    return ApiResponse(data={"id": str(case.id), "name": case.name, "stage": "ouvert"})


@router.patch("/cases/{case_id}/stage")
async def change_stage(case_id: str, body: dict, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(get_current_user)):
    case = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not case:
        raise HTTPException(404, "Dossier introuvable")
    new_stage = body.get("new_stage")
    if new_stage not in VALID_STAGES:
        raise HTTPException(400, f"Stage invalide. Valeurs: {VALID_STAGES}")
    old_stage = case.stage
    case.stage = new_stage
    if new_stage == "cloture":
        case.date_close = date.today()
        case.result = body.get("result", "en_cours")
        case.result_comment = body.get("result_comment", "")
    db.add(LegalCaseEvent(case_id=case.id, event_type="STAGE_CHANGE",
                          title=body.get("title", f"Passage de {old_stage} a {new_stage}"),
                          description=body.get("description", ""), old_stage=old_stage, new_stage=new_stage,
                          created_by=user.email))
    db.commit()
    return ApiResponse(data={"id": str(case.id), "old_stage": old_stage, "new_stage": new_stage})


@router.post("/cases/{case_id}/event")
async def add_event(case_id: str, body: dict, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(get_current_user)):
    case = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not case:
        raise HTTPException(404, "Dossier introuvable")
    event_type = body.get("event_type", "NOTE")
    event = LegalCaseEvent(
        case_id=case.id, event_type=event_type,
        title=body.get("title", ""), description=body.get("description", ""),
        amount=Decimal(str(body["amount"])) if body.get("amount") else None,
        document_id=body.get("document_id"), created_by=user.email,
    )
    # Update costs if COST event
    if event_type == "COST" and body.get("amount"):
        amt = Decimal(str(body["amount"]))
        cost_type = body.get("cost_type", "honoraires")
        if cost_type == "honoraires":
            case.cost_honoraires = (case.cost_honoraires or 0) + amt
        elif cost_type == "expertise":
            case.cost_expertise = (case.cost_expertise or 0) + amt
        elif cost_type == "frais_justice":
            case.cost_frais_justice = (case.cost_frais_justice or 0) + amt
        case.cost_total = (case.cost_honoraires or 0) + (case.cost_frais_justice or 0) + (case.cost_expertise or 0)
    db.add(event)
    db.commit()
    return ApiResponse(data={"id": str(event.id), "event_type": event_type})


@router.patch("/cases/{case_id}")
async def update_case(case_id: str, body: dict, db: Session = Depends(get_db),
                      user: CurrentUser = Depends(get_current_user)):
    case = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not case:
        raise HTTPException(404, "Dossier introuvable")
    for field in ["title", "description", "priority", "partner_name", "partner_lawyer",
                  "company_lawyer", "assigned_juriste", "project_code", "employee_name",
                  "contract_ref", "invoice_ref", "result", "result_comment"]:
        if field in body:
            setattr(case, field, body[field])
    if "amount_claimed" in body:
        case.amount_claimed = Decimal(str(body["amount_claimed"]))
    if "amount_recovered" in body:
        case.amount_recovered = Decimal(str(body["amount_recovered"]))
    if "date_deadline" in body and body["date_deadline"]:
        case.date_deadline = date.fromisoformat(body["date_deadline"])
    db.commit()
    return ApiResponse(data={"id": str(case.id), "updated": True})


# ═══ CONTRACTS — from database ═══

@router.get("/contracts")
async def list_contracts(status: str = None, contract_type: str = None,
                         db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    q = db.query(LegalContract).order_by(LegalContract.created_at.desc())
    if status:
        q = q.filter(LegalContract.status == status)
    if contract_type:
        q = q.filter(LegalContract.contract_type == contract_type)
    contracts = q.all()
    today = date.today()
    return ApiResponse(data=[{
        "id": str(c.id), "name": c.name, "type": c.contract_type, "title": c.title,
        "partner": c.partner_name, "status": c.status,
        "date_start": str(c.date_start) if c.date_start else None,
        "date_end": str(c.date_end) if c.date_end else None,
        "amount": str(c.amount_ht), "amount_ttc": str(c.amount_ttc or 0),
        "renewal_type": c.renewal_type, "compliance_status": c.compliance_status,
        "days_to_expiry": (c.date_end - today).days if c.date_end else None,
        "alert": f"Contrat expire depuis {(today - c.date_end).days} jours" if c.date_end and c.date_end < today and c.status != "resilie" else
                 f"Expire dans {(c.date_end - today).days} jours" if c.date_end and (c.date_end - today).days <= 30 else None,
        "project": c.project.code if c.project else None,
        "clauses_count": len(c.clauses or []),
    } for c in contracts], meta=Meta(total=len(contracts)))


@router.get("/contracts/{contract_id}")
async def contract_detail(contract_id: str, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    c = db.query(LegalContract).filter(LegalContract.id == contract_id).first()
    if not c:
        raise HTTPException(404, {"code": "LEGAL_010", "message": "Contrat introuvable", "details": {}})
    return ApiResponse(data={
        "id": str(c.id), "name": c.name, "type": c.contract_type, "title": c.title,
        "partner_name": c.partner_name, "partner_nif": c.partner_nif, "partner_rc": c.partner_rc,
        "project_id": str(c.project_id) if c.project_id else None,
        "project_code": c.project.code if c.project else None,
        "date_start": str(c.date_start) if c.date_start else None,
        "date_end": str(c.date_end) if c.date_end else None,
        "renewal_type": c.renewal_type, "renewal_notice_days": c.renewal_notice_days,
        "amount_ht": str(c.amount_ht), "amount_ttc": str(c.amount_ttc or 0),
        "status": c.status, "compliance_status": c.compliance_status,
        "ai_risk_assessment": c.ai_risk_assessment, "ai_extracted_clauses": c.ai_extracted_clauses,
        "clauses": c.clauses or [],
        "signed_document_id": c.signed_document_id,
        "created_by": c.created_by, "created_at": str(c.created_at),
    })


@router.post("/contracts")
async def create_contract(body: dict, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    co = db.query(Company).first()
    seq = db.query(LegalContract).count() + 1
    year = date.today().year
    c = LegalContract(
        company_id=co.id, name=f"CTR/{year}/{seq:05d}",
        contract_type=body.get("contract_type", "fournisseur"),
        title=body.get("title", ""), partner_name=body.get("partner_name"),
        date_start=date.fromisoformat(body["date_start"]) if body.get("date_start") else None,
        date_end=date.fromisoformat(body["date_end"]) if body.get("date_end") else None,
        amount_ht=Decimal(str(body["amount_ht"])) if body.get("amount_ht") else Decimal("0"),
        renewal_type=body.get("renewal_type", "manuelle"),
        status="brouillon", created_by=user.email,
    )
    if body.get("project_code"):
        proj = db.query(Project).filter(Project.code == body["project_code"]).first()
        if proj: c.project_id = proj.id
    db.add(c)
    db.commit()
    db.refresh(c)
    return ApiResponse(data={"id": str(c.id), "name": c.name, "status": "brouillon"})


@router.patch("/contracts/{contract_id}")
async def update_contract(contract_id: str, body: dict, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    c = db.query(LegalContract).filter(LegalContract.id == contract_id).first()
    if not c:
        raise HTTPException(404, {"code": "LEGAL_010", "message": "Contrat introuvable", "details": {}})
    for field in ["title", "partner_name", "partner_nif", "partner_rc", "contract_type",
                  "status", "compliance_status", "renewal_type", "clauses", "signed_document_id"]:
        if field in body:
            setattr(c, field, body[field])
    if "amount_ht" in body:
        c.amount_ht = Decimal(str(body["amount_ht"]))
    db.commit()
    return ApiResponse(data={"id": str(c.id), "status": c.status, "updated": True})


# ═══ BC BLOCKING RULE (audit fix NC-D1) ═══
# This endpoint is called by the purchase order validation hook in GFI

@router.get("/contracts/check-supplier/{supplier_name}")
async def check_supplier_contract(supplier_name: str, db: Session = Depends(get_db),
                                   user: CurrentUser = Depends(get_current_user)):
    """Check if a supplier has an active valid contract. Called before BC validation.
    Returns blocked=True if no valid contract. Fail-closed: if timeout, block by default."""
    today = date.today()
    valid = db.query(LegalContract).filter(
        LegalContract.partner_name.ilike(f"%{supplier_name}%"),
        LegalContract.status.in_(["actif", "signe"]),
        LegalContract.contract_type.in_(["fournisseur", "prestation", "cadre"]),
    ).first()

    if valid:
        # Check if not expired
        if valid.date_end and valid.date_end < today:
            return ApiResponse(data={
                "blocked": True, "reason": f"Contrat {valid.name} expire le {valid.date_end}. Renouvellement requis.",
                "code": "LEGAL_BC_001", "contract_id": str(valid.id),
            })
        return ApiResponse(data={
            "blocked": False, "contract_id": str(valid.id), "contract_name": valid.name,
            "message": f"Contrat valide: {valid.name} ({valid.status})",
        })
    else:
        return ApiResponse(data={
            "blocked": True,
            "reason": f"Aucun contrat fournisseur actif pour '{supplier_name}'. Bon de commande bloque.",
            "code": "LEGAL_BC_002",
            "escalation": "DAF",
            "message": "Regle fail-closed: blocage par defaut. Le DAF peut debloquer manuellement.",
        })


@router.get("/compliance/dashboard")
async def compliance_dashboard(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    total_cases = db.query(LegalCase).count()
    open_cases = db.query(LegalCase).filter(LegalCase.stage != "cloture").count()
    closed = db.query(LegalCase).filter(LegalCase.stage == "cloture").count()
    amounts = db.query(func.sum(LegalCase.amount_claimed)).filter(LegalCase.stage != "cloture").scalar() or 0
    return ApiResponse(data={
        "kpis": {
            "open_litigations": open_cases, "total_cases": total_cases,
            "resolution_rate": f"{(closed * 100 // total_cases) if total_cases else 0}%",
            "amounts_at_stake": str(amounts),
        },
    })


@router.get("/compliance/alerts")
async def compliance_alerts(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """NC-D3: Real compliance rules evaluated against DB data."""
    from app.models.core import Employee, Payslip
    alerts = []
    today = date.today()

    # ALG-CDD-24M: CDD contracts exceeding 24 months cumulative
    # (employee contracts are in RH, but legal monitors compliance)

    # ALG-PAY-90J: Supplier payment delay > 90 days
    # Check contracts with invoices unpaid > 90 days (simplified: contracts active > 90 days past end)
    overdue_contracts = db.query(LegalContract).filter(
        LegalContract.status == "actif",
        LegalContract.date_end != None,
        LegalContract.date_end < today - __import__('datetime').timedelta(days=90),
    ).all()
    for c in overdue_contracts:
        alerts.append({
            "rule_code": "ALG-PAY-90J", "severity": "majeur", "state": "ouverte",
            "description": f"Contrat {c.name} ({c.partner_name}) depasse 90 jours apres echeance",
            "target": c.name, "target_id": str(c.id),
        })

    # ALG-CTR-REV: Service contracts > 12 months without price revision clause
    long_contracts = db.query(LegalContract).filter(
        LegalContract.status.in_(["actif", "signe"]),
        LegalContract.contract_type.in_(["prestation", "fournisseur"]),
    ).all()
    for c in long_contracts:
        if c.date_start and c.date_end:
            duration = (c.date_end - c.date_start).days
            if duration > 365:
                has_revision = any("revis" in (cl.get("text", "") or "").lower() for cl in (c.clauses or []))
                if not has_revision:
                    alerts.append({
                        "rule_code": "ALG-CTR-REV", "severity": "majeur", "state": "ouverte",
                        "description": f"Contrat {c.name} > 12 mois sans clause de revision des prix",
                        "target": c.name, "target_id": str(c.id),
                    })

    # ALG-RC-FRNR: Supplier without registre de commerce
    no_rc = db.query(LegalContract).filter(
        LegalContract.contract_type.in_(["fournisseur", "prestation"]),
        LegalContract.status.in_(["actif", "signe"]),
        (LegalContract.partner_rc == None) | (LegalContract.partner_rc == ""),
    ).all()
    for c in no_rc:
        alerts.append({
            "rule_code": "ALG-RC-FRNR", "severity": "critique", "state": "ouverte",
            "description": f"Fournisseur {c.partner_name} sans registre de commerce enregistre",
            "target": c.name, "target_id": str(c.id),
        })

    # ALG-NC-2ANS: Non-compete clause > 2 years
    for c in db.query(LegalContract).filter(LegalContract.status.in_(["actif", "signe"])).all():
        for clause in (c.clauses or []):
            text_lower = (clause.get("text", "") or "").lower()
            if "non-concurrence" in text_lower or "non concurrence" in text_lower:
                # Check if duration mentioned > 2 years
                if "3 ans" in text_lower or "4 ans" in text_lower or "5 ans" in text_lower:
                    alerts.append({
                        "rule_code": "ALG-NC-2ANS", "severity": "majeur", "state": "ouverte",
                        "description": f"Clause non-concurrence > 2 ans detectee dans {c.name}",
                        "target": c.name, "target_id": str(c.id),
                    })

    # ALG-DEP-1M: Contracts > 1M DA without legal visa
    big_no_visa = db.query(LegalContract).filter(
        LegalContract.amount_ht > 1000000,
        LegalContract.compliance_status.in_(["non_evalue", "non_conforme"]),
        LegalContract.status.in_(["brouillon", "en_revue"]),
    ).all()
    for c in big_no_visa:
        alerts.append({
            "rule_code": "ALG-DEP-1M", "severity": "critique", "state": "ouverte",
            "description": f"Contrat {c.name} ({c.partner_name}) > 1M DA sans visa juridique",
            "target": c.name, "target_id": str(c.id),
        })

    # Expiring contracts (< 30 days)
    expiring = db.query(LegalContract).filter(
        LegalContract.status == "actif",
        LegalContract.date_end != None,
        LegalContract.date_end <= today + __import__('datetime').timedelta(days=30),
        LegalContract.date_end >= today,
    ).all()
    for c in expiring:
        days_left = (c.date_end - today).days
        alerts.append({
            "rule_code": "CTR-EXPIRY", "severity": "majeur" if days_left <= 7 else "mineur", "state": "ouverte",
            "description": f"Contrat {c.name} ({c.partner_name}) expire dans {days_left} jours",
            "target": c.name, "target_id": str(c.id),
        })

    # Expired contracts not renewed
    expired = db.query(LegalContract).filter(
        LegalContract.status == "actif",
        LegalContract.date_end != None,
        LegalContract.date_end < today,
    ).all()
    for c in expired:
        alerts.append({
            "rule_code": "ALG-LIC-EXP", "severity": "critique", "state": "ouverte",
            "description": f"Contrat {c.name} expire depuis {(today - c.date_end).days} jours — renouvellement requis",
            "target": c.name, "target_id": str(c.id),
        })

    return ApiResponse(data=alerts, meta=Meta(total=len(alerts)))


# ═══ AI FEEDBACK (NC-E4) ═══

@router.post("/cases/{case_id}/feedback")
async def submit_feedback(case_id: str, body: dict, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    """Submit feedback on AI prediction for a case. Feeds the learning loop."""
    case = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not case:
        raise HTTPException(404, {"code": "LEGAL_020", "message": "Dossier introuvable", "details": {}})
    fb = LegalAiFeedback(
        case_id=case.id,
        prediction_type=body.get("prediction_type", "risk_score"),
        predicted_value=body.get("predicted_value"),
        actual_value=body.get("actual_value"),
        was_correct=body.get("was_correct"),
        feedback_by=user.email,
        comment=body.get("comment"),
    )
    db.add(fb)
    db.commit()
    return ApiResponse(data={"id": str(fb.id), "message": "Feedback enregistre"})


@router.get("/feedback")
async def list_feedback(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    feedbacks = db.query(LegalAiFeedback).order_by(LegalAiFeedback.feedback_date.desc()).limit(50).all()
    return ApiResponse(data=[{
        "id": str(f.id), "case_id": str(f.case_id) if f.case_id else None,
        "prediction_type": f.prediction_type, "predicted": f.predicted_value,
        "actual": f.actual_value, "correct": f.was_correct,
        "by": f.feedback_by, "date": str(f.feedback_date), "comment": f.comment,
    } for f in feedbacks])


# ═══ PDF REPORT (NC-F6) ═══

@router.get("/cases/{case_id}/report")
async def generate_case_report(case_id: str, db: Session = Depends(get_db),
                                user: CurrentUser = Depends(get_current_user)):
    """Generate a PDF report for a legal case. Uses reportlab."""
    from fastapi.responses import StreamingResponse
    import io

    case = db.query(LegalCase).filter(LegalCase.id == case_id).first()
    if not case:
        raise HTTPException(404, {"code": "LEGAL_030", "message": "Dossier introuvable", "details": {}})

    events = db.query(LegalCaseEvent).filter(LegalCaseEvent.case_id == case.id).order_by(LegalCaseEvent.event_date).all()

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph(f"RAPPORT JURIDIQUE — {case.name}", styles['Title']))
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(f"<b>{case.title}</b>", styles['Heading2']))
        story.append(Spacer(1, 0.3*cm))

        # Info table
        info_data = [
            ["Type", case.case_type], ["Stade", case.stage], ["Priorite", case.priority],
            ["Partie adverse", case.partner_name or "-"],
            ["Avocat adverse", case.partner_lawyer or "-"],
            ["Notre avocat", case.company_lawyer or "-"],
            ["Montant reclame", f"{case.amount_claimed} DA"],
            ["Ouvert le", str(case.date_open)],
            ["Prochaine echeance", str(case.date_deadline) if case.date_deadline else "-"],
        ]
        t = Table(info_data, colWidths=[5*cm, 12*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.Color(0.95, 0.95, 0.95)),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

        # Description
        if case.description:
            story.append(Paragraph("<b>Description</b>", styles['Heading3']))
            story.append(Paragraph(case.description, styles['Normal']))
            story.append(Spacer(1, 0.3*cm))

        # AI Summary
        if case.ai_summary:
            story.append(Paragraph("<b>Analyse IA</b>", styles['Heading3']))
            story.append(Paragraph(f"Score de risque: {case.ai_risk_score}%", styles['Normal']))
            story.append(Paragraph(case.ai_summary, styles['Normal']))
            story.append(Spacer(1, 0.3*cm))

        # Costs
        story.append(Paragraph("<b>Couts du dossier</b>", styles['Heading3']))
        cost_data = [
            ["Honoraires", f"{case.cost_honoraires or 0} DA"],
            ["Frais justice", f"{case.cost_frais_justice or 0} DA"],
            ["Expertise", f"{case.cost_expertise or 0} DA"],
            ["TOTAL", f"{case.cost_total or 0} DA"],
        ]
        ct = Table(cost_data, colWidths=[5*cm, 5*cm])
        ct.setStyle(TableStyle([
            ('BACKGROUND', (-1, -1), (-1, -1), colors.Color(0.9, 0.95, 0.9)),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(ct)
        story.append(Spacer(1, 0.5*cm))

        # Events timeline
        story.append(Paragraph(f"<b>Historique ({len(events)} evenements)</b>", styles['Heading3']))
        for ev in events:
            story.append(Paragraph(
                f"<b>[{ev.event_type}]</b> {str(ev.event_date)[:10]} — {ev.title}",
                styles['Normal']
            ))
            if ev.description:
                story.append(Paragraph(f"   {ev.description}", styles['Normal']))

        # Footer
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph(f"Rapport genere le {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC — GFI v7.0 Groupe GFI", styles['Normal']))

        doc.build(story)
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/pdf",
                                  headers={"Content-Disposition": f"attachment; filename=rapport_{case.name.replace('/', '_')}.pdf"})

    except ImportError:
        # Fallback: return JSON if reportlab not installed
        return ApiResponse(data={
            "format": "json_fallback",
            "message": "reportlab non installe. Rapport en format JSON.",
            "case": {"name": case.name, "title": case.title, "stage": case.stage,
                     "amount": str(case.amount_claimed), "events": len(events)},
        })


# ═══ COMPLIANCE RULES LIST ═══

@router.get("/compliance/rules")
async def compliance_rules(user: CurrentUser = Depends(get_current_user)):
    return ApiResponse(data=[
        {"code": "ALG-CDD-24M", "name": "CDD cumule > 24 mois", "severity": "critique", "evaluation_mode": "realtime", "is_active": True,
         "description": "Un employe en CDD dont la duree cumulee depasse 24 mois doit etre converti en CDI (Loi 90-11 art. 14)"},
        {"code": "ALG-PAY-90J", "name": "Paiement fournisseur > 90 jours", "severity": "majeur", "evaluation_mode": "batch_daily", "is_active": True,
         "description": "Le delai de paiement fournisseur ne doit pas exceder 90 jours (Code de commerce algerien)"},
        {"code": "ALG-CTR-REV", "name": "Contrat > 12 mois sans revision prix", "severity": "majeur", "evaluation_mode": "batch_weekly", "is_active": True,
         "description": "Les contrats de prestation > 12 mois doivent contenir une clause de revision des prix"},
        {"code": "ALG-NC-2ANS", "name": "Non-concurrence > 2 ans", "severity": "majeur", "evaluation_mode": "realtime", "is_active": True,
         "description": "La clause de non-concurrence ne peut exceder 2 ans en droit algerien"},
        {"code": "ALG-RC-FRNR", "name": "Fournisseur sans registre de commerce", "severity": "critique", "evaluation_mode": "realtime", "is_active": True,
         "description": "Tout fournisseur doit avoir un registre de commerce valide avant toute commande"},
        {"code": "ALG-LIC-EXP", "name": "Licence/autorisation expiree", "severity": "critique", "evaluation_mode": "batch_daily", "is_active": True,
         "description": "Les licences d exploitation et autorisations doivent etre renouvelees avant expiration"},
        {"code": "ALG-INT-TAUX", "name": "Taux penalite contractuel excessif", "severity": "majeur", "evaluation_mode": "realtime", "is_active": True,
         "description": "Les penalites contractuelles ne doivent pas depasser le taux legal maximum"},
        {"code": "ALG-DEP-1M", "name": "Depense > 1M DA sans visa juridique", "severity": "critique", "evaluation_mode": "realtime", "is_active": True,
         "description": "Toute depense depassant 1 000 000 DA doit recevoir un visa du service juridique"},
    ])
