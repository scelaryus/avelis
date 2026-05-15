"""GFI Platform — Treasury & Consolidation models.

New tables from Blueprint v6.0:
  - journaux               – Accounting journals per company
  - comptes_bancaires       – Company bank accounts
  - bulletins_paie          – Full payroll bulletin with D/ND
  - declarations_fiscales   – G50, IBS, DADS, TAP
  - echeancier_clients      – Client payment schedule with alerts
  - capital_associes        – Capital contributions by partner
  - retraits_associes       – Withdrawals by partner
  - consolidation_associes  – Monthly view per partner
  - consolidation_entreprises – Monthly view per company
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

class TypeJournal(str, enum.Enum):
    ACHAT = "ACHAT"
    VENTE = "VENTE"
    BANQUE = "BANQUE"
    CAISSE = "CAISSE"
    OD = "OD"


class StatutDeclaration(str, enum.Enum):
    BROUILLON = "BROUILLON"
    DEPOSE = "DEPOSE"
    VALIDE = "VALIDE"


class TypeDeclaration(str, enum.Enum):
    G50 = "G50"
    IBS = "IBS"
    DADS = "DADS"
    TAP = "TAP"


class StatutBulletinPaie(str, enum.Enum):
    BROUILLON = "BROUILLON"
    VALIDE = "VALIDE"
    APPROUVE = "APPROUVE"
    PAYE = "PAYE"


class StatutEcheance(str, enum.Enum):
    EN_ATTENTE = "EN_ATTENTE"
    PAYE = "PAYE"
    EN_RETARD = "EN_RETARD"


# ────────────────────────────────────────────────────────────────────────────
# Journaux Comptables (accounting journals per company)
# ────────────────────────────────────────────────────────────────────────────

class Journal(Base):
    """Accounting journals per company (Table #16)."""
    __tablename__ = "journaux"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    code = Column(String(20), nullable=False)
    libelle = Column(String(200), nullable=False)
    type_journal = Column(SAEnum(TypeJournal), default=TypeJournal.OD)
    actif = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("entreprise_id", "code", name="uq_journal_ent_code"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Comptes Bancaires (Table #20)
# ────────────────────────────────────────────────────────────────────────────

class CompteBancaire(Base):
    """Company bank accounts."""
    __tablename__ = "comptes_bancaires"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    banque = Column(String(100), nullable=False)
    agence = Column(String(200))
    numero_compte = Column(String(50))
    iban = Column(String(50))
    rib = Column(String(30))
    devise = Column(String(3), default="DZD")
    solde_actuel = Column(Numeric(18, 2), default=0)
    actif = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Bulletins de Paie (full payroll with D/ND — Table #28)
# ────────────────────────────────────────────────────────────────────────────

class BulletinPaie(Base):
    """Full payroll bulletin with declared/non-declared components."""
    __tablename__ = "bulletins_paie"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    employe_id = Column(String(36), ForeignKey("employees.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=True)
    mois = Column(Integer, nullable=False)
    annee = Column(Integer, nullable=False)

    # Declared part (RD)
    salaire_base = Column(Numeric(18, 2), nullable=False, default=0)
    heures_sup = Column(Numeric(18, 2), default=0)
    prime_rendement = Column(Numeric(18, 2), default=0)
    indemnites = Column(Numeric(18, 2), default=0)
    salaire_brut = Column(Numeric(18, 2), nullable=False, default=0)
    cnas_salarie = Column(Numeric(18, 2), nullable=False, default=0)  # 9%
    irg = Column(Numeric(18, 2), nullable=False, default=0)
    autres_retenues = Column(Numeric(18, 2), default=0)
    total_retenues = Column(Numeric(18, 2), nullable=False, default=0)
    salaire_net = Column(Numeric(18, 2), nullable=False, default=0)

    # Employer charges (RD)
    cnas_patronal = Column(Numeric(18, 2), nullable=False, default=0)  # 26%
    cacobatph = Column(Numeric(18, 2), default=0)  # 1.75% BTP
    cout_employeur_rd = Column(Numeric(18, 2), nullable=False, default=0)

    # Non-declared complement (RND)
    complement_nd = Column(Numeric(18, 2), default=0)
    salaire_reel_total = Column(Numeric(18, 2), default=0)  # net + complement_nd
    reference_fiche_caisse = Column(String(100))

    statut = Column(SAEnum(StatutBulletinPaie), default=StatutBulletinPaie.BROUILLON)
    est_test_fictif = Column(Boolean, default=False)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("employe_id", "annee", "mois", name="uq_bulletin_emp_mois"),
        CheckConstraint("mois >= 1 AND mois <= 12", name="ck_bulletin_mois"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Déclarations Fiscales (G50, IBS, etc. — Table #29)
# ────────────────────────────────────────────────────────────────────────────

class DeclarationFiscale(Base):
    """G50, IBS, DADS, TAP fiscal declarations."""
    __tablename__ = "declarations_fiscales"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    exercice_id = Column(String(36), ForeignKey("exercices.id"), nullable=False)
    type_declaration = Column(SAEnum(TypeDeclaration), nullable=False)
    mois = Column(Integer, nullable=True)
    annee = Column(Integer, nullable=False)
    montant_tva_collectee = Column(Numeric(18, 2), default=0)
    montant_tva_deductible = Column(Numeric(18, 2), default=0)
    montant_tva_a_payer = Column(Numeric(18, 2), default=0)
    montant_tap = Column(Numeric(18, 2), default=0)
    montant_irg_salaires = Column(Numeric(18, 2), default=0)
    montant_total = Column(Numeric(18, 2), nullable=False, default=0)
    date_depot = Column(Date)
    reference = Column(String(100))
    statut = Column(SAEnum(StatutDeclaration), default=StatutDeclaration.BROUILLON)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Échéancier Clients (Table #24)
# ────────────────────────────────────────────────────────────────────────────

class EcheancierClient(Base):
    """Client payment schedule with 30/60/90 day overdue alerts."""
    __tablename__ = "echeancier_clients"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    client_id = Column(String(36), ForeignKey("clients_cc.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    lot_id = Column(String(36), ForeignKey("lots.id"), nullable=True)
    numero_echeance = Column(Integer, nullable=False)
    montant = Column(Numeric(18, 2), nullable=False)
    date_prevue = Column(Date, nullable=False)
    date_paiement = Column(Date)
    statut = Column(SAEnum(StatutEcheance), default=StatutEcheance.EN_ATTENTE)
    jours_retard = Column(Integer, default=0)
    alerte_envoyee = Column(Boolean, default=False)
    encaissement_id = Column(String(36), ForeignKey("encaissements.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ────────────────────────────────────────────────────────────────────────────
# Capital Associés (Table #42)
# ────────────────────────────────────────────────────────────────────────────

class CapitalAssocie(Base):
    """Capital contributions by partner per project."""
    __tablename__ = "capital_associes"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    associe_id = Column(String(36), ForeignKey("associes.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    montant = Column(Numeric(18, 2), nullable=False)
    date_apport = Column(Date, nullable=False)
    description = Column(Text)
    reference = Column(String(100))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint("montant > 0", name="ck_capital_montant_positif"),
        Index("ix_capital_associe", "associe_id", "projet_id"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Retraits Associés (Table #43)
# ────────────────────────────────────────────────────────────────────────────

class RetraitAssocie(Base):
    """Partner withdrawal request with approval workflow (R-003)."""
    __tablename__ = "retraits_associes"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    associe_id = Column(String(36), ForeignKey("associes.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    montant = Column(Numeric(18, 2), nullable=False)
    date_retrait = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    reference = Column(String(100))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    # ── Approval workflow ──
    statut = Column(String(20), default="DEMANDE")  # DEMANDE, APPROUVE, REFUSE, BLOQUE
    motif_rejet = Column(Text)
    approuve_par = Column(String(36), ForeignKey("users.id"))
    date_decision = Column(DateTime)
    # ── R-003 blocking feedback snapshot ──
    solde_individuel = Column(Numeric(18, 2))  # CCA balance at request time
    max_autorise = Column(Numeric(18, 2))  # 50% of solde at request time
    solde_global_cca = Column(Numeric(18, 2))  # sum of all CCAs at request time
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        CheckConstraint("montant > 0", name="ck_retrait_montant_positif"),
        Index("ix_retrait_associe", "associe_id", "projet_id"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Consolidation par Associé (Table #34)
# ────────────────────────────────────────────────────────────────────────────

class ConsolidationAssocie(Base):
    """Monthly consolidated view per partner per project."""
    __tablename__ = "consolidation_associes"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    associe_id = Column(String(36), ForeignKey("associes.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    exercice_id = Column(String(36), ForeignKey("exercices.id"), nullable=True)
    mois = Column(Integer, nullable=False)
    annee = Column(Integer, nullable=False)
    pourcentage = Column(Numeric(8, 2), default=0)
    capital_verse = Column(Numeric(18, 2), default=0)
    retraits = Column(Numeric(18, 2), default=0)
    quote_part_recettes = Column(Numeric(18, 2), default=0)
    quote_part_depenses = Column(Numeric(18, 2), default=0)
    quote_part_resultat = Column(Numeric(18, 2), default=0)
    position_nette = Column(Numeric(18, 2), default=0)  # Capital - Retraits + QP résultat
    alerte_negative = Column(Boolean, default=False)  # 🔴 if position_nette < 0
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("associe_id", "projet_id", "annee", "mois",
                         name="uq_consol_associe_mois"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Consolidation par Entreprise (Table #35)
# ────────────────────────────────────────────────────────────────────────────

class ConsolidationEntreprise(Base):
    """Monthly consolidated view per company."""
    __tablename__ = "consolidation_entreprises"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    exercice_id = Column(String(36), ForeignKey("exercices.id"), nullable=True)
    mois = Column(Integer, nullable=False)
    annee = Column(Integer, nullable=False)
    total_recettes = Column(Numeric(18, 2), default=0)
    total_depenses = Column(Numeric(18, 2), default=0)
    total_resultat = Column(Numeric(18, 2), default=0)
    nombre_projets_actifs = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("entreprise_id", "annee", "mois",
                         name="uq_consol_ent_mois"),
    )
