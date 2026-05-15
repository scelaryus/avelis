"""AI Proof Evaluator — scores task proof documents (GFI v7).

Uses the LLM agent to evaluate whether an uploaded proof document
demonstrates that the assigned task was completed satisfactorily.
Returns a score (0-100) and a textual note.

GFI v7 integration:
  - Supports both HRTask and TacheSPI models
  - For TacheSPI: sets score_qualite and valide_par_systeme fields
  - Feeds into C2 (Quality) component of SPI scoring
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Document
from app.models.hr import HRTask
from app.models.planification import TacheSPI, StatutTache
from app.storage.service import get_storage_service

logger = structlog.get_logger(__name__)

_EVAL_SYSTEM_PROMPT = """\
You are an expert Task Evaluation Agent for the GFI v7 SPI system. You receive:

1. A task description (title, description, acceptance criteria, required role,
   due date, deliverables).
2. Information about a proof document uploaded by the employee: filename,
   file type, file size, and any extracted text content.

Your job is to evaluate whether the proof adequately demonstrates that the
task was completed. Consider:
- Relevance: Does the document relate to the task described?
- Completeness: Does the proof show the task was fully done, not partially?
  Check against the acceptance criteria if provided.
- Quality: Is the output professional and well-executed?
- Timeliness: Was the proof submitted by the due date?

Return a JSON object with:
- "score": integer 0-100 (0=no evidence, 50=partial, 75=good, 90+=excellent)
- "note": a 2-3 sentence assessment in the SAME LANGUAGE as the task description
  explaining why you gave that score. Be constructive and specific.
- "system_validated": boolean — true if score >= 60 (system considers task complete)
- "quality_score": integer 0-100 — separate quality assessment for SPI C2 component

Nothing else. No markdown fences.
"""


async def evaluate_task_proof(task: HRTask, db: AsyncSession) -> tuple[float, str]:
    """Evaluate the proof document against the task requirements (HRTask).

    Returns (score, note) tuple.
    """
    if not task.proof_document_id:
        return 0.0, "Aucune preuve soumise."

    doc_result = await db.execute(
        select(Document).where(Document.id == task.proof_document_id)
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        return 0.0, "Document de preuve introuvable."

    text_content = await _read_doc_content(doc)

    task_info = (
        f"Task Title: {task.title}\n"
        f"Description: {task.description or 'N/A'}\n"
        f"Required Role: {task.required_role or 'N/A'}\n"
        f"Due Date: {task.due_date.isoformat() if task.due_date else 'N/A'}\n"
        f"Billable Value: {task.manager_final_price or task.employee_estimated_price or 'N/A'}\n"
        f"Completed At: {task.completed_at.isoformat() if task.completed_at else 'N/A'}\n"
    )

    proof_info = (
        f"Proof Document: {doc.filename}\n"
        f"File Type: {doc.mime_type}\n"
        f"File Size: {doc.file_size} bytes\n"
        f"Content/Preview:\n{text_content}\n"
    )

    return await _run_evaluation(task_info, proof_info)


async def evaluate_tache_spi_proof(
    tache: TacheSPI,
    db: AsyncSession,
) -> tuple[float, str, float, bool]:
    """Evaluate proof for a TacheSPI task (GFI v7).

    Returns (score, note, quality_score, system_validated) tuple.
    Sets tache.score_qualite and tache.valide_par_systeme.
    """
    preuves = tache.preuves or []
    if not preuves:
        return 0.0, "Aucune preuve soumise.", 0.0, False

    # Collect all proof documents
    doc_ids = [p.get("document_ged_id") for p in preuves if p.get("document_ged_id")]
    docs = []
    if doc_ids:
        doc_result = await db.execute(
            select(Document).where(Document.id.in_(doc_ids))
        )
        docs = doc_result.scalars().all()

    if not docs and not preuves:
        return 0.0, "Documents de preuve introuvables.", 0.0, False

    # Build proof info from all documents
    proof_parts = []
    for doc in docs:
        text_content = await _read_doc_content(doc)
        proof_parts.append(
            f"- {doc.filename} ({doc.mime_type}, {doc.file_size} bytes):\n  {text_content[:1000]}"
        )

    # Also include proof metadata that doesn't have GED docs
    for p in preuves:
        if not p.get("document_ged_id"):
            proof_parts.append(f"- {p.get('type_preuve', 'autre')}: uploaded {p.get('date_upload', 'N/A')}")

    livrables = tache.livrables_attendus or []
    livrables_str = ", ".join(livrables) if livrables else "N/A"

    task_info = (
        f"Task Title: {tache.titre}\n"
        f"Description: {tache.description or 'N/A'}\n"
        f"Acceptance Criteria: {tache.criteres_acceptation or 'N/A'}\n"
        f"Expected Deliverables: {livrables_str}\n"
        f"Due Date: {tache.date_fin_prevue.isoformat() if tache.date_fin_prevue else 'N/A'}\n"
        f"Actual Completion: {tache.date_fin_reelle.isoformat() if tache.date_fin_reelle else 'N/A'}\n"
        f"KPIs: {json.dumps(tache.kpis, ensure_ascii=False) if tache.kpis else 'N/A'}\n"
    )

    proof_info = f"Proof Documents ({len(docs)} files):\n" + "\n".join(proof_parts)

    score, note = await _run_evaluation(task_info, proof_info, use_extended=True)

    # Parse extended response for quality_score and system_validated
    quality_score = score  # default: same as overall score
    system_validated = score >= 60

    # Update TacheSPI fields for SPI C2 integration
    tache.score_qualite = quality_score
    tache.valide_par_systeme = system_validated

    # Mark proof as AI-validated
    for p in (tache.preuves or []):
        p["validee_ia"] = system_validated

    return score, note, quality_score, system_validated


async def _read_doc_content(doc: Document) -> str:
    """Read text content from a document."""
    try:
        storage = get_storage_service()
        content_bytes = await storage.download(doc.storage_key)
        if doc.mime_type and doc.mime_type.startswith("text"):
            return content_bytes.decode("utf-8", errors="replace")[:4000]
        else:
            return f"[Binary file: {doc.filename}, {doc.file_size} bytes, type: {doc.mime_type}]"
    except Exception as exc:
        logger.warning("proof_content_read_failed", error=str(exc))
        return f"[Could not read file content: {doc.filename}]"


async def _run_evaluation(
    task_info: str,
    proof_info: str,
    use_extended: bool = False,
) -> tuple[float, str]:
    """Run AI evaluation and return (score, note)."""
    user_prompt = f"--- TASK ---\n{task_info}\n--- PROOF ---\n{proof_info}"

    try:
        from app.services.llm_graph import invoke_json_agent
        result = await invoke_json_agent(
            system_prompt=_EVAL_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=1024,
        )
        parsed = result.get("parsed_json", {})
        score = float(parsed.get("score", 50))
        note = parsed.get("note", "Évaluation automatique sans commentaire détaillé.")
        score = max(0.0, min(100.0, score))
        return score, note
    except Exception as exc:
        logger.error("ai_proof_evaluation_failed", error=str(exc))
        return 50.0, f"Évaluation automatique échouée ({exc}). Score neutre attribué."


# Avoid circular import — only needed for TacheSPI proof evaluation
import json
