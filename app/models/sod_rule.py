"""
GFI v7.0 — SodRule: Separation of Duties rules.

Enforced at system level, not by convention.
Each rule defines a pair of actions that the SAME user cannot perform
on the SAME resource within a single workflow.

Examples:
- Creator of a purchase order cannot validate it.
- Payment recorder cannot reconcile it.
- Agent cannot validate their own discount > 5%.

System reference data (no company_id).
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class SodRule(Base):
    __tablename__ = "sod_rule"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    code = Column(String(20), unique=True, nullable=False)
    description = Column(Text, nullable=False)

    # ── The conflicting action pair ──────────────────────────────────────
    action_a = Column(String(60), nullable=False)  # e.g., "achats.write"
    action_b = Column(String(60), nullable=False)  # e.g., "achats.validate"

    # ── Scope of the conflict ────────────────────────────────────────────
    # SAME_RECORD: same user cannot do A and B on the same record
    # SAME_TYPE: same user cannot do A and B on the same resource type
    scope = Column(String(20), nullable=False, server_default="'SAME_RECORD'")

    # ── Auto-escalation ──────────────────────────────────────────────────
    # When violated, escalate to this role (code)
    escalate_to_role = Column(String(40), nullable=True)

    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self):
        return f"<SodRule {self.code}: {self.action_a} vs {self.action_b}>"
