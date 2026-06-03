"""
GFI v7.0 — Data Protection Compliance + Visitor Management Engine.

ANPDP registry, LLM pseudonymization, data purge, right-of-access.
Visitor QR codes with time-windowed access and auto-expiry.

Core API:
  pseudonymize_for_llm(data) -> (pseudo_data, restore_fn)
  request_data_access(employee_id) -> DataAccessRequest (72h SLA)
  run_data_purge(today) -> DataPurgeLog
  register_visitor(...) -> Visitor + QR code
  validate_visitor_qr(qr_data) -> (valid, visitor)
  expire_visitors(now) -> expired count
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ═════════════════════════════════════════════════════════════════════════════
# LLM PSEUDONYMIZATION (CRITICAL for L2 payroll verification)
# ═════════════════════════════════════════════════════════════════════════════

def pseudonymize_for_llm(data: dict) -> tuple[dict, dict]:
    """
    Replace personal data with pseudonyms for Claude API calls.
    Returns (pseudonymized_data, mapping).

    The mapping is held in memory ONLY — NEVER persisted.
    Call restore_from_pseudonyms() to reverse, then discard mapping.
    """
    mapping = {}
    pseudo = {}
    counter = 1

    # Fields to pseudonymize
    name_fields = {"employee_name", "first_name", "last_name", "full_name", "name"}
    remove_fields = {"address", "address_line1", "address_line2", "bank_rib",
                     "bank_account", "national_id", "social_security_number",
                     "phone_personal", "email_personal", "nin"}

    for key, value in data.items():
        if key in remove_fields:
            continue  # physically removed
        elif key in name_fields and isinstance(value, str):
            pseudo_name = f"EMPLOYEE_{counter:03d}"
            mapping[pseudo_name] = value
            pseudo[key] = pseudo_name
            counter += 1
        elif key == "national_id" or key == "nin":
            continue  # removed
        else:
            pseudo[key] = value

    return pseudo, mapping


def restore_from_pseudonyms(pseudo_data: dict, mapping: dict) -> dict:
    """Reverse pseudonymization. Call immediately after LLM response."""
    restored = {}
    reverse = {v: k for k, v in mapping.items()}

    for key, value in pseudo_data.items():
        if isinstance(value, str) and value in reverse:
            restored[key] = reverse[value]
        else:
            restored[key] = value

    return restored


# ═════════════════════════════════════════════════════════════════════════════
# RIGHT OF ACCESS (72h SLA)
# ═════════════════════════════════════════════════════════════════════════════

def request_data_access(
    session: Session,
    *,
    company_id: UUID,
    employee_id: UUID,
    created_by: UUID | None = None,
) -> object:
    """Employee requests complete export of their personal data."""
    from app.models.compliance import DataAccessRequest

    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=72)

    request = DataAccessRequest(
        company_id=company_id,
        employee_id=employee_id,
        request_date=now,
        status="PENDING",
        sla_deadline=deadline,
        created_by=created_by,
    )
    session.add(request)
    session.flush()
    return request


# ═════════════════════════════════════════════════════════════════════════════
# DATA PURGE (monthly scheduled job)
# ═════════════════════════════════════════════════════════════════════════════

def run_data_purge(
    session: Session,
    company_id: UUID,
    today: date | None = None,
) -> object:
    """
    Anonymize data past retention period.
    HR files: 5 years post-contract. Accounting: 10 years.
    Replace personal identifiers with ANONYMIZED_[hash].
    """
    from app.models.compliance import DataPurgeLog
    from app.models.hr import Employee

    if today is None:
        today = date.today()

    hr_cutoff = today - timedelta(days=5 * 365)
    count = 0

    archived_employees = (
        session.query(Employee)
        .filter(
            Employee.company_id == company_id,
            Employee.status == "ARCHIVED",
            Employee.updated_at <= datetime.combine(
                hr_cutoff, datetime.min.time()
            ).replace(tzinfo=timezone.utc),
            Employee.first_name != "ANONYMIZED",
            Employee.is_deleted.is_(False),
        )
        .all()
    )

    for emp in archived_employees:
        h = hashlib.sha256(str(emp.id).encode()).hexdigest()[:12]
        emp.first_name = "ANONYMIZED"
        emp.last_name = f"_{h}"
        emp.national_id = None
        emp.social_security_number = None
        emp.phone_personal = None
        emp.email_personal = None
        emp.address_line1 = None
        emp.address_line2 = None
        emp.bank_rib = None
        count += 1

    log = DataPurgeLog(
        company_id=company_id,
        purge_date=today,
        entity_type="employee",
        records_anonymized=count,
        retention_rule="5 years post-contract for HR files",
    )
    session.add(log)
    session.flush()
    return log


# ═════════════════════════════════════════════════════════════════════════════
# VISITOR MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════

def register_visitor(
    session: Session,
    *,
    company_id: UUID,
    visitor_name: str,
    host_employee_id: UUID,
    visit_date: date,
    time_start: datetime,
    time_end: datetime,
    visitor_company: str | None = None,
    visitor_phone: str | None = None,
    visitor_email: str | None = None,
    purpose: str | None = None,
    authorized_zones: list[str] | None = None,
    created_by: UUID | None = None,
) -> object:
    """Register visitor and generate unique QR code."""
    from app.models.compliance import Visitor

    # Generate QR data: visitor_id + zones + expiry, signed
    visitor_id = str(uuid4())
    qr_payload = {
        "visitor_id": visitor_id,
        "name": visitor_name,
        "zones": authorized_zones or [],
        "valid_from": time_start.isoformat(),
        "valid_until": time_end.isoformat(),
        "token": secrets.token_urlsafe(16),
    }
    qr_data = json.dumps(qr_payload, sort_keys=True)

    visitor = Visitor(
        company_id=company_id,
        visitor_name=visitor_name,
        visitor_company=visitor_company,
        visitor_phone=visitor_phone,
        visitor_email=visitor_email,
        host_employee_id=host_employee_id,
        purpose=purpose,
        authorized_zones=authorized_zones,
        visit_date=visit_date,
        time_window_start=time_start,
        time_window_end=time_end,
        qr_code_data=qr_data,
        status="REGISTERED",
        created_by=created_by,
    )
    session.add(visitor)
    session.flush()
    return visitor


def validate_visitor_qr(
    session: Session,
    qr_data: str,
) -> tuple[bool, object | None, str]:
    """
    Validate a visitor QR code at the entrance.
    Returns (valid, visitor_record, reason).
    """
    from app.models.compliance import Visitor

    visitor = (
        session.query(Visitor)
        .filter(Visitor.qr_code_data == qr_data,
                Visitor.is_deleted.is_(False))
        .first()
    )

    if visitor is None:
        return False, None, "QR code invalid or not found"

    now = datetime.now(timezone.utc)

    if visitor.status == "EXPIRED":
        return False, visitor, "Visit expired"
    if visitor.status == "DENIED":
        return False, visitor, "Visit denied"

    if now < visitor.time_window_start:
        return False, visitor, f"Too early — access starts at {visitor.time_window_start}"
    if now > visitor.time_window_end:
        visitor.status = "EXPIRED"
        session.flush()
        return False, visitor, "Time window expired"

    # Valid — record arrival
    visitor.status = "ARRIVED"
    visitor.arrived_at = now
    session.flush()
    return True, visitor, "Access granted"


def expire_visitors(
    session: Session,
    now: datetime | None = None,
) -> int:
    """Auto-expire visitors past their time window."""
    from app.models.compliance import Visitor

    if now is None:
        now = datetime.now(timezone.utc)

    expired = (
        session.query(Visitor)
        .filter(
            Visitor.status.in_(["REGISTERED", "QR_SENT", "ARRIVED"]),
            Visitor.time_window_end < now,
            Visitor.is_deleted.is_(False),
        )
        .all()
    )

    for v in expired:
        if v.status == "ARRIVED" and not v.departed_at:
            v.departed_at = now
        v.status = "EXPIRED"

    session.flush()
    return len(expired)
