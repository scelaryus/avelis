"""
GFI v7.0 — PartProjet: project-level ownership percentages.

This table answers: "What % does each associate own in each PROJECT?"
Used for: profit distribution, direct project charges (terrain, construction),
shared charges ventilated to a project.

CRITICAL: These percentages can DIFFER from the company-level ownership.
Example: IRENE (SARL-DP) is 60/20/20/0 while SARL-DP itself is 25/25/25/25.

Rules:
- Rows ONLY exist for projects with status ACTIF, TERRAIN, or DONATION.
- Projects with status A_DEVELOPPER or EN_ATTENTE_CONFIRMATION have NO rows.
  Moving to ACTIF triggers FC-013 which collects the splits.
- For any given project_id, the sum of non-deleted percentages MUST equal
  exactly 100.0000% (enforced by DB trigger, KT-09).
"""

from sqlalchemy import Column, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class PartProjet(GFIBase, Base):
    __tablename__ = "part_projet"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "associate_id",
            name="uq_part_projet_project_associate",
        ),
    )

    # ── FK to the project ────────────────────────────────────────────────
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── FK to the associate (person) ─────────────────────────────────────
    associate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("associate.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Ownership percentage ─────────────────────────────────────────────
    percentage = Column(Numeric(7, 4), nullable=False)

    # ── Relationships ────────────────────────────────────────────────────
    project = relationship("Project", back_populates="parts")
    associate = relationship("Associate")
    company = relationship("Company")

    def __repr__(self):
        return (
            f"<PartProjet project={self.project_id} "
            f"associate={self.associate_id} {self.percentage}%>"
        )
