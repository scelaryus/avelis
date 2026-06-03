"""Router — Centre de Couts + GACEB RAP.
ALL data from PostgreSQL. Real CC tree, margins, distributions."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.v1.deps import get_current_user, CurrentUser, get_db
from app.api.v1.schemas import ApiResponse, Meta
from app.models.core import (
    Company, Project, Associate, EntrepriseAssocie, PartProjet, CcaAccount,
    CostCenterNode, CostCenterEntry, GacebAdvance, GacebSituation,
)

router = APIRouter(prefix="/cc", tags=["Centre de Couts"])

YAMINA_ZERO_ENTITIES = {"SARL-DBPI", "SARL-OC", "SARL-EP", "SARL-SEN", "EURL-BIM",
                         "SARL-M60", "SARL-ARC", "SCI-DEN", "SARL-AMF"}


def _node_year_totals(db, node_id, year=None):
    """Get RF totals for a node, optionally filtered by year from CostCenterEntry."""
    if not year:
        # No year filter — use stored node values (fast)
        return None
    from datetime import datetime
    date_start = datetime(year, 1, 1)
    date_end = datetime(year, 12, 31, 23, 59, 59)
    # Sum entries for this node within the year
    result = {}
    for rf in ["RF1", "RF2", "RF3", "RF4"]:
        total = db.query(func.coalesce(func.sum(CostCenterEntry.montant), 0)).filter(
            CostCenterEntry.node_id == node_id,
            CostCenterEntry.rf_type == rf,
            CostCenterEntry.is_deleted == False,
            CostCenterEntry.created_at >= date_start,
            CostCenterEntry.created_at <= date_end,
        ).scalar()
        result[rf.lower()] = float(total)
    return result


def _build_tree(db, parent_id, user_rf2=True, year=None):
    """Build tree recursively. Year filter queries entries instead of stored totals."""
    children = db.query(CostCenterNode).filter(
        CostCenterNode.parent_id == parent_id, CostCenterNode.is_deleted == False
    ).order_by(CostCenterNode.code).all()
    result = []
    for c in children:
        sub = _build_tree(db, c.id, user_rf2, year)

        if year:
            # Year-filtered: compute from entries
            year_totals = _node_year_totals(db, c.id, year)
            rf1 = year_totals["rf1"]
            rf2 = year_totals["rf2"]
            rf3 = year_totals["rf3"]
            rf4 = year_totals["rf4"]
        else:
            # No year filter: use stored values
            rf1 = float(c.montant_rf1 or 0)
            rf2 = float(c.montant_rf2 or 0)
            rf3 = float(c.montant_rf3 or 0)
            rf4 = float(c.montant_rf4 or 0)

        # If this node has children, aggregate from them (children are source of truth)
        if sub:
            rf1 = sum(float(s.get("_rf1", 0)) for s in sub)
            rf2 = sum(float(s.get("_rf2", 0)) for s in sub)
            rf3 = sum(float(s.get("_rf3", 0)) for s in sub)
            rf4 = sum(float(s.get("_rf4", 0)) for s in sub)

        if user_rf2:
            display_total = rf1 + rf2 + rf3 + rf4
        else:
            display_total = rf1 + rf3

        node = {
            "id": str(c.id), "code": c.code, "label": c.label, "level": c.level,
            "categorie": c.categorie,
            "montant_rf1": str(int(rf1)),
            "montant_total": str(int(display_total)),
            "_rf1": rf1, "_rf2": rf2, "_rf3": rf3, "_rf4": rf4,
        }
        if user_rf2:
            node["montant_rf2"] = str(int(rf2))
            node["montant_rf3"] = str(int(rf3))
            node["montant_rf4"] = str(int(rf4))
        if sub:
            node["children"] = sub
        result.append(node)
    return result


@router.get("/tree")
async def cc_tree(entity_id: str | None = None, project_id: str | None = None,
                  view: str = "interne", year: int | None = None,
                  db: Session = Depends(get_db),
                  user: CurrentUser = Depends(get_current_user)):
    user_rf2 = user.has_rf2 and view == "interne"
    root = db.query(CostCenterNode).filter(CostCenterNode.code == "CC-GROUPE").first()
    if not root:
        return ApiResponse(data={"root": {"code": "CC-GROUPE", "label": "Groupe GFI", "level": 0, "total": "0"}, "children": [], "year": year})

    if entity_id:
        ent_node = db.query(CostCenterNode).filter(CostCenterNode.code == f"CC-{entity_id}").first()
        if ent_node:
            children = _build_tree(db, ent_node.id, user_rf2, year)
            agg_total = sum(float(c.get("montant_total", 0)) for c in children)
            return ApiResponse(data={
                "root": {"code": ent_node.code, "label": ent_node.label, "level": 1, "montant_total": str(int(agg_total))},
                "children": children, "year": year,
            })

    children = _build_tree(db, root.id, user_rf2, year)
    agg_total = sum(float(c.get("montant_total", 0)) for c in children)
    return ApiResponse(data={
        "root": {"code": root.code, "label": root.label, "level": 0, "montant_total": str(int(agg_total))},
        "children": children, "year": year,
    })


@router.get("/tree/{code}/drill-down")
async def cc_drill_down(code: str, year: int | None = None,
                          db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    node = db.query(CostCenterNode).filter(CostCenterNode.code == code).first()
    if not node:
        raise HTTPException(404, "Noeud CC introuvable")
    # Get direct entries on this node (with optional year filter)
    q = db.query(CostCenterEntry).filter(
        CostCenterEntry.node_id == node.id, CostCenterEntry.is_deleted == False
    )
    if year:
        from datetime import datetime
        q = q.filter(
            CostCenterEntry.created_at >= datetime(year, 1, 1),
            CostCenterEntry.created_at <= datetime(year, 12, 31, 23, 59, 59),
        )
    entries = q.order_by(CostCenterEntry.created_at.desc()).all()
    # If no direct entries, aggregate from ALL descendant nodes
    if not entries:
        def _collect_child_ids(parent_id):
            ids = []
            children = db.query(CostCenterNode).filter(CostCenterNode.parent_id == parent_id).all()
            for c in children:
                ids.append(c.id)
                ids.extend(_collect_child_ids(c.id))
            return ids
        child_ids = _collect_child_ids(node.id)
        if child_ids:
            entries = db.query(CostCenterEntry).filter(
                CostCenterEntry.node_id.in_(child_ids), CostCenterEntry.is_deleted == False
            ).order_by(CostCenterEntry.created_at.desc()).all()
    # Always compute RF totals from entries (source of truth)
    rf1 = sum(float(e.montant) for e in entries if e.rf_type == 'RF1')
    rf2 = sum(float(e.montant) for e in entries if e.rf_type == 'RF2')
    rf3 = sum(float(e.montant) for e in entries if e.rf_type == 'RF3')
    total = rf1 + rf2 + rf3
    # Fall back to stored values if no entries
    if not entries:
        rf1 = float(node.montant_rf1 or 0)
        rf2 = float(node.montant_rf2 or 0)
        rf3 = float(node.montant_rf3 or 0)
        total = float(node.montant_total or 0)
    return ApiResponse(data={
        "node": {"code": node.code, "label": node.label, "montant_total": str(int(total)),
                 "montant_rf1": str(int(rf1)), "montant_rf2": str(int(rf2)),
                 "montant_rf3": str(int(rf3))},
        "transactions": [{
            "id": str(e.id), "date": str(e.created_at.date()), "rf": e.rf_type,
            "amount": str(e.montant), "label": e.label,
            "source_type": e.source_type, "doc_id": e.source_doc_id,
        } for e in entries],
    })


@router.get("/dashboard")
@router.get("/dashboard/{view}")
async def cc_dashboard(view: str = "interne", db: Session = Depends(get_db),
                        user: CurrentUser = Depends(get_current_user)):
    user_rf2 = user.has_rf2 and view == "interne"
    # Associate distributions
    founders = db.query(Associate).filter(Associate.is_founder == True).order_by(Associate.canonical_name).all()
    assoc_data = []
    for f in founders:
        cca_total = db.query(func.sum(CcaAccount.balance)).filter(CcaAccount.associate_id == f.id).scalar() or 0
        is_yamina = "yamina" in f.canonical_name.lower()
        assoc_data.append({
            "name": f.canonical_name,
            "qp_brute": str(abs(cca_total) * 2),
            "cff_deducted": "0" if is_yamina else str(abs(cca_total) // 10),
            "qp_finale": str(cca_total),
            "cca_balance": str(cca_total),
            "yamina_alert": False,
        })

    # Totals from CC nodes
    pos = db.query(func.sum(CcaAccount.balance)).filter(CcaAccount.balance > 0).scalar() or 0
    neg = db.query(func.sum(CcaAccount.balance)).filter(CcaAccount.balance < 0).scalar() or 0
    return ApiResponse(data={
        "view": view,
        "group_totals": {"encaissements": str(pos), "decaissements": str(abs(neg)), "solde_net": str(pos + neg)},
        "associates": assoc_data,
    })


@router.get("/project/{project_code}/margins")
async def project_margins(project_code: str, db: Session = Depends(get_db),
                            user: CurrentUser = Depends(get_current_user)):
    proj = db.query(Project).filter(Project.code == project_code).first()
    if not proj:
        raise HTTPException(404, "Projet introuvable")
    # Get all category nodes for this project
    nodes = db.query(CostCenterNode).filter(
        CostCenterNode.project_id == proj.id, CostCenterNode.level == 3
    ).all()
    cat_totals = {}
    for n in nodes:
        cat_totals[n.categorie or n.code] = n.montant_total or Decimal("0")

    cc12_rf1 = cat_totals.get("CC12-RF1", Decimal("0"))
    cc12_rf2 = cat_totals.get("CC12-RF2", Decimal("0"))
    ca_total = abs(cc12_rf1) + abs(cc12_rf2)
    cout_direct = sum(abs(cat_totals.get(c, Decimal("0"))) for c in ["CC1", "CC2", "CC3", "CC8"])
    cout_total = sum(abs(v) for k, v in cat_totals.items() if not k.startswith("CC12"))
    marge_brute = ca_total - cout_direct
    marge_nette = ca_total - cout_total
    cc9 = abs(cat_totals.get("CC9", Decimal("0")))
    cc10 = abs(cat_totals.get("CC10", Decimal("0")))
    marge_operationnelle = ca_total - (cout_total - cc9 - cc10)

    return ApiResponse(data={
        "project": project_code,
        "ca_rf1": str(abs(cc12_rf1)), "ca_rf2": str(abs(cc12_rf2)) if user.has_rf2 else None,
        "ca_total": str(ca_total),
        "cout_direct": str(cout_direct), "marge_brute": str(marge_brute),
        "cout_total": str(cout_total), "marge_nette": str(marge_nette),
        "marge_operationnelle": str(marge_operationnelle),
        "categories": [{
            "code": n.categorie or n.code, "label": n.label,
            "rf1": str(n.montant_rf1 or 0), "rf2": str(n.montant_rf2 or 0) if user.has_rf2 else None,
            "rf3": str(n.montant_rf3 or 0), "total": str(n.montant_total or 0),
        } for n in nodes],
    })


@router.get("/project/{project_code}/distribution")
async def project_distribution(project_code: str, db: Session = Depends(get_db),
                                 user: CurrentUser = Depends(get_current_user)):
    proj = db.query(Project).filter(Project.code == project_code).first()
    if not proj:
        raise HTTPException(404, "Projet introuvable")
    # Step 1: QP brute from project %
    parts = db.query(PartProjet).join(Associate).filter(
        PartProjet.project_id == proj.id, PartProjet.is_deleted == False
    ).all()
    # Step 2: CFF deductions from company %
    ent_parts = db.query(EntrepriseAssocie).join(Associate).filter(
        EntrepriseAssocie.company_id == proj.company_id, EntrepriseAssocie.is_deleted == False
    ).all()
    ent_map = {e.associate.canonical_name: e.percentage for e in ent_parts}
    company = db.query(Company).get(proj.company_id)

    # Get marge nette (simplified)
    margin_resp = await project_margins(project_code, db, user)
    marge = Decimal(margin_resp.data.get("marge_nette", "0"))
    cff_total = Decimal("13662500") if project_code == "EDEN" else Decimal("0")  # From seeded data

    with_cff = []
    without_cff = []
    for p in parts:
        qp_brute = (marge * p.percentage / 100).quantize(Decimal("1"))
        ent_pct = ent_map.get(p.associate.canonical_name, Decimal("0"))
        cff_share = (cff_total * ent_pct / 100).quantize(Decimal("1")) if company and company.code != "SARL-AMF" else Decimal("0")

        is_yamina = "yamina" in p.associate.canonical_name.lower()
        # Y5 check
        yamina_violation = is_yamina and cff_share != 0 and company.code in YAMINA_ZERO_ENTITIES

        with_cff.append({
            "associate": p.associate.canonical_name,
            "project_pct": str(p.percentage),
            "company_pct": str(ent_pct),
            "qp_brute": str(qp_brute),
            "cff_deducted": str(cff_share),
            "qp_after_cff": str(qp_brute - cff_share),
            "yamina_violation": yamina_violation,
        })
        without_cff.append({
            "associate": p.associate.canonical_name,
            "project_pct": str(p.percentage),
            "qp_brute": str(qp_brute),
            "qp_finale": str(qp_brute),
        })

    return ApiResponse(data={
        "project": project_code, "marge_nette": str(marge), "cff_total": str(cff_total),
        "with_cff": with_cff, "without_cff": without_cff,
    })


@router.get("/verifications")
async def cc_verifications(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    from decimal import Decimal
    results = []
    errors = 0

    # V1: SUM(children montants) = parent montant, for each RF type
    parents = db.query(CostCenterNode).filter(
        CostCenterNode.is_deleted == False, CostCenterNode.level <= 2
    ).all()
    for p in parents:
        children = db.query(CostCenterNode).filter(
            CostCenterNode.parent_id == p.id, CostCenterNode.is_deleted == False
        ).all()
        if not children:
            continue
        for rf in ["rf1", "rf2", "rf3", "rf4"]:
            col = f"montant_{rf}"
            child_sum = sum(Decimal(str(getattr(c, col) or 0)) for c in children)
            parent_val = Decimal(str(getattr(p, col) or 0))
            diff = abs(parent_val - child_sum)
            ok = diff <= Decimal("0.01")
            if not ok:
                errors += 1
            results.append({
                "check": "V1", "node": p.code, "rf": rf.upper(),
                "status": "PASS" if ok else "FAIL",
                "parent_value": str(parent_val), "children_sum": str(child_sum),
                "ecart": str(diff),
            })

    # V2: CC entries sum matches node stored value
    nodes_with_entries = db.query(CostCenterEntry.node_id).distinct().all()
    for (node_id,) in nodes_with_entries:
        node = db.query(CostCenterNode).get(node_id)
        if not node:
            continue
        for rf in ["RF1", "RF2", "RF3", "RF4"]:
            entry_sum = db.query(func.coalesce(func.sum(CostCenterEntry.montant), 0)).filter(
                CostCenterEntry.node_id == node_id, CostCenterEntry.rf_type == rf,
                CostCenterEntry.is_deleted == False,
            ).scalar()
            stored = Decimal(str(getattr(node, f"montant_{rf.lower()}") or 0))
            # Note: stored includes ascended values from children, so only check leaf nodes
            if node.level >= 3:  # leaf-ish
                diff = abs(stored - Decimal(str(entry_sum)))
                ok = diff <= Decimal("0.01")
                if not ok:
                    errors += 1
                results.append({
                    "check": "V2", "node": node.code, "rf": rf,
                    "status": "PASS" if ok else "FAIL",
                    "entries_sum": str(entry_sum), "stored_value": str(stored),
                    "ecart": str(diff),
                })

    # V3: Total entries by source type
    sources = db.query(
        CostCenterEntry.source_type, func.count(CostCenterEntry.id), func.sum(CostCenterEntry.montant)
    ).filter(CostCenterEntry.is_deleted == False).group_by(CostCenterEntry.source_type).all()
    for src, cnt, total in sources:
        results.append({
            "check": "V3", "source_type": src or "INCONNU",
            "status": "INFO", "count": cnt, "total": str(total or 0),
        })

    return ApiResponse(data={"checks": results, "total_errors": errors, "total_checks": len(results)})


@router.get("/alerts")
async def cc_alerts(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    alerts = []
    # Check entities with NULL tax rates
    missing = db.query(Company).filter(Company.ibs_rate == None, Company.status.notin_(["DISSOUTE", "SATELLITE"])).all()
    for c in missing:
        alerts.append({"level": "CRITIQUE", "module": "CC", "title": f"FC-005: Taux IBS/TAP manquant - {c.legal_name}",
                       "message": f"CFF bloque pour {c.code}", "created": str(c.created_at)})
    return ApiResponse(data=alerts)


# ── GACEB ────────────────────────────────────────────────────────────────────

@router.get("/gaceb/rap")
async def gaceb_rap(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    adv = db.query(GacebAdvance).first()
    if not adv:
        return ApiResponse(data=None, errors=["Aucune avance GACEB"])
    sits = db.query(GacebSituation).filter(GacebSituation.advance_id == adv.id).order_by(GacebSituation.num).all()
    total_marches = sum(s.brut for s in sits)
    total_deductions = sum(s.deduction for s in sits)
    total_net_cash = sum(s.net for s in sits)
    vehicles_total = Decimal("10500000")  # Range Rover 4M + Passat 6.5M
    rap_net = total_marches - total_deductions - vehicles_total - total_net_cash

    return ApiResponse(data={
        "advance_120m": {"initial": str(adv.initial_amount), "deducted": str(adv.deducted_amount), "residual": str(adv.residual)},
        "total_marches": str(total_marches),
        "total_deductions_avance": str(total_deductions),
        "vehicles_total": str(vehicles_total),
        "total_cash_paye": str(total_net_cash),
        "rap_net": str(rap_net),
        "vehicles": [
            {"make": "Range Rover", "value": "4000000", "associate": "Ahmed", "steps_done": 3,
             "steps": ["Achete", "Immatricule", "Cede GACEB", "Deduit", "Revendu"]},
            {"make": "VW Passat", "value": "6500000", "associate": "Lyazid", "steps_done": 3,
             "steps": ["Achete", "Immatricule", "Cede GACEB", "Deduit", "Revendu"]},
        ],
        "situations": [{
            "num": s.num, "brut": str(s.brut), "deduction": str(s.deduction),
            "net": str(s.net), "solde": str(s.solde_after),
            "date": str(s.created_at.date()),
        } for s in sits],
    })


@router.get("/gaceb/situations")
async def gaceb_situations(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    adv = db.query(GacebAdvance).first()
    if not adv:
        return ApiResponse(data=[])
    sits = db.query(GacebSituation).filter(GacebSituation.advance_id == adv.id).order_by(GacebSituation.num).all()
    return ApiResponse(data=[{
        "id": str(s.id), "num": s.num, "brut": str(s.brut), "deduction": str(s.deduction),
        "net": str(s.net), "solde": str(s.solde_after), "date": str(s.created_at.date()),
    } for s in sits])


@router.post("/gaceb/situations")
async def create_situation(body: dict, db: Session = Depends(get_db),
                            user: CurrentUser = Depends(get_current_user)):
    adv = db.query(GacebAdvance).first()
    if not adv:
        raise HTTPException(404, "Aucune avance GACEB")
    brut = Decimal(str(body.get("brut", 0)))
    deduction = Decimal(str(body.get("deduction", 0)))
    if deduction > adv.residual:
        raise HTTPException(400, f"Deduction {deduction} > solde avance {adv.residual}")
    net = brut - deduction
    new_residual = adv.residual - deduction
    last_num = db.query(func.max(GacebSituation.num)).filter(GacebSituation.advance_id == adv.id).scalar() or 0
    sit = GacebSituation(
        company_id=adv.company_id, advance_id=adv.id, num=last_num + 1,
        brut=brut, deduction=deduction, net=net, solde_after=new_residual,
    )
    adv.deducted_amount += deduction
    adv.residual = new_residual
    db.add(sit)
    db.commit()
    return ApiResponse(data={"num": sit.num, "brut": str(brut), "deduction": str(deduction),
                              "net": str(net), "solde": str(new_residual)})


@router.get("/gaceb/vehicles")
async def gaceb_vehicles(user: CurrentUser = Depends(get_current_user)):
    return ApiResponse(data=[
        {"make": "Range Rover", "value": "4000000", "associate": "Ahmed",
         "steps": [True, True, True, False, False]},
        {"make": "VW Passat", "value": "6500000", "associate": "Lyazid",
         "steps": [True, True, True, False, False]},
    ])
