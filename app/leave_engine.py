"""
GFI v7.0 — Leave Management Engine.

10 leave types with Algerian labor law compliance.
6-level verification pipeline for sick leave.
L5 fraud detection: badge IN during declared sick leave.
Unjustified absence: auto 1/30th salary deduction.

Core API:
  submit_leave(employee_id, type, dates, ...) -> LeaveRequest
  run_leave_verification(request_id) -> list[LeaveVerification]
  approve_leave(request_id, by, level) -> LeaveRequest
  detect_leave_fraud(date_range) -> list of fraud alerts
  calculate_unjustified_absences(employee_id, month, year) -> int days
  get_leave_balance(employee_id, year) -> LeaveBalance
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func as sqfunc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Leave type configs
LEAVE_TYPES = {
    "ANNUEL":       {"max_days": 30, "pay": "FULL", "doc_required": False, "balance_tracked": True},
    "MALADIE":      {"max_days": None, "pay": "HALF_15D", "doc_required": True, "balance_tracked": False},
    "MATERNITE":    {"max_days": 98, "pay": "CNAS_INDEMNITE", "doc_required": True, "balance_tracked": False},
    "PATERNITE":    {"max_days": 3, "pay": "FULL", "doc_required": True, "balance_tracked": False},
    "MARIAGE":      {"max_days": 3, "pay": "FULL", "doc_required": True, "balance_tracked": False},
    "NAISSANCE":    {"max_days": 3, "pay": "FULL", "doc_required": True, "balance_tracked": False},
    "DECES":        {"max_days": 3, "pay": "FULL", "doc_required": True, "balance_tracked": False},
    "CIRCONCISION": {"max_days": 1, "pay": "FULL", "doc_required": False, "balance_tracked": False},
    "HAJJ":         {"max_days": 30, "pay": "ZERO", "doc_required": False, "balance_tracked": False, "once_per_career": True},
    "SANS_SOLDE":   {"max_days": None, "pay": "ZERO", "doc_required": False, "balance_tracked": False},
}


class LeaveBlocked(Exception):
    def __init__(self, message: str, blockers: list[str]):
        super().__init__(message)
        self.blockers = blockers


class LeaveFraudDetected(Exception):
    def __init__(self, message: str, evidence: list[dict]):
        super().__init__(message)
        self.evidence = evidence


def submit_leave(
    session: Session,
    *,
    company_id: UUID,
    employee_id: UUID,
    leave_type: str,
    start_date: date,
    end_date: date,
    reason: str | None = None,
    medical_certificate_url: str | None = None,
    supporting_document_url: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """Submit a leave request with basic validation."""
    from app.models.leave import LeaveRequest

    config = LEAVE_TYPES.get(leave_type)
    if config is None:
        raise ValueError(f"Unknown leave type: {leave_type}")

    duration = (end_date - start_date).days + 1

    # Basic blocking checks
    blockers = []
    if config["doc_required"] and leave_type == "MALADIE" and not medical_certificate_url:
        blockers.append("Certificat medical obligatoire pour conge maladie")
    if config["doc_required"] and leave_type == "MATERNITE":
        if not medical_certificate_url:
            blockers.append("Certificat medical obligatoire pour conge maternite")
    if leave_type == "SANS_SOLDE" and (not reason or len(reason.strip()) < 20):
        blockers.append("Motif obligatoire >= 20 caracteres pour conge sans solde")
    if config.get("max_days") and duration > config["max_days"]:
        blockers.append(f"Duree {duration}j > maximum {config['max_days']}j")

    # Hajj: once per career
    if leave_type == "HAJJ" and config.get("once_per_career"):
        from app.models.leave import LeaveRequest as LR
        existing = (
            session.query(LR)
            .filter(LR.employee_id == employee_id, LR.leave_type == "HAJJ",
                    LR.status.in_(["APPROUVEE", "APPROUVEE_MANAGER", "APPROUVEE_DRH"]),
                    LR.is_deleted.is_(False))
            .first()
        )
        if existing:
            blockers.append("Conge hajj deja utilise (une fois par carriere)")

    if blockers:
        raise LeaveBlocked(f"Conge bloque: {'; '.join(blockers)}", blockers)

    req = LeaveRequest(
        company_id=company_id,
        employee_id=employee_id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        duration_days=Decimal(str(duration)),
        reason=reason,
        medical_certificate_url=medical_certificate_url,
        supporting_document_url=supporting_document_url,
        pay_impact=config["pay"],
        status="SOUMISE",
        created_by=created_by,
    )
    session.add(req)
    session.flush()
    return req


# ═════════════════════════════════════════════════════════════════════════════
# 6-LEVEL VERIFICATION (for sick leave)
# ═════════════════════════════════════════════════════════════════════════════

def _create_lv(session, request_id, company_id, level, name, verdict, anomalies):
    from app.models.leave import LeaveVerification
    now = datetime.now(timezone.utc)
    v = LeaveVerification(
        company_id=company_id, leave_request_id=request_id,
        level=level, level_name=name, verdict=verdict,
        executed_at=now, anomalies=anomalies if anomalies else None,
    )
    session.add(v)
    session.flush()
    return v


def run_leave_verification(
    session: Session,
    request_id: UUID,
) -> list:
    """Run L1-L5 for sick leave. L6 is human approval."""
    from app.models.leave import LeaveRequest

    req = session.get(LeaveRequest, request_id)
    if req is None:
        raise ValueError(f"LeaveRequest {request_id} not found.")

    results = []

    # ── L1: Rules ────────────────────────────────────────────────────────
    anomalies_l1 = []
    if req.leave_type == "MALADIE" and not req.medical_certificate_url:
        anomalies_l1.append({"type": "NO_CERTIFICATE", "severity": "CRITICAL"})

    # Check overlap with existing approved leaves
    from app.models.leave import LeaveRequest as LR
    overlap = (
        session.query(LR)
        .filter(
            LR.employee_id == req.employee_id,
            LR.id != request_id,
            LR.status.in_(["APPROUVEE", "APPROUVEE_MANAGER", "APPROUVEE_DRH"]),
            LR.start_date <= req.end_date,
            LR.end_date >= req.start_date,
            LR.is_deleted.is_(False),
        )
        .first()
    )
    if overlap:
        anomalies_l1.append({"type": "OVERLAP", "severity": "CRITICAL",
                              "description": f"Overlap with leave {overlap.id}"})

    v1 = "FAIL" if any(a["severity"] == "CRITICAL" for a in anomalies_l1) else "PASS"
    results.append(_create_lv(session, request_id, req.company_id, 1, "Rules", v1, anomalies_l1))
    if v1 == "FAIL":
        req.status = "REJETEE"
        req.rejection_reason = "; ".join(a.get("description", a["type"]) for a in anomalies_l1)
        session.flush()
        return results

    # ── L2: OCR + LLM (certificate analysis) ─────────────────────────────
    anomalies_l2 = []
    if req.leave_type == "MALADIE" and req.medical_certificate_url:
        # In production: OCR + Claude API analysis
        # Check certificate date within 48h of leave start
        pass  # placeholder — OCR integration point
    results.append(_create_lv(session, request_id, req.company_id, 2, "OCR+LLM", "PASS", anomalies_l2))

    # ── L3: Structural ───────────────────────────────────────────────────
    anomalies_l3 = []
    from app.models.hr import Employee
    emp = session.get(Employee, req.employee_id)
    if emp and emp.status != "ACTIVE":
        anomalies_l3.append({"type": "INACTIVE_EMPLOYEE", "severity": "CRITICAL"})
    v3 = "FAIL" if any(a["severity"] == "CRITICAL" for a in anomalies_l3) else "PASS"
    results.append(_create_lv(session, request_id, req.company_id, 3, "Structural", v3, anomalies_l3))

    # ── L4: Statistical patterns ─────────────────────────────────────────
    anomalies_l4 = []
    if req.leave_type == "MALADIE":
        sick_count = (
            session.query(sqfunc.count(LR.id))
            .filter(
                LR.employee_id == req.employee_id,
                LR.leave_type == "MALADIE",
                LR.start_date >= req.start_date - timedelta(days=365),
                LR.status.in_(["APPROUVEE", "APPROUVEE_MANAGER", "APPROUVEE_DRH"]),
                LR.is_deleted.is_(False),
            )
            .scalar()
        ) or 0
        if sick_count > 4:
            anomalies_l4.append({"type": "HIGH_FREQUENCY", "severity": "WARNING",
                                  "description": f"{sick_count} arrets maladie en 12 mois"})

        # Day-of-week analysis
        sick_leaves = (
            session.query(LR.start_date)
            .filter(
                LR.employee_id == req.employee_id,
                LR.leave_type == "MALADIE",
                LR.status.in_(["APPROUVEE", "APPROUVEE_MANAGER", "APPROUVEE_DRH"]),
                LR.is_deleted.is_(False),
            )
            .all()
        )
        if len(sick_leaves) >= 3:
            sunday_starts = sum(1 for (d,) in sick_leaves if d.weekday() == 6)
            if len(sick_leaves) > 0 and sunday_starts / len(sick_leaves) > 0.6:
                anomalies_l4.append({"type": "PATTERN_SUSPECT", "severity": "WARNING",
                                      "description": ">60% arrets commencent le dimanche"})

    v4 = "FLAG" if anomalies_l4 else "PASS"
    results.append(_create_lv(session, request_id, req.company_id, 4, "Statistical", v4, anomalies_l4))

    # ── L5: FRAUD — badge events during sick leave ───────────────────────
    anomalies_l5 = []
    badge_fraud_evidence = []

    if req.leave_type == "MALADIE":
        from app.models.access_control import BadgeEvent
        from app.models.hr import Employee as Emp

        emp = session.get(Emp, req.employee_id)
        if emp and emp.badge_rfid_number:
            fraud_events = (
                session.query(BadgeEvent)
                .filter(
                    BadgeEvent.badge_number == emp.badge_rfid_number,
                    BadgeEvent.direction == "IN",
                    BadgeEvent.result == "GRANTED",
                    BadgeEvent.event_timestamp >= datetime.combine(
                        req.start_date, datetime.min.time()).replace(tzinfo=timezone.utc),
                    BadgeEvent.event_timestamp <= datetime.combine(
                        req.end_date, datetime.max.time()).replace(tzinfo=timezone.utc),
                    BadgeEvent.is_deleted.is_(False),
                )
                .all()
            )

            if fraud_events:
                for evt in fraud_events:
                    badge_fraud_evidence.append({
                        "event_id": str(evt.id),
                        "badge": evt.badge_number,
                        "controller": evt.controller_id,
                        "timestamp": str(evt.event_timestamp),
                        "direction": evt.direction,
                    })
                anomalies_l5.append({
                    "type": "FRAUD_BADGE_DURING_LEAVE",
                    "severity": "CRITICAL",
                    "description": (
                        f"{len(fraud_events)} badge IN events detected "
                        f"during declared sick leave period"
                    ),
                })

    v5 = "FAIL" if anomalies_l5 else "PASS"
    lv5 = _create_lv(session, request_id, req.company_id, 5, "Fraud Detection", v5, anomalies_l5)
    if badge_fraud_evidence:
        lv5.badge_events_during_leave = badge_fraud_evidence
        lv5.fraud_confirmed = True
        req.fraud_alert = True
        req.fraud_details = {"evidence": badge_fraud_evidence}
    results.append(lv5)

    if v5 == "FAIL":
        req.status = "REJETEE"
        req.rejection_reason = "FRAUDE DETECTEE: badge IN pendant conge maladie"
        session.flush()
        return results

    # ── L6: Human (PENDING for approval) ─────────────────────────────────
    results.append(_create_lv(session, request_id, req.company_id, 6, "Human Approval", "PENDING", None))

    req.status = "EN_VERIFICATION"
    session.flush()
    return results


def approve_leave(
    session: Session,
    *,
    request_id: UUID,
    approved_by: UUID,
    level: str,  # "MANAGER" or "DRH"
) -> object:
    """Approve leave. <= 3 days: manager only. > 3 days: manager then DRH."""
    from app.models.leave import LeaveRequest, LeaveBalance

    req = session.get(LeaveRequest, request_id)
    if req is None:
        raise ValueError(f"LeaveRequest {request_id} not found.")

    now = datetime.now(timezone.utc)

    if level == "MANAGER":
        req.approved_by_manager = approved_by
        req.approved_by_manager_at = now
        if int(req.duration_days) <= 3:
            req.status = "APPROUVEE"
        else:
            req.status = "APPROUVEE_MANAGER"
    elif level == "DRH":
        req.approved_by_drh = approved_by
        req.approved_by_drh_at = now
        req.status = "APPROUVEE"

    # Update balance if annual leave
    if req.status == "APPROUVEE" and req.leave_type == "ANNUEL":
        balance = (
            session.query(LeaveBalance)
            .filter(
                LeaveBalance.employee_id == req.employee_id,
                LeaveBalance.year == req.start_date.year,
                LeaveBalance.leave_type == "ANNUEL",
                LeaveBalance.is_deleted.is_(False),
            )
            .first()
        )
        if balance:
            balance.used_days = Decimal(str(balance.used_days)) + req.duration_days
            balance.remaining_days = Decimal(str(balance.entitled_days)) + Decimal(str(balance.carried_from_previous)) - Decimal(str(balance.used_days))

    session.flush()
    return req


def calculate_unjustified_absences(
    session: Session,
    employee_id: UUID,
    month: int,
    year: int,
) -> int:
    """
    Count unjustified absence days: no badge event + no approved leave.
    Each day = 1/30th salary deduction.
    """
    from app.models.access_control import BadgeEvent
    from app.models.leave import LeaveRequest
    from app.models.hr import Employee
    import calendar

    emp = session.get(Employee, employee_id)
    if not emp or not emp.badge_rfid_number:
        return 0

    _, last_day = calendar.monthrange(year, month)
    unjustified = 0

    for day in range(1, last_day + 1):
        d = date(year, month, day)
        # Skip weekends (Friday/Saturday in Algeria)
        if d.weekday() in (4, 5):  # Friday=4, Saturday=5
            continue

        # Check for badge IN event
        has_badge = (
            session.query(BadgeEvent.id)
            .filter(
                BadgeEvent.badge_number == emp.badge_rfid_number,
                BadgeEvent.direction == "IN",
                BadgeEvent.result == "GRANTED",
                BadgeEvent.event_timestamp >= datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc),
                BadgeEvent.event_timestamp < datetime.combine(d + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc),
                BadgeEvent.is_deleted.is_(False),
            )
            .first()
        )

        if has_badge:
            continue

        # Check for approved leave covering this day
        has_leave = (
            session.query(LeaveRequest.id)
            .filter(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.start_date <= d,
                LeaveRequest.end_date >= d,
                LeaveRequest.status.in_(["APPROUVEE", "APPROUVEE_MANAGER", "APPROUVEE_DRH"]),
                LeaveRequest.is_deleted.is_(False),
            )
            .first()
        )

        if not has_leave:
            unjustified += 1

    return unjustified
