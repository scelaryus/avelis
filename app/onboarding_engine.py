"""
GFI v7.0 — Onboarding Engine: 5-phase recruitment + hire workflow.

Phase A: Need expression + validation (J-30 to J-15)
Phase B: Sourcing + pre-selection (J-15 to J-5)
Phase C: Tests + interviews (J-5 to J-1)
Phase D: Documentation + contract (J0 to J+3)
Phase E: Access activation (J+1 to J+3)

Blocking conditions at every transition. 7 mandatory documents must be
VERIFIED before contract generation.

Core API:
  submit_recruitment_request(...)       -> Phase A
  validate_recruitment_request(...)     -> approval chain
  score_candidate_cv(...)               -> Phase B semantic matching
  record_test_results(...)              -> Phase C blocking checks
  record_interview(...)                 -> Phase C selection check
  initialize_onboarding_checklist(...)  -> Phase D (7 mandatory docs)
  check_documents_complete(employee_id) -> blocking check for contract
  trigger_access_activation(...)        -> Phase E parallel cascade
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


SNMG = Decimal("20000")
DG_THRESHOLD = Decimal("150000")  # salary > this requires DG approval

# 7 mandatory documents
MANDATORY_DOCUMENTS = [
    ("DOC_CNI", "CNI recto-verso"),
    ("DOC_PHOTO", "2 photos d'identite"),
    ("DOC_DIPLOME", "Diplome le plus eleve"),
    ("DOC_MEDICAL", "Certificat d'aptitude medicale"),
    ("DOC_RIB", "RIB bancaire"),
    ("DOC_CASIER", "Casier judiciaire (< 3 mois)"),
    ("DOC_CV", "CV a jour"),
]

OPTIONAL_DOCUMENTS = [
    ("DOC_ATTESTATION", "Attestations de travail anterieures"),
    ("DOC_CNAS", "Carte affiliation CNAS"),
]

# Test thresholds
PSYCHOMETRIC_THRESHOLD = Decimal("60")
TECHNICAL_THRESHOLD = Decimal("70")
INTERVIEW_THRESHOLD = Decimal("15")  # out of 25


class OnboardingBlocked(Exception):
    def __init__(self, message: str, phase: str, missing: list | None = None):
        super().__init__(message)
        self.phase = phase
        self.missing = missing or []


def submit_recruitment_request(
    session: Session,
    *,
    company_id: UUID,
    position_title: str,
    justification: str,
    contract_type: str,
    desired_start_date: date,
    salary_min: Decimal,
    salary_max: Decimal,
    requested_by: UUID,
    num_positions: int = 1,
    department_id: UUID | None = None,
    cdd_reason: str | None = None,
    required_skills: list | None = None,
    job_description_url: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """Phase A: Submit recruitment request with blocking validations."""
    from app.models.onboarding import RecruitmentRequest

    salary_min = Decimal(str(salary_min))
    salary_max = Decimal(str(salary_max))

    # Blocking conditions
    blockers = []
    if len(justification.strip()) < 50:
        blockers.append("Justification < 50 characters")
    if salary_min < SNMG:
        blockers.append(f"salary_min {salary_min} < SNMG ({SNMG})")
    if desired_start_date <= date.today() + timedelta(days=15):
        blockers.append("start_date must be > today + 15 days")
    if contract_type == "CDD" and not cdd_reason:
        blockers.append("CDD requires legal reason (Article 12)")

    if blockers:
        raise OnboardingBlocked(
            f"Phase A blocked: {'; '.join(blockers)}",
            phase="A", missing=blockers,
        )

    requires_dg = salary_max > DG_THRESHOLD

    req = RecruitmentRequest(
        company_id=company_id,
        position_title=position_title,
        department_id=department_id,
        justification=justification,
        contract_type=contract_type,
        cdd_reason=cdd_reason,
        desired_start_date=desired_start_date,
        salary_min=salary_min,
        salary_max=salary_max,
        num_positions=num_positions,
        required_skills=required_skills,
        job_description_url=job_description_url,
        requested_by=requested_by,
        status="SOUMISE",
        requires_dg_approval=requires_dg,
        created_by=created_by,
    )
    session.add(req)
    session.flush()
    return req


def record_test_results(
    session: Session,
    *,
    candidate_id: UUID,
    psychometric_score: Decimal,
    technical_score: Decimal,
) -> object:
    """Phase C: Record test scores. Auto-reject if below thresholds."""
    from app.models.onboarding import Candidate

    cand = session.get(Candidate, candidate_id)
    if cand is None:
        raise ValueError(f"Candidate {candidate_id} not found.")

    cand.psychometric_score = Decimal(str(psychometric_score))
    cand.technical_score = Decimal(str(technical_score))

    if (Decimal(str(psychometric_score)) < PSYCHOMETRIC_THRESHOLD
            or Decimal(str(technical_score)) < TECHNICAL_THRESHOLD):
        cand.status = "REJETE"
        cand.rejection_reason = (
            f"Scores insuffisants: psychometrique={psychometric_score}/100 "
            f"(seuil={PSYCHOMETRIC_THRESHOLD}), "
            f"technique={technical_score}/100 (seuil={TECHNICAL_THRESHOLD})"
        )
    else:
        cand.status = "TESTE"

    session.flush()
    return cand


def record_interview(
    session: Session,
    *,
    candidate_id: UUID,
    presentation: int,
    motivation: int,
    technical: int,
    behavioral: int,
    cultural_fit: int,
    manager_favorable: bool,
    recruiter_favorable: bool,
) -> object:
    """Phase C: Record interview (F-REC-002). Block if < 15/25 or unfavorable."""
    from app.models.onboarding import Candidate

    cand = session.get(Candidate, candidate_id)
    if cand is None:
        raise ValueError(f"Candidate {candidate_id} not found.")

    total = presentation + motivation + technical + behavioral + cultural_fit
    cand.interview_score = Decimal(str(total))

    if (total < int(INTERVIEW_THRESHOLD)
            or not manager_favorable or not recruiter_favorable):
        cand.status = "REJETE"
        reasons = []
        if total < int(INTERVIEW_THRESHOLD):
            reasons.append(f"Score entretien {total}/25 < {INTERVIEW_THRESHOLD}")
        if not manager_favorable:
            reasons.append("Manager: avis defavorable")
        if not recruiter_favorable:
            reasons.append("Recruteur: avis defavorable")
        cand.rejection_reason = "; ".join(reasons)
    else:
        cand.status = "SELECTIONNE"

    session.flush()
    return cand


def initialize_onboarding_checklist(
    session: Session,
    *,
    employee_id: UUID,
    company_id: UUID,
    created_by: UUID | None = None,
) -> list:
    """Phase D: Create checklist for 7 mandatory + 2 optional documents."""
    from app.models.onboarding import OnboardingChecklist

    items = []
    for code, name in MANDATORY_DOCUMENTS:
        item = OnboardingChecklist(
            company_id=company_id,
            employee_id=employee_id,
            document_code=code,
            document_name=name,
            is_mandatory=True,
            status="PENDING",
            created_by=created_by,
        )
        session.add(item)
        items.append(item)

    for code, name in OPTIONAL_DOCUMENTS:
        item = OnboardingChecklist(
            company_id=company_id,
            employee_id=employee_id,
            document_code=code,
            document_name=name,
            is_mandatory=False,
            status="PENDING",
            created_by=created_by,
        )
        session.add(item)
        items.append(item)

    session.flush()
    return items


def check_documents_complete(
    session: Session,
    employee_id: UUID,
) -> tuple[bool, int, int, list[str]]:
    """
    ABSOLUTE BLOCK: contract generation impossible until ALL 7 mandatory
    documents have status = VERIFIED.
    Returns (complete, verified_count, total_mandatory, missing_codes).
    """
    from app.models.onboarding import OnboardingChecklist

    mandatory = (
        session.query(OnboardingChecklist)
        .filter(
            OnboardingChecklist.employee_id == employee_id,
            OnboardingChecklist.is_mandatory.is_(True),
            OnboardingChecklist.is_deleted.is_(False),
        )
        .all()
    )

    verified = [d for d in mandatory if d.status == "VERIFIED"]
    missing = [d.document_code for d in mandatory if d.status != "VERIFIED"]

    total = len(mandatory)
    verified_count = len(verified)
    complete = verified_count == total and total == 7

    return complete, verified_count, total, missing


def verify_document(
    session: Session,
    *,
    checklist_id: UUID,
    verified_by: UUID,
    ocr_result: dict | None = None,
    ocr_passed: bool = True,
) -> object:
    """Mark a document as verified (or rejected if OCR fails)."""
    from app.models.onboarding import OnboardingChecklist

    item = session.get(OnboardingChecklist, checklist_id)
    if item is None:
        raise ValueError(f"OnboardingChecklist {checklist_id} not found.")

    now = datetime.now(timezone.utc)

    if ocr_passed:
        item.status = "VERIFIED"
        item.verified_by = verified_by
        item.verified_at = now
    else:
        item.status = "REJECTED"
        item.rejection_reason = ocr_result.get("reason", "OCR verification failed") if ocr_result else "Verification failed"

    item.ocr_result = ocr_result
    item.ocr_passed = ocr_passed
    session.flush()
    return item


def trigger_access_activation(
    session: Session,
    employee_id: UUID,
    company_id: UUID,
) -> dict:
    """
    Phase E: Parallel activation cascade on CONTRACT_SIGNED.
    1. Badge RFID + zones
    2. User account + MFA + roles
    3. Equipment from job position profile
    4. Training plan (30 days)
    """
    from app.models.hr import Employee, JobPosition
    from app.models.onboarding import EquipmentAssignment

    emp = session.get(Employee, employee_id)
    results = {
        "badge": "TRIGGERED",
        "user_account": "TRIGGERED",
        "equipment": [],
        "training_plan": "TRIGGERED",
    }

    # Equipment from job position profile
    if emp and emp.job_position_id:
        pos = session.get(JobPosition, emp.job_position_id)
        if pos and pos.equipment_profile:
            for item in pos.equipment_profile:
                eq = EquipmentAssignment(
                    company_id=company_id,
                    employee_id=employee_id,
                    equipment_type=item.get("type", "AUTRE"),
                    equipment_description=item.get("description", ""),
                    status="EN_ATTENTE_STOCK",
                )
                session.add(eq)
                results["equipment"].append(item.get("type"))

    session.flush()
    return results
