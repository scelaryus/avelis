"""
GFI v7.0 — AuditTrail: immutable, append-only audit log.

This is the most protected table in the system:
- A database trigger blocks ALL UPDATE and DELETE operations.
- Even the system administrator cannot modify or remove entries.
- No is_deleted, no updated_at, no version — records are permanent.
- company_id is present for multi-tenant filtering.

Every action generates an entry with:
  WHO:   user_id, role_code (snapshot), ip_address, user_agent
  WHAT:  action, resource_type, resource_id, data_before, data_after
  WHEN:  created_at (server UTC)
  WHERE: module, workflow_step, verification_level, event_id
  FLAGS: rf2_access (every RF2 read/write is tagged)
"""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base


class AuditTrail(Base):
    __tablename__ = "audit_trail"

    # ── PK ───────────────────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # ── Multi-tenant ─────────────────────────────────────────────────────
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── WHO ──────────────────────────────────────────────────────────────
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role_code = Column(String(40), nullable=True)  # snapshot at action time
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)

    # ── WHAT ─────────────────────────────────────────────────────────────
    # CREATE, READ, UPDATE, DELETE, APPROVE, REJECT,
    # LOGIN, LOGOUT, EXPORT, PRINT, ESCALATE
    action = Column(String(20), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    data_before = Column(JSONB, nullable=True)
    data_after = Column(JSONB, nullable=True)

    # ── WHEN ─────────────────────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # ── CONTEXT ──────────────────────────────────────────────────────────
    module = Column(String(40), nullable=True)
    workflow_step = Column(String(60), nullable=True)
    verification_level = Column(Integer, nullable=True)
    event_id = Column(UUID(as_uuid=True), nullable=True)

    # ── RF2 flag ─────────────────────────────────────────────────────────
    rf2_access = Column(
        Boolean, nullable=False, server_default="false", index=True
    )

    def __repr__(self):
        return (
            f"<AuditTrail {self.action} {self.resource_type} "
            f"by user={self.user_id} at {self.created_at}>"
        )
