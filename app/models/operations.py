"""
GFI v7.0 — Operations Management: Operation, OperationBudgetAgrege,
OperationPlanningTask, OperationDependency, OperationSnapshot, WbsTemplate.

Budget = automatic aggregation of 11 sources, NOT contract alone.
Critical path calculation. S-curve (physical vs financial advancement).
25 business rules (RM-01 through RM-25).
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Operation(GFIBase, Base):
    """Operational engagement with multi-source budget aggregation."""

    __tablename__ = "operation"

    code_operation = Column(String(30), unique=True, nullable=False, index=True)
    intitule = Column(String(300), nullable=False)

    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    categorie = Column(String(30), nullable=False)
    # BET_ARCHITECTURE, GROS_OEUVRE, SECOND_OEUVRE, MACHINE_OEM,
    # FOURNITURE, PRESTATION, RH_CDI, RH_CDD, ADV_VENTE,
    # MAINTENANCE, IT_LICENCE, ASSURANCE, AUTRE

    tiers_id = Column(UUID(as_uuid=True), nullable=True)
    contrat_legal_id = Column(
        UUID(as_uuid=True), ForeignKey("legal_contract.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # ── Financial ────────────────────────────────────────────────────────
    montant_engage_ht = Column(Numeric(15, 2), nullable=True)
    montant_engage_ttc = Column(Numeric(15, 2), nullable=True)
    montant_rf2 = Column(Numeric(15, 2), nullable=True)
    devise = Column(String(3), nullable=False, server_default="'DZD'")

    # ── State machine ────────────────────────────────────────────────────
    statut = Column(String(20), nullable=False, server_default="'BROUILLON'")
    date_debut = Column(Date, nullable=True)
    date_fin_prevue = Column(Date, nullable=True)
    date_fin_reelle = Column(Date, nullable=True)

    responsable_id = Column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    visa_tresorier = Column(Boolean, nullable=False, server_default="false")
    visa_tresorier_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    project = relationship("Project")

    def __repr__(self):
        return f"<Operation {self.code_operation} {self.statut}>"


class OperationBudgetAgrege(GFIBase, Base):
    """Budget from one of 11 sources for an operation."""

    __tablename__ = "operation_budget_agrege"

    operation_id = Column(
        UUID(as_uuid=True), ForeignKey("operation.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    source_code = Column(String(20), nullable=False, index=True)
    # S1_CONTRAT through S11_OVERHEAD
    source_label = Column(String(100), nullable=False)

    montant_prevu = Column(Numeric(15, 2), nullable=False, server_default="0")
    montant_reel = Column(Numeric(15, 2), nullable=False, server_default="0")
    methode_calcul = Column(String(20), nullable=False)
    # DIRECT, API_PULL, TRIGGER, CLE_REPARTITION, CRON_MENSUEL
    cle_repartition = Column(JSONB, nullable=True)
    derniere_maj = Column(DateTime(timezone=True), nullable=True)
    detail_lignes = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<BudgetAgrege {self.source_code} prevu={self.montant_prevu}>"


class OperationPlanningTask(GFIBase, Base):
    """WBS task in an operation's Gantt planning."""

    __tablename__ = "operation_planning_task"

    operation_id = Column(
        UUID(as_uuid=True), ForeignKey("operation.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    parent_task_id = Column(
        UUID(as_uuid=True), ForeignKey("operation_planning_task.id", ondelete="SET NULL"),
        nullable=True,
    )
    jalon_id = Column(UUID(as_uuid=True), nullable=True)

    code_wbs = Column(String(20), nullable=False)
    intitule = Column(String(300), nullable=False)
    type_tache = Column(String(20), nullable=False)
    # SUMMARY, TACHE, JALON_PLANNING, LIVRABLE, PAIEMENT

    date_debut_prevue = Column(Date, nullable=True)
    date_fin_prevue = Column(Date, nullable=True)
    date_debut_reelle = Column(Date, nullable=True)
    date_fin_reelle = Column(Date, nullable=True)

    avancement_pct = Column(Numeric(5, 2), nullable=False, server_default="0")
    avancement_methode = Column(String(20), nullable=True)
    # MANUEL, PREUVE_PHOTO, SITUATION_TRAVAUX, IA_DETECTION, CAPTEUR_IOT

    budget_tache = Column(Numeric(15, 2), nullable=True)
    cout_reel_tache = Column(Numeric(15, 2), nullable=False, server_default="0")
    est_critique = Column(Boolean, nullable=False, server_default="false")

    responsable_id = Column(UUID(as_uuid=True), nullable=True)
    statut_tache = Column(String(20), nullable=False, server_default="'A_FAIRE'")
    notes = Column(Text, nullable=True)

    parent = relationship("OperationPlanningTask", remote_side="OperationPlanningTask.id")

    def __repr__(self):
        return f"<PlanningTask {self.code_wbs} {self.avancement_pct}% {self.statut_tache}>"


class OperationDependency(GFIBase, Base):
    """Dependency between planning tasks (FD/DD/FF/DF)."""

    __tablename__ = "operation_dependency"

    predecesseur_id = Column(
        UUID(as_uuid=True), ForeignKey("operation_planning_task.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    successeur_id = Column(
        UUID(as_uuid=True), ForeignKey("operation_planning_task.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    type_dependance = Column(String(2), nullable=False, server_default="'FD'")
    decalage_jours = Column(Integer, nullable=False, server_default="0")

    def __repr__(self):
        return f"<Dependency {self.type_dependance} lag={self.decalage_jours}>"


class OperationSnapshot(GFIBase, Base):
    """Planning snapshots (baselines) for variance analysis."""

    __tablename__ = "operation_snapshot"

    operation_id = Column(
        UUID(as_uuid=True), ForeignKey("operation.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    type_snapshot = Column(String(20), nullable=False)
    # BASELINE_INITIALE, AVENANT, MENSUEL, MANUEL
    date_snapshot = Column(Date, nullable=False)
    donnees_taches = Column(JSONB, nullable=False)
    commentaire = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Snapshot {self.type_snapshot} {self.date_snapshot}>"


class WbsTemplate(Base):
    """Pre-configured WBS templates per operation category."""

    __tablename__ = "wbs_template"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=__import__("sqlalchemy").text("gen_random_uuid()"))
    categorie = Column(String(30), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    tasks = Column(JSONB, nullable=False)
    # [{code_wbs, intitule, type_tache, duration_default, dependencies}]
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=__import__("sqlalchemy").func.now())

    def __repr__(self):
        return f"<WbsTemplate {self.categorie} {self.name}>"
