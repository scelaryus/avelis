"""
GFI v7.0 — Meta-IA: auto-generative module proposals.

Detects uncovered functional needs and proposes new modules.
Double DAF validation: approve exploration + approve deployment.
No auto-generated module EVER touches production without both approvals.
"""

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer,
    String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base, GFIBase


class MetaIaProposal(GFIBase, Base):
    """Structured proposal for a new module detected by Meta-IA."""

    __tablename__ = "meta_ia_proposal"

    # ── Detection context ────────────────────────────────────────────────
    detection_trigger = Column(Text, nullable=False)
    # What pattern/signal triggered this proposal
    evidence = Column(JSONB, nullable=True)
    # Supporting data: frequencies, overrides, unhandled flows

    # ── Proposal ─────────────────────────────────────────────────────────
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    proposed_functionality = Column(Text, nullable=False)
    data_consumed = Column(JSONB, nullable=True)
    outputs_produced = Column(JSONB, nullable=True)
    interacting_modules = Column(JSONB, nullable=True)
    estimated_complexity = Column(String(20), nullable=True)
    # LOW, MEDIUM, HIGH, CRITICAL

    # ── Lifecycle (double DAF approval) ──────────────────────────────────
    # DETECTED, PROPOSED, EXPLORATION_APPROVED, SANDBOX_CREATED,
    # SANDBOX_TESTING, SANDBOX_VALIDATED, DEPLOYMENT_APPROVED,
    # DEPLOYED, REJECTED, DEFERRED
    status = Column(String(30), nullable=False, server_default="'DETECTED'")

    # ── First approval: explore ──────────────────────────────────────────
    exploration_approved_by = Column(UUID(as_uuid=True), nullable=True)
    exploration_approved_at = Column(DateTime(timezone=True), nullable=True)

    # ── Second approval: deploy ──────────────────────────────────────────
    deployment_approved_by = Column(UUID(as_uuid=True), nullable=True)
    deployment_approved_at = Column(DateTime(timezone=True), nullable=True)

    rejection_reason = Column(Text, nullable=True)

    def __repr__(self):
        return f"<MetaIaProposal '{self.title[:40]}' {self.status}>"


class MetaIaSandbox(GFIBase, Base):
    """Isolated sandbox environment for testing a Meta-IA proposal."""

    __tablename__ = "meta_ia_sandbox"

    proposal_id = Column(
        UUID(as_uuid=True), ForeignKey("meta_ia_proposal.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Sandbox config ───────────────────────────────────────────────────
    sandbox_name = Column(String(100), nullable=False)
    # CREATING, READY, TESTING, VALIDATED, FAILED, DESTROYED
    status = Column(String(20), nullable=False, server_default="'CREATING'")

    # ── Testing ──────────────────────────────────────────────────────────
    test_data_config = Column(JSONB, nullable=True)
    test_results = Column(JSONB, nullable=True)
    test_passed = Column(Boolean, nullable=True)
    tested_at = Column(DateTime(timezone=True), nullable=True)

    # ── Generated code/config ────────────────────────────────────────────
    generated_schema = Column(JSONB, nullable=True)
    generated_rules = Column(JSONB, nullable=True)

    proposal = __import__("sqlalchemy.orm", fromlist=["relationship"]).relationship("MetaIaProposal")

    def __repr__(self):
        return f"<MetaIaSandbox {self.sandbox_name} {self.status}>"
