"""GFI Platform — Gestion de Projets & Chantiers (Section 10).

Models:
  - TacheChantier: planning tasks with % avancement
  - SousTraitant: subcontractor with performance scoring
  - SituationTravaux: work progress reports (triggers debt + cost center charge)
  - RapportExpert: expert reports for VSP fund releases
"""
import uuid
import enum
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, Date,
    ForeignKey, Enum as SAEnum, Numeric, JSON, func, CheckConstraint, Index,
)
from app.database import Base


class StatutTache(str, enum.Enum):
    A_FAIRE = "A_FAIRE"
    EN_COURS = "EN_COURS"
    TERMINE = "TERMINE"
    BLOQUE = "BLOQUE"
    ANNULE = "ANNULE"


class StatutSituation(str, enum.Enum):
    BROUILLON = "BROUILLON"
    SOUMISE = "SOUMISE"
    VALIDEE = "VALIDEE"
    REJETEE = "REJETEE"
    PAYEE = "PAYEE"


# ── Planning tasks (EX-PROJ-101) ──────────────────────────────────────────

class TacheChantier(Base):
    """Project planning task with physical progress tracking.

    EX-PROJ-101: Chiefs update task advancement (%).
    This advancement drives VSP fund releases.
    """
    __tablename__ = "taches_chantier"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=True)

    code = Column(String(50), nullable=False)
    libelle = Column(String(500), nullable=False)
    description = Column(Text)
    categorie = Column(String(100))  # GROS_OEUVRE, SECOND_OEUVRE, VRD, etc.
    lot_concerne = Column(String(100))  # which lot/block this task covers

    # Planning
    date_debut_prevue = Column(Date)
    date_fin_prevue = Column(Date)
    date_debut_reelle = Column(Date)
    date_fin_reelle = Column(Date)
    duree_prevue_jours = Column(Integer)

    # Progress
    avancement_pct = Column(Numeric(5, 2), default=0)  # 0-100%
    statut = Column(SAEnum(StatutTache), default=StatutTache.A_FAIRE)

    # Assignment
    responsable_id = Column(String(36), ForeignKey("employees.id"))
    sous_traitant_id = Column(String(36), ForeignKey("sous_traitants.id"))

    # Dependencies
    tache_parent_id = Column(String(36), ForeignKey("taches_chantier.id"))
    ordre = Column(Integer, default=0)

    # Cost
    budget_prevu = Column(Numeric(18, 2), default=0)
    cout_reel = Column(Numeric(18, 2), default=0)

    notes = Column(Text)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("avancement_pct >= 0 AND avancement_pct <= 100", name="ck_tache_avancement"),
        Index("ix_tache_projet", "projet_id"),
    )


# ── Sous-traitants (EX-PROJ-103) ─────────────────────────────────────────

class SousTraitant(Base):
    """Subcontractor with performance scoring.

    EX-PROJ-103: Scored on quality, deadlines, safety.
    Score used for future tender prioritization.
    """
    __tablename__ = "sous_traitants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    fournisseur_id = Column(String(36), ForeignKey("fournisseurs.id"), nullable=True)

    raison_sociale = Column(String(300), nullable=False)
    specialite = Column(String(200))  # GROS_OEUVRE, PLOMBERIE, ELECTRICITE, etc.
    nif = Column(String(50))
    rc = Column(String(50))
    adresse = Column(Text)
    telephone = Column(String(50))
    email = Column(String(255))

    # Performance scoring (0-100 each)
    score_qualite = Column(Numeric(5, 2), default=50)
    score_delais = Column(Numeric(5, 2), default=50)
    score_securite = Column(Numeric(5, 2), default=50)
    score_global = Column(Numeric(5, 2), default=50)  # weighted average
    nb_evaluations = Column(Integer, default=0)

    # Status
    est_agree = Column(Boolean, default=True)
    motif_blacklist = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ── Situations de Travaux (EX-PROJ-102) ──────────────────────────────────

class SituationTravaux(Base):
    """Work progress report from subcontractor.

    EX-PROJ-102: Validation generates:
      - A debt toward the subcontractor (accounts payable)
      - A charge in the project's cost center
    """
    __tablename__ = "situations_travaux"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    sous_traitant_id = Column(String(36), ForeignKey("sous_traitants.id"), nullable=False)

    # Reference
    numero = Column(String(50), nullable=False)  # e.g. SIT-2025-001
    periode = Column(String(20))  # e.g. "2025-03"

    # Amounts
    montant_ht = Column(Numeric(18, 2), nullable=False)
    taux_tva = Column(Numeric(5, 4), default=0.19)
    montant_tva = Column(Numeric(18, 2), default=0)
    montant_ttc = Column(Numeric(18, 2), default=0)

    # Retenue de garantie (typically 5%)
    retenue_garantie_pct = Column(Numeric(5, 2), default=5)
    retenue_garantie = Column(Numeric(18, 2), default=0)

    # Net à payer
    montant_net = Column(Numeric(18, 2), default=0)

    # Avancement
    avancement_cumule_pct = Column(Numeric(5, 2), default=0)
    avancement_periode_pct = Column(Numeric(5, 2), default=0)

    # Status & workflow
    statut = Column(SAEnum(StatutSituation), default=StatutSituation.BROUILLON)
    realite_financiere = Column(String(4), default="RF1")  # RF1/RF2/RF3/RF4

    # Validation
    validee_par = Column(String(36), ForeignKey("users.id"))
    date_validation = Column(DateTime)
    motif_rejet = Column(Text)

    # Auto-generated references
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id"))
    document_id = Column(String(36), ForeignKey("documents.id"))

    notes = Column(Text)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_situation_projet", "projet_id", "sous_traitant_id"),
    )


# ── Rapports d'Expert (for VSP fund releases) ───────────────────────────

class RapportExpert(Base):
    """Expert report validating construction progress for VSP fund releases."""
    __tablename__ = "rapports_expert"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)

    numero = Column(String(50), nullable=False)
    date_visite = Column(Date, nullable=False)
    avancement_constate_pct = Column(Numeric(5, 2), nullable=False)
    palier_vsp = Column(Integer)  # which VSP milestone this validates
    observations = Column(Text)

    # Document
    document_id = Column(String(36), ForeignKey("documents.id"))

    # Status
    est_valide = Column(Boolean, default=False)
    valide_par = Column(String(36), ForeignKey("users.id"))

    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
