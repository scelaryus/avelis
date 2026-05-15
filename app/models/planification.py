"""GFI v7.0 — Planification, Taches, Offres de Performance models.

Tables:
  plans_strategiques    — strategic plans proposed by any employee
  taches_spi            — tasks with performance offers and SPI tracking
  offres_performance    — bonus/malus offer per task (symmetric)
  spi_mensuels          — monthly SPI with 4 components + adaptive weights
  alertes_rh            — HR alerts (sous-perf, freeze, rupture)
"""
import uuid
import enum
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, Date,
    ForeignKey, Enum as SAEnum, JSON, Numeric, UniqueConstraint, Index,
    CheckConstraint, func,
)
from app.database import Base


# ── Enums ──────────────────────────────────────────────────────────────────

class StatutPlan(str, enum.Enum):
    SOUMIS = "SOUMIS"
    EN_ANALYSE = "EN_ANALYSE"
    VALIDE = "VALIDE"
    CONTRE_PROPOSITION = "CONTRE_PROPOSITION"
    DECLINE = "DECLINE"
    EN_EXECUTION = "EN_EXECUTION"
    TERMINE = "TERMINE"
    ABANDONNE = "ABANDONNE"


class HorizonPlan(str, enum.Enum):
    MOIS_1 = "MOIS_1"
    MOIS_3 = "MOIS_3"
    MOIS_6 = "MOIS_6"
    MOIS_12 = "MOIS_12"


class SourceTache(str, enum.Enum):
    PLAN_STRATEGIQUE = "PLAN_STRATEGIQUE"
    OBJECTIF_CEO = "OBJECTIF_CEO"
    OBJECTIF_MANAGER = "OBJECTIF_MANAGER"
    AUTO_PROPOSEE = "AUTO_PROPOSEE"
    CRM = "CRM"
    MAINTENANCE = "MAINTENANCE"
    URGENCE = "URGENCE"


class StatutTache(str, enum.Enum):
    PROPOSEE = "PROPOSEE"
    ASSIGNEE = "ASSIGNEE"
    OFFRE_EN_COURS = "OFFRE_EN_COURS"
    VERROUILLEE = "VERROUILLEE"
    EN_COURS = "EN_COURS"
    EN_REVUE = "EN_REVUE"
    VALIDEE = "VALIDEE"
    REJETEE = "REJETEE"
    ANNULEE = "ANNULEE"


class PrioriteTache(str, enum.Enum):
    CRITIQUE = "CRITIQUE"
    ELEVEE = "ELEVEE"
    NORMALE = "NORMALE"
    BASSE = "BASSE"


class StatutOffre(str, enum.Enum):
    PROPOSEE = "PROPOSEE"
    CONTRE_OFFRE = "CONTRE_OFFRE"
    ACCEPTEE = "ACCEPTEE"
    VERROUILLEE = "VERROUILLEE"
    EXECUTEE = "EXECUTEE"


class ResultatOffre(str, enum.Enum):
    EN_ATTENTE = "EN_ATTENTE"
    BONUS_VERSE = "BONUS_VERSE"
    MALUS_APPLIQUE = "MALUS_APPLIQUE"
    CONTESTEE = "CONTESTEE"


class TypeAlerte(str, enum.Enum):
    AVERTISSEMENT = "AVERTISSEMENT"
    SURVEILLANCE = "SURVEILLANCE"
    PLAN_REDRESSEMENT = "PLAN_REDRESSEMENT"
    RUPTURE_SPI = "RUPTURE_SPI"
    GEL_SALAIRE = "GEL_SALAIRE"
    PROTECTION = "PROTECTION"


# ── Plan Stratégique ───────────────────────────────────────────────────────

