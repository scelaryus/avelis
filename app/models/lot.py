"""
GFI v7.0 — Lot: real estate inventory unit (EDD single source of truth).

Each lot is a sellable unit within a project: apartment, commercial space,
parking, cave, etc. The EDD tracks every lot's lifecycle from creation
to delivery.

Pricing follows the RF classification:
  rf1_price: declared contractual price (visible in official docs)
  rf2_price: undeclared cash complement (encrypted, restricted access)
  real_price: computed RF1 + RF2 (used by Centre de Couts)

RF2 price is encrypted at rest and access-restricted — only users with
rf2.read permission can see it. The column is physically stripped from
query results for users without permission.

Uses GFIBase (company_id = the entity selling the lot).
"""

from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Lot(GFIBase, Base):
    __tablename__ = "lot"

    # ── Project link ─────────────────────────────────────────────────────
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Lot identity ─────────────────────────────────────────────────────
    # e.g., T-F3-A-012 = Tour-F3-BlocA-Apt012
    lot_ref = Column(String(50), nullable=False, index=True)
    # Typology
    typology = Column(String(30), nullable=False)
    # F2, F3, F4, F5, DUPLEX, LOCAL_COMMERCIAL, PARKING, CAVE

    # ── Physical characteristics ─────────────────────────────────────────
    surface_m2 = Column(Numeric(8, 2), nullable=True)
    floor_number = Column(Integer, nullable=True)
    block = Column(String(20), nullable=True)  # A, B, C, Tour 1, etc.
    orientation = Column(String(20), nullable=True)
    # NORD, SUD, EST, OUEST, DOUBLE, N/A

    # ── Status (state machine — see EDD engine) ──────────────────────────
    # DISPONIBLE, VERROUILLE, RESERVE, PROMIS, VENDU, LIVRE,
    # PRELEVEMENT (associate withdrawal), BLOQUE, ANNULE
    status = Column(String(20), nullable=False, server_default="'DISPONIBLE'")

    # ── Pricing (RF classification) ──────────────────────────────────────
    rf1_price = Column(Numeric(15, 2), nullable=True)  # declared
    rf2_price_encrypted = Column(Text, nullable=True)   # encrypted at rest
    rf2_price = Column(Numeric(15, 2), nullable=True)   # in-memory only for authorized
    real_price = Column(Numeric(15, 2), nullable=True)  # RF1 + RF2 computed

    # ── Delivery ─────────────────────────────────────────────────────────
    expected_delivery_date = Column(Date, nullable=True)
    actual_delivery_date = Column(Date, nullable=True)

    # ── Client (set when reserved/sold) ──────────────────────────────────
    client_name = Column(String(255), nullable=True)
    client_id = Column(UUID(as_uuid=True), nullable=True)

    # ── Associate withdrawal (PRELEVEMENT status) ────────────────────────
    withdrawn_by_associate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("associate.id", ondelete="SET NULL"),
        nullable=True,
    )
    withdrawal_value = Column(Numeric(15, 2), nullable=True)

    # ── Metadata ─────────────────────────────────────────────────────────
    description = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    project = relationship("Project")
    company = relationship("Company", foreign_keys="[Lot.company_id]")
    withdrawn_by = relationship("Associate")

    def __repr__(self):
        return f"<Lot {self.lot_ref} {self.typology} {self.status}>"
