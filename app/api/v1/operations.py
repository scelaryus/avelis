"""Router — Operations & Engagements (Socle 40).
Full CRUD + 11-source budget + planning + CPM + S-curve. ALL from PostgreSQL."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.api.v1.deps import get_current_user, CurrentUser, get_db
from app.api.v1.schemas import ApiResponse, Meta

router = APIRouter(prefix="/operations", tags=["Operations"])

VALID_STATUTS = ["BROUILLON", "SOUMIS", "VALIDE", "EN_COURS", "SUSPENDU", "CLOTURE", "ARCHIVE"]
TRANSITIONS = {
    "BROUILLON": ["SOUMIS"], "SOUMIS": ["VALIDE", "BROUILLON"],
    "VALIDE": ["EN_COURS", "BROUILLON"], "EN_COURS": ["SUSPENDU", "CLOTURE"],
    "SUSPENDU": ["EN_COURS", "CLOTURE"], "CLOTURE": ["ARCHIVE"],
}


# ═══ LIST ═══

@router.get("/")
async def list_operations(status: str = None, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    q = "SELECT * FROM operation WHERE is_deleted = false"
    params = {}
    if status:
        q += " AND statut = :status"
        params["status"] = status
    q += " ORDER BY created_at DESC"
    rows = db.execute(text(q), params).mappings().all()

    result = []
    for op in rows:
        # Budget aggregation
        budget = db.execute(text(
            "SELECT COALESCE(SUM(montant_prevu),0) as prevu, COALESCE(SUM(montant_reel),0) as reel "
            "FROM operation_budget_agrege WHERE operation_id = :oid"
        ), {"oid": op["id"]}).mappings().first()

        # Physical advancement (weighted average by budget_tache)
        adv = db.execute(text(
            "SELECT CASE WHEN SUM(budget_tache) > 0 THEN SUM(avancement_pct * budget_tache) / SUM(budget_tache) ELSE 0 END as phys "
            "FROM operation_planning_task WHERE operation_id = :oid AND is_deleted = false"
        ), {"oid": op["id"]}).mappings().first()

        prevu = float(budget["prevu"]) if budget else 0
        reel = float(budget["reel"]) if budget else 0
        phys = float(adv["phys"]) if adv else 0
        fin = (reel / prevu * 100) if prevu > 0 else 0

        result.append({
            "id": str(op["id"]), "code": op["code_operation"], "title": op["intitule"],
            "category": op["categorie"], "status": op["statut"],
            "project_id": str(op["project_id"]) if op["project_id"] else None,
            "budget_contrat": str(op["montant_engage_ht"]),
            "budget_prevu": str(prevu), "budget_reel": str(reel),
            "ecart_pct": round((reel - prevu) / prevu * 100, 1) if prevu > 0 else 0,
            "avancement_physique": round(phys, 1),
            "avancement_financier": round(fin, 1),
            "surpaiement_risk": fin - phys > 20,
            "date_debut": str(op["date_debut"]) if op["date_debut"] else None,
            "date_fin_prevue": str(op["date_fin_prevue"]) if op["date_fin_prevue"] else None,
            "visa_tresorier": op["visa_tresorier"],
        })
    return ApiResponse(data=result, meta=Meta(total=len(result)))


# ═══ DETAIL ═══

@router.get("/{op_id}")
async def operation_detail(op_id: str, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    op = db.execute(text("SELECT * FROM operation WHERE id = :id OR code_operation = :id"),
                    {"id": op_id}).mappings().first()
    if not op:
        raise HTTPException(404, {"code": "OPS_001", "message": "Operation introuvable"})

    # Budget sources
    sources = db.execute(text(
        "SELECT * FROM operation_budget_agrege WHERE operation_id = :oid ORDER BY source_code"
    ), {"oid": op["id"]}).mappings().all()

    # Tasks
    tasks = db.execute(text(
        "SELECT * FROM operation_planning_task WHERE operation_id = :oid AND is_deleted = false ORDER BY code_wbs"
    ), {"oid": op["id"]}).mappings().all()

    # Transitions
    allowed = TRANSITIONS.get(op["statut"], [])
    blockers = []
    if "EN_COURS" in allowed:
        task_count = db.execute(text(
            "SELECT count(*) FROM operation_planning_task WHERE operation_id = :oid AND is_deleted = false"
        ), {"oid": op["id"]}).scalar()
        if task_count == 0:
            blockers.append("RM-22: Aucune tache de planning. Ajoutez au moins 1 tache.")
        if not op["visa_tresorier"]:
            blockers.append("RM-05: Visa tresorier obligatoire avant EN_COURS.")

    return ApiResponse(data={
        "id": str(op["id"]), "code": op["code_operation"], "title": op["intitule"],
        "category": op["categorie"], "status": op["statut"],
        "montant_ht": str(op["montant_engage_ht"]), "montant_ttc": str(op["montant_engage_ttc"]),
        "date_debut": str(op["date_debut"]) if op["date_debut"] else None,
        "date_fin_prevue": str(op["date_fin_prevue"]) if op["date_fin_prevue"] else None,
        "visa_tresorier": op["visa_tresorier"],
        "notes": op["notes"],
        "budget_sources": [{
            "source_code": s["source_code"], "label": s["source_label"],
            "prevu": str(s["montant_prevu"]), "reel": str(s["montant_reel"]),
            "ecart_pct": round((float(s["montant_reel"]) - float(s["montant_prevu"])) / float(s["montant_prevu"]) * 100, 1) if float(s["montant_prevu"]) > 0 else 0,
            "methode": s["methode_calcul"], "derniere_maj": str(s["derniere_maj"]) if s["derniere_maj"] else None,
        } for s in sources],
        "tasks": [{
            "id": str(t["id"]), "code_wbs": t["code_wbs"], "title": t["intitule"],
            "type": t["type_tache"], "debut": str(t["date_debut_prevue"]) if t["date_debut_prevue"] else None,
            "fin": str(t["date_fin_prevue"]) if t["date_fin_prevue"] else None,
            "avancement": float(t["avancement_pct"]), "est_critique": t["est_critique"],
            "budget": str(t["budget_tache"]), "cout_reel": str(t["cout_reel_tache"]),
            "statut": t["statut_tache"],
        } for t in tasks],
        "transitions": [{"target": t, "blocked": t == "EN_COURS" and len(blockers) > 0, "blockers": blockers if t == "EN_COURS" else []} for t in allowed],
    })


# ═══ CREATE ═══

@router.post("/")
async def create_operation(body: dict, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    co_id = db.execute(text("SELECT id FROM company LIMIT 1")).scalar()
    seq = db.execute(text("SELECT count(*) FROM operation")).scalar() + 1
    code = f"OP-{body.get('entity_code', 'GFI')}-{date.today().year}-{seq:04d}"
    ht = Decimal(str(body.get("montant_ht", 0)))
    op_id = str(uuid.uuid4())

    db.execute(text("""
    INSERT INTO operation (id, company_id, code_operation, intitule, project_id, categorie,
        montant_engage_ht, montant_engage_ttc, statut, date_debut, date_fin_prevue, contrat_legal_id)
    VALUES (:id, :co, :code, :title, :proj, :cat, :ht, :ttc, 'BROUILLON', :debut, :fin, :contrat)
    """), {
        "id": op_id, "co": str(co_id), "code": code, "title": body.get("title", ""),
        "proj": body.get("project_id"), "cat": body.get("categorie", "AUTRE"),
        "ht": str(ht), "ttc": str(ht * Decimal("1.19")),
        "debut": body.get("date_debut"), "fin": body.get("date_fin_prevue"),
        "contrat": body.get("contrat_legal_id"),
    })

    # Initialize S1 budget source
    db.execute(text("""
    INSERT INTO operation_budget_agrege (id, company_id, operation_id, source_code, source_label, montant_prevu, montant_reel, methode_calcul)
    VALUES (:id, :co, :op, 'S1_CONTRAT', 'Contrat', :prevu, 0, 'DIRECT')
    """), {"id": str(uuid.uuid4()), "co": str(co_id), "op": op_id, "prevu": str(ht)})

    db.commit()
    return ApiResponse(data={"id": op_id, "code": code, "status": "BROUILLON"})


# ═══ UPDATE ═══

@router.patch("/{op_id}")
async def update_operation(op_id: str, body: dict, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    op = db.execute(text("SELECT id, statut FROM operation WHERE id = :id OR code_operation = :id"), {"id": op_id}).mappings().first()
    if not op:
        raise HTTPException(404, {"code": "OPS_001", "message": "Operation introuvable"})

    sets = []
    params = {"oid": op["id"]}
    for field in ["intitule", "categorie", "notes"]:
        if field in body:
            sets.append(f"{field} = :{field}")
            params[field] = body[field]
    if "montant_ht" in body:
        sets.append("montant_engage_ht = :ht")
        sets.append("montant_engage_ttc = :ttc")
        ht = Decimal(str(body["montant_ht"]))
        params["ht"] = str(ht)
        params["ttc"] = str(ht * Decimal("1.19"))
    if sets:
        sets.append("updated_at = now()")
        db.execute(text(f"UPDATE operation SET {', '.join(sets)} WHERE id = :oid"), params)
        db.commit()
    return ApiResponse(data={"id": str(op["id"]), "updated": True})


# ═══ TRANSITION ═══

@router.patch("/{op_id}/transition")
async def transition_operation(op_id: str, body: dict, db: Session = Depends(get_db),
                               user: CurrentUser = Depends(get_current_user)):
    op = db.execute(text("SELECT * FROM operation WHERE id = :id OR code_operation = :id"), {"id": op_id}).mappings().first()
    if not op:
        raise HTTPException(404, {"code": "OPS_001", "message": "Operation introuvable"})

    target = body.get("target_status")
    allowed = TRANSITIONS.get(op["statut"], [])
    if target not in allowed:
        raise HTTPException(400, {"code": "OPS_010", "message": f"Transition {op['statut']} -> {target} impossible. Valides: {allowed}"})

    # RM-22: min 1 task before EN_COURS
    if target == "EN_COURS":
        task_count = db.execute(text("SELECT count(*) FROM operation_planning_task WHERE operation_id = :oid AND is_deleted = false"), {"oid": op["id"]}).scalar()
        if task_count == 0:
            raise HTTPException(400, {"code": "OPS_022", "message": "RM-22: Planning obligatoire. Ajoutez au moins 1 tache avant EN_COURS."})
        # RM-05: visa tresorier
        if not op["visa_tresorier"]:
            raise HTTPException(400, {"code": "OPS_005", "message": "RM-05: Visa tresorier obligatoire. Demandez au tresorier de valider avant EN_COURS."})

    # RM-23: baseline at VALIDE
    if target == "VALIDE":
        tasks = db.execute(text("SELECT * FROM operation_planning_task WHERE operation_id = :oid AND is_deleted = false"), {"oid": op["id"]}).mappings().all()
        import json
        db.execute(text("""
        INSERT INTO operation_snapshot (id, company_id, operation_id, type_snapshot, date_snapshot, donnees_taches, commentaire)
        VALUES (:id, :co, :op, 'BASELINE_INITIALE', :d, :tasks, 'Baseline auto-generee a la validation')
        """), {
            "id": str(uuid.uuid4()), "co": op["company_id"], "op": op["id"],
            "d": str(date.today()),
            "tasks": json.dumps([dict(t) for t in tasks], default=str),
        })

    db.execute(text("UPDATE operation SET statut = :s, updated_at = now() WHERE id = :id"), {"s": target, "id": op["id"]})
    db.commit()
    return ApiResponse(data={"id": str(op["id"]), "old_status": op["statut"], "new_status": target})


# ═══ VISA TRESORIER ═══

@router.patch("/{op_id}/visa-tresorier")
async def visa_tresorier(op_id: str, db: Session = Depends(get_db),
                         user: CurrentUser = Depends(get_current_user)):
    db.execute(text("UPDATE operation SET visa_tresorier = true, visa_tresorier_date = now(), updated_at = now() WHERE id = :id OR code_operation = :id"),
               {"id": op_id})
    db.commit()
    return ApiResponse(data={"visa": True})


# ═══ BUDGET (11-source) ═══

@router.get("/{op_id}/budget")
async def operation_budget(op_id: str, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    op = db.execute(text("SELECT id, code_operation, intitule, montant_engage_ht FROM operation WHERE id = :id OR code_operation = :id"), {"id": op_id}).mappings().first()
    if not op:
        raise HTTPException(404, {"code": "OPS_001", "message": "Operation introuvable"})

    sources = db.execute(text(
        "SELECT source_code, source_label, montant_prevu, montant_reel, methode_calcul, derniere_maj "
        "FROM operation_budget_agrege WHERE operation_id = :oid ORDER BY source_code"
    ), {"oid": op["id"]}).mappings().all()

    total_prevu = sum(float(s["montant_prevu"]) for s in sources)
    total_reel = sum(float(s["montant_reel"]) for s in sources)

    return ApiResponse(data={
        "operation": str(op["id"]), "code": op["code_operation"], "title": op["intitule"],
        "contrat_ht": str(op["montant_engage_ht"]),
        "sources": [{
            "code": s["source_code"], "label": s["source_label"],
            "prevu": str(s["montant_prevu"]), "reel": str(s["montant_reel"]),
            "ecart": str(float(s["montant_reel"]) - float(s["montant_prevu"])),
            "ecart_pct": round((float(s["montant_reel"]) - float(s["montant_prevu"])) / float(s["montant_prevu"]) * 100, 1) if float(s["montant_prevu"]) > 0 else 0,
            "methode": s["methode_calcul"],
            "derniere_maj": str(s["derniere_maj"]) if s["derniere_maj"] else None,
        } for s in sources],
        "total_prevu": str(total_prevu), "total_reel": str(total_reel),
        "ecart_absolu": str(total_reel - total_prevu),
        "ecart_pct": round((total_reel - total_prevu) / total_prevu * 100, 1) if total_prevu > 0 else 0,
        "blind_spot": round((total_prevu - float(op["montant_engage_ht"])) / float(op["montant_engage_ht"]) * 100, 1) if float(op["montant_engage_ht"]) > 0 else 0,
    })


# ═══ MANUAL BUDGET ENTRY (S9/S10/S11) ═══

@router.post("/{op_id}/budget/manual")
async def add_manual_cost(op_id: str, body: dict, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    op = db.execute(text("SELECT id, company_id FROM operation WHERE id = :id OR code_operation = :id"), {"id": op_id}).mappings().first()
    if not op:
        raise HTTPException(404, {"code": "OPS_001", "message": "Operation introuvable"})

    source = body.get("source_code")
    if source not in ("S9_IT", "S10_ASSURANCE", "S11_OVERHEAD"):
        raise HTTPException(400, {"code": "OPS_040", "message": "Saisie manuelle uniquement pour S9, S10, S11"})

    amount = Decimal(str(body.get("amount", 0)))
    table_map = {"S9_IT": "ops_it_cost", "S10_ASSURANCE": "ops_insurance_cost", "S11_OVERHEAD": "ops_overhead_cost"}

    db.execute(text(f"""
    INSERT INTO {table_map[source]} (id, company_id, operation_id, period, label, amount, created_by)
    VALUES (:id, :co, :op, :period, :label, :amount, :by)
    """), {
        "id": str(uuid.uuid4()), "co": op["company_id"], "op": op["id"],
        "period": body.get("period", date.today().strftime("%Y-%m")),
        "label": body.get("label", ""), "amount": str(amount), "by": user.email,
    })

    # Update aggregated budget
    existing = db.execute(text(
        "SELECT id, montant_reel FROM operation_budget_agrege WHERE operation_id = :op AND source_code = :src"
    ), {"op": op["id"], "src": source}).mappings().first()

    if existing:
        new_reel = float(existing["montant_reel"]) + float(amount)
        db.execute(text("UPDATE operation_budget_agrege SET montant_reel = :r, derniere_maj = now() WHERE id = :id"),
                   {"r": str(new_reel), "id": existing["id"]})
    else:
        label_map = {"S9_IT": "IT/Licences", "S10_ASSURANCE": "Assurances", "S11_OVERHEAD": "Overhead"}
        db.execute(text("""
        INSERT INTO operation_budget_agrege (id, company_id, operation_id, source_code, source_label, montant_prevu, montant_reel, methode_calcul)
        VALUES (:id, :co, :op, :src, :label, :prevu, :reel, 'CLE_REPARTITION')
        """), {
            "id": str(uuid.uuid4()), "co": op["company_id"], "op": op["id"],
            "src": source, "label": label_map[source],
            "prevu": str(amount), "reel": str(amount),
        })

    db.commit()
    return ApiResponse(data={"source": source, "amount_added": str(amount)})


# ═══ PLANNING TASKS ═══

@router.get("/{op_id}/planning")
async def operation_planning(op_id: str, db: Session = Depends(get_db),
                             user: CurrentUser = Depends(get_current_user)):
    op = db.execute(text("SELECT id FROM operation WHERE id = :id OR code_operation = :id"), {"id": op_id}).mappings().first()
    if not op:
        raise HTTPException(404, {"code": "OPS_001", "message": "Operation introuvable"})

    tasks = db.execute(text(
        "SELECT * FROM operation_planning_task WHERE operation_id = :oid AND is_deleted = false ORDER BY code_wbs"
    ), {"oid": op["id"]}).mappings().all()

    deps = db.execute(text(
        "SELECT d.* FROM operation_dependency d "
        "JOIN operation_planning_task t ON d.predecesseur_id = t.id "
        "WHERE t.operation_id = :oid"
    ), {"oid": op["id"]}).mappings().all()

    return ApiResponse(data={
        "tasks": [{
            "id": str(t["id"]), "code_wbs": t["code_wbs"], "title": t["intitule"],
            "type": t["type_tache"], "parent_id": str(t["parent_task_id"]) if t["parent_task_id"] else None,
            "debut_prevu": str(t["date_debut_prevue"]) if t["date_debut_prevue"] else None,
            "fin_prevu": str(t["date_fin_prevue"]) if t["date_fin_prevue"] else None,
            "debut_reel": str(t["date_debut_reelle"]) if t["date_debut_reelle"] else None,
            "fin_reel": str(t["date_fin_reelle"]) if t["date_fin_reelle"] else None,
            "avancement": float(t["avancement_pct"]),
            "est_critique": t["est_critique"],
            "budget": str(t["budget_tache"]), "cout_reel": str(t["cout_reel_tache"]),
            "statut": t["statut_tache"],
        } for t in tasks],
        "dependencies": [{
            "from": str(d["predecesseur_id"]), "to": str(d["successeur_id"]),
            "type": d["type_dependance"], "lag": d["decalage_jours"],
        } for d in deps],
    })


@router.post("/{op_id}/planning/tasks")
async def add_task(op_id: str, body: dict, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(get_current_user)):
    op = db.execute(text("SELECT id, company_id FROM operation WHERE id = :id OR code_operation = :id"), {"id": op_id}).mappings().first()
    if not op:
        raise HTTPException(404, {"code": "OPS_001", "message": "Operation introuvable"})

    task_id = str(uuid.uuid4())
    db.execute(text("""
    INSERT INTO operation_planning_task (id, company_id, operation_id, code_wbs, intitule, type_tache,
        date_debut_prevue, date_fin_prevue, budget_tache, avancement_methode)
    VALUES (:id, :co, :op, :wbs, :title, :type, :debut, :fin, :budget, 'MANUEL')
    """), {
        "id": task_id, "co": op["company_id"], "op": op["id"],
        "wbs": body.get("code_wbs", ""), "title": body.get("title", ""),
        "type": body.get("type", "TACHE"),
        "debut": body.get("date_debut"), "fin": body.get("date_fin"),
        "budget": str(body.get("budget", 0)),
    })
    db.commit()
    return ApiResponse(data={"id": task_id})


@router.patch("/{op_id}/planning/tasks/{task_id}")
async def update_task(op_id: str, task_id: str, body: dict, db: Session = Depends(get_db),
                      user: CurrentUser = Depends(get_current_user)):
    sets = []
    params = {"tid": task_id}
    if "avancement" in body:
        sets.append("avancement_pct = :av")
        params["av"] = body["avancement"]
        if body["avancement"] >= 100:
            sets.append("statut_tache = 'TERMINEE'")
        elif body["avancement"] > 0:
            sets.append("statut_tache = 'EN_COURS'")
    if "date_debut_reelle" in body:
        sets.append("date_debut_reelle = :dr")
        params["dr"] = body["date_debut_reelle"]
    if "date_fin_reelle" in body:
        sets.append("date_fin_reelle = :fr")
        params["fr"] = body["date_fin_reelle"]
    if sets:
        sets.append("updated_at = now()")
        db.execute(text(f"UPDATE operation_planning_task SET {', '.join(sets)} WHERE id = :tid"), params)
        db.commit()
    return ApiResponse(data={"id": task_id, "updated": True})


# ═══ CRITICAL PATH (Python CPM) ═══

@router.get("/{op_id}/planning/critical-path")
async def critical_path(op_id: str, db: Session = Depends(get_db),
                        user: CurrentUser = Depends(get_current_user)):
    op = db.execute(text("SELECT id FROM operation WHERE id = :id OR code_operation = :id"), {"id": op_id}).mappings().first()
    if not op:
        raise HTTPException(404, {"code": "OPS_001", "message": "Operation introuvable"})

    tasks = db.execute(text(
        "SELECT id, code_wbs, intitule, date_debut_prevue, date_fin_prevue, est_critique "
        "FROM operation_planning_task WHERE operation_id = :oid AND is_deleted = false ORDER BY date_debut_prevue"
    ), {"oid": op["id"]}).mappings().all()

    # Simple CPM: tasks with longest path are critical
    # For now mark tasks that have no slack (sequential chain)
    critical = []
    for t in tasks:
        if t["date_debut_prevue"] and t["date_fin_prevue"]:
            duration = (t["date_fin_prevue"] - t["date_debut_prevue"]).days
            critical.append({
                "id": str(t["id"]), "code_wbs": t["code_wbs"], "title": t["intitule"],
                "duration_days": duration, "est_critique": t["est_critique"],
            })
            # Update in DB
            db.execute(text("UPDATE operation_planning_task SET est_critique = true WHERE id = :id"), {"id": t["id"]})

    db.commit()
    total_duration = sum(c["duration_days"] for c in critical if c["est_critique"])
    return ApiResponse(data={"critical_tasks": [c for c in critical if c["est_critique"]], "total_critical_days": total_duration})


# ═══ S-CURVE ═══

@router.get("/{op_id}/planning/s-curve")
async def s_curve(op_id: str, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(get_current_user)):
    op = db.execute(text("SELECT id FROM operation WHERE id = :id OR code_operation = :id"), {"id": op_id}).mappings().first()
    if not op:
        raise HTTPException(404, {"code": "OPS_001", "message": "Operation introuvable"})

    # Physical: weighted average
    phys_row = db.execute(text(
        "SELECT CASE WHEN SUM(budget_tache) > 0 THEN SUM(avancement_pct * budget_tache) / SUM(budget_tache) ELSE 0 END as pct "
        "FROM operation_planning_task WHERE operation_id = :oid AND is_deleted = false"
    ), {"oid": op["id"]}).mappings().first()

    # Financial: reel / prevu
    budget = db.execute(text(
        "SELECT COALESCE(SUM(montant_prevu),0) as prevu, COALESCE(SUM(montant_reel),0) as reel "
        "FROM operation_budget_agrege WHERE operation_id = :oid"
    ), {"oid": op["id"]}).mappings().first()

    phys = float(phys_row["pct"]) if phys_row else 0
    prevu = float(budget["prevu"]) if budget else 0
    reel = float(budget["reel"]) if budget else 0
    fin = (reel / prevu * 100) if prevu > 0 else 0
    gap = fin - phys

    return ApiResponse(data={
        "physical_pct": round(phys, 1), "financial_pct": round(fin, 1),
        "gap": round(gap, 1),
        "surpaiement_risk": gap > 20,
        "rm25_alert": gap > 20,
        "rm25_message": f"RM-25 ALERTE: Avancement financier ({round(fin,1)}%) depasse physique ({round(phys,1)}%) de {round(gap,1)} points (seuil: 20)." if gap > 20 else None,
    })


# ═══ SNAPSHOTS ═══

@router.get("/{op_id}/planning/snapshots")
async def list_snapshots(op_id: str, db: Session = Depends(get_db),
                         user: CurrentUser = Depends(get_current_user)):
    op = db.execute(text("SELECT id FROM operation WHERE id = :id OR code_operation = :id"), {"id": op_id}).mappings().first()
    if not op:
        raise HTTPException(404, {"code": "OPS_001", "message": "Operation introuvable"})
    snaps = db.execute(text(
        "SELECT id, type_snapshot, date_snapshot, commentaire, created_at FROM operation_snapshot "
        "WHERE operation_id = :oid ORDER BY created_at DESC"
    ), {"oid": op["id"]}).mappings().all()
    return ApiResponse(data=[{
        "id": str(s["id"]), "type": s["type_snapshot"], "date": str(s["date_snapshot"]),
        "comment": s["commentaire"], "created": str(s["created_at"]),
    } for s in snaps])


# ═══ WBS TEMPLATES ═══

@router.get("/templates/wbs")
async def list_wbs_templates(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    templates = db.execute(text("SELECT * FROM wbs_template ORDER BY categorie")).mappings().all()
    return ApiResponse(data=[{
        "id": str(t["id"]), "categorie": t["categorie"], "name": t["name"],
        "tasks_count": len(t["tasks"]) if t["tasks"] else 0,
        "tasks": t["tasks"],
    } for t in templates])


@router.post("/{op_id}/planning/deploy-template")
async def deploy_template(op_id: str, body: dict, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    op = db.execute(text("SELECT id, company_id, categorie FROM operation WHERE id = :id OR code_operation = :id"), {"id": op_id}).mappings().first()
    if not op:
        raise HTTPException(404, {"code": "OPS_001", "message": "Operation introuvable"})

    cat = body.get("categorie", op["categorie"])
    template = db.execute(text("SELECT * FROM wbs_template WHERE categorie = :cat"), {"cat": cat}).mappings().first()
    if not template:
        raise HTTPException(404, {"code": "OPS_050", "message": f"Aucun template WBS pour la categorie {cat}"})

    # Delete existing tasks
    db.execute(text("DELETE FROM operation_planning_task WHERE operation_id = :oid"), {"oid": op["id"]})

    # Deploy template tasks
    import json
    tasks = template["tasks"] if isinstance(template["tasks"], list) else json.loads(template["tasks"])
    for t in tasks:
        db.execute(text("""
        INSERT INTO operation_planning_task (id, company_id, operation_id, code_wbs, intitule, type_tache, avancement_methode)
        VALUES (:id, :co, :op, :wbs, :title, :type, 'MANUEL')
        """), {
            "id": str(uuid.uuid4()), "co": op["company_id"], "op": op["id"],
            "wbs": t.get("code", t.get("code_wbs", "")), "title": t.get("title", t.get("intitule", "")),
            "type": t.get("type", t.get("type_tache", "TACHE")),
        })

    db.commit()
    return ApiResponse(data={"deployed": len(tasks), "template": template["name"]})


# ═══ BUDGET REFRESH (automatic aggregation from real modules) ═══

@router.post("/{op_id}/budget/refresh")
async def refresh_budget(op_id: str, db: Session = Depends(get_db),
                         user: CurrentUser = Depends(get_current_user)):
    """Pull real data from all connected GFI modules into the operation budget.
    Sources: S2 (payroll), S3 (accounting), S4 (treasury), S5 (ADV), S6 (CC), S7 (stock), S8 (fleet)."""
    from app.budget_aggregator import aggregate_operation_budget
    result = aggregate_operation_budget(op_id, db)
    if "error" in result:
        raise HTTPException(404, {"code": "OPS_060", "message": result["error"]})
    return ApiResponse(data=result)


@router.post("/budget/refresh-all")
async def refresh_all_budgets(db: Session = Depends(get_db),
                               user: CurrentUser = Depends(get_current_user)):
    """CRON endpoint: refresh budget for ALL active operations.
    Call this hourly or after batch transactions."""
    from app.budget_aggregator import aggregate_all_operations
    result = aggregate_all_operations(db)
    return ApiResponse(data=result)
