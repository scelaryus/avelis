"""GFI Platform - VerificationAgent (self-check + arithmetic).

Validates internal consistency before matching/ledger.
Fail-closed: blocks on missing evidence or inconsistency.
"""
import uuid
import structlog
from decimal import Decimal, InvalidOperation
from app.schemas.artifacts import (
    WorkflowState, NodeResult, VerificationReport, VerificationCheck,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Run verification checks on normalized entities."""
    from sqlalchemy import select
    from app.models.core import Artifact, ArtifactType

    artifacts_created = []
    all_blocking = False

    # Get normalized entity sets
    norm_ids = state.artifacts.get("normalization", [])

    for norm_id in norm_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == norm_id)
        )
        artifact = result.scalar_one_or_none()
        if not artifact:
            continue

        data = artifact.data
        doc_id = data.get("doc_id", "")
        doc_type = data.get("doc_type", "OTHER")
        fields = data.get("fields", [])
        derived_checks = data.get("derived_checks", [])

        checks = []
        blocking_reasons = []
        warnings_list = []

        # 1. Invoice arithmetic check
        if doc_type == "INVOICE":
            check = _check_invoice_arithmetic(fields, derived_checks, ctx)
            checks.append(check)
            if check.result == "FAIL":
                blocking_reasons.append(f"E_ARITHMETIC: {check.details}")

        # 2. Mandatory fields check
        from app.agents.extraction import REQUIRED_FIELDS
        required = REQUIRED_FIELDS.get(doc_type, [])
        check = _check_mandatory_fields(fields, required)
        checks.append(check)
        if check.result == "FAIL":
            blocking_reasons.append(f"E_MISSING_FIELDS: {check.details}")

        # 3. Confidence threshold check
        threshold = ctx.settings.CONFIDENCE_GATE_THRESHOLD
        check = _check_confidence_thresholds(fields, threshold)
        checks.append(check)
        if check.result == "FAIL":
            blocking_reasons.append(f"E_LOW_CONFIDENCE: {check.details}")
        elif check.result == "WARN":
            warnings_list.append(check.details)

        # 4. Evidence anchors existence check
        check = _check_evidence_anchors(fields, doc_type)
        checks.append(check)
        if check.result == "FAIL":
            blocking_reasons.append(f"E_CRITICAL_FIELD_NO_EVIDENCE: {check.details}")

        # 5. VAT rate plausibility
        if doc_type == "INVOICE":
            check = _check_vat_plausibility(fields, ctx)
            checks.append(check)
            if check.result == "FAIL":
                blocking_reasons.append(f"E_VAT_IMPLAUSIBLE: {check.details}")

        # 6. Duplicate ref check (within document)
        check = _check_duplicate_refs(fields)
        checks.append(check)
        if check.result == "WARN":
            warnings_list.append(check.details)

        status = "BLOCK" if blocking_reasons else "PASS"
        if blocking_reasons:
            all_blocking = True

        report = VerificationReport(
            doc_id=doc_id,
            status=status,
            blocking_reasons=blocking_reasons,
            warnings=warnings_list,
            checks=checks,
        )

        ver_artifact = Artifact(
            id=uuid.uuid4(),
            tenant_id=state.tenant_id,
            workflow_id=state.workflow_id,
            doc_id=doc_id,
            artifact_type=ArtifactType.VERIFICATION_REPORT,
            data=report.model_dump(),
            algo_version="v3.0-verify",
        )
        ctx.db_session.add(ver_artifact)
        artifacts_created.append(str(ver_artifact.id))

        logger.info("verification_complete", doc_id=doc_id, status=status, checks=len(checks))

    await ctx.db_session.flush()

    if all_blocking:
        return NodeResult(
            status="BLOCK",
            artifacts_created=artifacts_created,
            warnings=[],
            errors=[{"code": "VERIFICATION_BLOCKED", "message": "One or more documents failed verification"}],
        )

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=[])


def _check_invoice_arithmetic(fields: list[dict], derived_checks: list[dict], ctx) -> VerificationCheck:
    """Check HT + TVA ≈ TTC within tolerance."""
    tolerance = ctx.settings.ROUNDING_TOLERANCE

    for check in derived_checks:
        if check.get("check") == "HT+TVA=TTC":
            if check.get("result") == "OK":
                return VerificationCheck(check_code="INVOICE_ARITHMETIC", result="OK", details="HT+TVA=TTC within tolerance")
            elif check.get("result") == "MISMATCH":
                diff = check.get("difference", "?")
                try:
                    if Decimal(str(diff)) <= Decimal(str(tolerance)):
                        return VerificationCheck(check_code="INVOICE_ARITHMETIC", result="WARN",
                                                 details=f"HT+TVA-TTC diff={diff} within tolerance")
                except (InvalidOperation, ValueError):
                    pass
                return VerificationCheck(check_code="INVOICE_ARITHMETIC", result="FAIL",
                                         details=f"HT+TVA≠TTC difference={diff}")

    return VerificationCheck(check_code="INVOICE_ARITHMETIC", result="WARN",
                             details="Could not verify arithmetic (missing values)")


def _check_mandatory_fields(fields: list[dict], required: list[str]) -> VerificationCheck:
    """Check all required fields are present."""
    field_names = {f.get("field_name") for f in fields if f.get("normalized_value") is not None}
    # Also check original_value for extraction artifacts
    for f in fields:
        if f.get("value") is not None:
            field_names.add(f.get("field_name"))

    missing = [r for r in required if r not in field_names]

    if not missing:
        return VerificationCheck(check_code="MANDATORY_FIELDS", result="OK",
                                 details="All mandatory fields present")

    if len(missing) <= 2:
        return VerificationCheck(check_code="MANDATORY_FIELDS", result="WARN",
                                 details=f"Missing optional-ish fields: {', '.join(missing)}")

    return VerificationCheck(check_code="MANDATORY_FIELDS", result="FAIL",
                             details=f"Missing required fields: {', '.join(missing)}")


def _check_confidence_thresholds(fields: list[dict], threshold: float) -> VerificationCheck:
    """Check field confidence levels."""
    low_confidence = []
    for f in fields:
        conf = f.get("confidence", 0)
        if conf is not None and conf < threshold:
            low_confidence.append(f"{f.get('field_name', '?')} ({conf:.2f})")

    if not low_confidence:
        return VerificationCheck(check_code="CONFIDENCE_GATE", result="OK",
                                 details="All fields above confidence threshold")

    if len(low_confidence) <= 2:
        return VerificationCheck(check_code="CONFIDENCE_GATE", result="WARN",
                                 details=f"Low confidence: {', '.join(low_confidence)}")

    return VerificationCheck(check_code="CONFIDENCE_GATE", result="FAIL",
                             details=f"Multiple low confidence fields: {', '.join(low_confidence)}")


def _check_evidence_anchors(fields: list[dict], doc_type: str) -> VerificationCheck:
    """Check that critical fields have evidence anchors."""
    critical_fields = {"total_ht", "total_ttc", "total_tva", "total_amount",
                       "invoice_number", "net_salary", "gross_salary", "amount"}

    missing_anchors = []
    for f in fields:
        fname = f.get("field_name", "")
        if fname in critical_fields:
            anchor = f.get("evidence_anchor")
            if not anchor:
                missing_anchors.append(fname)

    if not missing_anchors:
        return VerificationCheck(check_code="EVIDENCE_ANCHORS", result="OK",
                                 details="Critical fields have evidence anchors")

    return VerificationCheck(check_code="EVIDENCE_ANCHORS", result="FAIL",
                             details=f"Missing evidence anchors for: {', '.join(missing_anchors)}")


def _check_vat_plausibility(fields: list[dict], ctx) -> VerificationCheck:
    """Check VAT rate is plausible."""
    allowed_rates = [float(r) for r in ctx.settings.VAT_RATES_ALLOWED.split(",")]

    field_map = {}
    for f in fields:
        val = f.get("normalized_value") or f.get("value")
        field_map[f.get("field_name", "")] = val

    total_ht = field_map.get("total_ht")
    total_tva = field_map.get("total_tva")

    if total_ht and total_tva:
        try:
            ht = Decimal(str(total_ht))
            tva = Decimal(str(total_tva))
            if ht > 0:
                rate = float(tva / ht * 100)
                closest = min(allowed_rates, key=lambda r: abs(r - rate))
                if abs(rate - closest) <= 2:
                    return VerificationCheck(check_code="VAT_PLAUSIBILITY", result="OK",
                                             details=f"VAT rate ~{rate:.1f}% matches allowed {closest}%")
                else:
                    return VerificationCheck(check_code="VAT_PLAUSIBILITY", result="FAIL",
                                             details=f"VAT rate ~{rate:.1f}% not in allowed rates {allowed_rates}")
        except (InvalidOperation, ValueError, ZeroDivisionError):
            pass

    return VerificationCheck(check_code="VAT_PLAUSIBILITY", result="WARN",
                             details="Cannot compute VAT rate")


def _check_duplicate_refs(fields: list[dict]) -> VerificationCheck:
    """Check for duplicate references within document."""
    refs = [f.get("value") for f in fields
            if f.get("field_name") in ("invoice_number", "payment_ref", "contract_number")
            and f.get("value")]

    if len(refs) != len(set(refs)):
        return VerificationCheck(check_code="DUPLICATE_REFS", result="WARN",
                                 details="Duplicate reference numbers found within document")

    return VerificationCheck(check_code="DUPLICATE_REFS", result="OK",
                             details="No duplicate references")
