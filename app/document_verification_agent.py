"""
GFI v7.0 — AI Document Verification Agent.

When a formulaire response includes proof documents (certificates, PVs,
medical attestations, contracts, etc.), this agent automatically verifies
them for conformity BEFORE the response is accepted.

The agent:
  1. Reads the document (PDF/image via Claude's vision capabilities)
  2. Checks it against the formulaire's required field definitions
  3. Returns a structured conformity assessment
  4. Flags issues for human review — NEVER auto-rejects without explanation

Verification statuses:
  CONFORME        — document passes all checks
  NON_CONFORME    — document fails one or more checks (details provided)
  NEEDS_REVIEW    — agent is uncertain, escalates to human reviewer

The agent assists decision-making but does NOT make final decisions.
A human (DAF or assigned reviewer) always has the last word.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class VerificationStatus(Enum):
    PENDING = "PENDING"
    CONFORME = "CONFORME"
    NON_CONFORME = "NON_CONFORME"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class ConformityCheck:
    """A single conformity criterion and its result."""

    criterion: str
    passed: bool
    detail: str
    severity: str = "INFO"  # INFO, WARNING, CRITICAL


@dataclass
class VerificationResult:
    """Complete verification result for a document."""

    status: VerificationStatus
    checks: list[ConformityCheck] = field(default_factory=list)
    summary: str = ""
    extracted_fields: dict = field(default_factory=dict)
    confidence: float = 0.0
    raw_analysis: str = ""


# ── Conformity rules per formulaire category ────────────────────────────────

VERIFICATION_RULES: dict[str, list[dict]] = {
    # Medical certificates (congé maladie, maternité)
    "F-CON-001:maladie": [
        {"criterion": "Document is a medical certificate",
         "check": "contains_medical_header"},
        {"criterion": "Doctor name and stamp are visible",
         "check": "has_doctor_signature"},
        {"criterion": "Patient name matches employee",
         "check": "patient_name_match"},
        {"criterion": "Dates of rest period are specified",
         "check": "has_date_range"},
        {"criterion": "Duration is consistent with leave request",
         "check": "duration_match"},
    ],
    "F-CON-001:maternite": [
        {"criterion": "CNAS maternity attestation present",
         "check": "is_cnas_attestation"},
        {"criterion": "Expected delivery date specified",
         "check": "has_delivery_date"},
        {"criterion": "Employee name matches",
         "check": "patient_name_match"},
    ],
    "F-CON-001:deces": [
        {"criterion": "Document is a death certificate",
         "check": "is_death_certificate"},
        {"criterion": "Deceased name is specified",
         "check": "has_deceased_name"},
        {"criterion": "Relationship to employee can be inferred",
         "check": "has_relationship_info"},
    ],
    "F-CON-001:mariage": [
        {"criterion": "Document is a marriage certificate",
         "check": "is_marriage_certificate"},
        {"criterion": "Employee name appears on certificate",
         "check": "employee_name_present"},
        {"criterion": "Marriage date is specified",
         "check": "has_date"},
    ],
    # Recruitment evaluation grid
    "F-REC-002": [
        {"criterion": "All 5 criteria are scored 1-5",
         "check": "has_complete_scores"},
        {"criterion": "Recommendation is favorable or unfavorable",
         "check": "has_recommendation"},
    ],
    # Disciplinary PV
    "F-DIS-001": [
        {"criterion": "Date, time, and place of infraction specified",
         "check": "has_datetime_place"},
        {"criterion": "Fault description is present and detailed",
         "check": "has_fault_description"},
        {"criterion": "Witnesses listed (if any)",
         "check": "has_witnesses_section"},
        {"criterion": "Evidence is attached or referenced",
         "check": "has_evidence_reference"},
    ],
    # Audition convocation (48h rule)
    "F-DIS-002": [
        {"criterion": "Audition date is at least 48h after PV date",
         "check": "48h_rule_respected"},
        {"criterion": "Employee rights statement is included",
         "check": "has_rights_statement"},
    ],
    # Expense report
    "F-MIS-002": [
        {"criterion": "Each expense line has date, description, amount",
         "check": "expense_lines_complete"},
        {"criterion": "Justification scans are referenced",
         "check": "has_justification_refs"},
        {"criterion": "Total matches sum of lines",
         "check": "total_matches_sum"},
    ],
    # Reception discrepancy report
    "F-INV-001": [
        {"criterion": "Each item has qty ordered vs qty received",
         "check": "has_qty_comparison"},
        {"criterion": "Reason selected from dropdown for each discrepancy",
         "check": "has_reason_codes"},
        {"criterion": "Photo evidence attached for damaged items",
         "check": "has_photo_evidence"},
    ],
    # CTC submission
    "F-CTC-001": [
        {"criterion": "Structure plans are included",
         "check": "has_structure_plans"},
        {"criterion": "Calculation notes present",
         "check": "has_calculation_notes"},
        {"criterion": "Vulnerability PV present (mandatory since décret 24-247)",
         "check": "has_vulnerability_pv"},
    ],
}


def _build_verification_prompt(
    formulaire_code: str,
    field_context: dict,
    rules: list[dict],
) -> str:
    """Build the prompt for Claude to verify the document."""
    rules_text = "\n".join(
        f"  {i+1}. {r['criterion']}" for i, r in enumerate(rules)
    )

    return f"""You are a document verification agent for GFI v7.0, an ERP system
