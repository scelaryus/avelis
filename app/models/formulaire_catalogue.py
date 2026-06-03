"""
GFI v7.0 — FormulaireCatalogue: template definitions for all 35 formulaires.

Each catalogue entry defines:
- code (FC-001, F-REC-001, etc.)
- name, trigger_description, question_template
- priority (CRITIQUE / ELEVEE / STANDARD)
- default assignee role
- escalation schedule (J+3, J+7, J+14, J+30)
- whether it blocks dependent operations

System reference data (no company_id).
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base


class FormulaireCatalogue(Base):
    __tablename__ = "formulaire_catalogue"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(20), nullable=False)  # GFI_CORE, DRH, BIM
    trigger_description = Column(Text, nullable=False)
    question_template = Column(Text, nullable=False)
    priority = Column(String(20), nullable=False)  # CRITIQUE, ELEVEE, STANDARD

    # ── Default assignment ───────────────────────────────────────────────
    default_assignee_role = Column(String(40), nullable=False, server_default="'DAF'")

    # ── Blocking behavior ────────────────────────────────────────────────
    blocks_operation = Column(Boolean, nullable=False, server_default="true")

    # ── Escalation schedule (days) ───────────────────────────────────────
    escalation_reminder_days = Column(Integer, nullable=False, server_default="3")
    escalation_alert_days = Column(Integer, nullable=False, server_default="7")
    escalation_critique_days = Column(Integer, nullable=False, server_default="14")
    escalation_blocking_days = Column(Integer, nullable=False, server_default="30")

    # ── Field definitions (JSON schema for required fields) ──────────────
    field_definitions = Column(JSONB, nullable=True)

    # ── Timestamps ───────────────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    def __repr__(self):
        return f"<FormulaireCatalogue {self.code} — {self.name}>"
