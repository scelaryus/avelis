"""GFI Platform – SPI (Score de Performance Intégré) & Organization models.

Derived from:
  - docs/SYSTÈME DE RÉMUNÉRATION AUTOMATISÉ SPI 360°.md
  - docs/Structure du système de rémunération.md
  - docs/Organigrammes AVELIS 2025.md
  - docs/NOMENCLATURE DES ENTREPRISE ET ACTIONNAIRE.md

Tables:
  departments           – organizational hierarchy
  hierarchy_relations   – manager/subordinate reporting lines
  spi_rules             – SPI calculation rules per role
  spi_kpis              – KPI definitions linked to tasks/projects
  spi_scores            – computed daily/monthly SPI scores per employee
  spi_bonus_malus_rules – bonus/malus thresholds
  ownership_relations   – company-shareholder ownership mapping (extends Associe)
"""
import uuid
from datetime import date
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

class SPICategory(str, enum.Enum):
    """Main SPI scoring categories (weighted)."""
    PLANIFICATION = "PLANIFICATION"        # 30%
    QUALITE_EXECUTION = "QUALITE_EXECUTION"  # 25%
    COMPORTEMENT = "COMPORTEMENT"          # 25%
    PERFORMANCE_METIER = "PERFORMANCE_METIER"  # 20%


class SPIScorePeriod(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class BonusMalusType(str, enum.Enum):
    BONUS = "BONUS"
    MALUS = "MALUS"


class CommissionType(str, enum.Enum):
    CASH_SALE = "CASH_SALE"          # 1%
    CREDIT_SALE = "CREDIT_SALE"      # 0.5%
    RECOVERY = "RECOVERY"            # recovery-based


class FunctionCategory(str, enum.Enum):
    """Employee function category for remuneration barème."""
    SUPPORT = "SUPPORT"
    COMMERCIAL = "COMMERCIAL"
    MARKETING = "MARKETING"
    SAV = "SAV"
    MANAGEMENT = "MANAGEMENT"
    OPERATIONS = "OPERATIONS"


# ────────────────────────────────────────────────────────────────────────────
# Department (Org hierarchy)
# ────────────────────────────────────────────────────────────────────────────

class Department(Base):
    """Departments extracted from docs/Organigrammes AVELIS 2025.md.

    Hierarchy: DG → DAF, DMV, DO (Direction Générale → Finance, Marketing/Vente, Opérations).
    """
    __tablename__ = "departments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    parent_id = Column(String(36), ForeignKey("departments.id"), nullable=True)
    head_employee_id = Column(String(36), ForeignKey("employees.id"), nullable=True)
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_dept_tenant_code"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Hierarchy Relations (reporting lines)
# ────────────────────────────────────────────────────────────────────────────

class HierarchyRelation(Base):
    """Explicit manager→subordinate reporting lines.

    Extracted from employee dataset (Manager column).
    """
    __tablename__ = "hierarchy_relations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    manager_id = Column(String(36), ForeignKey("employees.id"), nullable=False)
    subordinate_id = Column(String(36), ForeignKey("employees.id"), nullable=False)
    relation_type = Column(String(50), default="direct")  # direct, functional, mentor
    is_active = Column(Boolean, default=True)
    effective_from = Column(Date)
    effective_to = Column(Date)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("manager_id", "subordinate_id", "relation_type",
                         name="uq_hierarchy_relation"),
        Index("ix_hierarchy_manager", "manager_id"),
        Index("ix_hierarchy_subordinate", "subordinate_id"),
    )


# ────────────────────────────────────────────────────────────────────────────
# SPI Rules (scoring formulas per role)
# ────────────────────────────────────────────────────────────────────────────

