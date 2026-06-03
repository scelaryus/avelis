"""
GFI v7.0 — Project + Construction Site Management models.

ProjectTask: task planning with completion tracking.
TaskAdvancement: timestamped advancement records.
SubcontractorContract: subcontractor agreements with performance scoring.

Advancement % drives credit disbursement eligibility.
Work situations feed CC2 (construction) in the cost center.
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class ProjectTask(GFIBase, Base):
    """Task in a project's construction plan."""

    __tablename__ = "project_task"

    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    parent_task_id = Column(
        UUID(as_uuid=True), ForeignKey("project_task.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    code = Column(String(30), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    # TERRASSEMENT, FONDATION, STRUCTURE, MACONNERIE, ETANCHEITE,
    # ELECTRICITE, PLOMBERIE, REVETEMENT, VRD, FINITIONS, AUTRE
    category = Column(String(30), nullable=True)

    # ── Planning ─────────────────────────────────────────────────────────
    planned_start = Column(Date, nullable=True)
    planned_end = Column(Date, nullable=True)
    actual_start = Column(Date, nullable=True)
    actual_end = Column(Date, nullable=True)
    duration_days = Column(Integer, nullable=True)

    # ── Advancement ──────────────────────────────────────────────────────
    completion_pct = Column(Numeric(5, 2), nullable=False, server_default="0")
    # Links to credit tier thresholds
    tier_threshold_pct = Column(Numeric(5, 2), nullable=True)
    # e.g., 30 for tier 15%, 65 for tier 35%, 90 for tier 25%

    # ── Budget ───────────────────────────────────────────────────────────
    budget_amount = Column(Numeric(15, 2), nullable=True)
    actual_cost = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Status ───────────────────────────────────────────────────────────
    # A_FAIRE, EN_COURS, TERMINE, BLOQUE
    status = Column(String(20), nullable=False, server_default="'A_FAIRE'")

    # ── Responsible ──────────────────────────────────────────────────────
    assigned_to = Column(UUID(as_uuid=True), nullable=True)
    subcontractor_id = Column(
        UUID(as_uuid=True), ForeignKey("subcontractor_contract.id", ondelete="SET NULL"),
        nullable=True,
    )

    project = relationship("Project")
    parent_task = relationship("ProjectTask", remote_side="ProjectTask.id")

    def __repr__(self):
        return f"<ProjectTask {self.code} {self.completion_pct}% {self.status}>"


class TaskAdvancement(GFIBase, Base):
    """Timestamped advancement record for a project task."""

    __tablename__ = "task_advancement"

    task_id = Column(
        UUID(as_uuid=True), ForeignKey("project_task.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    record_date = Column(Date, nullable=False, index=True)
    previous_pct = Column(Numeric(5, 2), nullable=False)
    new_pct = Column(Numeric(5, 2), nullable=False)
    observations = Column(Text, nullable=True)
    photo_urls = Column(JSONB, nullable=True)

    recorded_by = Column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    validated_by = Column(UUID(as_uuid=True), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)

    # ── Tier trigger check ───────────────────────────────────────────────
    tier_triggered = Column(String(20), nullable=True)
    # e.g., "TIER_15PCT" if this advancement crossed a threshold

    task = relationship("ProjectTask")

    def __repr__(self):
        return (
            f"<TaskAdvancement {self.previous_pct}->{self.new_pct}% "
            f"on {self.record_date}>"
        )


class SubcontractorContract(GFIBase, Base):
    """Subcontractor agreement for a project."""

    __tablename__ = "subcontractor_contract"

    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    supplier_id = Column(
        UUID(as_uuid=True), ForeignKey("supplier.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )

    subcontractor_name = Column(String(255), nullable=False)
    contract_ref = Column(String(50), nullable=True)
    contract_date = Column(Date, nullable=True)
    scope = Column(Text, nullable=True)

    # ── Financial ────────────────────────────────────────────────────────
    montant_total = Column(Numeric(15, 2), nullable=True)
    montant_facture = Column(Numeric(15, 2), nullable=False, server_default="0")
    montant_paye = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Performance (0-100 per criterion) ────────────────────────────────
    score_quality = Column(Numeric(5, 2), nullable=True)
    score_deadlines = Column(Numeric(5, 2), nullable=True)
    score_safety = Column(Numeric(5, 2), nullable=True)
    score_overall = Column(Numeric(5, 2), nullable=True)

    # ── Status ───────────────────────────────────────────────────────────
    # ACTIF, TERMINE, SUSPENDU, RESILIE
    status = Column(String(20), nullable=False, server_default="'ACTIF'")

    project = relationship("Project")

    def __repr__(self):
        return f"<SubcontractorContract {self.subcontractor_name} {self.status}>"
