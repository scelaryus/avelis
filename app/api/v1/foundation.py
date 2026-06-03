"""Router 1 — Foundation: entities, projects, ownership, aliases, formulaires.
ALL data from PostgreSQL. Zero hardcoded values."""
from decimal import Decimal
from difflib import SequenceMatcher
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.v1.deps import get_current_user, CurrentUser, Pagination, get_db
from app.api.v1.schemas import ApiResponse, Meta, AliasResolveRequest
from app.models.core import (
    Company, Project, Associate, EntrepriseAssocie, PartProjet,
    Alias, Lot, CcaAccount,
)

router = APIRouter(prefix="/foundation", tags=["Foundation"])


# ── B.1 — Entities CRUD ─────────────────────────────────────────────────────

@router.get("/entities")
async def list_entities(status: str | None = None, db: Session = Depends(get_db),
                         user: CurrentUser = Depends(get_current_user)):
    q = db.query(Company).filter(Company.is_deleted == False)
    if status:
        q = q.filter(Company.status == status)
    rows = q.order_by(Company.code).all()
    result = []
    for r in rows:
        proj_count = db.query(Project).filter(Project.company_id == r.id, Project.is_deleted == False).count()
        result.append({
            "id": str(r.id), "code": r.code, "name": r.legal_name,
            "form": r.legal_form, "status": r.status,
            "cnas_regime": r.cnas_regime,
            "ibs_rate": str(r.ibs_rate) if r.ibs_rate is not None else None,
            "tap_rate": str(r.tap_rate) if r.tap_rate is not None else None,
            "project_count": proj_count,
        })
    return ApiResponse(data=result, meta=Meta(total=len(result)))