class PlanStrategique(Base):
    """Strategic plan proposed by any employee."""
    __tablename__ = "plans_strategiques"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    reference = Column(String(50))  # PLAN-{YYYY}-{SEQ}

    # Proposer
    proposeur_id = Column(String(36), ForeignKey("employees.id"), nullable=False)
    date_proposition = Column(DateTime, server_default=func.now())

    # Content
    titre = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    objectif_mesurable = Column(String(500))
    kpis_proposes = Column(JSON, default=[])  # [{indicateur, cible, unite}]
    horizon = Column(SAEnum(HorizonPlan), default=HorizonPlan.MOIS_3)
    benefice_estime = Column(Text)
    ressources_necessaires = Column(Text)
    documents_joints = Column(JSON, default=[])  # [doc_ids]

    # System analysis
    score_pertinence_ia = Column(Numeric(5, 2), default=0)
    doublons_detectes = Column(JSON, default=[])
    ameliorations_proposees = Column(Text)
    faisabilite_score = Column(Numeric(5, 2), default=0)

    # Validation
    statut = Column(SAEnum(StatutPlan), default=StatutPlan.SOUMIS)
    valideur_id = Column(String(36), ForeignKey("employees.id"), nullable=True)
    date_validation = Column(DateTime, nullable=True)
    modifications_valideur = Column(Text)
    justification_refus = Column(Text)

    # Prime
    prime_versee = Column(Boolean, default=False)
    montant_prime = Column(Numeric(12, 2), default=0)  # 5% salary

    # Execution tracking
    avancement_pct = Column(Numeric(5, 2), default=0)

    # GFI links
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=True)
    entite_juridique_id = Column(String(36), ForeignKey("entreprises.id"), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ── Tâche SPI ──────────────────────────────────────────────────────────────

class TacheSPI(Base):
    """Task with performance offer and SPI tracking."""
    __tablename__ = "taches_spi"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    reference = Column(String(50))  # TACHE-{YYYY}-{SEQ}

    # Origin
    source_type = Column(SAEnum(SourceTache), default=SourceTache.OBJECTIF_MANAGER)
    plan_strategique_id = Column(String(36), ForeignKey("plans_strategiques.id"), nullable=True)
    parent_tache_id = Column(String(36), ForeignKey("taches_spi.id"), nullable=True)

    # Content
    titre = Column(String(300), nullable=False)
    description = Column(Text)
    criteres_acceptation = Column(Text)
    livrables_attendus = Column(JSON, default=[])

    # Assignment
    assignee_id = Column(String(36), ForeignKey("employees.id"), nullable=False)
    assigneur_id = Column(String(36), ForeignKey("employees.id"), nullable=True)

    # Timeline
    date_creation = Column(DateTime, server_default=func.now())
    date_debut_prevue = Column(Date)
    date_fin_prevue = Column(Date, nullable=False)
    date_debut_reelle = Column(Date, nullable=True)
    date_fin_reelle = Column(Date, nullable=True)
    duree_estimee_heures = Column(Numeric(8, 2), default=0)

    # Dependencies
    taches_predecesseurs = Column(JSON, default=[])  # [task_ids]
    est_bloquee = Column(Boolean, default=False)

    # KPIs per task
    kpis = Column(JSON, default=[])  # [{indicateur, cible, unite, poids_pct, valeur_reelle, score_kpi}]

    # Proofs
    preuves = Column(JSON, default=[])  # [{type_preuve, document_ged_id, date_upload, validee_ia, validee_manager}]

    # Evaluation scores
    score_execution = Column(Numeric(5, 2), nullable=True)  # 0-100
    score_qualite = Column(Numeric(5, 2), nullable=True)  # 0-100
    score_global_tache = Column(Numeric(5, 2), nullable=True)

    # Validation
    valide_par_systeme = Column(Boolean, nullable=True)
    valide_par_manager = Column(Boolean, nullable=True)
    date_validation = Column(DateTime, nullable=True)
    commentaire_manager = Column(Text)
    manager_rating = Column(Integer)  # 1-5

    # Status
    statut = Column(SAEnum(StatutTache), default=StatutTache.ASSIGNEE)
    priorite = Column(SAEnum(PrioriteTache), default=PrioriteTache.NORMALE)

    # GFI links
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=True)
    entite_juridique_id = Column(String(36), ForeignKey("entreprises.id"), nullable=True)

    # ── Estimate & Approval workflow (merged from HRTask) ──
    employee_estimated_time = Column(Float, nullable=True)  # hours
    employee_estimated_price = Column(Numeric(18, 2), nullable=True)
    estimated_at = Column(DateTime, nullable=True)
    manager_final_time = Column(Float, nullable=True)
    manager_final_price = Column(Numeric(18, 2), nullable=True)
    manager_approved_at = Column(DateTime, nullable=True)
    manager_approved_by = Column(String(36), nullable=True)

    # ── Proof document (single-file proof, complementary to preuves JSON) ──
    proof_document_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    proof_uploaded_at = Column(DateTime, nullable=True)

    # ── AI evaluation results ──
    ai_score = Column(Float, nullable=True)  # 0-100
    ai_note = Column(Text, nullable=True)
    ai_evaluated_at = Column(DateTime, nullable=True)

    # ── Origin metadata ──
    source_text = Column(Text, nullable=True)  # original raw text from manager
    task_type = Column(String(100), nullable=True)  # daily_plan, etc.
    required_role = Column(String(100), nullable=True)  # finance, hr, sales, etc.

    # Contestation
    est_contestee = Column(Boolean, default=False)
    contestation = Column(JSON, nullable=True)  # {motif, date, statut, resolution}

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_taches_spi_assignee", "assignee_id", "statut"),
        Index("ix_taches_spi_plan", "plan_strategique_id"),
    )


# ── Offre de Performance ───────────────────────────────────────────────────