for a real estate group in Algeria. Your job is to check if uploaded proof
documents conform to the requirements of formulaire {formulaire_code}.

CONTEXT:
{json.dumps(field_context, ensure_ascii=False, indent=2)}

CONFORMITY CRITERIA TO CHECK:
{rules_text}

INSTRUCTIONS:
1. Examine the document carefully.
2. For EACH criterion, determine if it passes or fails.
3. Extract any relevant fields (names, dates, amounts) you can read.
4. If you cannot determine a criterion with confidence, mark it as NEEDS_REVIEW.
5. Be thorough but fair — flag real issues, not minor formatting differences.
6. For Algerian administrative documents, accept both Arabic and French.

RESPOND WITH VALID JSON ONLY:
{{
  "status": "CONFORME" | "NON_CONFORME" | "NEEDS_REVIEW",
  "confidence": 0.0 to 1.0,
  "summary": "brief overall assessment",
  "checks": [
    {{
      "criterion": "exact criterion text",
      "passed": true/false/null,
      "detail": "explanation",
      "severity": "INFO" | "WARNING" | "CRITICAL"
    }}
  ],
  "extracted_fields": {{
    "field_name": "extracted_value"
  }}
}}"""


async def verify_document(
    *,
    formulaire_code: str,
    document_path: str,
    mime_type: str,
    field_context: dict,
    api_key: str | None = None,
) -> VerificationResult:
    """
    Verify a proof document using Claude's vision capabilities.

    Args:
        formulaire_code: The formulaire code (e.g., "F-CON-001:maladie")
        document_path: Path to the uploaded document
        mime_type: MIME type of the document
        field_context: Context about what the document should contain
        api_key: Anthropic API key (reads from env if not provided)

    Returns:
        VerificationResult with status, checks, and extracted fields.
    """
    import os

    try:
        import anthropic
    except ImportError:
        # If anthropic SDK not installed, return NEEDS_REVIEW
        return VerificationResult(
            status=VerificationStatus.NEEDS_REVIEW,
            summary="AI verification unavailable — anthropic SDK not installed.",
            confidence=0.0,
        )

    rules = VERIFICATION_RULES.get(formulaire_code, [])
    if not rules:
        # No specific rules defined — generic document check
        rules = [
            {"criterion": "Document is readable and not blank",
             "check": "is_readable"},
            {"criterion": "Document appears relevant to the formulaire",
             "check": "is_relevant"},
        ]

    prompt = _build_verification_prompt(formulaire_code, field_context, rules)

    # Read and encode the document
    doc_path = Path(document_path)
    if not doc_path.exists():
        return VerificationResult(
            status=VerificationStatus.NON_CONFORME,
            checks=[ConformityCheck(
                criterion="Document exists",
                passed=False,
                detail=f"File not found: {document_path}",
                severity="CRITICAL",
            )],
            summary="Document file not found.",
            confidence=1.0,
        )

    doc_bytes = doc_path.read_bytes()
    doc_b64 = base64.standard_b64encode(doc_bytes).decode("utf-8")

    # Determine media type for Claude API
    media_type_map = {
        "application/pdf": "application/pdf",
        "image/jpeg": "image/jpeg",
        "image/jpg": "image/jpeg",
        "image/png": "image/png",
        "image/webp": "image/webp",
    }
    claude_media_type = media_type_map.get(mime_type)

    if not claude_media_type:
        return VerificationResult(
            status=VerificationStatus.NEEDS_REVIEW,
            summary=f"Unsupported document type for AI verification: {mime_type}",
            confidence=0.0,
        )

    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return VerificationResult(
            status=VerificationStatus.NEEDS_REVIEW,
            summary="AI verification unavailable — ANTHROPIC_API_KEY not set.",
            confidence=0.0,
        )

    client = anthropic.Anthropic(api_key=key)

    # Build the message with document as image/PDF
    content = [
        {
            "type": "image" if claude_media_type.startswith("image") else "document",
            "source": {
                "type": "base64",
                "media_type": claude_media_type,
                "data": doc_b64,
            },
        },
        {"type": "text", "text": prompt},
    ]

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": content}],
        )

        raw_text = response.content[0].text
        result_data = json.loads(raw_text)

        checks = [
            ConformityCheck(
                criterion=c.get("criterion", ""),
                passed=c.get("passed"),
                detail=c.get("detail", ""),
                severity=c.get("severity", "INFO"),
            )
            for c in result_data.get("checks", [])
        ]

        status_str = result_data.get("status", "NEEDS_REVIEW")
        status = VerificationStatus[status_str]

        return VerificationResult(
            status=status,
            checks=checks,
            summary=result_data.get("summary", ""),
            extracted_fields=result_data.get("extracted_fields", {}),
            confidence=result_data.get("confidence", 0.5),
            raw_analysis=raw_text,
        )

    except json.JSONDecodeError:
        return VerificationResult(
            status=VerificationStatus.NEEDS_REVIEW,
            summary="AI response was not valid JSON — needs human review.",
            confidence=0.0,
            raw_analysis=raw_text if "raw_text" in dir() else "",
        )
    except Exception as e:
        return VerificationResult(
            status=VerificationStatus.NEEDS_REVIEW,
            summary=f"AI verification error: {e}",
            confidence=0.0,
        )


def verify_formulaire_attachments(
    session: Session,
    formulaire_id: UUID,
    *,
    api_key: str | None = None,
) -> list[dict]:
    """
    Verify ALL attachments on a formulaire. Updates each attachment's
    ai_verification_status and the formulaire's overall status.

    Returns list of {attachment_id, status, summary} dicts.

    Must be called with asyncio.run() or from an async context.
    """
    import asyncio

    from app.models.formulaire import Formulaire
    from app.models.formulaire_attachment import FormulaireAttachment

    formulaire = session.get(Formulaire, formulaire_id)
    if not formulaire:
        raise ValueError(f"Formulaire {formulaire_id} not found.")

    attachments = (
        session.query(FormulaireAttachment)
        .filter(
            FormulaireAttachment.formulaire_id == formulaire_id,
            FormulaireAttachment.is_deleted.is_(False),
        )
        .all()
    )

    if not attachments:
        return []

    results = []
    overall_status = VerificationStatus.CONFORME

    for att in attachments:
        field_context = {
            "formulaire_code": formulaire.code,
            "field_code": att.field_code,
            "trigger_context": formulaire.trigger_context,
        }

        # Determine the specific rule key
        rule_key = formulaire.code
        if att.field_code:
            rule_key = f"{formulaire.code}:{att.field_code}"

        result = asyncio.run(verify_document(
            formulaire_code=rule_key,
            document_path=att.storage_path,
            mime_type=att.mime_type,
            field_context=field_context,
            api_key=api_key,
        ))

        # Update attachment
        att.ai_verification_status = result.status.value
        att.ai_verification_result = {
            "summary": result.summary,
            "confidence": result.confidence,
            "checks": [
                {
                    "criterion": c.criterion,
                    "passed": c.passed,
                    "detail": c.detail,
                    "severity": c.severity,
                }
                for c in result.checks
            ],
            "extracted_fields": result.extracted_fields,
        }

        results.append({
            "attachment_id": att.id,
            "filename": att.filename,
            "status": result.status.value,
            "summary": result.summary,
            "confidence": result.confidence,
        })

        # Determine overall status (worst case wins)
        if result.status == VerificationStatus.NON_CONFORME:
            overall_status = VerificationStatus.NON_CONFORME
        elif (result.status == VerificationStatus.NEEDS_REVIEW
              and overall_status != VerificationStatus.NON_CONFORME):
            overall_status = VerificationStatus.NEEDS_REVIEW

    # Update formulaire overall AI status
    formulaire.ai_verification_status = overall_status.value
    formulaire.ai_verification_result = {
        "overall_status": overall_status.value,
        "attachment_results": results,
    }

    session.flush()
    return results
