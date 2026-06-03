"""
GFI v7.0 — Physical Access Control: controllers, badges, events, zones.

S4A Industrial controllers (ACB-W4PS, 4 doors, TCP/IP, Wiegand).
Per-site middleware communicates with controllers.
Badge events feed attendance, payroll L5, fraud detection.
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class SiteMiddleware(GFIBase, Base):
    """Per-site middleware service configuration."""

    __tablename__ = "site_middleware"

    site_name = Column(String(255), nullable=False)
    site_code = Column(String(20), nullable=False, index=True)
    api_base_url = Column(String(255), nullable=False)
    # e.g., http://site-eden.local:8080/api

    # ── Status ───────────────────────────────────────────────────────────
    # CONNECTED, SYNCING, DISCONNECTED
    status = Column(String(20), nullable=False, server_default="'DISCONNECTED'")
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    pending_commands = Column(Integer, nullable=False, server_default="0")
    pending_events = Column(Integer, nullable=False, server_default="0")

    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    def __repr__(self):
        return f"<SiteMiddleware {self.site_code} {self.status}>"


class AccessController(GFIBase, Base):
    """S4A ACB-W4PS controller (4 doors each)."""

    __tablename__ = "access_controller"

    middleware_id = Column(
        UUID(as_uuid=True), ForeignKey("site_middleware.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    controller_id = Column(String(30), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=True)
    firmware_version = Column(String(20), nullable=True)
    door_count = Column(Integer, nullable=False, server_default="4")
    user_capacity = Column(Integer, nullable=False, server_default="10000")
    current_user_count = Column(Integer, nullable=False, server_default="0")

    # ONLINE, OFFLINE
    status = Column(String(20), nullable=False, server_default="'OFFLINE'")
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<AccessController {self.controller_id} {self.status}>"


class AccessZone(GFIBase, Base):
    """Logical zone: set of controller doors with a schedule."""

    __tablename__ = "access_zone"

    zone_code = Column(String(30), nullable=False, index=True)
    zone_name = Column(String(255), nullable=False)
    controllers_config = Column(JSONB, nullable=False)
    # [{controller_id, door_ids: [1,2], schedule: "24/7" or "8-17"}]
    is_active = Column(Boolean, nullable=False, server_default="true")

    def __repr__(self):
        return f"<AccessZone {self.zone_code} {self.zone_name}>"


class BadgeRecord(GFIBase, Base):
    """Badge lifecycle: creation -> activation -> deactivation."""

    __tablename__ = "badge_record"

    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    badge_number = Column(String(50), unique=True, nullable=False, index=True)
    employee_name = Column(String(255), nullable=False)

    # ── Access zones assigned ────────────────────────────────────────────
    access_zones = Column(JSONB, nullable=True)

    # ── Validity ─────────────────────────────────────────────────────────
    valid_from = Column(Date, nullable=False)
    valid_until = Column(Date, nullable=True)
    # NULL = permanent (CDI), date = end of contract (CDD)

    # ── Lifecycle ────────────────────────────────────────────────────────
    # PENDING_SYNC, ACTIVE, DEACTIVATED, LOST, REPLACED
    status = Column(String(20), nullable=False, server_default="'PENDING_SYNC'")
    activated_at = Column(DateTime(timezone=True), nullable=True)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    deactivation_reason = Column(String(30), nullable=True)
    # OFFBOARDING, TERMINATION, LOST, CDD_EXPIRED, MANUAL

    # ── Sync tracking ────────────────────────────────────────────────────
    synced_to_controllers = Column(JSONB, nullable=True)
    # [{controller_id, synced_at, status}]
    sync_failures = Column(Integer, nullable=False, server_default="0")
    last_sync_attempt = Column(DateTime(timezone=True), nullable=True)

    employee = relationship("Employee")

    def __repr__(self):
        return f"<BadgeRecord {self.badge_number} {self.status}>"


class BadgeEvent(GFIBase, Base):
    """Raw badge event from S4A controller."""

    __tablename__ = "badge_event"

    badge_number = Column(String(50), nullable=False, index=True)
    controller_id = Column(String(30), nullable=False)
    door_id = Column(Integer, nullable=False)
    direction = Column(String(3), nullable=False)  # IN or OUT
    event_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    result = Column(String(10), nullable=False)  # GRANTED or DENIED
    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # ── Dedup ────────────────────────────────────────────────────────────
    event_hash = Column(String(64), nullable=True, unique=True)
    # SHA-256 of (badge+controller+door+timestamp) for idempotent processing

    # ── Processing ───────────────────────────────────────────────────────
    processed_for_attendance = Column(Boolean, nullable=False, server_default="false")
    anomaly_detected = Column(Boolean, nullable=False, server_default="false")
    anomaly_type = Column(String(30), nullable=True)
    # DENIED_REPEATED, AFTER_HOURS, UNUSUAL_SITE, FRAUD_LEAVE

    middleware_id = Column(
        UUID(as_uuid=True), ForeignKey("site_middleware.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self):
        return (
            f"<BadgeEvent {self.badge_number} {self.direction} "
            f"{self.result} @ {self.event_timestamp}>"
        )


class MiddlewareCommand(GFIBase, Base):
    """Queued commands for offline resilience."""

    __tablename__ = "middleware_command"

    middleware_id = Column(
        UUID(as_uuid=True), ForeignKey("site_middleware.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    command_type = Column(String(20), nullable=False)
    # CREATE_BADGE, DELETE_BADGE, OPEN_DOOR
    payload = Column(JSONB, nullable=False)
    priority = Column(Integer, nullable=False, server_default="5")

    # QUEUED, SENT, CONFIRMED, FAILED, EXPIRED
    status = Column(String(20), nullable=False, server_default="'QUEUED'")
    retry_count = Column(Integer, nullable=False, server_default="0")
    max_retries = Column(Integer, nullable=False, server_default="48")
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<MiddlewareCommand {self.command_type} {self.status}>"
