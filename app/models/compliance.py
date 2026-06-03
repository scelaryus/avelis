"""
GFI v7.0 — Data Protection + Visitor Management.

ANPDP registry, consent, right-of-access, data purge, pseudonymization.
Visitor QR codes with time-windowed access.
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class DataProcessingRegistry(Base):
    """ANPDP register of personal data processing activities."""

    __tablename__ = "data_processing_registry"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=__import__("sqlalchemy").text("gen_random_uuid()"))
    activity_name = Column(String(255), nullable=False)
    purpose = Column(Text, nullable=False)
    data_categories = Column(JSONB, nullable=False)
    recipients = Column(JSONB, nullable=True)
    retention_period_years = Column(Integer, nullable=False)
    security_measures = Column(JSONB, nullable=True)
    legal_basis = Column(String(100), nullable=True)
    module = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    last_reviewed = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=__import__("sqlalchemy").func.now())

    def __repr__(self):
        return f"<DataProcessingRegistry {self.activity_name}>"


class ConsentRecord(GFIBase, Base):
    """Employee consent for personal data processing."""

    __tablename__ = "consent_record"

    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    consent_type = Column(String(50), nullable=False)
    # DATA_PROCESSING, BIOMETRIC, PHOTO, COMMUNICATION
    consent_given = Column(Boolean, nullable=False, server_default="false")
    consent_date = Column(DateTime(timezone=True), nullable=True)
    consent_document_url = Column(Text, nullable=True)
    withdrawn = Column(Boolean, nullable=False, server_default="false")
    withdrawn_date = Column(DateTime(timezone=True), nullable=True)

    employee = relationship("Employee")

    def __repr__(self):
        return f"<ConsentRecord {self.consent_type} given={self.consent_given}>"


class DataAccessRequest(GFIBase, Base):
    """Employee right-of-access request (72h SLA)."""

    __tablename__ = "data_access_request"

    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    request_date = Column(DateTime(timezone=True), nullable=False)
    # PENDING, PROCESSING, FULFILLED, REJECTED
    status = Column(String(20), nullable=False, server_default="'PENDING'")
    sla_deadline = Column(DateTime(timezone=True), nullable=False)
    export_json_url = Column(Text, nullable=True)
    export_pdf_url = Column(Text, nullable=True)
    fulfilled_at = Column(DateTime(timezone=True), nullable=True)
    fulfilled_by = Column(UUID(as_uuid=True), nullable=True)

    employee = relationship("Employee")

    def __repr__(self):
        return f"<DataAccessRequest {self.status}>"


class DataPurgeLog(GFIBase, Base):
    """Record of data anonymization events."""

    __tablename__ = "data_purge_log"

    purge_date = Column(Date, nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    records_anonymized = Column(Integer, nullable=False)
    retention_rule = Column(String(100), nullable=False)
    reviewed_by_dpo = Column(Boolean, nullable=False, server_default="false")
    dpo_review_date = Column(DateTime(timezone=True), nullable=True)
    detail = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<DataPurgeLog {self.purge_date} {self.records_anonymized} records>"


class Visitor(GFIBase, Base):
    """Visitor registration with QR-coded temporary access."""

    __tablename__ = "visitor"

    visitor_name = Column(String(255), nullable=False)
    visitor_company = Column(String(255), nullable=True)
    visitor_phone = Column(String(30), nullable=True)
    visitor_email = Column(String(255), nullable=True)

    # ── Host ─────────────────────────────────────────────────────────────
    host_employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    purpose = Column(Text, nullable=True)

    # ── Access ───────────────────────────────────────────────────────────
    authorized_zones = Column(JSONB, nullable=True)
    visit_date = Column(Date, nullable=False, index=True)
    time_window_start = Column(DateTime(timezone=True), nullable=False)
    time_window_end = Column(DateTime(timezone=True), nullable=False)

    # ── QR code ──────────────────────────────────────────────────────────
    qr_code_data = Column(Text, nullable=True, unique=True)
    qr_sent_via = Column(String(10), nullable=True)  # SMS, EMAIL
    qr_sent_at = Column(DateTime(timezone=True), nullable=True)

    # ── Status ───────────────────────────────────────────────────────────
    # REGISTERED, QR_SENT, ARRIVED, DEPARTED, EXPIRED, DENIED
    status = Column(String(20), nullable=False, server_default="'REGISTERED'")
    arrived_at = Column(DateTime(timezone=True), nullable=True)
    departed_at = Column(DateTime(timezone=True), nullable=True)

    host = relationship("Employee")

    def __repr__(self):
        return f"<Visitor {self.visitor_name} {self.status}>"


class HrDocumentTemplate(Base):
    """HR document templates with QR verification codes."""

    __tablename__ = "hr_document_template"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=__import__("sqlalchemy").text("gen_random_uuid()"))
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(30), nullable=False)
    # OFFBOARDING, ATTESTATION, PASSATION, QUITUS, PAIEMENT, BON_SORTIE
    template_path = Column(Text, nullable=True)
    fields_schema = Column(JSONB, nullable=True)
    qr_enabled = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=__import__("sqlalchemy").func.now())

    def __repr__(self):
        return f"<HrDocumentTemplate {self.code}>"
