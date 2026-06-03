"""
GFI v7.0 — Onboarding: RecruitmentRequest, Candidate, CandidateTest,
InterviewEvaluation, OnboardingChecklist, EquipmentAssignment.

5-phase workflow: Need -> Sourcing -> Tests -> Documentation -> Access.
Blocking conditions at every transition.
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class RecruitmentRequest(GFIBase, Base):
    """F-REC-001: hiring need with 13 validated fields."""

    __tablename__ = "recruitment_request"

    position_title = Column(String(255), nullable=False)
    department_id = Column(
        UUID(as_uuid=True), ForeignKey("department.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    job_position_id = Column(
        UUID(as_uuid=True), ForeignKey("job_position.id", ondelete="SET NULL"),
        nullable=True,
    )
    justification = Column(Text, nullable=False)
    contract_type = Column(String(20), nullable=False)
    cdd_reason = Column(Text, nullable=True)
    desired_start_date = Column(Date, nullable=False)
    salary_min = Column(Numeric(15, 2), nullable=False)
    salary_max = Column(Numeric(15, 2), nullable=False)
    num_positions = Column(Integer, nullable=False, server_default="1")
    required_skills = Column(JSONB, nullable=True)
    job_description_url = Column(Text, nullable=True)
    priority = Column(String(20), nullable=False, server_default="'NORMAL'")

    requested_by = Column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=False,
    )

    # ── Validation chain ─────────────────────────────────────────────────
    # BROUILLON, SOUMISE, VALIDEE_RECRUTEMENT, VALIDEE_DRH,
    # VALIDEE_DG, EN_COURS, POURVUE, ANNULEE
    status = Column(String(30), nullable=False, server_default="'BROUILLON'")
    validated_recrutement_by = Column(UUID(as_uuid=True), nullable=True)
    validated_drh_by = Column(UUID(as_uuid=True), nullable=True)
    validated_dg_by = Column(UUID(as_uuid=True), nullable=True)
    requires_dg_approval = Column(Boolean, nullable=False, server_default="false")

    def __repr__(self):
        return f"<RecruitmentRequest {self.position_title} {self.status}>"


class Candidate(GFIBase, Base):
    """Applicant in the recruitment pipeline."""

    __tablename__ = "candidate"

    recruitment_request_id = Column(
        UUID(as_uuid=True), ForeignKey("recruitment_request.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(30), nullable=True)

    cv_url = Column(Text, nullable=True)
    cv_extracted_data = Column(JSONB, nullable=True)
    cv_similarity_score = Column(Numeric(5, 2), nullable=True)

    source = Column(String(50), nullable=True)
    # EMPLOITIC, EMPLOI_PARTNER, LINKEDIN, CANDIDATURE_SPONTANEE

    # ── Pipeline status ──────────────────────────────────────────────────
    # RECU, PRESELECTIONNEE, TESTS_EN_COURS, TESTE, ENTRETIEN_EN_COURS,
    # ENTRETIEN_FAIT, SELECTIONNE, REJETE, EMBAUCHE
    status = Column(String(30), nullable=False, server_default="'RECU'")
    rejection_reason = Column(Text, nullable=True)

    # ── Test scores ──────────────────────────────────────────────────────
    psychometric_score = Column(Numeric(5, 2), nullable=True)
    technical_score = Column(Numeric(5, 2), nullable=True)
    interview_score = Column(Numeric(5, 2), nullable=True)

    # ── Final ────────────────────────────────────────────────────────────
    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self):
        return f"<Candidate {self.first_name} {self.last_name} {self.status}>"


class OnboardingChecklist(GFIBase, Base):
    """Tracks mandatory document verification for new hire."""

    __tablename__ = "onboarding_checklist"

    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    document_code = Column(String(20), nullable=False)
    document_name = Column(String(255), nullable=False)
    is_mandatory = Column(Boolean, nullable=False, server_default="true")

    # PENDING, UPLOADED, VERIFIED, REJECTED
    status = Column(String(20), nullable=False, server_default="'PENDING'")
    file_url = Column(Text, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(UUID(as_uuid=True), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # ── OCR verification results ─────────────────────────────────────────
    ocr_result = Column(JSONB, nullable=True)
    ocr_passed = Column(Boolean, nullable=True)

    # ── Relance tracking ─────────────────────────────────────────────────
    relance_count = Column(Integer, nullable=False, server_default="0")
    last_relance_at = Column(DateTime(timezone=True), nullable=True)

    employee = relationship("Employee")

    def __repr__(self):
        return f"<OnboardingChecklist {self.document_code} {self.status}>"


class EquipmentAssignment(GFIBase, Base):
    """Equipment assigned to employee at onboarding."""

    __tablename__ = "equipment_assignment"

    employee_id = Column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    equipment_type = Column(String(50), nullable=False)
    equipment_description = Column(String(255), nullable=False)
    serial_number = Column(String(100), nullable=True)
    assigned_date = Column(Date, nullable=True)

    # ASSIGNE, EN_ATTENTE_STOCK, RESTITUE
    status = Column(String(20), nullable=False, server_default="'EN_ATTENTE_STOCK'")
    bon_sortie_ref = Column(String(50), nullable=True)
    bon_sortie_signed = Column(Boolean, nullable=False, server_default="false")
    restitution_date = Column(Date, nullable=True)

    employee = relationship("Employee")

    def __repr__(self):
        return f"<EquipmentAssignment {self.equipment_type} {self.status}>"
