"""GFI v7.0 — Juridique & Moyens Généraux models.

Tables:
  - dossiers_juridiques: legal dossiers with succession flag (FC-002)
  - permis_autorisations: permits and authorizations
  - fournisseurs_v7: extended suppliers with GACEB flag
  - commandes_achats: purchase orders with RF + material advance flag (KT-05)
  - stock_materiel: material stock tracking
"""
import uuid
import enum
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, Date,
    ForeignKey, Enum as SAEnum, Numeric, Index, UniqueConstraint, func,
)
from app.database import Base


# ────────────────────────────────────────────────────────────────────────────
# DossierJuridique
# ────────────────────────────────────────────────────────────────────────────

class StatutDossierJuridique(str, enum.Enum):
    OUVERT = "OUVERT"
    EN_COURS = "EN_COURS"
    CLOS = "CLOS"
    ARCHIVE = "ARCHIVE"


class DossierJuridique(Base):
    """Legal dossier — est_succession flag for FC-002."""
    __tablename__ = "dossiers_juridiques"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"))
    projet_id = Column(String(36), ForeignKey("projets.id"))
    reference = Column(String(100), unique=True)
    titre = Column(String(500), nullable=False)
    description = Column(Text)
    type_dossier = Column(String(100))  # CONTENTIEUX, SUCCESSION, RECOUVREMENT, etc.
    est_succession = Column(Boolean, default=False)  # FC-002
    partie_adverse = Column(String(300))
    tribunal = Column(String(300))
    montant_litige = Column(Numeric(18, 2))
    statut = Column(SAEnum(StatutDossierJuridique), default=StatutDossierJuridique.OUVERT)
    date_ouverture = Column(Date)
    date_cloture = Column(Date)
    avocat_responsable = Column(String(300))
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ────────────────────────────────────────────────────────────────────────────
# PermisAutorisation
# ────────────────────────────────────────────────────────────────────────────

class PermisAutorisation(Base):
    """Permits and authorizations with expiration tracking."""
    __tablename__ = "permis_autorisations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"))
    projet_id = Column(String(36), ForeignKey("projets.id"))
    type_permis = Column(String(100), nullable=False)  # CONSTRUIRE, CONFORMITE, HABITER, etc.
    numero = Column(String(100))
    date_delivrance = Column(Date)
    date_expiration = Column(Date)
    autorite_delivrance = Column(String(300))
    est_valide = Column(Boolean, default=True)
    document_id = Column(String(36), ForeignKey("documents.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ────────────────────────────────────────────────────────────────────────────
# CommandeAchat — with RF + est_avance_materiel (KT-05)
# ────────────────────────────────────────────────────────────────────────────

class StatutCommande(str, enum.Enum):
    BROUILLON = "BROUILLON"
    VALIDEE = "VALIDEE"
    EN_COURS = "EN_COURS"
    LIVREE = "LIVREE"
    ANNULEE = "ANNULEE"


class CommandeAchat(Base):
    """Purchase order with RF tag and material advance flag for KT-05."""
    __tablename__ = "commandes_achats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"))
    fournisseur_id = Column(String(36), ForeignKey("fournisseurs.id"))
    reference = Column(String(100))
    realite_financiere = Column(String(4))  # RF1-RF4
    montant_ht = Column(Numeric(18, 2), nullable=False)
    montant_tva = Column(Numeric(18, 2), default=0)
    montant_ttc = Column(Numeric(18, 2))
    est_avance_materiel = Column(Boolean, default=False)  # KT-05: no cash 512 outflow
    statut = Column(SAEnum(StatutCommande), default=StatutCommande.BROUILLON)
    date_commande = Column(Date, nullable=False)
    date_livraison_prevue = Column(Date)
    date_livraison_effective = Column(Date)
    description = Column(Text)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ────────────────────────────────────────────────────────────────────────────
# StockMateriel
# ────────────────────────────────────────────────────────────────────────────

class StockMateriel(Base):
    """Material stock tracking."""
    __tablename__ = "stock_materiel"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    code_article = Column(String(50), nullable=False)
    designation = Column(String(300), nullable=False)
    unite = Column(String(50), default="unité")
    quantite = Column(Numeric(18, 4), nullable=False, default=0)
    valeur_unitaire = Column(Numeric(18, 4), nullable=False, default=0)
    valeur_totale = Column(Numeric(18, 2), default=0)
    emplacement = Column(String(200))
    seuil_alerte = Column(Numeric(18, 4), default=0)
    est_actif = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("entreprise_id", "code_article", name="uq_stock_materiel_code"),
    )


# ════════════════════════════════════════════════════════════════════════════
# Section 11 — Cycle d'approvisionnement complet (EX-ACH-001)
# ════════════════════════════════════════════════════════════════════════════

