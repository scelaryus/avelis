"""GFI Platform - ResolutionAgent (patch-based).

Generates minimal patch options to fix blocking issues.
"""
import uuid
import structlog
from app.schemas.artifacts import (
    WorkflowState, NodeResult, ResolutionPatchOptions,
    ResolutionOption, PatchOperation,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)

RESOLUTION_SYSTEM_PROMPT = """You are a financial data resolution engine. Output ONLY valid JSON.
Given blocking anomalies and current artifacts, produce 2-3 minimal patch options.
Each option should contain JSON Patch operations (replace/add/remove) that fix the blocking issue.
Never invent evidence. Only re-map existing data or mark fields as "needs user input".

Output format:
{
  "blocking_anomaly_codes": ["..."],
  "options": [
    {
      "option_id": "fix_1",
      "description": "...",
      "patches": [{"op": "replace", "path": "/fields/0/value", "value": "..."}],
      "confidence": 0.0-1.0,
      "requires_user_input": false
    }
  ]
}"""


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Generate resolution patch options for blocking anomalies."""
    from sqlalchemy import select
    from app.models.core import Artifact, ArtifactType

    artifacts_created = []

    # Get anomaly reports
    anomaly_ids = state.artifacts.get("anomaly", [])
    # Also check verification
    verification_ids = state.artifacts.get("verification", [])

    blocking_anomalies = []

    for aid in anomaly_ids + verification_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == aid)
        )
        artifact = result.scalar_one_or_none()
        if not artifact:
            continue

        data = artifact.data
        if data.get("has_blocking") or data.get("status") == "BLOCK":
            # Collect blocking items
            for anomaly in data.get("anomalies", []):
                if anomaly.get("severity") == "BLOCKING":
                    blocking_anomalies.append(anomaly)
            for reason in data.get("blocking_reasons", []):
                blocking_anomalies.append({"anomaly_code": reason, "description": reason})

    if not blocking_anomalies:
        return NodeResult(status="OK", artifacts_created=[], warnings=[], errors=[])

    # Generate resolution options
    options = _generate_resolution_options(blocking_anomalies)

    patch_options = ResolutionPatchOptions(
        blocking_anomaly_codes=[a.get("anomaly_code", "UNKNOWN") for a in blocking_anomalies],
        options=options,
    )

    artifact = Artifact(
        id=uuid.uuid4(),
        tenant_id=state.tenant_id,
        workflow_id=state.workflow_id,
        artifact_type=ArtifactType.RESOLUTION_PATCH_OPTIONS,
        data=patch_options.model_dump(),
        algo_version="v3.0-resolution",
    )
    ctx.db_session.add(artifact)
    artifacts_created.append(str(artifact.id))

    await ctx.db_session.flush()
    logger.info("resolution_options_generated", blocking=len(blocking_anomalies), options=len(options))

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=[])


def _generate_resolution_options(blocking_anomalies: list[dict]) -> list[ResolutionOption]:
    """Generate deterministic resolution options based on anomaly type."""
    options = []

    for anomaly in blocking_anomalies:
        code = anomaly.get("anomaly_code", "")

        if "UNBALANCED" in code:
            options.extend(_resolve_unbalanced(anomaly))
        elif "DUPLICATE" in code:
            options.extend(_resolve_duplicate(anomaly))
        elif "NEGATIVE" in code:
            options.extend(_resolve_negative(anomaly))
        elif "MISSING_FIELDS" in code or "E_MISSING_FIELDS" in code:
            options.extend(_resolve_missing_fields(anomaly))
        elif "LOW_CONFIDENCE" in code or "E_LOW_CONFIDENCE" in code:
            options.extend(_resolve_low_confidence(anomaly))
        elif "NO_EVIDENCE" in code or "E_CRITICAL_FIELD_NO_EVIDENCE" in code:
            options.extend(_resolve_missing_evidence(anomaly))
        else:
            # Generic: request user input
            options.append(ResolutionOption(
                option_id=f"user_review_{code}",
                description=f"Request manual review for: {anomaly.get('description', code)}",
                patches=[],
                confidence=0.3,
                requires_user_input=True,
            ))

    return options[:6]  # Max 6 options


def _resolve_unbalanced(anomaly: dict) -> list[ResolutionOption]:
    details = anomaly.get("details", {})
    diff = details.get("diff", 0)
    return [
        ResolutionOption(
            option_id="adjust_rounding",
            description=f"Adjust rounding difference of {diff} to expense account",
            patches=[PatchOperation(
                op="add", path="/entries/0/lines/-",
                value={"account_code": "6586", "label": "Écart d'arrondi",
                       "debit": diff if diff > 0 else 0, "credit": abs(diff) if diff < 0 else 0}
            )],
            confidence=0.7,
            requires_user_input=False,
        ),
        ResolutionOption(
            option_id="request_correction",
            description="Request user to correct amounts manually",
            patches=[],
            confidence=0.5,
            requires_user_input=True,
        ),
    ]


def _resolve_duplicate(anomaly: dict) -> list[ResolutionOption]:
    return [
        ResolutionOption(
            option_id="confirm_not_duplicate",
            description="Confirm this is NOT a duplicate (different transaction)",
            patches=[PatchOperation(op="add", path="/decisions/-",
                                     value={"type": "override_duplicate", "confirmed": True})],
            confidence=0.5,
            requires_user_input=True,
        ),
        ResolutionOption(
            option_id="reject_duplicate",
            description="Reject as duplicate submission",
            patches=[PatchOperation(op="replace", path="/status", value="REJECTED")],
            confidence=0.6,
            requires_user_input=False,
        ),
    ]


def _resolve_negative(anomaly: dict) -> list[ResolutionOption]:
    return [
        ResolutionOption(
            option_id="abs_amounts",
            description="Convert negative amounts to absolute values",
            patches=[PatchOperation(op="replace", path="/fix_negative", value=True)],
            confidence=0.6,
            requires_user_input=False,
        ),
        ResolutionOption(
            option_id="swap_debit_credit",
            description="Swap debit/credit for negative lines",
            patches=[PatchOperation(op="replace", path="/swap_lines", value=True)],
            confidence=0.7,
            requires_user_input=False,
        ),
    ]


def _resolve_missing_fields(anomaly: dict) -> list[ResolutionOption]:
    return [
        ResolutionOption(
            option_id="fill_missing",
            description="User provides missing field values",
            patches=[],
            confidence=0.3,
            requires_user_input=True,
        ),
    ]


def _resolve_low_confidence(anomaly: dict) -> list[ResolutionOption]:
    return [
        ResolutionOption(
            option_id="accept_low_confidence",
            description="Accept values despite low OCR confidence",
            patches=[PatchOperation(op="add", path="/decisions/-",
                                     value={"type": "accept_low_confidence"})],
            confidence=0.5,
            requires_user_input=True,
        ),
        ResolutionOption(
            option_id="re_ocr",
            description="Re-run OCR with different settings",
            patches=[PatchOperation(op="replace", path="/rerun_ocr", value=True)],
            confidence=0.4,
            requires_user_input=False,
        ),
    ]


def _resolve_missing_evidence(anomaly: dict) -> list[ResolutionOption]:
    return [
        ResolutionOption(
            option_id="manual_anchor",
            description="User manually selects evidence region for critical fields",
            patches=[],
            confidence=0.4,
            requires_user_input=True,
        ),
    ]
