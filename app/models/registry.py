"""GFI Platform — Registry & Real Estate models.

New tables from Blueprint v6.0:
  - notaires                    – Notary directory
  - banques_partenaires         – Partner banks
  - projet_notaires             – Project ↔ Notary assignments
  - projet_banques              – Project ↔ Bank assignments
  - parts_projets               – Ownership shares per project per partner
  - mutations_foncieres         – Land mutation chains
  - lots_immobiliers            – Full real estate EDD stock (Bloc/Étage/Lot)
  - projet_entreprise_historique – Project ownership transitions (OPERA)
  - dossiers_fictifs_reference   – Fictitious test reference data
"""
import uuid

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, Date,
    ForeignKey, Enum as SAEnum, JSON, Numeric, UniqueConstraint, Index,
    CheckConstraint, func,
)
from app.database import Base
import enum


# ────────────────────────────────────────────────────────────────────────────
# Enums
# ────────────────────────────────────────────────────────────────────────────

class TypeMutation(str, enum.Enum):
    PROPRIETE_INITIALE = "PROPRIETE_INITIALE"
    ECHANGE = "ECHANGE"
    DONATION = "DONATION"
    VENTE = "VENTE"
    ACHAT = "ACHAT"
    DESISTEMENT = "DESISTEMENT"


class TypeCedant(str, enum.Enum):
    ENTREPRISE = "ENTREPRISE"
    ASSOCIE = "ASSOCIE"
    TIERS = "TIERS"


class StatutLotImmo(str, enum.Enum):
    DISPONIBLE = "DISPONIBLE"
    RESERVE = "RESERVE"
    VENDU = "VENDU"
    LIVRE = "LIVRE"
    LITIGE = "LITIGE"


class TypeBien(str, enum.Enum):
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    LOCAL_COMMERCIAL = "LOCAL_COMMERCIAL"
    PARKING = "PARKING"
    DUPLEX = "DUPLEX"
    AUTRE = "AUTRE"


class TypeTransition(str, enum.Enum):
    DONATION = "DONATION"
    CESSION = "CESSION"
    CREATION = "CREATION"


