"""Budget Aggregator — pulls real data from 8 GFI modules into operation_budget_agrege.
Called by CRON endpoint or after any relevant transaction.

S1: Contract amount (set at creation — no pull needed)
S2: Payroll — SUM payslips where operation_id matches
S3: Accounting — SUM cost_center_entries where operation's project CC matches, class 6 expenses
S4: Treasury — SUM payments where operation_id matches
S5: ADV — SUM payments on dossiers linked to operation's project
S6: Centre Cout — SUM cost_center_entries for operation's project
S7: Stock — SUM gaceb_situations + cost_center_entries CC3 for operation's project
S8: Fleet — estimated from CC13 for operation's project
S9/S10/S11: Manual (ops_it_cost, ops_insurance_cost, ops_overhead_cost)
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import text


def aggregate_operation_budget(op_id: str, db) -> dict:
    """Pull real data from all GFI modules and update operation_budget_agrege."""
    op = db.execute(text("SELECT * FROM operation WHERE id = :id"), {"id": op_id}).mappings().first()
    if not op:
        return {"error": "Operation not found"}

    co_id = str(op["company_id"])
    project_id = str(op["project_id"]) if op["project_id"] else None
    results = {}

    # ── S2: Payroll ──
    # Sum of all payslips linked to this operation
    # gross already includes the employee cost; employer charges ~26% CNAS
    s2_reel = db.execute(text(
        "SELECT COALESCE(SUM(gross * 1.26), 0) as total "
        "FROM payslip WHERE operation_id = :oid"
    ), {"oid": op_id}).scalar() or 0
    # If no direct link, try matching by project via employee assignment
    if s2_reel == 0 and project_id:
        # Fallback: estimate from all payslips in company, divided by active operations
        s2_reel = db.execute(text("""
            SELECT COALESCE(SUM(p.gross * 1.26), 0)
            FROM payslip p
            JOIN employee e ON p.employee_id = e.id
            WHERE e.company_id = :coid
        """), {"coid": co_id}).scalar() or 0
        op_count = db.execute(text("SELECT count(*) FROM operation WHERE company_id = :c AND statut IN ('EN_COURS','VALIDE')"), {"c": co_id}).scalar() or 1
        s2_reel = float(s2_reel) / op_count
    results["S2_RH_PAIE"] = {"reel": float(s2_reel), "label": "Masse salariale"}

    # ── S4: Treasury (payments) ──
    s4_reel = db.execute(text(
        "SELECT COALESCE(SUM(montant), 0) FROM payment WHERE operation_id = :oid AND status = 'ENCAISSE'"
    ), {"oid": op_id}).scalar() or 0
    results["S4_TRESORERIE"] = {"reel": float(s4_reel), "label": "Flux tresorerie"}

    # ── S6: Centre de Cout ──
    s6_reel = 0
    if project_id:
        s6_reel = db.execute(text("""
            SELECT COALESCE(SUM(ce.montant), 0)
            FROM cost_center_entry ce
            JOIN cost_center_node cn ON ce.node_id = cn.id
            WHERE cn.project_id = :pid AND ce.rf_type = 'RF1'
        """), {"pid": project_id}).scalar() or 0
    results["S6_CENTRE_COUT"] = {"reel": float(s6_reel), "label": "Centre de cout"}

    # ── S7: Stock / GACEB ──
    s7_reel = 0
    if project_id:
        # GACEB situations net cash for this project
        s7_gaceb = db.execute(text("""
            SELECT COALESCE(SUM(gs.net), 0)
            FROM gaceb_situation gs
            JOIN gaceb_advance ga ON gs.advance_id = ga.id
            WHERE gs.operation_id = :oid OR ga.project_id = :pid
        """), {"oid": op_id, "pid": project_id}).scalar() or 0
        # CC3 materials from cost center
        s7_cc3 = db.execute(text("""
            SELECT COALESCE(SUM(ce.montant), 0)
            FROM cost_center_entry ce
            JOIN cost_center_node cn ON ce.node_id = cn.id
            WHERE cn.project_id = :pid AND cn.code LIKE '%-CC3%'
        """), {"pid": project_id}).scalar() or 0
        s7_reel = float(s7_gaceb) + float(s7_cc3)
    results["S7_STOCK"] = {"reel": s7_reel, "label": "Stock/Materiaux"}

    # ── S5: ADV ──
    s5_reel = 0
    if project_id:
        s5_reel = db.execute(text("""
            SELECT COALESCE(SUM(p.montant), 0)
            FROM payment p
            JOIN dossier_adv d ON p.dossier_id = d.id
            WHERE d.project_id = :pid AND p.status = 'ENCAISSE' AND p.type_rf = 'RF1'
        """), {"pid": project_id}).scalar() or 0
    results["S5_ADV"] = {"reel": float(s5_reel), "label": "ADV encaissements"}

    # ── S8: Fleet ──
    s8_reel = 0
    if project_id:
        s8_reel = db.execute(text("""
            SELECT COALESCE(SUM(ce.montant), 0)
            FROM cost_center_entry ce
            JOIN cost_center_node cn ON ce.node_id = cn.id
            WHERE cn.project_id = :pid AND cn.code LIKE '%-CC13%'
        """), {"pid": project_id}).scalar() or 0
    results["S8_FLOTTE"] = {"reel": float(s8_reel), "label": "Vehicules/Flotte"}

    # ── S3: Accounting (class 6 expenses) ──
    s3_reel = 0
    if project_id:
        # Sum all cost center entries (which come from accounting) excluding revenue (CC12)
        s3_reel = db.execute(text("""
            SELECT COALESCE(SUM(ce.montant), 0)
            FROM cost_center_entry ce
            JOIN cost_center_node cn ON ce.node_id = cn.id
            WHERE cn.project_id = :pid AND cn.code NOT LIKE '%-CC12%' AND ce.montant > 0
        """), {"pid": project_id}).scalar() or 0
    results["S3_FINANCE"] = {"reel": float(s3_reel), "label": "Finance/Compta"}

    # ── S9/S10/S11: Manual (already in separate tables) ──
    for src, tbl, label in [
        ("S9_IT", "ops_it_cost", "IT/Licences"),
        ("S10_ASSURANCE", "ops_insurance_cost", "Assurances"),
        ("S11_OVERHEAD", "ops_overhead_cost", "Overhead"),
    ]:
        manual = db.execute(text(f"SELECT COALESCE(SUM(amount), 0) FROM {tbl} WHERE operation_id = :oid"), {"oid": op_id}).scalar() or 0
        results[src] = {"reel": float(manual), "label": label}

    # ── Update operation_budget_agrege ──
    now = datetime.now(timezone.utc)
    updated_sources = []
    for src_code, data in results.items():
        existing = db.execute(text(
            "SELECT id, montant_prevu FROM operation_budget_agrege WHERE operation_id = :oid AND source_code = :src"
        ), {"oid": op_id, "src": src_code}).mappings().first()

        if existing:
            db.execute(text(
                "UPDATE operation_budget_agrege SET montant_reel = :reel, derniere_maj = :now WHERE id = :id"
            ), {"reel": str(data["reel"]), "now": now, "id": existing["id"]})
        else:
            # Create new source row — prevu = reel for first time (DAF can adjust later)
            db.execute(text("""
                INSERT INTO operation_budget_agrege (id, company_id, operation_id, source_code, source_label, montant_prevu, montant_reel, methode_calcul, derniere_maj)
                VALUES (:id, :co, :op, :src, :label, :prevu, :reel, :method, :now)
            """), {
                "id": str(uuid.uuid4()), "co": co_id, "op": op_id,
                "src": src_code, "label": data["label"],
                "prevu": str(data["reel"]), "reel": str(data["reel"]),
                "method": "CRON_MENSUEL" if src_code not in ("S9_IT", "S10_ASSURANCE", "S11_OVERHEAD") else "CLE_REPARTITION",
                "now": now,
            })
        updated_sources.append({"source": src_code, "reel": data["reel"]})

    db.commit()
    return {"operation_id": op_id, "sources_updated": len(updated_sources), "details": updated_sources}


def aggregate_all_operations(db) -> dict:
    """Refresh budget for ALL active operations. Called by CRON."""
    ops = db.execute(text("SELECT id FROM operation WHERE statut IN ('EN_COURS', 'VALIDE') AND is_deleted = false")).fetchall()
    results = []
    for op in ops:
        r = aggregate_operation_budget(str(op[0]), db)
        results.append(r)
    return {"operations_refreshed": len(results), "results": results}
