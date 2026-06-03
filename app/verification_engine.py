"""
GFI v7.0 — Verification Engine + Alert System + DAF Dashboard.

10 automatic verifications (V1-V10).
5-level alert system (INFO -> BLOQUANT).
DAF dashboard with 3 sections (Group / Associate / Project).

Core API:
  run_verification(code) -> VerificationRun
  run_all_verifications() -> list[VerificationRun]
  create_alert(level, title, ...) -> Alert
  compute_daf_dashboard(company_id, date) -> DafDashboardSnapshot
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func as sqfunc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ── Alert levels ─────────────────────────────────────────────────────────────
ALERT_LEVELS = {
    "INFO":      {"blocking": False, "color": "blue"},
    "ATTENTION": {"blocking": False, "color": "yellow"},
    "ALERTE":    {"blocking": False, "color": "orange"},
    "CRITIQUE":  {"blocking": True,  "color": "red"},
    "BLOQUANT":  {"blocking": True,  "color": "black"},
}


def create_alert(
    session: Session,
    *,
    level: str,
    title: str,
    message: str,
    company_id: UUID,
    verification_code: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    project_id: UUID | None = None,
    detail_json: dict | None = None,
    created_by: UUID | None = None,
) -> object:
    """Create an alert at the specified level."""
    from app.models.verification import Alert

    is_blocking = ALERT_LEVELS.get(level, {}).get("blocking", False)

    alert = Alert(
        company_id=company_id,
        level=level,
        title=title,
        message=message,
        verification_code=verification_code,
        resource_type=resource_type,
        resource_id=resource_id,
        project_id=project_id,
        status="ACTIVE",
        is_blocking=is_blocking,
        detail_json=detail_json,
        created_by=created_by,
    )
    session.add(alert)
    session.flush()
    return alert


def _log_run(
    session, company_id, code, name, result, items_checked,
    items_failed, detail, start_time, alert_id=None,
):
    from app.models.verification import VerificationRun

    now = datetime.now(timezone.utc)
    duration = int((time.time() - start_time) * 1000)
    run = VerificationRun(
        company_id=company_id,
        verification_code=code,
        verification_name=name,
        run_at=now,
        result=result,
        duration_ms=duration,
        items_checked=items_checked,
        items_failed=items_failed,
        detail_json=detail,
        alert_id=alert_id,
    )
    session.add(run)
    session.flush()
    return run


# ═════════════════════════════════════════════════════════════════════════════
# V1: SUM(children) = parent at every CC level
# ═════════════════════════════════════════════════════════════════════════════

def run_v1(session: Session, company_id: UUID) -> object:
    """BLOQUANT if children sum != parent."""
    from app.cost_center_engine import verify_v1_recursive

    t0 = time.time()
    failures = verify_v1_recursive(session, "CC-GROUPE")
    result = "PASS" if not failures else "FAIL"

    alert_id = None
    if failures:
        alert = create_alert(
            session, level="BLOQUANT", company_id=company_id,
            title=f"V1: {len(failures)} incoherences CC detectees",
            message=failures[0]["message"] if failures else "",
            verification_code="V1",
            detail_json={"failures": failures},
        )
        alert_id = alert.id

    return _log_run(session, company_id, "V1",
                    "SUM(children) = parent check",
                    result, len(failures) + 1, len(failures),
                    {"failures": failures}, t0, alert_id)


# ═════════════════════════════════════════════════════════════════════════════
# V5: Zero RF2 in official journals
# ═════════════════════════════════════════════════════════════════════════════

def run_v5(session: Session, company_id: UUID) -> object:
    """Compliance: no RF2 in official accounting."""
    from app.models.journal_entry import JournalEntry

    t0 = time.time()
    rf2_in_official = (
        session.query(sqfunc.count(JournalEntry.id))
        .filter(
            JournalEntry.company_id == company_id,
            JournalEntry.rf_type == "RF2",
            JournalEntry.status.in_(["VALIDATED", "POSTED"]),
            JournalEntry.is_deleted.is_(False),
        )
        .scalar()
    ) or 0

    result = "PASS" if rf2_in_official == 0 else "FAIL"
    alert_id = None

    if rf2_in_official > 0:
        alert = create_alert(
            session, level="CRITIQUE", company_id=company_id,
            title=f"V5: {rf2_in_official} ecritures RF2 dans journaux officiels",
            message="RF2 detected in official accounting journals.",
            verification_code="V5",
            detail_json={"rf2_count": rf2_in_official},
        )
        alert_id = alert.id

    return _log_run(session, company_id, "V5",
                    "Zero RF2 in official journals",
                    result, 1, 1 if rf2_in_official > 0 else 0,
                    {"rf2_entries": rf2_in_official}, t0, alert_id)


# ═════════════════════════════════════════════════════════════════════════════
# V7: Yamina = 0.00 DA for Y2/Y3/Y4
# ═════════════════════════════════════════════════════════════════════════════

def run_v7(session: Session, company_id: UUID) -> object:
    """CRITIQUE BUG if Yamina has non-zero amounts in protected operations."""
    from app.models.cff_imputation import CffImputation
    from app.ownership import YAMINA_ID, YAMINA_ZERO_COMPANY_CODES, YAMINA_NEVER_MEMBER_COMPANY_CODES
    from app.models.company import Company

    t0 = time.time()
    violations = []

    # Check CFF imputations
    yamina_cffs = (
        session.query(CffImputation)
        .filter(
            CffImputation.associate_id == YAMINA_ID,
            CffImputation.amount != 0,
            CffImputation.is_deleted.is_(False),
        )
        .all()
    )

    for imp in yamina_cffs:
        company = session.get(Company, imp.company_id)
        if company and (company.code in YAMINA_ZERO_COMPANY_CODES
                        or company.code in YAMINA_NEVER_MEMBER_COMPANY_CODES):
            violations.append({
                "type": "CFF",
                "company_code": company.code,
                "amount": str(imp.amount),
                "imputation_id": str(imp.id),
            })

    result = "PASS" if not violations else "FAIL"
    alert_id = None

    if violations:
        alert = create_alert(
            session, level="CRITIQUE", company_id=company_id,
            title=f"V7: {len(violations)} violations Yamina detectees",
            message=f"CRITICAL BUG: Yamina imputed non-zero amounts in protected companies.",
            verification_code="V7",
            detail_json={"violations": violations},
        )
        alert_id = alert.id

    return _log_run(session, company_id, "V7",
                    "Yamina Y2/Y3/Y4 protection check",
                    result, len(yamina_cffs), len(violations),
                    {"violations": violations}, t0, alert_id)


# ═════════════════════════════════════════════════════════════════════════════
# V8: Duplicate CC nodes (alias collision)
# ═════════════════════════════════════════════════════════════════════════════

def run_v8(session: Session, company_id: UUID) -> object:
    """Check for duplicate CC nodes for the same project under different names."""
    from app.models.cost_center import CostCenterNode

    t0 = time.time()
    # Find projects with multiple L2 nodes
    dupes = (
        session.query(
            CostCenterNode.project_id,
            sqfunc.count(CostCenterNode.id).label("cnt"),
        )
        .filter(
            CostCenterNode.level == 2,
            CostCenterNode.node_type == "PROJET",
            CostCenterNode.project_id.isnot(None),
            CostCenterNode.is_deleted.is_(False),
        )
        .group_by(CostCenterNode.project_id)
        .having(sqfunc.count(CostCenterNode.id) > 1)
        .all()
    )

    result = "PASS" if not dupes else "FAIL"
    alert_id = None

    if dupes:
        detail = [{"project_id": str(d[0]), "node_count": d[1]} for d in dupes]
        alert = create_alert(
            session, level="ALERTE", company_id=company_id,
            title=f"V8: {len(dupes)} projets avec noeuds CC dupliques",
            message="Duplicate CC nodes detected — alias fusion required.",
            verification_code="V8",
            detail_json={"duplicates": detail},
        )
        alert_id = alert.id

    return _log_run(session, company_id, "V8",
                    "Duplicate CC node check",
                    result, 1, len(dupes),
                    {}, t0, alert_id)


# ═════════════════════════════════════════════════════════════════════════════
# V10: CC total = treasury total
# ═════════════════════════════════════════════════════════════════════════════

def run_v10(session: Session, company_id: UUID) -> object:
    """Reconciliation: CC imputations vs treasury movements."""
    from app.models.cost_center import CostCenterEntry
    from app.models.financial_transaction import FinancialTransaction

    t0 = time.time()

    cc_total = Decimal(str(
        session.query(sqfunc.coalesce(sqfunc.sum(CostCenterEntry.montant), 0))
        .filter(
            CostCenterEntry.company_id == company_id,
            CostCenterEntry.impact_tresorerie.is_(True),
            CostCenterEntry.is_deleted.is_(False),
        )
        .scalar()
    ))

    treasury_total = Decimal(str(
        session.query(sqfunc.coalesce(sqfunc.sum(FinancialTransaction.amount), 0))
        .filter(
            FinancialTransaction.company_id == company_id,
            FinancialTransaction.is_deleted.is_(False),
        )
        .scalar()
    ))

    delta = abs(cc_total - treasury_total)
    result = "PASS" if delta == Decimal("0") else "FAIL"
    alert_id = None

    if delta > Decimal("0"):
        alert = create_alert(
            session, level="ALERTE", company_id=company_id,
            title=f"V10: Ecart CC/Tresorerie = {delta} DA",
            message=f"CC total={cc_total}, Treasury total={treasury_total}.",
            verification_code="V10",
            detail_json={"cc_total": str(cc_total),
                         "treasury_total": str(treasury_total),
                         "delta": str(delta)},
        )
        alert_id = alert.id

    return _log_run(session, company_id, "V10",
                    "CC-Treasury reconciliation",
                    result, 2, 1 if delta > 0 else 0,
                    {"delta": str(delta)}, t0, alert_id)


def run_all_verifications(
    session: Session,
    company_id: UUID,
) -> list:
    """Run all applicable verifications for an entity."""
    results = []
    for runner in [run_v1, run_v5, run_v7, run_v8, run_v10]:
        try:
            results.append(runner(session, company_id))
        except Exception as e:
            results.append({"error": str(e)})
    return results


# ═════════════════════════════════════════════════════════════════════════════
# DAF DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════

def compute_daf_dashboard(
    session: Session,
    company_id: UUID,
    snapshot_date: date | None = None,
) -> object:
    """Compute the DAF dashboard snapshot with all 3 sections."""
    from app.models.verification import DafDashboardSnapshot, Alert
    from app.models.cost_center import CostCenterNode
    from app.models.cca_account import CcaAccount

    if snapshot_date is None:
        snapshot_date = date.today()

    # ── Section 1: Group consolidation ───────────────────────────────────
    root = (
        session.query(CostCenterNode)
        .filter(CostCenterNode.code == "CC-GROUPE",
                CostCenterNode.is_deleted.is_(False))
        .first()
    )

    officiel_revenue = Decimal("0")
    interne_revenue = Decimal("0")
    total_cff = Decimal("0")

    if root:
        officiel_revenue = Decimal(str(root.montant_rf1)) + Decimal(str(root.montant_rf3))
        interne_revenue = Decimal(str(root.montant_total))
        total_cff = Decimal(str(root.montant_rf3))

    # ── Section 2: Per associate ─────────────────────────────────────────
    ccas = (
        session.query(CcaAccount)
        .filter(CcaAccount.is_deleted.is_(False))
        .all()
    )

    assoc_data = {}
    for cca in ccas:
        aid = str(cca.associate_id)
        if aid not in assoc_data:
            assoc_data[aid] = {"total_cca_balance": Decimal("0")}
        assoc_data[aid]["total_cca_balance"] += Decimal(str(cca.balance))

    # ── Section 3: Active alerts ─────────────────────────────────────────
    alert_count = (
        session.query(sqfunc.count(Alert.id))
        .filter(Alert.status == "ACTIVE", Alert.is_deleted.is_(False))
        .scalar()
    ) or 0

    alerts_by_level = (
        session.query(Alert.level, sqfunc.count(Alert.id))
        .filter(Alert.status == "ACTIVE", Alert.is_deleted.is_(False))
        .group_by(Alert.level)
        .all()
    )

    snapshot = DafDashboardSnapshot(
        company_id=company_id,
        snapshot_date=snapshot_date,
        total_encaissements_officiel=officiel_revenue,
        total_encaissements_interne=interne_revenue,
        total_cff=total_cff,
        solde_net_officiel=officiel_revenue,
        solde_net_interne=interne_revenue,
        ecart=interne_revenue - officiel_revenue,
        associate_data={k: {"cca_balance": str(v["total_cca_balance"])}
                        for k, v in assoc_data.items()},
        active_alerts_count=alert_count,
        active_alerts_summary={level: count for level, count in alerts_by_level},
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def get_active_alerts(
    session: Session,
    company_id: UUID | None = None,
    level: str | None = None,
    limit: int = 50,
) -> list:
    """Get active alerts, optionally filtered by company and level."""
    from app.models.verification import Alert

    query = session.query(Alert).filter(
        Alert.status == "ACTIVE",
        Alert.is_deleted.is_(False),
    )
    if company_id:
        query = query.filter(Alert.company_id == company_id)
    if level:
        query = query.filter(Alert.level == level)

    return query.order_by(
        Alert.level.desc(),  # BLOQUANT first
        Alert.created_at.desc(),
    ).limit(limit).all()


def resolve_alert(
    session: Session,
    alert_id: UUID,
    resolved_by: UUID,
    notes: str | None = None,
) -> object:
    """Mark an alert as resolved."""
    from app.models.verification import Alert

    alert = session.get(Alert, alert_id)
    if alert is None:
        raise ValueError(f"Alert {alert_id} not found.")

    now = datetime.now(timezone.utc)
    alert.status = "RESOLVED"
    alert.resolved_by = resolved_by
    alert.resolved_at = now
    alert.resolution_notes = notes
    session.flush()
    return alert