class SPIRule(Base):
    """SPI scoring rules per role/position.

    Extracted from docs/SYSTÈME DE RÉMUNÉRATION AUTOMATISÉ SPI 360°.md:
      Each role has 4 weighted categories that sum to 100%.
      Example: Technical Sales Executive →
        50% Ventes, 25% Leads, 15% Tenue de compte, 10% Participations.
    """
    __tablename__ = "spi_rules"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    role_code = Column(String(100), nullable=False)  # matches Employee.position
    role_label = Column(String(255), nullable=False)
    function_category = Column(SAEnum(FunctionCategory), default=FunctionCategory.SUPPORT)

    # Category weights (must sum to 100)
    weight_planification = Column(Numeric(5, 2), nullable=False, default=30)
    weight_qualite = Column(Numeric(5, 2), nullable=False, default=25)
    weight_comportement = Column(Numeric(5, 2), nullable=False, default=25)
    weight_performance = Column(Numeric(5, 2), nullable=False, default=20)

    # Per-role sub-criteria (JSON array of {label, weight_pct, description})
    criteria_planification = Column(JSON, default=[])
    criteria_qualite = Column(JSON, default=[])
    criteria_comportement = Column(JSON, default=[])
    criteria_performance = Column(JSON, default=[])

    # Commission rules for commercial roles
    commission_cash_pct = Column(Numeric(5, 2), default=0)       # e.g. 1.0%
    commission_credit_pct = Column(Numeric(5, 2), default=0)     # e.g. 0.5%
    commission_split_commercial = Column(Numeric(5, 2), default=50)  # 50% to commercial
    commission_split_manager = Column(Numeric(5, 2), default=25)     # 25% to manager
    commission_split_team = Column(Numeric(5, 2), default=25)        # 25% to team

    # Productivity multipliers
    task_points_per_completion = Column(Numeric(8, 2), default=10)
    inactivity_penalty_per_day = Column(Numeric(8, 2), default=10)  # -10 SPI/day
    absence_penalty_per_day = Column(Numeric(5, 2), default=5)      # -5% SPI/day

    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "role_code", "version", name="uq_spi_rule_role_version"),
    )


# ────────────────────────────────────────────────────────────────────────────
# SPI KPIs (Key Performance Indicators)
# ────────────────────────────────────────────────────────────────────────────

class SPIKpi(Base):
    """KPI definitions linked to tasks and projects.

    From docs/Structure du système de rémunération.md:
      - Each task has KPIs for measuring accomplishment
      - KPIs connected to planning, quality, behavior, and performance.
    """
    __tablename__ = "spi_kpis"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(SAEnum(SPICategory), nullable=False)
    target_value = Column(Numeric(18, 2))       # target numeric value
    unit = Column(String(50), default="points")  # points, %, count
    weight = Column(Numeric(5, 2), default=1.0)  # relative weight within category
    applicable_roles = Column(JSON, default=[])   # list of role_codes this KPI applies to
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_kpi_code"),
    )


# ────────────────────────────────────────────────────────────────────────────
# SPI Scores (computed daily/monthly)
# ────────────────────────────────────────────────────────────────────────────

class SPIScore(Base):
    """Computed SPI scores per employee per period.

    Each SPI calculated automatically every 24h:
      - 30% Planification
      - 25% Qualité exécution
      - 25% Comportement et discipline
      - 20% Performance métier directe

    Score range: 0–200 (can exceed 100 with accelerator).
    """
    __tablename__ = "spi_scores"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False)
    period_type = Column(SAEnum(SPIScorePeriod), nullable=False)
    period_date = Column(Date, nullable=False)  # date for daily, first-of-month for monthly
    period_label = Column(String(50))  # e.g. "2026-03" or "2026-03-06"

    # Category sub-scores (0–100 each, before weighting)
    score_planification = Column(Numeric(8, 2), default=0)
    score_qualite = Column(Numeric(8, 2), default=0)
    score_comportement = Column(Numeric(8, 2), default=0)
    score_performance = Column(Numeric(8, 2), default=0)

    # Weighted composite score
    spi_total = Column(Numeric(8, 2), nullable=False, default=0)

    # Task metrics
    tasks_planned = Column(Integer, default=0)
    tasks_completed = Column(Integer, default=0)
    tasks_validated = Column(Integer, default=0)
    tasks_rejected = Column(Integer, default=0)
    task_points_earned = Column(Numeric(10, 2), default=0)

    # Discipline metrics
    absences_injustifiees = Column(Integer, default=0)
    retards = Column(Integer, default=0)
    sanctions = Column(Integer, default=0)
    jours_inactifs = Column(Integer, default=0)

    # Sales/commercial metrics
    ventes_montant = Column(Numeric(18, 2), default=0)
    leads_traites = Column(Integer, default=0)
    taux_conversion = Column(Numeric(5, 2), default=0)

    # Bonus/malus applied
    bonus_pct = Column(Numeric(5, 2), default=0)
    malus_pct = Column(Numeric(5, 2), default=0)
    bonus_amount = Column(Numeric(18, 2), default=0)
    malus_amount = Column(Numeric(18, 2), default=0)

    # Salary impact
    base_salary = Column(Numeric(18, 2), default=0)
    adjusted_salary = Column(Numeric(18, 2), default=0)
    commission_amount = Column(Numeric(18, 2), default=0)
    mission_allowance = Column(Numeric(18, 2), default=0)  # +2000 DA/day for personal vehicle

    # Computation metadata
    spi_rule_id = Column(String(36), ForeignKey("spi_rules.id"))
    computed_by = Column(String(50), default="system")  # system | manual | ai_agent
    computation_details = Column(JSON, default={})
    is_validated = Column(Boolean, default=False)
    validated_by = Column(String(36), ForeignKey("users.id"))
    validated_at = Column(DateTime)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("employee_id", "period_type", "period_date",
                         name="uq_spi_employee_period"),
        Index("ix_spi_scores_employee", "employee_id", "period_date"),
        Index("ix_spi_scores_tenant_date", "tenant_id", "period_date"),
        CheckConstraint("spi_total >= 0", name="ck_spi_total_positive"),
    )