class StatutDemande(str, enum.Enum):
    BROUILLON = "BROUILLON"
    SOUMISE = "SOUMISE"
    APPROUVEE = "APPROUVEE"
    REJETEE = "REJETEE"
    ANNULEE = "ANNULEE"


class DemandeAchat(Base):
    """Purchase requisition — first step of procurement cycle (EX-ACH-001)."""
    __tablename__ = "demandes_achat"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"))
    reference = Column(String(100), nullable=False)
    objet = Column(String(500), nullable=False)
    description = Column(Text)
    montant_estime = Column(Numeric(18, 2), default=0)
    urgence = Column(String(20), default="NORMALE")  # NORMALE, URGENTE, CRITIQUE
    statut = Column(SAEnum(StatutDemande), default=StatutDemande.BROUILLON)
    # Maker/Checker (Socle S-08)
    demandeur_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    approbateur_id = Column(String(36), ForeignKey("users.id"))
    date_demande = Column(Date, nullable=False)
    date_approbation = Column(Date)
    motif_rejet = Column(Text)
    document_id = Column(String(36), ForeignKey("documents.id"))
    created_at = Column(DateTime, server_default=func.now())


class LigneDemandeAchat(Base):
    """Line item in a purchase requisition."""
    __tablename__ = "lignes_demande_achat"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    demande_id = Column(String(36), ForeignKey("demandes_achat.id"), nullable=False)
    designation = Column(String(300), nullable=False)
    quantite = Column(Numeric(18, 4), nullable=False)
    unite = Column(String(50), default="unité")
    prix_unitaire_estime = Column(Numeric(18, 2), default=0)
    montant_estime = Column(Numeric(18, 2), default=0)


class BonReception(Base):
    """Goods receipt note — validates received goods vs ordered (EX-ACH-001)."""
    __tablename__ = "bons_reception"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"))
    commande_id = Column(String(36), ForeignKey("commandes_achats.id"))
    reference = Column(String(100), nullable=False)
    date_reception = Column(Date, nullable=False)
    fournisseur_id = Column(String(36), ForeignKey("fournisseurs.id"))
    # Quantities
    quantite_commandee = Column(Numeric(18, 4), default=0)
    quantite_recue = Column(Numeric(18, 4), default=0)
    quantite_conforme = Column(Numeric(18, 4), default=0)
    quantite_rejetee = Column(Numeric(18, 4), default=0)
    # Status
    statut = Column(String(20), default="EN_ATTENTE")  # EN_ATTENTE, CONFORME, PARTIEL, REJETE
    observations = Column(Text)
    receptionnaire_id = Column(String(36), ForeignKey("users.id"))
    # Warehouse
    entrepot_id = Column(String(36), ForeignKey("entrepots.id"))
    document_id = Column(String(36), ForeignKey("documents.id"))
    created_at = Column(DateTime, server_default=func.now())


class FactureFournisseur(Base):
    """Supplier invoice — matches PO + receipt for 3-way matching (EX-ACH-001)."""
    __tablename__ = "factures_fournisseur"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    fournisseur_id = Column(String(36), ForeignKey("fournisseurs.id"), nullable=False)
    commande_id = Column(String(36), ForeignKey("commandes_achats.id"))
    reception_id = Column(String(36), ForeignKey("bons_reception.id"))
    reference_facture = Column(String(100), nullable=False)
    date_facture = Column(Date, nullable=False)
    date_echeance = Column(Date)
    montant_ht = Column(Numeric(18, 2), nullable=False)
    montant_tva = Column(Numeric(18, 2), default=0)
    montant_ttc = Column(Numeric(18, 2), default=0)
    realite_financiere = Column(String(4), default="RF1")
    statut = Column(String(20), default="A_VALIDER")  # A_VALIDER, VALIDEE, PAYEE, LITIGE
    # Matching
    ecart_montant = Column(Numeric(18, 2), default=0)  # vs PO
    ecart_quantite = Column(Numeric(18, 4), default=0)  # vs reception
    # Maker/Checker
    validee_par = Column(String(36), ForeignKey("users.id"))
    date_validation = Column(DateTime)
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id"))
    document_id = Column(String(36), ForeignKey("documents.id"))
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())


# ════════════════════════════════════════════════════════════════════════════
# Section 11 — Multi-entrepôt (EX-ACH-002)
# ════════════════════════════════════════════════════════════════════════════

class Entrepot(Base):
    """Warehouse / storage location (EX-ACH-002)."""
    __tablename__ = "entrepots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(50), nullable=False)
    designation = Column(String(300), nullable=False)
    adresse = Column(Text)
    projet_id = Column(String(36), ForeignKey("projets.id"))
    responsable_id = Column(String(36), ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
