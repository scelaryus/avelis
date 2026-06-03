"""
GFI v7.0 — Offboarding: DisciplinaryCase, OffboardingProcess,
StcCalculation, HandoverItem, EquipmentRestitution.

3 triggers: resignation, termination (disciplinary), end of CDD.
STC blocked until ALL prerequisites met — no override.
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class DisciplinaryCase(GFIBase, Base):
    """Full disciplinary workflow: PV constat -> convocation -> audition -> sanction."""

    __tablename__ = "disciplinary_case"

    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── F-DIS-001: PV de constat ─────────────────────────────────────────
    infraction_date = Column(DateTime(timezone=True), nullable=False)
    infraction_location = Column(String(255), nullable=True)
    infraction_description = Column(Text, nullable=False)
    witnesses = Column(Text, nullable=True)
    evidence_urls = Column(JSONB, nullable=True)
    severity = Column(String(20), nullable=False)
    # FAUTE_LEGERE, FAUTE_GRAVE, FAUTE_LOURDE
    pv_constat_date = Column(Date, nullable=False)
    pv_constat_url = Column(Text, nullable=True)

    # ── F-DIS-002: Convocation ───────────────────────────────────────────
    convocation_date = Column(Date, nullable=True)
    audition_date = Column(DateTime(timezone=True), nullable=True)
    audition_location = Column(String(255), nullable=True)
    rights_statement_included = Column(Boolean, nullable=True)
    convocation_url = Column(Text, nullable=True)
    # Rule: audition_date must be >= pv_constat_date + 48h

    # ── F-DIS-003: PV d'audition ─────────────────────────────────────────
    employee_statements = Column(Text, nullable=True)
    questions_answers = Column(Text, nullable=True)
    assistant_name = Column(String(255), nullable=True)
    assistant_role = Column(String(100), nullable=True)
    pv_audition_url = Column(Text, nullable=True)

    # ── Council decision ─────────────────────────────────────────────────
    # AVERTISSEMENT, BLAME, MISE_A_PIED, LICENCIEMENT
    sanction = Column(String(20), nullable=True)
    mise_a_pied_days = Column(Integer, nullable=True)
    decision_date = Column(Date, nullable=True)
    decision_justification = Column(Text, nullable=True)

    # ── Triple validation ────────────────────────────────────────────────
    validated_drh = Column(UUID(as_uuid=True), nullable=True)
    validated_dg = Column(UUID(as_uuid=True), nullable=True)
    validated_pdg = Column(UUID(as_uuid=True), nullable=True)

    # ── Status ───────────────────────────────────────────────────────────
    # PV_CONSTAT, CONVOQUE, AUDITION_FAITE, DECISION_PRISE, VALIDE, CLOS
    status = Column(String(20), nullable=False, server_default="'PV_CONSTAT'")

    employee = relationship("Employee")

    def __repr__(self):
        return f"<DisciplinaryCase {self.severity} {self.status}>"


class OffboardingProcess(GFIBase, Base):
    """Orchestrates the complete departure process."""

    __tablename__ = "offboarding_process"

    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    contract_id = Column(
        UUID(as_uuid=True), ForeignKey("employee_contract.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # ── Trigger ──────────────────────────────────────────────────────────
    trigger_type = Column(String(30), nullable=False)
    # DEMISSION, LICENCIEMENT_FAUTE, LICENCIEMENT_ECONOMIQUE,
    # FIN_CDD, FIN_CHANTIER, RETRAITE, DECES, ACCORD_MUTUEL
    trigger_date = Column(Date, nullable=False)
    last_working_day = Column(Date, nullable=True)
    notice_period_waived = Column(Boolean, nullable=False, server_default="false")

    # ── Checklist items (each must be True for STC) ──────────────────────
    handover_pv_signed = Column(Boolean, nullable=False, server_default="false")
    equipment_quitus_signed = Column(Boolean, nullable=False, server_default="false")
    badge_deactivated = Column(Boolean, nullable=False, server_default="false")
    badge_deactivated_at = Column(DateTime(timezone=True), nullable=True)
    digital_access_revoked = Column(Boolean, nullable=False, server_default="false")
    digital_access_revoked_at = Column(DateTime(timezone=True), nullable=True)
    stc_verified_l6 = Column(Boolean, nullable=False, server_default="false")
    stc_approved_triple = Column(Boolean, nullable=False, server_default="false")

    # ── STC link ─────────────────────────────────────────────────────────
    stc_calculation_id = Column(
        UUID(as_uuid=True), ForeignKey("stc_calculation.id", ondelete="SET NULL"),
        nullable=True,
    )
    stc_paid = Column(Boolean, nullable=False, server_default="false")
    stc_paid_at = Column(DateTime(timezone=True), nullable=True)

    # ── Status ───────────────────────────────────────────────────────────
    # INITIE, PASSATION, RESTITUTION, STC_EN_COURS, STC_APPROUVE,
    # STC_PAYE, ARCHIVE
    status = Column(String(20), nullable=False, server_default="'INITIE'")

    # ── Generated documents ──────────────────────────────────────────────
    certificat_travail_url = Column(Text, nullable=True)
    attestation_travail_url = Column(Text, nullable=True)

    employee = relationship("Employee")

    def __repr__(self):
        return f"<OffboardingProcess {self.trigger_type} {self.status}>"


class StcCalculation(GFIBase, Base):
    """Solde de Tout Compte: 6 components, full decomposition."""

    __tablename__ = "stc_calculation"

    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    offboarding_id = Column(UUID(as_uuid=True), nullable=True)

    calculation_date = Column(Date, nullable=False)

    # ── Components ───────────────────────────────────────────────────────
    last_month_salary = Column(Numeric(15, 2), nullable=False)
    days_worked = Column(Integer, nullable=True)
    leave_compensation = Column(Numeric(15, 2), nullable=False, server_default="0")
    leave_days_unused = Column(Numeric(5, 1), nullable=True)
    notice_indemnity = Column(Numeric(15, 2), nullable=False, server_default="0")
    severance_pay = Column(Numeric(15, 2), nullable=False, server_default="0")
    seniority_months = Column(Integer, nullable=True)
    thirteenth_month_prorated = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Deductions ───────────────────────────────────────────────────────
    advance_repayment = Column(Numeric(15, 2), nullable=False, server_default="0")
    loan_balance = Column(Numeric(15, 2), nullable=False, server_default="0")
    equipment_deduction = Column(Numeric(15, 2), nullable=False, server_default="0")
    other_deductions = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Totals ───────────────────────────────────────────────────────────
    gross_stc = Column(Numeric(15, 2), nullable=False)
    total_deductions = Column(Numeric(15, 2), nullable=False)
    net_stc = Column(Numeric(15, 2), nullable=False)

    # ── Verification + approval ──────────────────────────────────────────
    # CALCULATED, VERIFIED_L6, APPROVED_DRH, APPROVED_DG, APPROVED_PDG, PAID
    status = Column(String(20), nullable=False, server_default="'CALCULATED'")

    payslip_id = Column(
        UUID(as_uuid=True), ForeignKey("payslip.id", ondelete="SET NULL"),
        nullable=True,
    )

    employee = relationship("Employee")

    def __repr__(self):
        return f"<StcCalculation net={self.net_stc} {self.status}>"
