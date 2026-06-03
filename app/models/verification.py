"""
GFI v7.0 — Alert, VerificationRun, ScheduledReport, DafDashboardSnapshot.

10 automatic verifications, 5-level alert system, 7 automated reports.
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Alert(GFIBase, Base):
    """5-level alert system: INFO, ATTENTION, ALERTE, CRITIQUE, BLOQUANT."""

    __tablename__ = "alert"

    # ── Alert identity ───────────────────────────────────────────────────
    level = Column(String(10), nullable=False, index=True)
    # INFO, ATTENTION, ALERTE, CRITIQUE, BLOQUANT
    code = Column(String(30), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    # ── Context ──────────────────────────────────────────────────────────
    verification_code = Column(String(10), nullable=True)  # V1-V10
    resource_type = Column(String(60), nullable=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # ── Status ───────────────────────────────────────────────────────────
    # ACTIVE, ACKNOWLEDGED, RESOLVED, EXPIRED
    status = Column(String(20), nullable=False, server_default="'ACTIVE'")
    is_blocking = Column(Boolean, nullable=False, server_default="false")

    acknowledged_by = Column(UUID(as_uuid=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(UUID(as_uuid=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # ── Data ─────────────────────────────────────────────────────────────
    detail_json = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<Alert [{self.level}] {self.title[:40]}>"


class VerificationRun(GFIBase, Base):
    """Log of each verification execution (V1-V10)."""

    __tablename__ = "verification_run"

    verification_code = Column(String(10), nullable=False, index=True)
    verification_name = Column(String(100), nullable=False)
    run_at = Column(DateTime(timezone=True), nullable=False)
    # PASS, FAIL
    result = Column(String(10), nullable=False)
    duration_ms = Column(Integer, nullable=True)
    items_checked = Column(Integer, nullable=True)
    items_failed = Column(Integer, nullable=True)
    detail_json = Column(JSONB, nullable=True)
    alert_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alert.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self):
        return f"<VerificationRun {self.verification_code} {self.result}>"


class ScheduledReport(Base):
    """Configuration for the 7 automated reports. System reference."""

    __tablename__ = "scheduled_report"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=__import__("sqlalchemy").text("gen_random_uuid()"))
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    frequency = Column(String(20), nullable=False)
    # DAILY, WEEKLY, MONTHLY, IMMEDIATE
    schedule_cron = Column(String(50), nullable=True)
    recipient_roles = Column(JSONB, nullable=False)
    confidential = Column(Boolean, nullable=False, server_default="false")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=__import__("sqlalchemy").func.now())

    def __repr__(self):
        return f"<ScheduledReport {self.code} {self.frequency}>"


class DafDashboardSnapshot(GFIBase, Base):
    """Periodic snapshot of the DAF dashboard data."""

    __tablename__ = "daf_dashboard_snapshot"

    snapshot_date = Column(Date, nullable=False, index=True)

    # ── Section 1: Consolidation Groupe ──────────────────────────────────
    total_encaissements_officiel = Column(Numeric(15, 2), nullable=True)
    total_encaissements_interne = Column(Numeric(15, 2), nullable=True)
    total_decaissements_officiel = Column(Numeric(15, 2), nullable=True)
    total_decaissements_interne = Column(Numeric(15, 2), nullable=True)
    total_cff = Column(Numeric(15, 2), nullable=True)
    solde_net_officiel = Column(Numeric(15, 2), nullable=True)
    solde_net_interne = Column(Numeric(15, 2), nullable=True)
    ecart = Column(Numeric(15, 2), nullable=True)

    # ── Section 2: Par Associe ───────────────────────────────────────────
    associate_data = Column(JSONB, nullable=True)

    # ── Section 3: Par Projet + Alertes ──────────────────────────────────
    top_projects = Column(JSONB, nullable=True)
    active_alerts_count = Column(Integer, nullable=True)
    active_alerts_summary = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<DafDashboardSnapshot {self.snapshot_date}>"
