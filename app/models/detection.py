"""
GFI v7.0 — Autonomous Detection: DetectionPattern + DetectionFinding.

15 patterns that analyze raw data to discover entities, flows, and anomalies
without being told where to look.
"""

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class DetectionPattern(Base):
    """Configuration for each of the 15 detection patterns."""

    __tablename__ = "detection_pattern"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=__import__("sqlalchemy").text("gen_random_uuid()"))
    pattern_id = Column(Integer, unique=True, nullable=False)
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    evidence_signature = Column(Text, nullable=False)
    detection_method = Column(Text, nullable=False)
    # SQL_QUERY, NIF_CROSS_MATCH, ALIAS_MATCH, LABEL_SCAN, AMOUNT_PATTERN
    proposed_action = Column(String(50), nullable=False)
    # CREATE_ENTITY, RESOLVE_ALIAS, TRIGGER_CFF, GENERATE_FORMULAIRE, FLAG_REVIEW
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=__import__("sqlalchemy").func.now())

    def __repr__(self):
        return f"<DetectionPattern #{self.pattern_id} {self.code}>"


class DetectionFinding(GFIBase, Base):
    """A structured finding from pattern detection. Requires DAF validation."""

    __tablename__ = "detection_finding"

    pattern_id = Column(Integer, nullable=False, index=True)
    pattern_code = Column(String(30), nullable=False, index=True)

    # ── Finding data ─────────────────────────────────────────────────────
    confidence_score = Column(Numeric(5, 2), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    source_documents = Column(JSONB, nullable=True)
    extracted_values = Column(JSONB, nullable=True)
    proposed_action = Column(String(50), nullable=False)
    proposed_action_detail = Column(JSONB, nullable=True)

    # ── Context ──────────────────────────────────────────────────────────
    related_entity_ids = Column(JSONB, nullable=True)
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # ── DAF validation ───────────────────────────────────────────────────
    # DETECTED, VALIDATED, REJECTED, INTEGRATED, DEFERRED
    status = Column(String(20), nullable=False, server_default="'DETECTED'")
    validated_by = Column(UUID(as_uuid=True), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validation_notes = Column(Text, nullable=True)

    # ── Integration ──────────────────────────────────────────────────────
    integrated_at = Column(DateTime(timezone=True), nullable=True)
    integration_result = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<DetectionFinding P{self.pattern_id} {self.confidence_score}% {self.status}>"
