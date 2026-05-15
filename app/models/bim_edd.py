# GAP 8 — BIM / EDD MODULE — models/bim_edd.py
"""BIM (Building Information Modeling) and EDD (État Descriptif de Division) models.

Tables:
  - re_projects         – Real estate project master
  - re_blocks           – Building blocks within a project
  - re_levels           – Floor/level within a block
  - re_units            – Individual units (apartments, commerces, parkings)
  - re_unit_annexes     – Annexes attached to a unit (B/T/J/P/C)
  - re_pricing_rules    – Immobilier pricing coefficient rules
  - re_validations      – Multi-stage validation log
  - re_docs             – Project/unit documents (EDD, expert foncier…)
  - bim_import_jobs     – IFC/RVT import tracking
"""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    DateTime,
    Date,
    ForeignKey,
    Enum as SAEnum,
    JSON,
    Numeric,
    UniqueConstraint,
    Index,
    CheckConstraint,
    func,
)

from app.database import Base


# ────────────────────────────────────────────────────────────────────────────
# Enums
# ────────────────────────────────────────────────────────────────────────────

class AnnexType(str, enum.Enum):
    B = "B"  # balcon
    T = "T"  # terrasse
    J = "J"  # jardin
    P = "P"  # parking
    C = "C"  # cave


class EddState(str, enum.Enum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    FROZEN = "FROZEN"


class ValidationStage(str, enum.Enum):
    IDS_CHECK = "IDS_CHECK"
    SURFACE_TOLERANCE = "SURFACE_TOLERANCE"
    EXPERT_FONCIER = "EXPERT_FONCIER"
    COMPLETENESS = "COMPLETENESS"
    PUBLICATION = "PUBLICATION"
    FREEZE = "FREEZE"
    ROLLBACK = "ROLLBACK"


class ValidationStatus(str, enum.Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class ImportJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


class PricingRuleType(str, enum.Enum):
    FACADE = "FACADE"
    VERTICAL = "VERTICAL"
    COMMERCIAL = "COMMERCIAL"
    FINANCIAL = "FINANCIAL"
    PARTNERSHIP = "PARTNERSHIP"


class DocType(str, enum.Enum):
    EDD_REPORT = "EDD_REPORT"
    EXPERT_FONCIER = "EXPERT_FONCIER"
    CONFORMITE = "CONFORMITE"
    ETAT_DIVISION_CADASTRAL = "ETAT_DIVISION_CADASTRAL"
    DESCRIPTIF_TECHNIQUE = "DESCRIPTIF_TECHNIQUE"
    PLANCHE_A3 = "PLANCHE_A3"
    FICHE_PRODUIT = "FICHE_PRODUIT"


# ────────────────────────────────────────────────────────────────────────────
# RE Project
# ────────────────────────────────────────────────────────────────────────────

class REProject(Base):
    __tablename__ = "re_projects"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    lat = Column(Numeric(10, 7), nullable=True)
    lon = Column(Numeric(10, 7), nullable=True)
    north_angle = Column(Numeric(8, 4), nullable=True)
    status = Column(String(20), default="DRAFT")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ────────────────────────────────────────────────────────────────────────────
# RE Block (building)
# ────────────────────────────────────────────────────────────────────────────

class REBlock(Base):
    __tablename__ = "re_blocks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("re_projects.id"), nullable=False)
    code = Column(String(8), nullable=False)
    name = Column(String(200), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_re_block_project_code"),
    )


# ────────────────────────────────────────────────────────────────────────────
# RE Level (floor within a block)
# ────────────────────────────────────────────────────────────────────────────

class RELevel(Base):
    __tablename__ = "re_levels"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    block_id = Column(String(36), ForeignKey("re_blocks.id"), nullable=False)
    code = Column(String(10), nullable=False)  # format Lxx
    elevation = Column(Numeric(8, 2), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("block_id", "code", name="uq_re_level_block_code"),
    )


# ────────────────────────────────────────────────────────────────────────────
# RE Unit
# ────────────────────────────────────────────────────────────────────────────

class REUnit(Base):
    __tablename__ = "re_units"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    level_id = Column(String(36), ForeignKey("re_levels.id"), nullable=False)
    code = Column(String(100), nullable=False, unique=True)
    # PROJ-BLK-STA-Lxx-UNIT-AAA
    typology = Column(String(50), nullable=True)
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)
    height_clear = Column(Numeric(5, 2), nullable=True)
    # Surfaces
    area_sh = Column(Numeric(10, 2), nullable=True)   # habitable
    area_su = Column(Numeric(10, 2), nullable=True)   # utile
    area_sb = Column(Numeric(10, 2), nullable=True)   # balcon
    area_st = Column(Numeric(10, 2), nullable=True)   # terrasse
    area_sj = Column(Numeric(10, 2), nullable=True)   # jardin
    area_sp = Column(Numeric(10, 2), nullable=True)   # parking
    area_sc = Column(Numeric(10, 2), nullable=True)   # cave
    area_scom = Column(Numeric(10, 2), nullable=True)  # parties communes
    area_net_bim = Column(Numeric(10, 2), nullable=True)
    area_gross_bim = Column(Numeric(10, 2), nullable=True)
    # Orientation & view
    exposure = Column(String(5), nullable=True)  # N/NE/E/SE/S/SO/O/NO
    view_class = Column(String(20), nullable=True)  # mer/ville/jardin/none
    # Pricing
    price_base = Column(Numeric(15, 2), nullable=True)
    price_total = Column(Numeric(15, 2), nullable=True)
    # State
    edd_state = Column(String(20), default="DRAFT")  # DRAFT/VALIDATED/FROZEN
    is_annex = Column(Boolean, default=False)
    annex_type = Column(String(5), nullable=True)  # B/T/J/P/C if is_annex
    usage_type = Column(String(50), nullable=True)
    ifc_space_id = Column(String(200), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("bedrooms IS NULL OR bedrooms >= 0", name="ck_bedrooms_pos"),
        CheckConstraint("bathrooms IS NULL OR bathrooms >= 0", name="ck_bathrooms_pos"),
        Index("idx_re_unit_code", "code"),
        Index("idx_re_unit_level", "level_id"),
        Index("idx_re_unit_edd_state", "edd_state"),
    )


# ────────────────────────────────────────────────────────────────────────────
# RE Unit Annex
# ────────────────────────────────────────────────────────────────────────────

class REUnitAnnex(Base):
    __tablename__ = "re_unit_annexes"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    unit_id = Column(String(36), ForeignKey("re_units.id"), nullable=False)
    type = Column(SAEnum(AnnexType), nullable=False)
    area = Column(Numeric(10, 2), nullable=False)
    ifc_space_id = Column(String(200), nullable=True)
    code_suffix = Column(String(10), nullable=True)  # -P1 / -C1 / -B1 …
    created_at = Column(DateTime, server_default=func.now())


# ────────────────────────────────────────────────────────────────────────────
# RE Pricing Rule (coefficient-based)
# ────────────────────────────────────────────────────────────────────────────

class REPricingRule(Base):
    __tablename__ = "re_pricing_rules"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), nullable=False, unique=True)
    rule_type = Column(SAEnum(PricingRuleType), nullable=False)
    label = Column(String(200), nullable=True)
    value = Column(Numeric(8, 4), nullable=False)
    scope = Column(String(50), nullable=True)  # UNIT / VILLA / ALL
    condition_field = Column(String(100), nullable=True)
    condition_value = Column(String(100), nullable=True)
    is_per_level = Column(Boolean, default=False)
    cap_value = Column(Numeric(8, 4), nullable=True)
    active_from = Column(Date, nullable=True)
    active_to = Column(Date, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


# ────────────────────────────────────────────────────────────────────────────
# RE Validation (multi-stage)
# ────────────────────────────────────────────────────────────────────────────

class REValidation(Base):
    __tablename__ = "re_validations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    object_type = Column(String(50), nullable=False)
    object_id = Column(String(36), nullable=False)
    stage = Column(SAEnum(ValidationStage), nullable=False)
    validator_role = Column(String(50), nullable=True)
    status = Column(SAEnum(ValidationStatus), nullable=False)
    payload = Column(JSON, nullable=True)
    ts = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_re_validation_object", "object_type", "object_id"),
    )


