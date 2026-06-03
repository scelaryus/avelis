"""
GFI v7.0 — EntrepriseAssocie: company-level ownership percentages.

This table answers: "What % does each associate own in each COMPANY?"
Used for: CFF imputation, company-level charges (rent, admin, HQ costs).

CRITICAL: This is NOT the same as project-level ownership (part_projet).
IRENE is 60/20/20/0 even though its carrier SARL-DP is 25/25/25/25.

Constraint: For any given company_id, the sum of all non-deleted
percentages MUST equal exactly 100.0000% (enforced by DB trigger, KT-09).
"""

from sqlalchemy import Column, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class EntrepriseAssocie(GFIBase, Base):
    __tablename__ = "entreprise_associe"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "associate_id",
            name="uq_entreprise_associe_company_associate",
        ),
    )

    # ── FK to the associate (person) ─────────────────────────────────────
    associate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("associate.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Ownership percentage ─────────────────────────────────────────────
    # NUMERIC(7,4) allows 100.0000 with 4-decimal precision.
    percentage = Column(Numeric(7, 4), nullable=False)

    # ── Optional note (e.g., "approximate — confirm via FC-023") ─────────
    note = Column(String(255), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    associate = relationship("Associate")
    company = relationship("Company")

    def __repr__(self):
        return (
            f"<EntrepriseAssocie company={self.company_id} "
            f"associate={self.associate_id} {self.percentage}%>"
        )
