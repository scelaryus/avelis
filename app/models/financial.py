"""GFI Platform — Financial domain models (Centre de Coût, D/ND/F).

Implements the full data model from docs/changment.md / Blueprint v6.0 Annexe C:
- StatutFiscal enum (RD / RND / F)
- Entreprise, Projet, Exercice
- Encaissements & Décaissements with D/ND/F
- Paramètres système
- Ratio charges communes
- Centre de coût mensuel (~30 columns)
- Imputation paie projets (multi-project payroll allocation)
- Mouvements caisse (cash register)
- Comptes transitoires notaires
- Mouvements stock
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

class RealiteFinanciere(str, enum.Enum):
    """GFI v7.0 — 4 financial realities. MUST be on every transaction."""
    RF1 = "RF1"  # Réel Déclaré
    RF2 = "RF2"  # Réel Non Déclaré
    RF3 = "RF3"  # Fictif Déclaré — triggers CFF automatically
    RF4 = "RF4"  # Fictif Non Déclaré


class StatutFiscal(str, enum.Enum):
    """Fiscal realities used by the app.

    Legacy `FD` and `FND` values remain accepted for backward compatibility,
    but new writes should use only `F`.
    """
    REEL_DECLARE = "REEL_DECLARE"           # RD
    REEL_NON_DECLARE = "REEL_NON_DECLARE"   # RND
    FICTIF = "FICTIF"                       # F
    FICTIF_DECLARE = "FICTIF_DECLARE"       # legacy FD
    FICTIF_NON_DECLARE = "FICTIF_NON_DECLARE"  # legacy FND


# ── RF ↔ StatutFiscal mapping ──
RF_TO_STATUT = {
    RealiteFinanciere.RF1: StatutFiscal.REEL_DECLARE,
    RealiteFinanciere.RF2: StatutFiscal.REEL_NON_DECLARE,
    RealiteFinanciere.RF3: StatutFiscal.FICTIF_DECLARE,
    RealiteFinanciere.RF4: StatutFiscal.FICTIF_NON_DECLARE,
}
STATUT_TO_RF = {
    StatutFiscal.REEL_DECLARE: RealiteFinanciere.RF1,
    StatutFiscal.REEL_NON_DECLARE: RealiteFinanciere.RF2,
    StatutFiscal.FICTIF: RealiteFinanciere.RF3,
    StatutFiscal.FICTIF_DECLARE: RealiteFinanciere.RF3,
    StatutFiscal.FICTIF_NON_DECLARE: RealiteFinanciere.RF4,
}


class CategorieDepense(str, enum.Enum):
    MATERIEL = "MATERIEL"
    SOUS_TRAITANCE = "SOUS_TRAITANCE"
    MAIN_OEUVRE = "MAIN_OEUVRE"
    ETUDES = "ETUDES"
    TRANSPORT = "TRANSPORT"
    ASSURANCE = "ASSURANCE"
    FRAIS_NOTAIRE = "FRAIS_NOTAIRE"
    CONTENTIEUX = "CONTENTIEUX"
    LOYER = "LOYER"
    FOURNITURES = "FOURNITURES"
    TELEPHONE = "TELEPHONE"
    HONORAIRES = "HONORAIRES"
    FRAIS_BANCAIRES = "FRAIS_BANCAIRES"
    MARKETING = "MARKETING"
    CARBURANT = "CARBURANT"
    GARDIENNAGE = "GARDIENNAGE"
    TAXE_G50 = "TAXE_G50"
    CNAS_CASNOS = "CNAS_CASNOS"
    AUTRE = "AUTRE"


class TypeCharge(str, enum.Enum):
    """Whether a charge is project-specific or common."""
    PROJET = "PROJET"    # CP — directly assigned to one project
    COMMUNE = "COMMUNE"  # CC — shared across projects


class SensOperation(str, enum.Enum):
    GAIN = "GAIN"
    PERTE = "PERTE"


class StatutProjet(str, enum.Enum):
    EN_PREPARATION = "EN_PREPARATION"
    ACTIF = "ACTIF"
    EN_PAUSE = "EN_PAUSE"
    ABANDONNE = "ABANDONNE"
    TERMINE = "TERMINE"


class StatutLot(str, enum.Enum):
    DISPONIBLE = "DISPONIBLE"
    RESERVE = "RESERVE"
    VENDU = "VENDU"
    LIVRE = "LIVRE"
    CONTENTIEUX = "CONTENTIEUX"


class SensCaisse(str, enum.Enum):
    ENTREE = "ENTREE"
    SORTIE = "SORTIE"


class TypeMouvementStock(str, enum.Enum):
    ENTREE = "ENTREE"
    SORTIE = "SORTIE"
    INVENTAIRE = "INVENTAIRE"


class MethodeRatio(str, enum.Enum):
    CA = "CA"
    DEPENSES = "DEPENSES"


# ────────────────────────────────────────────────────────────────────────────
# Entreprise
# ────────────────────────────────────────────────────────────────────────────

class Entreprise(Base):
    __tablename__ = "entreprises"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(20))  # e.g. ETS-DK, SARL-DP
    raison_sociale = Column(String(300), nullable=False)
    statut = Column(String(30), default="ACTIF")  # ACTIF, À FERMER, À DÉVELOPPER, DISSOUTE, SATELLITE
    role_principal = Column(String(200))  # e.g. "Promotion immobilière"
    nif = Column(String(50))
    rc = Column(String(50))
    nis = Column(String(50))
    ai = Column(String(50))
    adresse = Column(Text)
    telephone = Column(String(50))
    email = Column(String(255))
    logo_storage_key = Column(String(500))
    devise = Column(String(3), default="DZD")
    # ── GFI v7.0 fiscal identifiers ──
    taux_ibs = Column(Numeric(5, 4), default=0.19)
    taux_tap = Column(Numeric(5, 4), default=0.02)
    taux_tva = Column(Numeric(5, 4), default=0.19)
    capital_social = Column(Numeric(18, 2), default=0)
    forme_juridique = Column(String(50))  # SARL, EURL, SPA, etc.
    date_creation = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "raison_sociale", name="uq_ent_tenant_nom"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Exercice Comptable
# ────────────────────────────────────────────────────────────────────────────

class Exercice(Base):
    __tablename__ = "exercices"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    annee = Column(Integer, nullable=False)
    date_debut = Column(Date, nullable=False)
    date_fin = Column(Date, nullable=False)
    is_cloture = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("entreprise_id", "annee", name="uq_exercice_annee"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Projet
# ────────────────────────────────────────────────────────────────────────────

class Projet(Base):
    __tablename__ = "projets"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    code = Column(String(50), nullable=False)
    nom = Column(String(300), nullable=False)
    statut = Column(SAEnum(StatutProjet), default=StatutProjet.ACTIF)
    adresse = Column(Text)
    date_debut = Column(Date)
    date_fin_prevue = Column(Date)
    budget_previsionnel = Column(Numeric(18, 2), default=0)
    nombre_lots = Column(Integer, default=0)
    # ── GFI v7.0 extensions ──
    nb_clients_total = Column(Integer, default=0)
    est_abandonne = Column(Boolean, default=False)
    passif_residuel = Column(Numeric(18, 2), default=0)
    superficie_terrain = Column(Numeric(12, 2))
    commune = Column(String(200))
    wilaya = Column(String(200))
    type_projet = Column(String(100))  # IMMOBILIER, INFRASTRUCTURE, etc.
    maitre_ouvrage = Column(String(300))
    numero_permis_construire = Column(String(100))
    date_permis_construire = Column(Date)
    taux_avancement = Column(Numeric(5, 2), default=0)
    metadata_ = Column("metadata", JSON, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("entreprise_id", "code", name="uq_projet_code"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Lot (unit within a project)
# ────────────────────────────────────────────────────────────────────────────

class Lot(Base):
    __tablename__ = "lots"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    code = Column(String(50), nullable=False)  # e.g. B1-E1-L01
    type_bien = Column(String(20))  # F3, F4, local, etc.
    surface = Column(Numeric(10, 2))
    prix_vente = Column(Numeric(18, 2))
    statut = Column(SAEnum(StatutLot), default=StatutLot.DISPONIBLE)
    client_id = Column(String(36), ForeignKey("clients_cc.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("projet_id", "code", name="uq_lot_code"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Client (cost-center domain — separate from ADV Client)
# ────────────────────────────────────────────────────────────────────────────

class ClientCC(Base):
    __tablename__ = "clients_cc"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    nom = Column(String(300), nullable=False)
    prenom = Column(String(300))
    telephone = Column(String(50))
    email = Column(String(255))
    adresse = Column(Text)
    nif_client = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Fournisseur
# ────────────────────────────────────────────────────────────────────────────

class Fournisseur(Base):
    __tablename__ = "fournisseurs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(50), nullable=False)
    raison_sociale = Column(String(300), nullable=False)
    nif = Column(String(50))
    rc = Column(String(50))
    adresse = Column(Text)
    telephone = Column(String(50))
    email = Column(String(255))
    est_fictif = Column(Boolean, default=False)  # marks fictitious suppliers
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Encaissement (receipt of money — revenue)
# ────────────────────────────────────────────────────────────────────────────

class Encaissement(Base):
    __tablename__ = "encaissements"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"))  # NULL → not project-specific
    client_id = Column(String(36), ForeignKey("clients_cc.id"))
    date_encaissement = Column(Date, nullable=False)
    montant = Column(Numeric(18, 2), nullable=False)
    statut_fiscal = Column(SAEnum(StatutFiscal), nullable=False)
    moyen_paiement = Column(String(50))  # cheque, virement, especes
    reference = Column(String(200))
    banque = Column(String(100))
    description = Column(Text)
    lot_id = Column(String(36), ForeignKey("lots.id"))
    document_id = Column(String(36), ForeignKey("documents.id"))
    is_deleted = Column(Boolean, default=False)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_enc_projet_date", "projet_id", "date_encaissement"),
        Index("ix_enc_entreprise_fiscal", "entreprise_id", "statut_fiscal"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Decaissement (disbursement — expense)
# ────────────────────────────────────────────────────────────────────────────

class Decaissement(Base):
    __tablename__ = "decaissements"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"))  # NULL → charge commune
    fournisseur_id = Column(String(36), ForeignKey("fournisseurs.id"))
    date_decaissement = Column(Date, nullable=False)
    montant = Column(Numeric(18, 2), nullable=False)
    montant_ht = Column(Numeric(18, 2))
    montant_tva = Column(Numeric(18, 2))
    taux_tva = Column(Numeric(5, 2))
    statut_fiscal = Column(SAEnum(StatutFiscal), nullable=False)
    type_charge = Column(SAEnum(TypeCharge), nullable=False)  # PROJET or COMMUNE
    categorie_depense = Column(SAEnum(CategorieDepense), default=CategorieDepense.AUTRE)
    sens = Column(SAEnum(SensOperation))  # for CONTENTIEUX: GAIN or PERTE
    reference_facture = Column(String(200))
    description = Column(Text)
    moyen_paiement = Column(String(50))
    document_id = Column(String(36), ForeignKey("documents.id"))
    is_deleted = Column(Boolean, default=False)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_dec_projet_date", "projet_id", "date_decaissement"),
        Index("ix_dec_entreprise_fiscal", "entreprise_id", "statut_fiscal"),
        Index("ix_dec_type_charge", "entreprise_id", "type_charge"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Paramètres Système
# ────────────────────────────────────────────────────────────────────────────

class Parametre(Base):
    __tablename__ = "parametres"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    cle = Column(String(100), nullable=False)
    valeur = Column(String(500), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "cle", name="uq_param_cle"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Ratio Charges Communes (monthly common charge ratio per project)
# ────────────────────────────────────────────────────────────────────────────

class RatioChargesCommunes(Base):
    __tablename__ = "ratio_charges_communes"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    exercice_id = Column(String(36), ForeignKey("exercices.id"))
    mois = Column(Integer, nullable=False)
    annee = Column(Integer, nullable=False)
    methode = Column(SAEnum(MethodeRatio), nullable=False, default=MethodeRatio.CA)
    # detail per project stored as JSON: [{projet_id, projet_code, valeur_base, ratio_pct}]
    detail_projets = Column(JSON, nullable=False, default=[])
    total_base = Column(Numeric(18, 2), nullable=False, default=0)
    total_charges_communes = Column(Numeric(18, 2), nullable=False, default=0)
    somme_ratios = Column(Numeric(10, 4), nullable=False, default=0)
    hash_verification = Column(String(64))
    genere_automatiquement = Column(Boolean, default=True)
    valide_par = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("entreprise_id", "annee", "mois", name="uq_ratio_mois"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Centre de Coût Mensuel (the main monthly cost center table — ~30 cols)
# ────────────────────────────────────────────────────────────────────────────

class CentreCoutMensuel(Base):
    __tablename__ = "centre_cout_mensuel"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    exercice_id = Column(String(36), ForeignKey("exercices.id"))
    mois = Column(Integer, nullable=False)
    annee = Column(Integer, nullable=False)

    # — A. RECETTES —
    encaissements_rd = Column(Numeric(18, 2), nullable=False, default=0)
    encaissements_rnd = Column(Numeric(18, 2), nullable=False, default=0)
    gains_contentieux = Column(Numeric(18, 2), nullable=False, default=0)
    liberations_transit = Column(Numeric(18, 2), nullable=False, default=0)
    total_recettes = Column(Numeric(18, 2), nullable=False, default=0)

    # — B. DÉPENSES DIRECTES —
    decaissements_rd = Column(Numeric(18, 2), nullable=False, default=0)
    decaissements_rnd = Column(Numeric(18, 2), nullable=False, default=0)
    montant_nominal_fd = Column(Numeric(18, 2), nullable=False, default=0)
    cout_fictif_fd = Column(Numeric(18, 2), nullable=False, default=0)
    montant_nominal_fnd = Column(Numeric(18, 2), nullable=False, default=0)
    cout_fictif_fnd = Column(Numeric(18, 2), nullable=False, default=0)
    pertes_contentieux = Column(Numeric(18, 2), nullable=False, default=0)
    stock_consomme_cump = Column(Numeric(18, 2), nullable=False, default=0)
    masse_salariale_directe = Column(Numeric(18, 2), nullable=False, default=0)
    total_depenses_directes = Column(Numeric(18, 2), nullable=False, default=0)

    # — C. CHARGES COMMUNES —
    ratio_pct = Column(Numeric(10, 4), nullable=False, default=0)
    charges_communes_montant = Column(Numeric(18, 2), nullable=False, default=0)

    # — D. TOTAUX —
    total_depenses = Column(Numeric(18, 2), nullable=False, default=0)
    resultat_ultra_reel = Column(Numeric(18, 2), nullable=False, default=0)
    resultat_fiscal = Column(Numeric(18, 2), nullable=False, default=0)

    # — E. INDICATEURS —
    marge_brute_pct = Column(Numeric(10, 2))
    ratio_cc_depenses_pct = Column(Numeric(10, 2))
    part_non_declare_pct = Column(Numeric(10, 2))
    montant_transit_notaire = Column(Numeric(18, 2), nullable=False, default=0)
    reste_a_payer_clients = Column(Numeric(18, 2), nullable=False, default=0)

    # — Vérification —
    hash_verification = Column(String(64))
    est_test_fictif = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("projet_id", "annee", "mois", name="uq_cc_projet_mois"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Imputation Paie Projets (multi-project payroll allocation)
# ────────────────────────────────────────────────────────────────────────────

class ImputationPaieProjet(Base):
    __tablename__ = "imputation_paie_projets"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    bulletin_id = Column(String(36), ForeignKey("payroll_proposals.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    pourcentage = Column(Numeric(8, 2), nullable=False)
    montant_impute_rd = Column(Numeric(18, 2), nullable=False, default=0)
    montant_impute_rnd = Column(Numeric(18, 2), nullable=False, default=0)
    montant_impute_total = Column(Numeric(18, 2), nullable=False, default=0)
    cnas_patronal_impute = Column(Numeric(18, 2), nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("bulletin_id", "projet_id", name="uq_imputation_bulletin_projet"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Mouvements Caisse (cash register movements)
# ────────────────────────────────────────────────────────────────────────────

class MouvementCaisse(Base):
    __tablename__ = "mouvements_caisse"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"))
    date_mouvement = Column(Date, nullable=False)
    sens = Column(SAEnum(SensCaisse), nullable=False)
    montant = Column(Numeric(18, 2), nullable=False)
    motif = Column(Text, nullable=False)
    beneficiaire = Column(String(300))
    reference_fiche = Column(String(100), nullable=False)
    bulletin_paie_id = Column(String(36), ForeignKey("payroll_proposals.id"))
    decaissement_id = Column(String(36), ForeignKey("decaissements.id"))
    encaissement_id = Column(String(36), ForeignKey("encaissements.id"))
    solde_avant = Column(Numeric(18, 2))
    solde_apres = Column(Numeric(18, 2))
    statut_fiscal = Column(SAEnum(StatutFiscal), nullable=False)
    document_id = Column(String(36), ForeignKey("documents.id"))
    est_test_fictif = Column(Boolean, default=False)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Comptes Transitoires Notaires
# ────────────────────────────────────────────────────────────────────────────

class CompteTransitoireNotaire(Base):
    __tablename__ = "comptes_transitoires_notaires"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    client_id = Column(String(36), ForeignKey("clients_cc.id"))
    lot_id = Column(String(36), ForeignKey("lots.id"))
    notaire_nom = Column(String(300), nullable=False)
    montant_total = Column(Numeric(18, 2), nullable=False)
    montant_tranche1_20pct = Column(Numeric(18, 2), nullable=False, default=0)
    montant_tranche2_5pct = Column(Numeric(18, 2), nullable=False, default=0)
    montant_direct_75pct = Column(Numeric(18, 2), nullable=False, default=0)
    statut = Column(String(50), default="EN_ATTENTE")
    # VEFA_SIGNE_20PCT_LIBERE, PV_SIGNE_5PCT_LIBERE, CLOTURE
    date_acte = Column(Date)
    date_liberation_tranche1 = Column(Date)
    date_liberation_tranche2 = Column(Date)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Stock (articles + movements for CUMP valuation)
# ────────────────────────────────────────────────────────────────────────────

class ArticleStock(Base):
    __tablename__ = "articles_stock"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    code = Column(String(50), nullable=False)
    designation = Column(String(300), nullable=False)
    unite = Column(String(50), default="unité")
    quantite_stock = Column(Numeric(18, 4), nullable=False, default=0)
    cump = Column(Numeric(18, 4), nullable=False, default=0)  # weighted avg unit cost
    valeur_stock = Column(Numeric(18, 2), nullable=False, default=0)
    seuil_alerte = Column(Numeric(18, 4), default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("entreprise_id", "code", name="uq_article_code"),
    )


class MouvementStock(Base):
    __tablename__ = "mouvements_stock"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    article_id = Column(String(36), ForeignKey("articles_stock.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"))
    date_mouvement = Column(Date, nullable=False)
    type_mouvement = Column(SAEnum(TypeMouvementStock), nullable=False)
    quantite = Column(Numeric(18, 4), nullable=False)
    prix_unitaire = Column(Numeric(18, 4), nullable=False)
    cump_apres = Column(Numeric(18, 4))
    stock_apres = Column(Numeric(18, 4))
    reference = Column(String(200))
    document_id = Column(String(36), ForeignKey("documents.id"))
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_mvt_stock_projet_date", "projet_id", "date_mouvement"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Enriched PayrollProposal fields (D/ND complement)
# These are added to the existing hr.py PayrollProposal via mixin-style columns
# We add them here as a separate overlay table to avoid breaking existing model
# ────────────────────────────────────────────────────────────────────────────

class BulletinPaieComplement(Base):
    """Extension table for undeclared payroll complement (RND)."""
    __tablename__ = "bulletin_paie_complements"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    bulletin_id = Column(String(36), ForeignKey("payroll_proposals.id"), nullable=False, unique=True)
    complement_nd = Column(Numeric(18, 2), nullable=False, default=0)
    salaire_reel_total = Column(Numeric(18, 2), nullable=False, default=0)
    reference_fiche_caisse = Column(String(100))
    projet_id = Column(String(36), ForeignKey("projets.id"))  # if mono-project
    # Charges patronales
    cnas_patronal = Column(Numeric(18, 2), default=0)
    cacobatph = Column(Numeric(18, 2), default=0)
    cout_employeur_rd = Column(Numeric(18, 2), default=0)
    # Breakdown
    salaire_brut = Column(Numeric(18, 2), default=0)
    cnas_salarie = Column(Numeric(18, 2), default=0)
    irg = Column(Numeric(18, 2), default=0)
    salaire_net_rd = Column(Numeric(18, 2), default=0)
    created_at = Column(DateTime, server_default=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Associé (partner/shareholder)
# ────────────────────────────────────────────────────────────────────────────

class Associe(Base):
    __tablename__ = "associes"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    nom = Column(String(300), nullable=False)
    prenom = Column(String(300))
    part_pct = Column(Numeric(8, 2), nullable=False)  # ownership share %
    capital_apporte = Column(Numeric(18, 2), default=0)
    retraits_cumules = Column(Numeric(18, 2), default=0)
    # ── GFI v7.0 extensions ──
    nin = Column(String(20), unique=True)  # National ID Number
    est_fondateur = Column(Boolean, default=False)
    ordre_priorite = Column(String(10))  # A-I hierarchical order
    date_naissance = Column(Date)
    lieu_naissance = Column(String(200))
    adresse = Column(Text)
    telephone = Column(String(50))
    email = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


# ────────────────────────────────────────────────────────────────────────────
# EntrepriseAssocie — % ownership in ENTERPRISE (not project!)
# Critical: CFF uses enterprise %, never project %
# ────────────────────────────────────────────────────────────────────────────

class EntrepriseAssocie(Base):
    """Participation of an associate in an enterprise (% entreprise)."""
    __tablename__ = "entreprise_associes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    associe_id = Column(String(36), ForeignKey("associes.id"), nullable=False)
    pourcentage = Column(Numeric(6, 4), nullable=False)  # % in the enterprise
    date_entree = Column(Date)
    date_sortie = Column(Date)
    est_actif = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("entreprise_id", "associe_id", name="uq_ent_assoc"),
        Index("ix_ent_assoc_entreprise", "entreprise_id"),
    )


# ────────────────────────────────────────────────────────────────────────────
# OrigineCapitalDetail — traces each capital contribution with RF
# ────────────────────────────────────────────────────────────────────────────

class OrigineCapitalDetail(Base):
    """Detail of capital origin with financial reality tag."""
    __tablename__ = "origine_capital_detail"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    associe_id = Column(String(36), ForeignKey("associes.id"), nullable=False)
    realite_financiere = Column(String(4))  # RF1-RF4
    montant = Column(Numeric(18, 2), nullable=False)
    document_reference = Column(String(300))
    description = Column(Text)
    date_apport = Column(Date)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_origine_capital_entreprise", "entreprise_id"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Transaction — every financial movement with MANDATORY RF1-RF4
# ────────────────────────────────────────────────────────────────────────────

class TypeTransaction(str, enum.Enum):
    ENCAISSEMENT = "ENCAISSEMENT"
    DECAISSEMENT = "DECAISSEMENT"
    VIREMENT_INTERNE = "VIREMENT_INTERNE"
    COMPENSATION = "COMPENSATION"
    AJUSTEMENT = "AJUSTEMENT"


class Transaction(Base):
    """Financial transaction with mandatory realite_financiere (RF1-RF4)."""
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"))
    realite_financiere = Column(SAEnum(RealiteFinanciere), nullable=False)
    type_transaction = Column(SAEnum(TypeTransaction), nullable=False)
    montant = Column(Numeric(18, 2), nullable=False)
    date_transaction = Column(Date, nullable=False)
    description = Column(Text)
    reference = Column(String(200))
    compte_debit = Column(String(20))
    compte_credit = Column(String(20))
    hash_sha256 = Column(String(64))
    document_id = Column(String(36), ForeignKey("documents.id"))
    created_by = Column(String(36), ForeignKey("users.id"))
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_txn_entreprise_rf", "entreprise_id", "realite_financiere"),
        Index("ix_txn_projet_date", "projet_id", "date_transaction"),
    )


# ────────────────────────────────────────────────────────────────────────────
# FluxInterProjet — inter-project flows with RF
# ────────────────────────────────────────────────────────────────────────────

class NatureFlux(str, enum.Enum):
    PRET_REMBOURSABLE = "PRET_REMBOURSABLE"
    AVANCE_TRESORERIE = "AVANCE_TRESORERIE"
    TRANSFERT_DEFINITIF = "TRANSFERT_DEFINITIF"
    REFACTURATION = "REFACTURATION"


class FluxInterProjet(Base):
    """Inter-project financial flow with RF1-RF4."""
    __tablename__ = "flux_inter_projets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_source_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    projet_destination_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    realite_financiere = Column(SAEnum(RealiteFinanciere), nullable=False)
    nature = Column(SAEnum(NatureFlux), nullable=False)
    montant = Column(Numeric(18, 2), nullable=False)
    solde_restant = Column(Numeric(18, 2), default=0)
    source_externe = Column(Boolean, default=False)
    date_flux = Column(Date, nullable=False)
    description = Column(Text)
    document_id = Column(String(36), ForeignKey("documents.id"))
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_flux_source", "projet_source_id"),
        Index("ix_flux_dest", "projet_destination_id"),
    )


# ────────────────────────────────────────────────────────────────────────────
# CompensationST — sub-contractor compensation (KT-05: no cash 512)
# ────────────────────────────────────────────────────────────────────────────

class CompensationST(Base):
    """Sub-contractor compensation — KT-05: sortie_cash_512 must be FALSE for material advances."""
    __tablename__ = "compensations_st"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    sous_traitant_id = Column(String(36), ForeignKey("fournisseurs.id"))
    realite_financiere = Column(SAEnum(RealiteFinanciere), nullable=False)
    montant = Column(Numeric(18, 2), nullable=False)
    type_ecriture = Column(String(50))
    compte_debit = Column(String(20))
    compte_credit = Column(String(20))
    sortie_cash_512 = Column(Boolean, default=False)  # KT-05: must be FALSE for material advances
    est_avance_materiel = Column(Boolean, default=False)
    description = Column(Text)
    date_compensation = Column(Date, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "NOT (est_avance_materiel = 1 AND sortie_cash_512 = 1)",
            name="ck_kt05_no_cash_512_material"
        ),
    )


# ────────────────────────────────────────────────────────────────────────────
# ClotureMensuelleRepartition — normalized distribution table
# ────────────────────────────────────────────────────────────────────────────

class ClotureMensuelleRepartition(Base):
    """Individual distribution line for a monthly closing."""
    __tablename__ = "clotures_mensuelles_repartitions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cloture_id = Column(String(36), ForeignKey("clotures_mensuelles.id"), nullable=False)
    associe_id = Column(String(36), ForeignKey("associes.id"), nullable=False)
    pourcentage = Column(Numeric(6, 4), nullable=False)
    montant = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("cloture_id", "associe_id", name="uq_repartition_cloture_assoc"),
    )


# ────────────────────────────────────────────────────────────────────────────
# VehiculeGroupe — full lifecycle: buy → register → cede → deduct → resell
# ────────────────────────────────────────────────────────────────────────────

class StatutVehicule(str, enum.Enum):
    EN_SERVICE = "EN_SERVICE"
    CEDE_ST = "CEDE_ST"
    EN_DEDUCTION = "EN_DEDUCTION"
    REVENDU = "REVENDU"
    REFORME = "REFORME"


class VehiculeGroupe(Base):
    """Group vehicle with full lifecycle tracking."""
    __tablename__ = "vehicules_groupe"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    immatriculation = Column(String(50), nullable=False, unique=True)
    marque = Column(String(100))
    modele = Column(String(100))
    date_acquisition = Column(Date, nullable=False)
    prix_acquisition = Column(Numeric(18, 2), nullable=False)
    statut = Column(SAEnum(StatutVehicule), default=StatutVehicule.EN_SERVICE)
    cede_a_st_id = Column(String(36), ForeignKey("fournisseurs.id"))
    date_cession_st = Column(Date)
    montant_cession_st = Column(Numeric(18, 2))
    situation_deduction_id = Column(String(36))
    montant_deduit = Column(Numeric(18, 2), default=0)
    date_debut_deduction = Column(Date)
    date_fin_deduction = Column(Date)
    prix_revente = Column(Numeric(18, 2))
    date_revente = Column(Date)
    acheteur_revente = Column(String(300))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
