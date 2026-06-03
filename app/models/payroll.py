"""
GFI v7.0 — Payslip: stores every component of the 10-step payroll calculation.

Each payslip records all intermediate values individually (not just totals)
so the DAF can see the full decomposition at any time.
"""

from sqlalchemy import (
    Column, Date, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Payslip(GFIBase, Base):
    __tablename__ = "payslip"

    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)

    # ── Step 1: CNAS regime ──────────────────────────────────────────────
    cnas_regime = Column(String(10), nullable=False)  # GENERAL or BTPH
    cnas_employee_rate = Column(Numeric(6, 3), nullable=False)
    cnas_employer_rate = Column(Numeric(6, 3), nullable=False)

    # ── Step 2: Gross components ─────────────────────────────────────────
    salary_base = Column(Numeric(15, 2), nullable=False)
    prime_rendement = Column(Numeric(15, 2), nullable=False, server_default="0")
    prime_nuisance = Column(Numeric(15, 2), nullable=False, server_default="0")
    prime_panier = Column(Numeric(15, 2), nullable=False, server_default="0")
    indemnite_transport = Column(Numeric(15, 2), nullable=False, server_default="0")
    prime_iep = Column(Numeric(15, 2), nullable=False, server_default="0")
    prime_chantier = Column(Numeric(15, 2), nullable=False, server_default="0")
    overtime_hours = Column(Numeric(6, 2), nullable=False, server_default="0")
    overtime_amount = Column(Numeric(15, 2), nullable=False, server_default="0")
    gross_salary = Column(Numeric(15, 2), nullable=False)

    # ── Step 3: CNAS employee ────────────────────────────────────────────
    cnas_employee_amount = Column(Numeric(15, 2), nullable=False)

    # ── Step 4: Taxable ──────────────────────────────────────────────────
    taxable_income = Column(Numeric(15, 2), nullable=False)

    # ── Step 5-6: IRG ────────────────────────────────────────────────────
    irg_brut = Column(Numeric(15, 2), nullable=False)
    irg_abatement = Column(Numeric(15, 2), nullable=False)
    irg_final = Column(Numeric(15, 2), nullable=False)

    # ── Step 7: Deductions ───────────────────────────────────────────────
    advance_repayment = Column(Numeric(15, 2), nullable=False, server_default="0")
    loan_installment = Column(Numeric(15, 2), nullable=False, server_default="0")
    other_deductions = Column(Numeric(15, 2), nullable=False, server_default="0")
    total_deductions = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Step 8: Net ──────────────────────────────────────────────────────
    net_salary = Column(Numeric(15, 2), nullable=False)

    # ── Step 9: Employer charges ─────────────────────────────────────────
    cnas_employer_amount = Column(Numeric(15, 2), nullable=False)
    formation_contribution = Column(Numeric(15, 2), nullable=False)
    apprentissage_contribution = Column(Numeric(15, 2), nullable=False)
    total_employer_cost = Column(Numeric(15, 2), nullable=False)

    # ── Step 10: Status ──────────────────────────────────────────────────
    # CALCULATED, VERIFIED, APPROVED_DRH, APPROVED_DG, APPROVED_PDG, PAID
    status = Column(String(20), nullable=False, server_default="'CALCULATED'")

    # ── SPI score that fed prime_rendement ───────────────────────────────
    spi_score = Column(Numeric(5, 2), nullable=True)

    # ── Accounting link ──────────────────────────────────────────────────
    journal_entry_id = Column(
        UUID(as_uuid=True), ForeignKey("journal_entry.id", ondelete="SET NULL"),
        nullable=True,
    )

    employee = relationship("Employee")

    def __repr__(self):
        return (
            f"<Payslip {self.period_year}-{self.period_month:02d} "
            f"gross={self.gross_salary} net={self.net_salary} {self.status}>"
        )
