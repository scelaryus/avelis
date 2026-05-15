# GAP 2 — FINANCE & ASSOCIÉS — finance_associes.py
# GAP 4 — ASSOCIATE ALIASES (AssociateAlias model included)
"""SQLAlchemy models for Finance & Associés domain.

Tables:
  - comptes_courants_associes
  - mouvements_comptes_courants
  - clotures_mensuelles
  - appels_de_fonds
  - cessions_parts
  - associate_aliases
"""
import uuid

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, Date,
    ForeignKey, Enum as SAEnum, JSON, Numeric, UniqueConstraint, Index,
    CheckConstraint, func,
)
from app.database import Base
import enum


# ────────────────────────────────────────────────────────────────────────────
# Enums
# ────────────────────────────────────────────────────────────────────────────

class TypeMouvement(str, enum.Enum):
    APPORT_CAPITAL = "APPORT_CAPITAL"
    AVANCE_ASSOCIE = "AVANCE_ASSOCIE"
    LIBERATION_BENEFICE = "LIBERATION_BENEFICE"
    CONSOMMATION = "CONSOMMATION"
    REMBOURSEMENT_AVANCE = "REMBOURSEMENT_AVANCE"
    CESSION_PARTS_CREDIT = "CESSION_PARTS_CREDIT"
    ACQUISITION_PARTS_DEBIT = "ACQUISITION_PARTS_DEBIT"
    APPEL_FONDS_CREDIT = "APPEL_FONDS_CREDIT"
    CORRECTION_MANUELLE = "CORRECTION_MANUELLE"
    DIVIDENDE_EXCEPTIONNEL = "DIVIDENDE_EXCEPTIONNEL"


class StatutCloture(str, enum.Enum):
    EN_COURS = "EN_COURS"
    SUCCES = "SUCCES"
    ECHEC = "ECHEC"
    ANNULEE = "ANNULEE"


class StatutAppelFonds(str, enum.Enum):
    BROUILLON = "BROUILLON"
    EMIS = "EMIS"
    PARTIELLEMENT_COUVERT = "PARTIELLEMENT_COUVERT"
    INTEGRALEMENT_COUVERT = "INTEGRALEMENT_COUVERT"
    EXPIRE = "EXPIRE"
    ANNULE = "ANNULE"


class StatutCession(str, enum.Enum):
    PROPOSEE = "PROPOSEE"
    EN_NEGOCIATION = "EN_NEGOCIATION"
    ACCEPTEE = "ACCEPTEE"
    FINALISEE = "FINALISEE"
    REJETEE = "REJETEE"
    ANNULEE = "ANNULEE"


# ────────────────────────────────────────────────────────────────────────────
# Comptes Courants Associés
# ────────────────────────────────────────────────────────────────────────────

class CompteCourantAssocie(Base):
    """Current account for each associate — one per associate."""
    __tablename__ = "comptes_courants_associes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    associe_id = Column(
        String(36), ForeignKey("associes.id"), nullable=False, unique=True
    )
    solde_global = Column(Numeric(15, 2), nullable=False, default=0)
    solde_disponible_retrait = Column(Numeric(15, 2), nullable=False, default=0)
    solde_avances_non_remboursees = Column(Numeric(15, 2), nullable=False, default=0)
    derniere_cloture_maj = Column(Date, nullable=True)
    est_gele = Column(Boolean, default=False)
    motif_gel = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Mouvements Comptes Courants
# ────────────────────────────────────────────────────────────────────────────