class OffrePerformance(Base):
    """Bonus/malus performance offer per task — symmetric."""
    __tablename__ = "offres_performance"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    tache_id = Column(String(36), ForeignKey("taches_spi.id"), nullable=False)
    employe_id = Column(String(36), ForeignKey("employees.id"), nullable=False)

    # Employee proposal
    bonus_propose_pct = Column(Numeric(5, 2), nullable=False)  # % of prime SPI plafond
    bonus_propose_da = Column(Numeric(12, 2), default=0)  # calculated amount
    delai_propose = Column(Date, nullable=True)
    justification_employe = Column(Text)
    date_proposition = Column(DateTime, server_default=func.now())

    # Manager counter-offer
    bonus_contre_offre_pct = Column(Numeric(5, 2), nullable=True)
    justification_manager = Column(Text)
    date_contre_offre = Column(DateTime, nullable=True)

    # Final agreed
    bonus_final_pct = Column(Numeric(5, 2), nullable=True)
    bonus_final_da = Column(Numeric(12, 2), nullable=True)
    malus_final_da = Column(Numeric(12, 2), nullable=True)  # = bonus_final_da ALWAYS

    # Lock
    statut = Column(SAEnum(StatutOffre), default=StatutOffre.PROPOSEE)
    date_verrouillage = Column(DateTime, nullable=True)
    signature_employe = Column(Boolean, default=False)
    signature_manager = Column(Boolean, default=False)

    # Result
    resultat = Column(SAEnum(ResultatOffre), default=ResultatOffre.EN_ATTENTE)
    montant_applique = Column(Numeric(12, 2), nullable=True)  # positive=bonus, negative=malus

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tache_id", "employe_id", name="uq_offre_tache_employe"),
    )


# ── SPI Mensuel ────────────────────────────────────────────────────────────

class SPIMensuel(Base):
    """Monthly SPI score with 4 components and adaptive weights."""
    __tablename__ = "spi_mensuels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    employe_id = Column(String(36), ForeignKey("employees.id"), nullable=False)
    mois = Column(String(7), nullable=False)  # "2026-03"

    # 4 component scores (0-100 each)
    c1_execution = Column(Numeric(5, 2), default=0)
    c2_qualite = Column(Numeric(5, 2), default=0)
    c3_comportement = Column(Numeric(5, 2), default=0)
    c4_metier = Column(Numeric(5, 2), default=0)

    # Adaptive weights (must sum to 100)
    w1 = Column(Numeric(5, 2), default=30)
    w2 = Column(Numeric(5, 2), default=25)
    w3 = Column(Numeric(5, 2), default=25)
    w4 = Column(Numeric(5, 2), default=20)

    # Computed SPI (will be calculated in Python for SQLite compat)
    score_spi = Column(Numeric(5, 2), default=0)

    # Reliability
    fiabilite_score = Column(Numeric(5, 2), default=100)
    est_confirme = Column(Boolean, default=False)

    # Financial impact
    prime_calculee = Column(Numeric(12, 2), default=0)
    malus_calcule = Column(Numeric(12, 2), default=0)
    solde_bm_mois = Column(Numeric(12, 2), default=0)
    commission_mois = Column(Numeric(12, 2), default=0)
    prime_plan = Column(Numeric(12, 2), default=0)

    # Task metrics
    taches_total = Column(Integer, default=0)
    taches_validees = Column(Integer, default=0)
    taches_rejetees = Column(Integer, default=0)
    taches_en_retard = Column(Integer, default=0)

    # Behavior metrics
    absences_injustifiees = Column(Integer, default=0)
    retards = Column(Integer, default=0)
    jours_travailles = Column(Integer, default=0)

    # Validation
    valide_par_manager = Column(Boolean, default=False)
    valideur_id = Column(String(36), ForeignKey("employees.id"), nullable=True)
    date_validation = Column(DateTime, nullable=True)

    # Details
    details = Column(JSON, default={})

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("employe_id", "mois", name="uq_spi_mensuel_employe_mois"),
        Index("ix_spi_mensuel_tenant_mois", "tenant_id", "mois"),
    )


# ── Alerte RH ──────────────────────────────────────────────────────────────

class AlerteRH(Base):
    """HR alerts for sub-performance, freezes, rupture procedures."""
    __tablename__ = "alertes_rh"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    employe_id = Column(String(36), ForeignKey("employees.id"), nullable=False)
    type_alerte = Column(SAEnum(TypeAlerte), nullable=False)
    message = Column(Text, nullable=False)
    severite = Column(String(20), default="INFO")  # INFO, WARNING, CRITICAL
    mois_reference = Column(String(7))  # "2026-03"
    score_spi = Column(Numeric(5, 2), nullable=True)
    est_traitee = Column(Boolean, default=False)
    traitee_par = Column(String(36), ForeignKey("employees.id"), nullable=True)
    date_traitement = Column(DateTime, nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_alertes_rh_employe", "employe_id", "est_traitee"),
    )
