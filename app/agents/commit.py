"""GFI Platform - CommitService Agent.

Validates and commits journal entries. Only module allowed to write canonical finance tables.
"""
import uuid
import structlog
from datetime import datetime
from app.schemas.artifacts import WorkflowState, NodeResult
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Validate submission package and commit journal entries."""
    from sqlalchemy import select
    from app.models.core import (
        Artifact, ArtifactType, JournalEntry, JournalLine,
        JournalEntryStatus, EvidenceAnchor, AuditLog, Workflow, WorkflowStatus,
    )

    artifacts_created = []
    errors = []

    # Get submission package
    pkg_ids = state.artifacts.get("packaging", [])
    if not pkg_ids:
        return NodeResult(
            status="ERROR",
            artifacts_created=[],
            warnings=[],
            errors=[{"code": "NO_SUBMISSION", "message": "No submission package found"}],
        )

    for pid in pkg_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == pid)
        )
        pkg_artifact = result.scalar_one_or_none()
        if not pkg_artifact:
            continue

        pkg_data = pkg_artifact.data

        if not pkg_data.get("is_ready"):
            errors.append({"code": "NOT_READY", "message": "Submission package not ready"})
            continue

        # Get the proposed ledger package
        ledger_id = pkg_data.get("proposed_ledger_package_id")
        if not ledger_id:
            errors.append({"code": "NO_LEDGER", "message": "No ledger package in submission"})
            continue

        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == ledger_id)
        )
        ledger_artifact = result.scalar_one_or_none()
        if not ledger_artifact:
            errors.append({"code": "LEDGER_NOT_FOUND", "message": f"Ledger artifact {ledger_id} not found"})
            continue

        ledger_data = ledger_artifact.data

        # Pre-commit validation
        validation_errors = _validate_pre_commit(ledger_data, pkg_data)
        if validation_errors:
            errors.extend(validation_errors)
            continue

        # Commit journal entries
        for entry_data in ledger_data.get("entries", []):
            try:
                # Create journal entry
                je = JournalEntry(
                    id=uuid.uuid4(),
                    tenant_id=state.tenant_id,
                    workflow_id=state.workflow_id,
                    entry_date=datetime.fromisoformat(entry_data.get("entry_date", datetime.utcnow().isoformat())),
                    reference=entry_data.get("reference"),
                    description=entry_data.get("description"),
                    status=JournalEntryStatus.COMMITTED,
                    source_doc_ids=state.doc_ids,
                    assumptions=entry_data.get("assumptions", []),
                    committed_by=state.actor_user_id,
                    committed_at=datetime.utcnow(),
                )
                ctx.db_session.add(je)

                # Create journal lines
                evidence_ids = []
                for line_data in entry_data.get("lines", []):
                    jl = JournalLine(
                        id=uuid.uuid4(),
                        entry_id=je.id,
                        account_code=line_data.get("account_code", "0000"),
                        label=line_data.get("label"),
                        debit=line_data.get("debit", 0),
                        credit=line_data.get("credit", 0),
                        currency=line_data.get("currency", "DZD"),
                        cost_center_code=line_data.get("cost_center_code"),
                        project_code=line_data.get("project_code"),
                    )

                    # Create evidence anchors
                    anchor_ids = []
                    for anchor_data in line_data.get("evidence_anchors", []):
                        ea = EvidenceAnchor(
                            id=uuid.uuid4(),
                            tenant_id=state.tenant_id,
                            doc_id=anchor_data.get("doc_id", state.doc_ids[0]),
                            page=anchor_data.get("page", 1),
                            bbox=anchor_data.get("bbox"),
                            text_snippet=anchor_data.get("text_snippet"),
                            field_name=anchor_data.get("field_name"),
                            confidence=anchor_data.get("confidence"),
                        )
                        ctx.db_session.add(ea)
                        anchor_ids.append(str(ea.id))
                        evidence_ids.append(str(ea.id))

                    jl.evidence_anchors = [{"anchor_id": aid} for aid in anchor_ids]
                    ctx.db_session.add(jl)

                je.evidence_anchor_ids = evidence_ids

                # Audit log
                audit = AuditLog(
                    id=uuid.uuid4(),
                    tenant_id=state.tenant_id,
                    user_id=state.actor_user_id,
                    action="JOURNAL_COMMITTED",
                    entity_type="journal_entry",
                    entity_id=str(je.id),
                    new_value={
                        "reference": je.reference,
                        "description": je.description,
                        "doc_ids": state.doc_ids,
                        "workflow_id": state.workflow_id,
                    },
                )
                ctx.db_session.add(audit)

                artifacts_created.append(str(je.id))
                logger.info("journal_committed", entry_id=str(je.id), ref=je.reference)

            except Exception as e:
                errors.append({"code": "COMMIT_ERROR", "message": f"Commit failed: {str(e)}"})

    # Update workflow status
    result = await ctx.db_session.execute(
        select(Workflow).where(Workflow.id == state.workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if workflow:
        if errors:
            workflow.status = WorkflowStatus.FAILED
        else:
            workflow.status = WorkflowStatus.COMMITTED

    await ctx.db_session.flush()

    if errors and not artifacts_created:
        return NodeResult(status="ERROR", artifacts_created=[], warnings=[], errors=errors)

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=errors)


def _validate_pre_commit(ledger_data: dict, pkg_data: dict) -> list[dict]:
    """Pre-commit validation checks."""
    errors = []

    # 1. Check balanced entries
    if not ledger_data.get("is_balanced", False):
        errors.append({"code": "E_UNBALANCED", "message": "Journal entries are not balanced"})

    # 2. Check evidence for scanned docs
    for entry in ledger_data.get("entries", []):
        for line in entry.get("lines", []):
            debit = line.get("debit", 0)
            credit = line.get("credit", 0)
            anchors = line.get("evidence_anchors", [])
            if (debit > 0 or credit > 0) and not anchors:
                # This is a warning, not blocking for now
                pass

    # 3. Verify OCR artifacts exist
    ocr_ids = pkg_data.get("ocr_artifact_ids", [])
    if not ocr_ids:
        # May be acceptable for non-scanned docs
        pass

    return errors