# ────────────────────────────────────────────────────────────────────────────
# SPI Bonus/Malus Rules
# ────────────────────────────────────────────────────────────────────────────

class SPIBonusMalusRule(Base):
    """Bonus/malus thresholds from SPI 360° specification.

    Bonus:
      SPI >= 90:  +20% to +50% salary
      SPI > 130 for 2 months: exceptional bonus + strategic position

    Malus:
      SPI < 70:  -15%
      SPI < 50:  -30% + HR alert
      SPI < 50 for 2 months: automatic termination

    Discipline:
      Absence injustifiée: -5% SPI/day
      Travail sans valeur: -15% SPI + written sanction
      5 days inactive: salary freeze + HR alert
    """
    __tablename__ = "spi_bonus_malus_rules"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    rule_type = Column(SAEnum(BonusMalusType), nullable=False)
    label = Column(String(255), nullable=False)
    description = Column(Text)

    # Threshold conditions
    spi_min = Column(Numeric(8, 2))           # SPI >= this
    spi_max = Column(Numeric(8, 2))           # SPI < this
    consecutive_months = Column(Integer, default=1)  # must hold for N months
    function_category = Column(SAEnum(FunctionCategory), nullable=True)  # NULL = all

    # Impact
    salary_adjustment_pct = Column(Numeric(5, 2), nullable=False)  # + or -
    triggers_hr_alert = Column(Boolean, default=False)
    triggers_termination = Column(Boolean, default=False)
    triggers_salary_freeze = Column(Boolean, default=False)

    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_bm_rules_type", "rule_type", "sort_order"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Ownership Relations (extends existing Associe model)
# ────────────────────────────────────────────────────────────────────────────

class OwnershipRelation(Base):
    """Company-shareholder-project ownership mapping.

    Extracted from docs/NOMENCLATURE DES ENTREPRISE ET ACTIONNAIRE.md.
    Links shareholders to companies and their projects with ownership percentages.
    Extends the existing Associe model with project-level granularity.
    """
    __tablename__ = "ownership_relations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    associe_id = Column(String(36), ForeignKey("associes.id"), nullable=True)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=True)
    shareholder_name = Column(String(300), nullable=False)
    ownership_pct = Column(Numeric(8, 4), nullable=False)  # ownership % in this project
    status = Column(String(100))  # A FERMER, A DEVLOPER, etc.
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_ownership_entreprise", "entreprise_id"),
        Index("ix_ownership_projet", "projet_id"),
    )


# ────────────────────────────────────────────────────────────────────────────
# Remuneration Barème Rules
# ────────────────────────────────────────────────────────────────────────────

class RemunerationBareme(Base):
    """Remuneration scale from docs/Structure du système de rémunération.md.

    Defines salary adjustment brackets by performance percentage:
      0–29%:  base salary only
      30–50%: negotiation, -20% on salary
      76–92%: +10% bonus
      93–100%: +20% bonus

    For commercial: commission rates on cash/credit sales.
    For SAV: recovery rate-based bonus.
    """
    __tablename__ = "remuneration_baremes"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    function_category = Column(SAEnum(FunctionCategory), nullable=False)
    label = Column(String(255), nullable=False)
    performance_min_pct = Column(Numeric(5, 2), nullable=False)  # lower bound %
    performance_max_pct = Column(Numeric(5, 2), nullable=False)  # upper bound %
    salary_adjustment_pct = Column(Numeric(5, 2), nullable=False)  # +/- %
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_bareme_category", "function_category", "sort_order"),
    )