class StatutDossierFictif(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"


# ────────────────────────────────────────────────────────────────────────────
# Notaires (Table #37)
# ────────────────────────────────────────────────────────────────────────────

class Notaire(Base):
    """Notary directory."""
    __tablename__ = "notaires"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    nom = Column(String(200), nullable=False)
    prenom = Column(String(200))
    titre = Column(String(50), default="Maître")
    adresse = Column(Text)
    telephone = Column(String(50))
    email = Column(String(200))
    actif = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Banques Partenaires (Table #38)
# ────────────────────────────────────────────────────────────────────────────

class BanquePartenaire(Base):
    """Partner banks directory."""
    __tablename__ = "banques_partenaires"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(20), nullable=False)
    nom_banque = Column(String(200), nullable=False)
    agence = Column(String(200))
    adresse = Column(Text)
    telephone = Column(String(50))
    actif = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_banque_code"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Projet ↔ Notaire (Table #40)
# ────────────────────────────────────────────────────────────────────────────

class ProjetNotaire(Base):
    """Dynamic project ↔ notary assignment."""
    __tablename__ = "projet_notaires"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    notaire_id = Column(String(36), ForeignKey("notaires.id"), nullable=False)
    date_debut = Column(Date)
    date_fin = Column(Date)
    actif = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("projet_id", "notaire_id", name="uq_projet_notaire"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Projet ↔ Banque (Table #41)
# ────────────────────────────────────────────────────────────────────────────

class ProjetBanque(Base):
    """Dynamic project ↔ bank assignment."""
    __tablename__ = "projet_banques"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    banque_id = Column(String(36), ForeignKey("banques_partenaires.id"), nullable=False)
    date_debut = Column(Date)
    date_fin = Column(Date)
    actif = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("projet_id", "banque_id", name="uq_projet_banque"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Parts Projets (Table #8)
# ────────────────────────────────────────────────────────────────────────────

class PartProjet(Base):
    """Ownership shares per project per partner. Sum per project must = 100%."""
    __tablename__ = "parts_projets"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    associe_id = Column(String(36), ForeignKey("associes.id"), nullable=False)
    pourcentage = Column(Numeric(8, 2), nullable=False)
    montant_apport = Column(Numeric(18, 2), default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("projet_id", "associe_id", name="uq_part_projet_associe"),
        CheckConstraint("pourcentage > 0 AND pourcentage <= 100",
                         name="ck_part_pct_range"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Mutations Foncières (Table #9)
# ────────────────────────────────────────────────────────────────────────────

class MutationFonciere(Base):
    """Land mutation chains with polymorphic cedant/cessionnaire."""
    __tablename__ = "mutations_foncieres"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    type_mutation = Column(SAEnum(TypeMutation), nullable=False)
    cedant_id = Column(String(36))  # polymorphic FK
    cedant_type = Column(SAEnum(TypeCedant))
    cessionnaire_id = Column(String(36))  # polymorphic FK
    cessionnaire_type = Column(SAEnum(TypeCedant))
    date_mutation = Column(Date)
    montant = Column(Numeric(18, 2))
    reference_acte = Column(String(100))
    description = Column(Text)
    ordre = Column(Integer, default=0)  # position in chain
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_mutation_projet", "projet_id", "ordre"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Lots Immobiliers — Full EDD stock (Table #44)
# ────────────────────────────────────────────────────────────────────────────

class LotImmobilier(Base):
    """Real estate EDD inventory: Projet/Bloc/Étage/Lot."""
    __tablename__ = "lots_immobiliers"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    bloc = Column(String(10), nullable=False)
    etage = Column(String(10), nullable=False)
    numero_lot = Column(String(20), nullable=False)
    type_bien = Column(SAEnum(TypeBien), nullable=False)
    surface = Column(Numeric(10, 2), nullable=False)
    prix = Column(Numeric(18, 2), nullable=False, default=0)
    statut = Column(SAEnum(StatutLotImmo), default=StatutLotImmo.DISPONIBLE)
    client_id = Column(String(36), ForeignKey("clients_cc.id"), nullable=True)
    date_reservation = Column(Date)
    date_vente = Column(Date)
    date_livraison = Column(Date)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("projet_id", "bloc", "etage", "numero_lot",
                         name="uq_lot_immo"),
        CheckConstraint("surface > 0", name="ck_lot_surface_pos"),
        CheckConstraint("prix >= 0", name="ck_lot_prix_pos"),
        Index("ix_lot_statut", "projet_id", "statut"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Projet Entreprise Historique — OPERA transitions (Table #46)
# ────────────────────────────────────────────────────────────────────────────

class ProjetEntrepriseHistorique(Base):
    """Project ownership transition history (e.g. ETS-DK → SARL-DP)."""
    __tablename__ = "projet_entreprise_historique"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    date_debut = Column(Date, nullable=False)
    date_fin = Column(Date, nullable=True)  # NULL = still active
    type_transition = Column(SAEnum(TypeTransition), nullable=True)
    reference_acte = Column(String(100))
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("projet_id", "entreprise_id", "date_debut",
                         name="uq_proj_ent_hist"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Dossiers Fictifs Référence (Table #45)
# ────────────────────────────────────────────────────────────────────────────

class DossierFictifReference(Base):
    """Reference data for fictitious test scenarios."""
    __tablename__ = "dossiers_fictifs_reference"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    description = Column(Text, nullable=False)
    donnees_entree = Column(JSON, nullable=False, default={})
    resultats_attendus = Column(JSON, nullable=False, default={})
    derniere_execution = Column(DateTime, nullable=True)
    dernier_resultat = Column(JSON, nullable=True)
    dernier_statut = Column(SAEnum(StatutDossierFictif), nullable=True)
    ecart_detecte = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
