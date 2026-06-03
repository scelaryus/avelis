"""
GFI v7.0 — CostCenterNode + CostCenterEntry: the financial truth engine.

6-level hierarchy consolidating ALL flows (RF1+RF2+RF3+RF4) to show
real profitability per project, per company, per associate.

Levels:
  0: Groupe (one root)
  1: Entreprise (12 entities)
  2: Projet ou Fonction (projects + siege/BBZ)
  3: Categorie de cout (16 standard categories)
  4: Sous-categorie (specific sub-items)
  5: Detail operationnel (individual transactions)

Ascending consolidation is REAL-TIME: level 5 -> 4 -> 3 -> 2 -> 1 -> 0
in the SAME database transaction.

Verification V1: SUM(children) = parent at every level. Even 0.01 DA
discrepancy -> BLOQUANT alert.
"""

from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class CostCenterNode(GFIBase, Base):
    """A node in the 6-level cost center hierarchy."""

    __tablename__ = "cost_center_node"

    # ── Hierarchy ────────────────────────────────────────────────────────
    code = Column(String(100), unique=True, nullable=False, index=True)
    level = Column(Integer, nullable=False, index=True)
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cost_center_node.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    parent_code = Column(String(100), nullable=True)

    # ── Identity ─────────────────────────────────────────────────────────
    libelle = Column(String(255), nullable=False)
    node_type = Column(String(30), nullable=False)
    # GROUPE, ENTREPRISE, PROJET, FONCTION, CATEGORIE,
    # SOUS_CATEGORIE, DETAIL

    # ── Scope ────────────────────────────────────────────────────────────
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    categorie = Column(String(30), nullable=True)
    sous_categorie = Column(String(60), nullable=True)

    # ── Amounts per RF (separate tracking) ───────────────────────────────
    montant_rf1 = Column(Numeric(15, 2), nullable=False, server_default="0")
    montant_rf2 = Column(Numeric(15, 2), nullable=False, server_default="0")
    montant_rf3 = Column(Numeric(15, 2), nullable=False, server_default="0")
    montant_rf4 = Column(Numeric(15, 2), nullable=False, server_default="0")
    montant_total = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Flags ────────────────────────────────────────────────────────────
    impact_tresorerie = Column(
        Boolean, nullable=False, server_default="true"
    )
    is_active = Column(Boolean, nullable=False, server_default="true")

    # ── Relationships ────────────────────────────────────────────────────
    parent = relationship("CostCenterNode", remote_side="CostCenterNode.id")
    project = relationship("Project")

    def __repr__(self):
        return f"<CostCenterNode {self.code} L{self.level} {self.montant_total} DA>"


class CostCenterEntry(GFIBase, Base):
    """Individual transaction imputed to a cost center node (level 5)."""

    __tablename__ = "cost_center_entry"

    node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cost_center_node.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    node_code = Column(String(100), nullable=False)

    # ── Transaction data ─────────────────────────────────────────────────
    entry_date = Column(
        __import__("sqlalchemy").Date, nullable=False, index=True
    )
    rf_type = Column(String(3), nullable=False)
    montant = Column(Numeric(15, 2), nullable=False)
    libelle = Column(Text, nullable=False)

    # ── Source document ──────────────────────────────────────────────────
    source_type = Column(String(60), nullable=True)
    source_id = Column(UUID(as_uuid=True), nullable=True)

    # ── Project context ──────────────────────────────────────────────────
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )

    # ── Flags ────────────────────────────────────────────────────────────
    impact_tresorerie = Column(
        Boolean, nullable=False, server_default="true"
    )

    node = relationship("CostCenterNode")

    def __repr__(self):
        return f"<CostCenterEntry {self.rf_type} {self.montant} DA on {self.node_code}>"