# ────────────────────────────────────────────────────────────────────────────
# RE Docs (project/unit documents)
# ────────────────────────────────────────────────────────────────────────────

class REDoc(Base):
    __tablename__ = "re_docs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    unit_id = Column(String(36), ForeignKey("re_units.id"), nullable=True)
    project_id = Column(String(36), ForeignKey("re_projects.id"), nullable=True)
    doc_type = Column(SAEnum(DocType), nullable=False)
    file_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    version = Column(Integer, default=1)
    hash = Column(String(64), nullable=False)
    is_obsolete = Column(Boolean, default=False)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ────────────────────────────────────────────────────────────────────────────
# BIM Import Job
# ────────────────────────────────────────────────────────────────────────────

class BIMImportJob(Base):
    __tablename__ = "bim_import_jobs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("re_projects.id"), nullable=True)
    filename = Column(String(500), nullable=False)
    file_format = Column(String(10), nullable=False)  # IFC / RVT
    file_id = Column(String(36), ForeignKey("documents.id"), nullable=True)
    status = Column(SAEnum(ImportJobStatus), default=ImportJobStatus.PENDING)
    ids_report = Column(JSON, nullable=True)
    bcf_report = Column(JSON, nullable=True)
    units_found = Column(Integer, default=0)
    units_valid = Column(Integer, default=0)
    units_rejected = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_bim_import_project", "project_id", "status"),
    )
