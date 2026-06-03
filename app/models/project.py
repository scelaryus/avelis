"""
GFI v7.0 — Project model.

A project belongs to a carrying entity (company_id via GFIBase).
Profit/cost distribution uses part_projet percentages, NOT the company-level
entreprise_associe percentages — confusing them causes grave financial errors.

Special cases modelled:
- Transfer (OPERA): transferred_from_company_id + transfer_date.
  Before transfer_date -> old entity; after -> current company_id.
- Land ownership != project parts (T21000): proprietaire_foncier tracks the
  legal deed holder; part_projet tracks the GFI profit/cost split.
- Non-commercial (MOSQUEE): is_non_commercial = True; parts exist for
  fund-origin tracking only, no profit distribution.
- Blocked projects: status EN_ATTENTE_CONFIRMATION or A_DEVELOPPER means
  no part_projet rows exist and no financial operations are permitted.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Project(GFIBase, Base):
    __tablename__ = "project"

    # ── Identity ─────────────────────────────────────────────────────────
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    aliases = Column(ARRAY(Text), nullable=True)

    # ── Status ───────────────────────────────────────────────────────────
    # ACTIF, TERRAIN, DONATION, EN_ATTENTE_CONFIRMATION, A_DEVELOPPER
    status = Column(String(40), nullable=False)

    # ── Client tracking ──────────────────────────────────────────────────
    client_count = Column(Integer, nullable=True)

    # ── Financial ────────────────────────────────────────────────────────
    terrain_cost_estimate = Column(Numeric(15, 2), nullable=True)

    # ── Land ownership (distinct from project parts) ─────────────────────
    # T21000: deed under Ahmed's name (100%) but GFI split is 25/25/25/25.
    # CFF and profit use part_projet, NOT proprietaire_foncier.
    proprietaire_foncier = Column(Text, nullable=True)

    # ── Non-commercial flag ──────────────────────────────────────────────
    is_non_commercial = Column(
        Boolean, nullable=False, server_default="false"
    )

    # ── Transfer tracking (FC-012) ───────────────────────────────────────
    transferred_from_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company.id", ondelete="RESTRICT"),
        nullable=True,
    )
    transfer_date = Column(Date, nullable=True)
    transfer_formulaire_ref = Column(String(20), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    company = relationship("Company", foreign_keys="[Project.company_id]")
    transferred_from = relationship(
        "Company", foreign_keys="[Project.transferred_from_company_id]"
    )
    parts = relationship("PartProjet", back_populates="project", lazy="select")

    def __repr__(self):
        return f"<Project {self.code} — {self.name}>"
