"""
GFI v7.0 — Formulaire: live formulaire instances.

When the system encounters missing data, it creates a Formulaire instance
linked to a catalogue template. The formulaire:
- Blocks the dependent operation until answered (status = REMPLI)
- Tracks escalation (reminder, alert, critique, blocking)
- Stores both the context (what triggered it) and the response (JSON)
- Links to the resource that needs the data (polymorphic via resource_type/id)

Uses GFIBase (has company_id) — financial table with soft-delete.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Formulaire(GFIBase, Base):
    __tablename__ = "formulaire"

    # ── Link to catalogue template ───────────────────────────────────────
    catalogue_id = Column(
        UUID(as_uuid=True),
        ForeignKey("formulaire_catalogue.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Instance data ────────────────────────────────────────────────────
    code = Column(String(20), nullable=False, index=True)
    priority = Column(String(20), nullable=False)
    # EN_ATTENTE, REMPLI, EXPIRE, ANNULE
    status = Column(String(20), nullable=False, server_default="'EN_ATTENTE'")

    # ── The rendered question (template with context filled in) ──────────
    question_text = Column(Text, nullable=False)

    # ── Context: what triggered this formulaire ──────────────────────────
    trigger_context = Column(JSONB, nullable=False)
    # Polymorphic link to the blocked resource
    blocked_resource_type = Column(String(100), nullable=True)
    blocked_resource_id = Column(UUID(as_uuid=True), nullable=True)

    # ── Assignment ───────────────────────────────────────────────────────
    assigned_to = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_role = Column(String(40), nullable=False, server_default="'DAF'")

    # ── Response ─────────────────────────────────────────────────────────
    response_data = Column(JSONB, nullable=True)
    responded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # ── Escalation tracking ──────────────────────────────────────────────
    escalation_level = Column(Integer, nullable=False, server_default="0")
    last_relance_at = Column(DateTime(timezone=True), nullable=True)
    next_escalation_at = Column(DateTime(timezone=True), nullable=True)

    # ── AI verification (for document proofs) ────────────────────────────
    ai_verification_status = Column(String(20), nullable=True)
    # PENDING, CONFORME, NON_CONFORME, NEEDS_REVIEW
    ai_verification_result = Column(JSONB, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    catalogue = relationship("FormulaireCatalogue")

    def __repr__(self):
        return f"<Formulaire {self.code} status={self.status}>"