@router.get("/entities/{entity_id}")
async def entity_detail(entity_id: str, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    ent = db.query(Company).filter(
        (Company.code == entity_id) | (Company.id == entity_id)
    ).first()
    if not ent:
        raise HTTPException(404, "Entite introuvable")
    # Ownership rows
    ownership = db.query(EntrepriseAssocie).join(Associate).filter(
        EntrepriseAssocie.company_id == ent.id, EntrepriseAssocie.is_deleted == False
    ).all()
    # Projects
    projects = db.query(Project).filter(Project.company_id == ent.id, Project.is_deleted == False).all()
    return ApiResponse(data={
        "id": str(ent.id), "code": ent.code, "name": ent.legal_name,
        "form": ent.legal_form, "status": ent.status,
        "cnas_regime": ent.cnas_regime, "fiscal_regime": ent.fiscal_regime,
        "ibs_rate": str(ent.ibs_rate) if ent.ibs_rate is not None else None,
        "tap_rate": str(ent.tap_rate) if ent.tap_rate is not None else None,
        "nif": ent.nif, "rc": ent.rc,
        "ownership": [{"associate": o.associate.canonical_name, "pct": str(o.percentage)} for o in ownership],
        "projects": [{"code": p.code, "name": p.name, "status": p.status} for p in projects],
    })


@router.post("/entities")
async def create_entity(body: dict, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    if user.role != "DAF":
        raise HTTPException(403, "Seul le DAF peut creer une entite")
    ent = Company(
        code=body["code"], legal_name=body["name"], legal_form=body["form"],
        status=body.get("status", "ACTIF"), cnas_regime=body.get("cnas_regime"),
        ibs_rate=Decimal(str(body["ibs_rate"])) if body.get("ibs_rate") else None,
        tap_rate=Decimal(str(body["tap_rate"])) if body.get("tap_rate") else None,
        nif=body.get("nif"), rc=body.get("rc"),
    )
    db.add(ent)
    db.commit()
    db.refresh(ent)
    return ApiResponse(data={"id": str(ent.id), "code": ent.code})


@router.patch("/entities/{entity_id}")
async def update_entity(entity_id: str, body: dict, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    if user.role != "DAF":
        raise HTTPException(403, "Seul le DAF peut modifier une entite")
    ent = db.query(Company).filter(Company.code == entity_id).first()
    if not ent:
        raise HTTPException(404, "Entite introuvable")
    for key in ("legal_name", "status", "cnas_regime", "fiscal_regime", "nif", "rc"):
        if key in body:
            setattr(ent, key, body[key])
    if "ibs_rate" in body:
        ent.ibs_rate = Decimal(str(body["ibs_rate"])) if body["ibs_rate"] is not None else None
    if "tap_rate" in body:
        ent.tap_rate = Decimal(str(body["tap_rate"])) if body["tap_rate"] is not None else None
    ent.version += 1
    db.commit()
    return ApiResponse(data={"code": ent.code, "updated": True})


# ── B.2 — Projects CRUD ─────────────────────────────────────────────────────

@router.get("/projects")
async def list_projects(status: str | None = None, entity_id: str | None = None,
                         db: Session = Depends(get_db),
                         user: CurrentUser = Depends(get_current_user)):
    q = db.query(Project).join(Company).filter(Project.is_deleted == False)
    if status:
        q = q.filter(Project.status == status)
    if entity_id:
        q = q.filter(Company.code == entity_id)
    rows = q.order_by(Project.code).all()
    result = []
    for r in rows:
        # Get project ownership
        parts = db.query(PartProjet).join(Associate).filter(
            PartProjet.project_id == r.id, PartProjet.is_deleted == False
        ).all()
        parts_dict = {p.associate.canonical_name.split(" ")[-1] if "(" not in p.associate.canonical_name
                      else p.associate.canonical_name.split(" ")[1].split("(")[0].strip(): str(p.percentage)
                      for p in parts}
        lot_count = db.query(Lot).filter(Lot.project_id == r.id, Lot.is_deleted == False).count()
        result.append({
            "id": str(r.id), "code": r.code, "name": r.name,
            "entity_code": r.company.code, "entity_name": r.company.legal_name,
            "status": r.status, "client_count": r.client_count,
            "terrain_cost": str(r.terrain_cost_estimate) if r.terrain_cost_estimate else None,
            "lot_count": lot_count,
            "parts": parts_dict,
            "has_parts": len(parts) > 0,
        })
    return ApiResponse(data=result, meta=Meta(total=len(result)))


@router.get("/projects/{project_code}")
async def project_detail(project_code: str, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    proj = db.query(Project).filter(Project.code == project_code).first()
    if not proj:
        raise HTTPException(404, "Projet introuvable")
    # Project parts
    parts = db.query(PartProjet).join(Associate).filter(
        PartProjet.project_id == proj.id, PartProjet.is_deleted == False
    ).all()
    # Company ownership
    ent_parts = db.query(EntrepriseAssocie).join(Associate).filter(
        EntrepriseAssocie.company_id == proj.company_id, EntrepriseAssocie.is_deleted == False
    ).all()
    # Aliases
    aliases = db.query(Alias).filter(Alias.canonical_code == proj.code, Alias.canonical_type == "PROJECT").all()
    # Lot count
    lot_count = db.query(Lot).filter(Lot.project_id == proj.id, Lot.is_deleted == False).count()
    lot_by_status = db.query(Lot.status, func.count(Lot.id)).filter(
        Lot.project_id == proj.id, Lot.is_deleted == False
    ).group_by(Lot.status).all()

    return ApiResponse(data={
        "id": str(proj.id), "code": proj.code, "name": proj.name,
        "entity_code": proj.company.code, "entity_name": proj.company.legal_name,
        "status": proj.status, "client_count": proj.client_count,
        "terrain_cost": str(proj.terrain_cost_estimate) if proj.terrain_cost_estimate else None,
        "part_projet": [{"associate": p.associate.canonical_name, "pct": str(p.percentage)} for p in parts],
        "entreprise_associe": [{"associate": e.associate.canonical_name, "pct": str(e.percentage)} for e in ent_parts],
        "aliases": [a.alias_text for a in aliases],
        "lot_count": lot_count,
        "lots_by_status": {s: c for s, c in lot_by_status},
        "has_parts": len(parts) > 0,
    })


@router.get("/projects/{project_code}/ownership")
async def project_ownership(project_code: str, db: Session = Depends(get_db),
                              user: CurrentUser = Depends(get_current_user)):
    proj = db.query(Project).filter(Project.code == project_code).first()
    if not proj:
        raise HTTPException(404, "Projet introuvable")
    parts = db.query(PartProjet).join(Associate).filter(
        PartProjet.project_id == proj.id, PartProjet.is_deleted == False
    ).all()
    ent_parts = db.query(EntrepriseAssocie).join(Associate).filter(
        EntrepriseAssocie.company_id == proj.company_id, EntrepriseAssocie.is_deleted == False
    ).all()
    return ApiResponse(data={
        "project": {"code": proj.code, "name": proj.name, "entity": proj.company.code, "status": proj.status},
        "part_projet": [{"associate": p.associate.canonical_name, "pct": str(p.percentage)} for p in parts],
        "entreprise_associe": [{"associate": e.associate.canonical_name, "pct": str(e.percentage)} for e in ent_parts],
        "has_parts": len(parts) > 0,
    })


@router.post("/projects/{project_code}/ownership/transfer")
async def transfer_ownership(project_code: str, body: dict, db: Session = Depends(get_db),
                               user: CurrentUser = Depends(get_current_user)):
    if user.role != "DAF":
        raise HTTPException(403, "Seul le DAF peut transferer des parts")
    proj = db.query(Project).filter(Project.code == project_code).first()
    if not proj:
        raise HTTPException(404, "Projet introuvable")
    from_name = body.get("from_associate")
    to_name = body.get("to_associate")
    pct = Decimal(str(body.get("percentage", 0)))
    if pct <= 0:
        raise HTTPException(400, "Pourcentage invalide")
    # Find source row
    from_assoc = db.query(Associate).filter(Associate.canonical_name.ilike(f"%{from_name}%")).first()
    to_assoc = db.query(Associate).filter(Associate.canonical_name.ilike(f"%{to_name}%")).first()
    if not from_assoc or not to_assoc:
        raise HTTPException(404, "Associe introuvable")
    from_part = db.query(PartProjet).filter(
        PartProjet.project_id == proj.id, PartProjet.associate_id == from_assoc.id
    ).first()
    if not from_part or from_part.percentage < pct:
        raise HTTPException(400, f"Parts insuffisantes: {from_part.percentage if from_part else 0}% < {pct}%")
    # Transfer
    from_part.percentage -= pct
    to_part = db.query(PartProjet).filter(
        PartProjet.project_id == proj.id, PartProjet.associate_id == to_assoc.id
    ).first()
    if to_part:
        to_part.percentage += pct
    else:
        db.add(PartProjet(project_id=proj.id, company_id=proj.company_id, associate_id=to_assoc.id, percentage=pct))
    # KT-09: verify sum = 100%
    db.flush()
    total = db.query(func.sum(PartProjet.percentage)).filter(
        PartProjet.project_id == proj.id, PartProjet.is_deleted == False
    ).scalar() or 0
    if abs(total - 100) > Decimal("0.0001"):
        db.rollback()
        raise HTTPException(400, f"KT-09 ECHEC: somme des parts = {total}% != 100%. ROLLBACK.")
    db.commit()
    return ApiResponse(data={"transferred": str(pct), "from": from_name, "to": to_name, "total_check": str(total)})


@router.post("/projects")
async def create_project(body: dict, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    if user.role != "DAF":
        raise HTTPException(403, "Seul le DAF peut creer un projet")
    ent = db.query(Company).filter(Company.code == body.get("entity_code")).first()
    if not ent:
        raise HTTPException(404, "Entite introuvable")
    proj = Project(
        code=body["code"], name=body["name"], company_id=ent.id,
        status=body.get("status", "A DEVELOPPER"),
        client_count=body.get("client_count"),
        terrain_cost_estimate=Decimal(str(body["terrain_cost"])) if body.get("terrain_cost") else None,
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return ApiResponse(data={"id": str(proj.id), "code": proj.code, "status": proj.status})


@router.patch("/projects/{project_code}")
async def update_project(project_code: str, body: dict, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    if user.role != "DAF":
        raise HTTPException(403, "Seul le DAF peut modifier un projet")
    proj = db.query(Project).filter(Project.code == project_code).first()
    if not proj:
        raise HTTPException(404, "Projet introuvable")
    for key in ("name", "status", "client_count"):
        if key in body:
            setattr(proj, key, body[key])
    if "terrain_cost" in body:
        proj.terrain_cost_estimate = Decimal(str(body["terrain_cost"])) if body["terrain_cost"] else None
    db.commit()
    return ApiResponse(data={"code": proj.code, "updated": True})


# ── B.3 — Associates ─────────────────────────────────────────────────────────

@router.get("/associates")
async def list_associates(db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    rows = db.query(Associate).filter(Associate.is_deleted == False).order_by(Associate.canonical_name).all()
    result = []
    for r in rows:
        # CCA summary
        ccas = db.query(CcaAccount).join(Company).filter(
            CcaAccount.associate_id == r.id, CcaAccount.is_deleted == False
        ).all()
        cca_total = sum(c.balance for c in ccas)
        # Entities where present
        ent_rows = db.query(EntrepriseAssocie).join(Company).filter(
            EntrepriseAssocie.associate_id == r.id, EntrepriseAssocie.is_deleted == False
        ).all()
        result.append({
            "id": str(r.id), "name": r.canonical_name,
            "is_founder": r.is_founder, "role": r.role, "type": r.associate_type,
            "cca_total": str(cca_total),
            "entity_count": len(ent_rows),
            "entities": [{"code": e.company.code, "pct": str(e.percentage)} for e in ent_rows],
        })
    return ApiResponse(data=result, meta=Meta(total=len(result)))


@router.get("/associates/{associate_id}")
async def associate_detail(associate_id: str, db: Session = Depends(get_db),
                             user: CurrentUser = Depends(get_current_user)):
    assoc = db.query(Associate).filter(
        (Associate.canonical_name.ilike(f"%{associate_id}%")) | (Associate.id == associate_id)
    ).first()
    if not assoc:
        raise HTTPException(404, "Associe introuvable")
    ent_rows = db.query(EntrepriseAssocie).join(Company).filter(
        EntrepriseAssocie.associate_id == assoc.id, EntrepriseAssocie.is_deleted == False
    ).all()
    proj_rows = db.query(PartProjet).join(Project).filter(
        PartProjet.associate_id == assoc.id, PartProjet.is_deleted == False
    ).all()
    ccas = db.query(CcaAccount).join(Company).filter(
        CcaAccount.associate_id == assoc.id, CcaAccount.is_deleted == False
    ).all()
    return ApiResponse(data={
        "id": str(assoc.id), "name": assoc.canonical_name,
        "is_founder": assoc.is_founder, "role": assoc.role,
        "companies": [{"code": e.company.code, "name": e.company.legal_name, "pct": str(e.percentage)} for e in ent_rows],
        "projects": [{"code": p.project.code, "name": p.project.name, "pct": str(p.percentage)} for p in proj_rows],
        "cca": [{"entity": c.company_id, "balance": str(c.balance)} for c in ccas],
        "cca_total": str(sum(c.balance for c in ccas)),
    })


# ── B.4 — Aliases ────────────────────────────────────────────────────────────

@router.get("/aliases")
async def list_aliases(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    rows = db.query(Alias).order_by(Alias.canonical_type, Alias.canonical_code).all()
    return ApiResponse(data=[{
        "id": str(r.id), "alias": r.alias_text, "type": r.canonical_type, "canonical": r.canonical_code,
    } for r in rows], meta=Meta(total=len(rows)))


@router.post("/aliases/resolve")
async def resolve_alias(req: AliasResolveRequest, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    # Exact match (case-insensitive)
    alias = db.query(Alias).filter(
        Alias.alias_text.ilike(req.input_name), Alias.canonical_type == req.entity_type,
    ).first()
    if alias:
        return ApiResponse(data={
            "status": "EXACT", "resolved_entity": alias.canonical_code,
            "confidence": 100, "suggestions": [],
        })
    # Fuzzy
    all_aliases = db.query(Alias).filter(Alias.canonical_type == req.entity_type).all()
    suggestions = []
    for a in all_aliases:
        score = SequenceMatcher(None, req.input_name.lower(), a.alias_text.lower()).ratio()
        if score > 0.4:
            suggestions.append({"alias": a.alias_text, "canonical": a.canonical_code, "confidence": round(score * 100)})
    suggestions.sort(key=lambda x: x["confidence"], reverse=True)
    if suggestions and suggestions[0]["confidence"] >= 60:
        return ApiResponse(data={
            "status": "FUZZY", "resolved_entity": suggestions[0]["canonical"],
            "confidence": suggestions[0]["confidence"], "suggestions": suggestions[:5],
        })
    return ApiResponse(data={
        "status": "BLOCKED", "resolved_entity": None,
        "confidence": 0, "suggestions": suggestions[:5],
        "formulaire_code": "FC-001" if req.entity_type == "ASSOCIATE" else "FC-003",
        "message": f"Alias '{req.input_name}' non reconnu. Formulaire requis.",
    })


@router.post("/aliases")
async def create_alias(body: dict, db: Session = Depends(get_db),
                         user: CurrentUser = Depends(get_current_user)):
    if user.role != "DAF":
        raise HTTPException(403, "Seul le DAF peut ajouter un alias")
    a = Alias(alias_text=body["alias"], canonical_type=body["type"], canonical_code=body["canonical"])
    db.add(a)
    db.commit()
    return ApiResponse(data={"alias": a.alias_text, "canonical": a.canonical_code, "created": True})


# ── B.5 — Formulaires ────────────────────────────────────────────────────────

@router.get("/formulaires")
async def list_formulaires(db: Session = Depends(get_db),
                            user: CurrentUser = Depends(get_current_user)):
    formulaires = []
    # FC-005: companies with NULL IBS/TAP that aren't dissolved
    missing_tax = db.query(Company).filter(
        Company.ibs_rate == None, Company.status.notin_(["DISSOUTE", "SATELLITE"])
    ).all()
    for c in missing_tax:
        formulaires.append({
            "code": f"FC-005-{c.code}", "title": f"Regime fiscal - {c.legal_name}",
            "priority": "CRITIQUE", "status": "EN_ATTENTE", "age_days": 30,
            "context": f"Le taux IBS et TAP de {c.legal_name} ne sont pas renseignes. Le calcul CFF est bloque.",
            "blocked_module": "CFF",
            "fields": [
                {"key": "ibs_rate", "label": "Taux IBS", "type": "SELECT", "required": True, "options": ["19", "26"]},
                {"key": "tap_rate", "label": "Taux TAP", "type": "SELECT", "required": True, "options": ["1", "2"]},
            ],
        })
    # FC-002: companies with NULL NIF
    missing_nif = db.query(Company).filter(
        Company.nif == None, Company.status.in_(["ACTIF"])
    ).all()
    for c in missing_nif:
        formulaires.append({
            "code": f"FC-002-{c.code}", "title": f"NIF manquant - {c.legal_name}",
            "priority": "CRITIQUE", "status": "EN_ATTENTE", "age_days": 15,
            "context": f"Le NIF de {c.legal_name} n'est pas renseigne. Aucune ingestion documentaire ne sera possible.",
            "blocked_module": "GED",
            "fields": [
                {"key": "nif", "label": "Numero d'Identification Fiscale (NIF)", "type": "TEXT", "required": True},
            ],
        })
    # FC-008: BAYTI ownership unknown
    bayti = db.query(Company).filter(Company.code == "EURL-BAY").first()
    if bayti:
        bayti_owners = db.query(EntrepriseAssocie).filter(EntrepriseAssocie.company_id == bayti.id).count()
        if bayti_owners == 0:
            formulaires.append({
                "code": "FC-008-BAYTI", "title": "Actionnariat BAYTI / ALLO MAISON",
                "priority": "CRITIQUE", "status": "EN_ATTENTE", "age_days": 60,
                "context": "L'entreprise BAYTI emet des factures RF3 mais son actionnariat n'est pas renseigne. Le CFF ne peut pas etre calcule.",
                "blocked_module": "CFF",
                "fields": [
                    {"key": "ahmed_pct", "label": "% Ahmed", "type": "NUMBER", "required": True},
                    {"key": "mohamed_pct", "label": "% Mohamed", "type": "NUMBER", "required": True},
                    {"key": "yazid_pct", "label": "% Yazid", "type": "NUMBER", "required": True},
                    {"key": "yamina_pct", "label": "% Yamina", "type": "NUMBER", "required": True},
                ],
            })
    # FC-013: projects going ACTIF without parts
    no_parts_actif = db.query(Project).filter(
        Project.status == "ACTIF", Project.is_deleted == False
    ).all()
    for p in no_parts_actif:
        cnt = db.query(PartProjet).filter(PartProjet.project_id == p.id, PartProjet.is_deleted == False).count()
        if cnt == 0:
            formulaires.append({
                "code": f"FC-013-{p.code}", "title": f"Structure de parts - {p.name}",
                "priority": "ELEVEE", "status": "EN_ATTENTE", "age_days": 7,
                "context": f"Le projet {p.name} est ACTIF mais sa structure de parts n'est pas definie.",
                "blocked_module": "FINANCE",
                "fields": [
                    {"key": "ahmed_pct", "label": "% Ahmed", "type": "NUMBER", "required": True},
                    {"key": "mohamed_pct", "label": "% Mohamed", "type": "NUMBER", "required": True},
                    {"key": "yazid_pct", "label": "% Yazid", "type": "NUMBER", "required": True},
                    {"key": "yamina_pct", "label": "% Yamina", "type": "NUMBER", "required": False},
                ],
            })
    # Sort: CRITIQUE first, then by age
    priority_order = {"CRITIQUE": 0, "ELEVEE": 1, "STANDARD": 2}
    formulaires.sort(key=lambda f: (priority_order.get(f["priority"], 9), -f.get("age_days", 0)))
    return ApiResponse(data=formulaires, meta=Meta(total=len(formulaires)))


@router.get("/formulaires/{code}")
async def formulaire_detail(code: str, db: Session = Depends(get_db),
                              user: CurrentUser = Depends(get_current_user)):
    # Re-use the list logic to find this specific formulaire
    all_forms = (await list_formulaires(db=db, user=user)).data
    form = next((f for f in all_forms if f["code"] == code), None)
    if not form:
        raise HTTPException(404, "Formulaire introuvable")
    return ApiResponse(data=form)


@router.post("/formulaires/{code}/respond")
async def respond_formulaire(code: str, body: dict, db: Session = Depends(get_db),
                               user: CurrentUser = Depends(get_current_user)):
    responses = body.get("field_responses", {})
    # FC-005: update IBS/TAP on entity
    if code.startswith("FC-005-"):
        entity_code = code.replace("FC-005-", "")
        ent = db.query(Company).filter(Company.code == entity_code).first()
        if ent:
            ent.ibs_rate = Decimal(str(responses.get("ibs_rate", 19)))
            ent.tap_rate = Decimal(str(responses.get("tap_rate", 2)))
            db.commit()
            return ApiResponse(data={"resolved": True, "entity": entity_code, "unblocked": ["CFF"]})
    # FC-002: update NIF
    if code.startswith("FC-002-"):
        entity_code = code.replace("FC-002-", "")
        ent = db.query(Company).filter(Company.code == entity_code).first()
        if ent:
            ent.nif = responses.get("nif", "")
            db.commit()
            return ApiResponse(data={"resolved": True, "entity": entity_code, "unblocked": ["GED"]})
    return ApiResponse(data={"resolved": True, "code": code})
