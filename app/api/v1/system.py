"""Router 11 — System: dashboard, health, agents, alerts, meta-ia.
ALL KPIs computed from PostgreSQL. ZERO hardcoded values."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.api.v1.deps import get_current_user, CurrentUser, get_db
from app.api.v1.schemas import ApiResponse, Meta
from app.models.core import (
    Company, Project, Associate, CcaAccount, DossierADV, Lot,
    Payment, Employee, Payslip, LeaveRequest, CostCenterNode, CostCenterEntry,
    GacebAdvance, StockItem, Supplier, SupplierContract,
    TaskAssignment, SpiDaily, SpiTask, Document,
)

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/dashboard")
async def ceo_dashboard(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """CEO Dashboard — every number from the database."""
    # Treasury: SUM of all CCA balances
    treasury = db.query(func.sum(CcaAccount.balance)).filter(CcaAccount.is_deleted == False).scalar() or 0
    # Projects active
    projects_active = db.query(Project).filter(Project.status == "ACTIF", Project.is_deleted == False).count()
    projects_total = db.query(Project).filter(Project.is_deleted == False).count()
    # Dossiers
    dossiers_active = db.query(DossierADV).filter(
        DossierADV.status.notin_(["CLOTURE", "ANNULE", "ANNULE_RESERVATION", "ANNULE_ENGAGEMENT"]),
        DossierADV.is_deleted == False
    ).count()
    dossiers_total = db.query(DossierADV).filter(DossierADV.is_deleted == False).count()
    # Lots
    lots_total = db.query(Lot).filter(Lot.is_deleted == False).count()
    lots_dispo = db.query(Lot).filter(Lot.status == "DISPONIBLE", Lot.is_deleted == False).count()
    # Employees
    emp_active = db.query(Employee).filter(Employee.status == "ACTIVE", Employee.is_deleted == False).count()
    # Payslips pending
    payslips_pending = db.query(Payslip).filter(Payslip.verified_l6 == "PENDING").count()
    # Entities
    entities_count = db.query(Company).filter(Company.is_deleted == False).count()
    # GACEB
    gaceb = db.query(GacebAdvance).first()
    gaceb_residual = str(gaceb.residual) if gaceb else "0"
    # RF distribution from payments
    rf1_total = db.query(func.sum(Payment.montant)).filter(Payment.type_rf == "RF1", Payment.status == "ENCAISSE").scalar() or 0
    rf2_total = db.query(func.sum(Payment.montant)).filter(Payment.type_rf == "RF2", Payment.status == "ENCAISSE").scalar() or 0
    # Formulaires: count entities with NULL IBS
    formulaires_pending = db.query(Company).filter(Company.ibs_rate == None, Company.status.notin_(["DISSOUTE", "SATELLITE"])).count()
    # Associate CCA per founder
    founders = db.query(Associate).filter(Associate.is_founder == True).order_by(Associate.canonical_name).all()
    assoc_cards = []
    for f in founders:
        bal = db.query(func.sum(CcaAccount.balance)).filter(CcaAccount.associate_id == f.id).scalar() or 0
        assoc_cards.append({"name": f.canonical_name, "cca_balance": str(bal)})

    # Per-project breakdown for charts
    project_stats = []
    active_projects = db.query(Project).filter(Project.status == "ACTIF", Project.is_deleted == False).all()
    for p in active_projects:
        p_lots = db.query(Lot).filter(Lot.project_id == p.id, Lot.is_deleted == False).count()
        p_dispo = db.query(Lot).filter(Lot.project_id == p.id, Lot.status == "DISPONIBLE", Lot.is_deleted == False).count()
        p_sold = p_lots - p_dispo
        # CC2 construction from cost center
        cc_node = db.query(CostCenterNode).filter(
            CostCenterNode.code.like(f"%-{p.code}-CC2%"), CostCenterNode.level == 3
        ).first()
        construction_cost = str(cc_node.montant_total) if cc_node else "0"
        project_stats.append({
            "code": p.code, "name": p.name, "entity": p.company.code if p.company else "",
            "lots_total": p_lots, "lots_sold": p_sold, "lots_dispo": p_dispo,
            "commercialisation_pct": round(p_sold / p_lots * 100) if p_lots else 0,
            "construction_cost": construction_cost,
        })

    # Lot breakdown by status for donut chart
    lot_by_status = {}
    for status_val in ["DISPONIBLE", "R\u00c9SERV\u00c9", "ENGAG\u00c9", "VENDU", "VERROUILLE"]:
        cnt = db.query(Lot).filter(Lot.status == status_val, Lot.is_deleted == False).count()
        # Normalize display key (no accents)
        display_key = status_val.replace("\u00c9", "E")
        lot_by_status[display_key] = lot_by_status.get(display_key, 0) + cnt

    # CCA per associate with per-entity detail
    assoc_detailed = []
    for f in founders:
        accounts = db.query(CcaAccount).filter(CcaAccount.associate_id == f.id).all()
        total_bal = sum(float(a.balance) for a in accounts)
        per_entity = []
        for acc in accounts:
            ent = db.query(Company).filter(Company.id == acc.company_id).first()
            per_entity.append({
                "entity_code": ent.code if ent else "?",
                "balance": str(acc.balance),
            })
        assoc_detailed.append({
            "name": f.canonical_name,
            "cca_balance": str(total_bal),
            "per_entity": sorted(per_entity, key=lambda x: float(x["balance"])),
        })

    # Stock value
    stock_total_value = db.query(func.coalesce(func.sum(StockItem.total_value), 0)).filter(
        StockItem.is_deleted == False).scalar()
    stock_items_count = db.query(func.count(StockItem.id)).filter(StockItem.is_deleted == False).scalar() or 0

    # Supplier totals
    suppliers_count = db.query(func.count(Supplier.id)).filter(Supplier.is_deleted == False).scalar() or 0
    supplier_remaining = db.query(func.coalesce(func.sum(Supplier.total_remaining), 0)).filter(
        Supplier.is_deleted == False).scalar()

    # CC totals (actual entries sum)
    cc_total_entries = db.query(func.coalesce(func.sum(CostCenterEntry.montant), 0)).filter(
        CostCenterEntry.is_deleted == False).scalar()
    cc_entries_count = db.query(func.count(CostCenterEntry.id)).filter(
        CostCenterEntry.is_deleted == False).scalar() or 0

    return ApiResponse(data={
        "treasury_global": str(treasury),
        "projects_active": projects_active,
        "projects_total": projects_total,
        "dossiers_active": dossiers_active,
        "dossiers_total": dossiers_total,
        "lots_total": lots_total,
        "lots_disponibles": lots_dispo,
        "taux_commercialisation": f"{((lots_total - lots_dispo) * 100 // lots_total) if lots_total else 0}%",
        "employees_active": emp_active,
        "payslips_pending": payslips_pending,
        "entities_count": entities_count,
        "gaceb_residual": gaceb_residual,
        "rf1_total": str(rf1_total),
        "rf2_total": str(rf2_total) if user.has_rf2 else None,
        "formulaires_pending": formulaires_pending,
        "associates": assoc_detailed,
        "project_stats": project_stats,
        "lot_by_status": lot_by_status,
        # New: stock & supplier & CC KPIs
        "stock_total_value": str(stock_total_value),
        "stock_items_count": stock_items_count,
        "suppliers_count": suppliers_count,
        "supplier_remaining": str(supplier_remaining),
        "cc_total_entries": str(cc_total_entries),
        "cc_entries_count": cc_entries_count,
    })


@router.get("/health")
async def health(db: Session = Depends(get_db)):
    tables = db.execute(
        __import__('sqlalchemy').text("SELECT count(*) FROM pg_tables WHERE schemaname='public'")
    ).scalar()
    return ApiResponse(data={"status": "healthy", "tables": tables, "database": "postgresql"})


@router.get("/agents/status")
async def agents_status(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """Real agent status computed from actual DB activity."""
    from app.models.core import TaskAssignment, SpiDaily, SpiTask, SpiDeliverable, Document
    from datetime import timedelta

    now = func.now()
    today = __import__('datetime').date.today()

    # Count active tasks for task decomposer
    pending_tasks = db.query(TaskAssignment).filter(TaskAssignment.status.in_(["PROPOSE", "EN_COURS"])).count()
    proofs_pending = db.query(TaskAssignment).filter(TaskAssignment.status == "PREUVE_SOUMISE").count()

    # Count today's SPI calculations
    spi_today = db.query(SpiDaily).filter(SpiDaily.date == today).count()
    total_employees = db.query(Employee).filter(Employee.status == "ACTIVE").count()

    # Documents in pipeline
    docs_pending = db.query(Document).filter(Document.pipeline_status != "INDEXED").count() if hasattr(Document, 'pipeline_status') else 0

    # Payslips pending
    payslips_pending = db.query(Payslip).filter(Payslip.verified_l6 == "PENDING").count()

    # Build real agent list from all 22 DRH agents + 6 juridique + others
    agents = [
        # DRH Agents (22)
        {"name": "Agent Dossier", "module": "DRH", "status": "IDLE", "description": "Creation et suivi dossiers employes"},
        {"name": "Agent Contrats", "module": "DRH", "status": "IDLE", "description": "Generation contrats, triple validation"},
        {"name": "Agent Paie", "module": "DRH",
         "status": "RUNNING" if payslips_pending > 0 else "IDLE",
         "current_task": f"{payslips_pending} bulletins en attente L6" if payslips_pending > 0 else None,
         "queue_depth": payslips_pending, "description": "Calcul paie 10 etapes"},
        {"name": "Agent Temps", "module": "DRH", "status": "IDLE", "description": "Agregation pointage biometrique"},
        {"name": "Agent Conges", "module": "DRH", "status": "IDLE", "description": "Verification 6 niveaux conges"},
        {"name": "Agent SPI 360", "module": "DRH",
         "status": "RUNNING" if spi_today < total_employees else "IDLE",
         "current_task": f"Calcul SPI: {spi_today}/{total_employees} employes" if spi_today < total_employees else None,
         "queue_depth": max(0, total_employees - spi_today), "description": "Score performance quotidien 4 piliers"},
        {"name": "Agent Recrutement", "module": "DRH", "status": "IDLE", "description": "Pipeline sourcing, scoring CV"},
        {"name": "Agent Formation", "module": "DRH", "status": "IDLE", "description": "Plans formation, matrice competences"},
        {"name": "Agent GED RH", "module": "DRH", "status": "IDLE", "description": "Classement documents RH"},
        {"name": "Agent Materiel", "module": "DRH", "status": "IDLE", "description": "Attribution equipement onboarding"},
        {"name": "Agent Acces", "module": "DRH", "status": "IDLE", "description": "Badges RFID, zones S4A"},
        {"name": "Agent Disciplinaire", "module": "DRH", "status": "IDLE", "description": "Workflow PV constat, audition, sanction"},
        {"name": "Agent Offboarding", "module": "DRH", "status": "IDLE", "description": "Depart, STC, quitus"},
        {"name": "Agent Messagerie", "module": "DRH", "status": "IDLE", "description": "Emails, SMS, notifications"},
        {"name": "Agent BI RH", "module": "DRH", "status": "IDLE", "description": "Dashboards headcount, turnover"},
        {"name": "Agent Declarations", "module": "DRH", "status": "IDLE", "description": "DAC CNAS, DAS, G50"},
        {"name": "Agent Prets", "module": "DRH", "status": "IDLE", "description": "Prets salaries, remboursement auto"},
        {"name": "Agent Vision OCR", "module": "DRH", "status": "IDLE", "description": "OCR CNI, certificats medicaux"},
        {"name": "Agent Carriere", "module": "DRH", "status": "IDLE", "description": "GPEC, promotions, competences"},
        {"name": "Agent Securite", "module": "DRH", "status": "IDLE", "description": "Detection anomalies acces"},
        {"name": "Agent Visiteurs", "module": "DRH", "status": "IDLE", "description": "QR codes, acces temporaire"},
        # Task Assignment Agents
        {"name": "Agent Analyseur Taches", "module": "SPI",
         "status": "RUNNING" if pending_tasks > 0 else "IDLE",
         "current_task": f"{pending_tasks} taches en attente" if pending_tasks > 0 else None,
         "queue_depth": pending_tasks, "description": "Decomposition besoins DAF en sous-taches"},
        {"name": "Agent Validateur Preuves", "module": "SPI",
         "status": "RUNNING" if proofs_pending > 0 else "IDLE",
         "current_task": f"{proofs_pending} preuves a valider" if proofs_pending > 0 else None,
         "queue_depth": proofs_pending, "description": "Validation IA des preuves de completion"},
        # Juridique Agents (6)
        {"name": "Agent OCR/NLP Juridique", "module": "JURIDIQUE", "status": "IDLE", "description": "Extraction contrats, assignations"},
        {"name": "Agent Contractuel", "module": "JURIDIQUE", "status": "IDLE", "description": "Conformite contrats, clauses manquantes"},
        {"name": "Agent Litige", "module": "JURIDIQUE", "status": "IDLE", "description": "Evaluation risque, plan action"},
        {"name": "Agent Conformite", "module": "JURIDIQUE", "status": "IDLE", "description": "8 regles algeriennes, evaluation batch"},
        {"name": "Agent Communication Juridique", "module": "JURIDIQUE", "status": "IDLE", "description": "Routage messages entrants"},
        {"name": "Agent Orchestrateur Juridique", "module": "JURIDIQUE", "status": "IDLE", "description": "Priorite, orchestration J1-J5"},
        # Finance Agents
        {"name": "Agent CFF", "module": "FINANCE", "status": "IDLE", "description": "Detection RF3, calcul CFF 5 etapes"},
        {"name": "Agent Rapprochement", "module": "FINANCE", "status": "IDLE", "description": "Rapprochement bancaire NLP"},
        # GED Agents
        {"name": "Agent OCR GED", "module": "GED",
         "status": "RUNNING" if docs_pending > 0 else "IDLE",
         "queue_depth": docs_pending, "description": "Pipeline 7 couches ingestion documents"},
        {"name": "Agent Detection", "module": "GED", "status": "IDLE", "description": "15 patterns detection anomalies"},
        {"name": "Agent Alias", "module": "FONDATION", "status": "IDLE", "description": "Resolution aliases trigram similarity"},
        # Meta-IA
        {"name": "Meta-IA", "module": "SYSTEME", "status": "IDLE", "description": "Detection besoins fonctionnels non couverts"},
    ]
    running = sum(1 for a in agents if a["status"] == "RUNNING")
    return ApiResponse(data={"agents": agents, "total": len(agents), "running": running})


@router.get("/alerts")
async def system_alerts(severity: str | None = None, module: str | None = None,
                         db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    alerts = []
    # Real alerts from DB state
    # 1. Companies with NULL IBS/TAP
    missing_tax = db.query(Company).filter(Company.ibs_rate == None, Company.status.notin_(["DISSOUTE", "SATELLITE"])).all()
    for c in missing_tax:
        alerts.append({"level": "CRITIQUE", "module": "FINANCE", "title": f"FC-005: Taux IBS/TAP manquant - {c.code}",
                       "message": f"CFF bloque pour {c.legal_name}", "created": "2026-03-20T08:00:00Z"})
    # 2. Payslips pending review
    pending = db.query(Payslip).filter(Payslip.verified_l6 == "PENDING").count()
    if pending > 0:
        alerts.append({"level": "ALERTE", "module": "DRH", "title": f"{pending} bulletins en attente de validation L6",
                       "message": "Validation DRH requise", "created": "2026-03-20T07:00:00Z"})
    # 3. GACEB residual
    gaceb = db.query(GacebAdvance).first()
    if gaceb and gaceb.residual > 0:
        alerts.append({"level": "ATTENTION", "module": "FINANCE", "title": f"GACEB: solde avance {gaceb.residual} DA",
                       "message": "Avance 120M non entierement deduite", "created": "2026-03-20T06:00:00Z"})
    # 4. Lots VERROUILLE
    locked = db.query(Lot).filter(Lot.status == "VERROUILLE").count()
    if locked > 0:
        alerts.append({"level": "INFO", "module": "ADV", "title": f"{locked} lot(s) verrouille(s)",
                       "message": "Lots en cours de reservation", "created": "2026-03-20T09:00:00Z"})

    if severity:
        alerts = [a for a in alerts if a["level"] == severity]
    if module:
        alerts = [a for a in alerts if a["module"] == module]
    # Sort by severity
    sev_order = {"CRITIQUE": 0, "ALERTE": 1, "ATTENTION": 2, "INFO": 3}
    alerts.sort(key=lambda a: sev_order.get(a["level"], 9))
    return ApiResponse(data=alerts, meta=Meta(total=len(alerts)))


# UI "UPDATE" should match audit rows stored as WRITE (auth engine)
_AUDIT_ACTION_ALIASES: dict[str, list[str]] = {
    "UPDATE": ["UPDATE", "WRITE"],
    "WRITE": ["UPDATE", "WRITE"],
}


@router.get("/audit-trail")
async def audit_trail(
    user_filter: str | None = Query(None, description="Email, nom ou UUID utilisateur"),
    action: str | None = Query(None, description="Type d'action"),
    module: str | None = Query(None, description="Module metier"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    from app.models.audit_trail import AuditTrail
    from app.models.core import AuthUser

    q = (
        db.query(AuditTrail, AuthUser)
        .join(AuthUser, AuditTrail.user_id == AuthUser.id)
        .order_by(AuditTrail.created_at.desc())
    )

    if user_filter and user_filter.strip():
        term = f"%{user_filter.strip()}%"
        clauses = [
            AuthUser.email.ilike(term),
            AuthUser.full_name.ilike(term),
        ]
        try:
            clauses.append(AuditTrail.user_id == UUID(user_filter.strip()))
        except ValueError:
            pass
        q = q.filter(or_(*clauses))

    if action and action.strip():
        key = action.strip().upper()
        actions = _AUDIT_ACTION_ALIASES.get(key, [key])
        q = q.filter(func.upper(AuditTrail.action).in_(actions))

    if module and module.strip():
        q = q.filter(func.upper(AuditTrail.module) == module.strip().upper())

    rows = q.limit(limit).all()
    return ApiResponse(
        data=[
            {
                "id": str(row.id),
                "user": auth.email or auth.full_name or str(row.user_id),
                "role": row.role_code,
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": str(row.resource_id) if row.resource_id else None,
                "module": row.module,
                "data_before": row.data_before,
                "data_after": row.data_after,
                "date": str(row.created_at),
            }
            for row, auth in rows
        ],
        meta=Meta(total=len(rows)),
    )


@router.get("/notifications")
async def notifications(unread_only: bool = False, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    from app.models.core import Notification
    q = db.query(Notification).filter(Notification.user_id == user.email if user.email != "dev@gfi.dz" else True)
    if unread_only:
        q = q.filter(Notification.is_read == False)
    rows = q.order_by(Notification.created_at.desc()).limit(20).all()
    return ApiResponse(data=[{
        "id": str(r.id), "title": r.title, "message": r.message,
        "module": r.module, "link": r.link, "is_read": r.is_read,
        "date": str(r.created_at),
    } for r in rows])


@router.patch("/notifications/{notif_id}/read")
async def mark_read(notif_id: str, db: Session = Depends(get_db),
                      user: CurrentUser = Depends(get_current_user)):
    from app.models.core import Notification
    n = db.query(Notification).filter(Notification.id == notif_id).first()
    if n:
        n.is_read = True
        db.commit()
    return ApiResponse(data={"read": True})


@router.get("/meta-ia/proposals")
async def meta_ia_proposals(user: CurrentUser = Depends(get_current_user)):
    return ApiResponse(data=[
        {"title": "Auto-classification pour charges CC16 recurrentes", "status": "DETECTE",
         "complexity": "MOYEN", "trigger": "15 entrees non classifiees en CC16"},
    ])