class MouvementCompteCourant(Base):
    """Individual movements on associate current accounts."""
    __tablename__ = "mouvements_comptes_courants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    compte_courant_id = Column(
        String(36), ForeignKey("comptes_courants_associes.id"), nullable=False
    )
    associe_id = Column(String(36), ForeignKey("associes.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=True)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=True)
    exercice_id = Column(String(36), ForeignKey("exercices.id"), nullable=True)
    type_mouvement = Column(SAEnum(TypeMouvement), nullable=False)
    montant = Column(
        Numeric(15, 2), nullable=False,
    )
    sens = Column(String(10), nullable=False)
    date_mouvement = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    reference_interne = Column(String(100), nullable=True)
    cloture_id = Column(
        String(36), ForeignKey("clotures_mensuelles.id", use_alter=True), nullable=True
    )
    appel_fonds_id = Column(
        String(36), ForeignKey("appels_de_fonds.id", use_alter=True), nullable=True
    )
    cession_parts_id = Column(
        String(36), ForeignKey("cessions_parts.id", use_alter=True), nullable=True
    )
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    statut_fiscal = Column(String(50), default="EN_ATTENTE")
    realite_financiere = Column(String(4))  # RF1-RF4 (GFI v7.0)
    valide_par = Column(String(36), ForeignKey("users.id"), nullable=True)
    date_validation = Column(DateTime, nullable=True)
    est_test_fictif = Column(Boolean, default=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint("montant > 0", name="ck_mvt_montant_positif"),
        CheckConstraint("sens IN ('CREDIT', 'DEBIT')", name="ck_mvt_sens"),
        Index("ix_mvt_cc_compte", "compte_courant_id"),
        Index("ix_mvt_cc_associe_date", "associe_id", "date_mouvement"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Clôtures Mensuelles
# ────────────────────────────────────────────────────────────────────────────

class ClotureMensuelle(Base):
    """Monthly closing with distribution to associates."""
    __tablename__ = "clotures_mensuelles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    exercice_id = Column(String(36), ForeignKey("exercices.id"), nullable=False)
    mois = Column(Integer, nullable=False)
    annee = Column(Integer, nullable=False)
    tresorerie_nette_mois = Column(Numeric(15, 2), nullable=False)
    montant_a_liberer = Column(Numeric(15, 2), nullable=False)
    pourcentage_liberation = Column(Numeric(5, 2), default=50.00)
    detail_distribution = Column(JSON, nullable=False)
    hash_verification = Column(String(64), nullable=False)
    double_computation_ok = Column(Boolean, default=False)
    # ── GFI v7.0: store both computations + ecart ──
    tnm_calcul_1 = Column(Numeric(15, 2))  # first independent computation
    tnm_calcul_2 = Column(Numeric(15, 2))  # second independent computation
    ecart_computation = Column(Numeric(15, 2))  # must be 0.00 DA exactly
    etape_courante = Column(Integer)  # 1-7 step tracking
    statut = Column(SAEnum(StatutCloture), default=StatutCloture.EN_COURS)
    erreur = Column(Text, nullable=True)
    date_execution = Column(DateTime, nullable=True)
    duree_execution_ms = Column(Integer, nullable=True)
    est_test_fictif = Column(Boolean, default=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("projet_id", "annee", "mois", name="uq_cloture_projet_mois"),
        CheckConstraint("mois >= 1 AND mois <= 12", name="ck_cloture_mois"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Appels de Fonds
# ────────────────────────────────────────────────────────────────────────────

class AppelDeFonds(Base):
    """Funding calls to associates."""
    __tablename__ = "appels_de_fonds"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=True)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    montant_total_requis = Column(Numeric(15, 2), nullable=False)
    montant_collecte = Column(Numeric(15, 2), nullable=False, default=0)
    motif = Column(Text, nullable=False)
    date_emission = Column(Date, nullable=False)
    date_limite = Column(Date, nullable=False)
    detail_contributions = Column(JSON, nullable=False)
    statut = Column(SAEnum(StatutAppelFonds), default=StatutAppelFonds.BROUILLON)
    emis_par = Column(String(36), ForeignKey("users.id"), nullable=True)
    est_test_fictif = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "montant_total_requis > 0", name="ck_appel_montant_positif"
        ),
    )


# ────────────────────────────────────────────────────────────────────────────
# Cessions de Parts
# ────────────────────────────────────────────────────────────────────────────

class CessionParts(Base):
    """Share transfer transactions between associates."""
    __tablename__ = "cessions_parts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    vendeur_id = Column(String(36), ForeignKey("associes.id"), nullable=False)
    acheteur_id = Column(String(36), ForeignKey("associes.id"), nullable=True)
    pourcentage_parts_cedees = Column(Numeric(5, 2), nullable=False)
    valorisation_systeme_par_point = Column(Numeric(15, 2), nullable=False)
    prix_demande_par_point = Column(Numeric(15, 2), nullable=True)
    prix_final_par_point = Column(Numeric(15, 2), nullable=True)
    montant_total_transaction = Column(Numeric(15, 2), nullable=True)
    date_proposition = Column(Date, nullable=False)
    date_limite_offres = Column(Date, nullable=True)
    date_finalisation = Column(Date, nullable=True)
    statut = Column(SAEnum(StatutCession), default=StatutCession.PROPOSEE)
    acte_cession_document_id = Column(
        String(36), ForeignKey("documents.id"), nullable=True
    )
    motif = Column(Text, nullable=True)
    est_cession_forcee = Column(Boolean, default=False)
    est_test_fictif = Column(Boolean, default=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "pourcentage_parts_cedees > 0", name="ck_cession_pct_positif"
        ),
    )


# ────────────────────────────────────────────────────────────────────────────
# Associate Aliases (GAP 4)
# ────────────────────────────────────────────────────────────────────────────

class AssociateAlias(Base):
    """Known name variants for each associate for strict identity resolution."""
    __tablename__ = "associate_aliases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    associe_id = Column(String(36), ForeignKey("associes.id"), nullable=False)
    alias = Column(String(200), nullable=False, unique=True)
    source = Column(String(100), nullable=True)  # e.g. "import_excel_2024", "manuel"
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_alias_associe", "associe_id"),
    )
