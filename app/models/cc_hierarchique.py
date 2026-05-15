"""GFI v7.0 — Hierarchical Cost Center models.

6-level hierarchy:
  Level 0: GROUPE (single root)
  Level 1: ENTREPRISE / ASSOCIE transversal
  Level 2: PROJET or FONCTION (siège, CFF, inter-projets)
  Level 3: CATÉGORIE (terrain, construction, ventes, CFF, fiscal...)
  Level 4: SOUS-CATÉGORIE
  Level 5: DÉTAIL (optional)

Tables:
  - cc_node: Hierarchical cost center tree
  - cc_distribution: % per associate per node (% entreprise + % projet)
  - cc_imputation: Every financial movement line mapped to a CC node
"""
import uuid
import enum
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, Date,
    ForeignKey, Enum as SAEnum, JSON, Numeric, UniqueConstraint, Index,
    CheckConstraint, func,
)
from app.database import Base


# ────────────────────────────────────────────────────────────────────────────
# Enums
# ────────────────────────────────────────────────────────────────────────────

class TypeImputation(str, enum.Enum):
    ENCAISSEMENT = "ENCAISSEMENT"
    DECAISSEMENT_DIRECT = "DECAISSEMENT_DIRECT"
    CFF = "CFF"
    CHARGE_PARTAGEE = "CHARGE_PARTAGEE"
    CHARGE_SOCIETE = "CHARGE_SOCIETE"
    INTER_PROJET = "INTER_PROJET"
    RETRAIT_ASSOCIE = "RETRAIT_ASSOCIE"
    ACHAT_STOCK = "ACHAT_STOCK"
    SORTIE_STOCK = "SORTIE_STOCK"
    VEHICULE = "VEHICULE"
    BUREAU_BBZ = "BUREAU_BBZ"
    AVANCE_NATURE = "AVANCE_NATURE"
    CAPITAL = "CAPITAL"


class SensImputation(str, enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class CategorieCC(str, enum.Enum):
    TERRAIN = "TERRAIN"
    CONSTR = "CONSTR"
    COMMERCIAL = "COMMERCIAL"
    VENTES = "VENTES"
    ASSOC = "ASSOC"
    CFF = "CFF"
    FISCAL = "FISCAL"
    ADMIN = "ADMIN"
    ASSURANCE = "ASSURANCE"
    MASSE_SAL = "MASSE_SAL"
    LOCAUX = "LOCAUX"
    ACHATS = "ACHATS"
    STOCK = "STOCK"
    VEHICULES = "VEHICULES"
    INTER_PROJ = "INTER_PROJ"
    DIVERS = "DIVERS"
    SIEGE = "SIEGE"


# ────────────────────────────────────────────────────────────────────────────
# CC Node — the hierarchical tree
# ────────────────────────────────────────────────────────────────────────────

class CCNode(Base):
    """Hierarchical cost center node (6 levels, 0-5)."""
    __tablename__ = "cc_nodes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(150), nullable=False)
    libelle = Column(String(500), nullable=False)

    # Hierarchy
    niveau = Column(Integer, nullable=False)
    parent_id = Column(String(36), ForeignKey("cc_nodes.id"))
    chemin_complet = Column(String(1000), nullable=False)

    # Links
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"))
    projet_id = Column(String(36), ForeignKey("projets.id"))
    associe_id = Column(String(36), ForeignKey("associes.id"))
    categorie = Column(SAEnum(CategorieCC))

    # Budget
    budget_annuel_prevu = Column(Numeric(18, 2), default=0)

    # Status
    est_actif = Column(Boolean, default=True)
    date_ouverture = Column(Date, server_default=func.current_date())
    date_cloture = Column(Date)
    accepte_imputation = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_cc_node_code"),
        Index("ix_cc_node_parent", "parent_id"),
        Index("ix_cc_node_entreprise", "entreprise_id"),
        Index("ix_cc_node_projet", "projet_id"),
        Index("ix_cc_node_niveau", "niveau"),
        CheckConstraint("niveau >= 0 AND niveau <= 5", name="ck_cc_niveau"),
    )


# ────────────────────────────────────────────────────────────────────────────
# CC Distribution — % per associate per CC node
# ────────────────────────────────────────────────────────────────────────────

class CCDistribution(Base):
    """Distribution percentages per associate per CC node."""
    __tablename__ = "cc_distributions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cc_node_id = Column(String(36), ForeignKey("cc_nodes.id"), nullable=False)
    associe_id = Column(String(36), ForeignKey("associes.id"), nullable=False)

    pct_entreprise = Column(Numeric(6, 2), nullable=False, default=0)
    pct_projet = Column(Numeric(6, 2), nullable=False, default=0)
    pct_applicable_charges = Column(Numeric(6, 2), nullable=False, default=0)
    pct_applicable_cff = Column(Numeric(6, 2), nullable=False, default=0)
    pct_applicable_benefice = Column(Numeric(6, 2), nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("cc_node_id", "associe_id", name="uq_cc_dist"),
    )


# ────────────────────────────────────────────────────────────────────────────
# CC Imputation — every financial movement mapped to a CC node
# ────────────────────────────────────────────────────────────────────────────

class CCImputation(Base):
    """Financial movement line imputed to a cost center node."""
    __tablename__ = "cc_imputations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    cc_node_id = Column(String(36), ForeignKey("cc_nodes.id"), nullable=False)

    date_imputation = Column(Date, nullable=False)
    periode = Column(String(7), nullable=False)  # "2026-03"

    # Source references (nullable — only one populated)
    encaissement_id = Column(String(36), ForeignKey("encaissements.id"))
    decaissement_id = Column(String(36), ForeignKey("decaissements.id"))
    cff_facture_id = Column(String(36), ForeignKey("cff_factures.id"))
    mouvement_stock_id = Column(String(36), ForeignKey("mouvements_stock.id"))
    flux_inter_projet_id = Column(String(36), ForeignKey("flux_inter_projets.id"))
    mouvement_caisse_id = Column(String(36), ForeignKey("mouvements_caisse.id"))

    # Nature
    type_imputation = Column(SAEnum(TypeImputation), nullable=False)
    sens = Column(SAEnum(SensImputation), nullable=False)
    montant = Column(Numeric(18, 2), nullable=False)
    realite_financiere = Column(String(3), nullable=False)  # RF1, RF2, RF3, RF4

    libelle = Column(String(500), nullable=False)

    # Quote-parts (calculated at imputation time)
    # JSON: [{"associe_id": "...", "pct": 60, "montant": 600000, "type_pct": "projet"}]
    quote_parts = Column(JSON, nullable=False, default=list)

    # Documents
    documents = Column(JSON)

    created_by = Column(String(36))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_cci_node", "cc_node_id"),
        Index("ix_cci_date", "date_imputation"),
        Index("ix_cci_rf", "realite_financiere"),
        Index("ix_cci_type", "type_imputation"),
        Index("ix_cci_periode", "periode"),
    )
