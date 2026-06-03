"""
GFI v7.0 — CC Category Configuration + PayrollImputation + AllocationKey.

16 cost categories, each with specific:
- Data sources (which accounts/modules feed it)
- Distribution rule (% PROJET, % ENTREPRISE, 100% associate, custom)
- Verifications
- Treasury impact flag
"""

from sqlalchemy import (
    Boolean, Column, Date, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class CcCategoryConfig(Base):
    """Configuration for each of the 16 CC categories. System reference."""

    __tablename__ = "cc_category_config"

    id = Column(UUID(as_uuid=True), primary_key=True,
                server_default=__import__("sqlalchemy").text("gen_random_uuid()"))
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    cc_number = Column(Integer, nullable=False)  # 1-16

    # ── Distribution rule ────────────────────────────────────────────────
    # PCT_PROJET, PCT_ENTREPRISE, ASSOCIATE_100PCT, CUSTOM, MIXED
    distribution_rule = Column(String(30), nullable=False)

    # ── Data sources ─────────────────────────────────────────────────────
    source_accounts = Column(JSONB, nullable=True)  # SCF account codes
    source_modules = Column(JSONB, nullable=True)   # module names

    # ── Flags ────────────────────────────────────────────────────────────
    impact_tresorerie = Column(Boolean, nullable=False, server_default="true")
    requires_allocation_key = Column(Boolean, nullable=False, server_default="false")
    auto_reclassify_days = Column(Integer, nullable=True)  # CC16: 30 days

    description = Column(Text, nullable=True)
    created_at = Column(__import__("sqlalchemy").DateTime(timezone=True),
                        nullable=False,
                        server_default=__import__("sqlalchemy").func.now())
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    def __repr__(self):
        return f"<CcCategoryConfig CC{self.cc_number} {self.code}>"


class PayrollImputation(GFIBase, Base):
    """Employee time allocation across projects for CC4 payroll split."""

    __tablename__ = "payroll_imputation"

    employee_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    employee_name = Column(String(255), nullable=False)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    pourcentage_temps = Column(Numeric(5, 2), nullable=False)

    # ── Validity period ──────────────────────────────────────────────────
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)  # NULL = still active

    project = relationship("Project")

    def __repr__(self):
        return (
            f"<PayrollImputation {self.employee_name} "
            f"{self.pourcentage_temps}% on {self.project_id}>"
        )


class AllocationKey(GFIBase, Base):
    """Configurable allocation key for ventilating shared charges (CC5 BBZ, etc.)."""

    __tablename__ = "allocation_key"

    # ── What this key ventilates ─────────────────────────────────────────
    key_name = Column(String(100), nullable=False)
    cc_category = Column(String(20), nullable=False, index=True)

    # ── Basis ────────────────────────────────────────────────────────────
    # CHIFFRE_AFFAIRES, SURFACE, POURCENTAGE_FIXE
    basis = Column(String(30), nullable=False)

    # ── If fixed %, per-project allocations ──────────────────────────────
    allocations = Column(JSONB, nullable=True)
    # e.g., {"EDEN": 40, "JASMINS": 30, "OPERA": 30}

    # ── Validity ─────────────────────────────────────────────────────────
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")

    def __repr__(self):
        return f"<AllocationKey {self.key_name} basis={self.basis}>"


class BbzCharge(GFIBase, Base):
    """BBZ (Bureau Bab Ezzouar) charge components for CC5."""

    __tablename__ = "bbz_charge"

    charge_type = Column(String(30), nullable=False)
    # FIT_OUT, RENT_ADVANCE, MONTHLY_RENT
    montant_total = Column(Numeric(15, 2), nullable=False)
    amortization_method = Column(String(20), nullable=True)
    # IMMEDIATE, AMORTIZED_USEFUL_LIFE, AMORTIZED_LEASE
    amortization_months = Column(Integer, nullable=True)
    monthly_amount = Column(Numeric(15, 2), nullable=True)
    description = Column(Text, nullable=True)

    def __repr__(self):
        return f"<BbzCharge {self.charge_type} {self.montant_total} DA>"
