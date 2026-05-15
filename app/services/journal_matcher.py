"""AI-powered journal entry ↔ document matcher.

After a journal is uploaded from CSV/Excel, this agent:
  1. Loads all uploaded scanned documents for the tenant
  2. For each journal entry, asks the LLM to find the best matching document(s)
     based on: amount, date, reference, description, emitter, etc.
  3. Returns match results + list of unmatched (unjustified) entries
"""
from __future__ import annotations

import json
import structlog
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Document, JournalEntry, JournalLine
from app.services.llm_graph import invoke_json_agent

logger = structlog.get_logger(__name__)


_SYSTEM_PROMPT = """\
You are an expert Algerian accountant AI. You are given:
- A list of JOURNAL ENTRIES (écritures comptables) just imported by the accountant,
  each with: id, date, reference, description, total_debit, line details (account codes, labels).
- A list of SCANNED DOCUMENTS already uploaded, each with: id, filename, doc_type,
  extracted_montant (amount), extracted_date, extracted_reference, extracted_emetteur (issuer),
  extracted_destinataire (recipient).

YOUR TASK: For each journal entry, find the best matching document(s) that justify it.
A match is based on:
 • Amount similarity (the journal debit/credit total ≈ document montant)
 • Date proximity (entry date ≈ document extracted_date)
 • Reference match (entry reference or description mentions the document reference/emitter)
 • Semantic relevance (a "facture fournisseur" doc matches an "achat" entry, etc.)

Return a JSON object with:
{
  "matches": [
    {
      "entry_id": "<journal_entry_id>",
      "matched_doc_ids": ["<doc_id>", ...],
      "confidence": 0.0 to 1.0,
      "reasoning": "brief explanation of why this match was made"
    },
    ...
  ],
  "unmatched_entries": [
    {
      "entry_id": "<journal_entry_id>",
      "reason": "why no match was found"
    },
    ...
  ]
}

Rules:
- Only match when you are reasonably confident (>0.3).
- A document can match multiple entries if appropriate (e.g., a bank statement covers several).
- An entry can link to multiple documents.
- If NO document matches an entry, put it in unmatched_entries.
- Be precise: prefer exact reference/amount matches over vague similarity.
- Respond ONLY with valid JSON, no extra text.
"""


async def match_entries_to_documents(
    db: AsyncSession,
    tenant_id: str,
    entry_ids: list[str],
) -> dict[str, Any]:
    """Use AI to match journal entries to scanned documents.

    Returns: {
        "matches": [...],
        "unmatched_entries": [...],
        "stats": {"total_entries", "matched", "unmatched"}
    }
    """
    # 1. Load the journal entries with their lines
    entries_data = []
    for eid in entry_ids:
        entry_result = await db.execute(
            select(JournalEntry).where(
                JournalEntry.id == eid,
                JournalEntry.tenant_id == tenant_id,
            )
        )
        entry = entry_result.scalar_one_or_none()
        if not entry:
            continue

        lines_result = await db.execute(
            select(JournalLine).where(JournalLine.entry_id == eid).order_by(JournalLine.line_no)
        )
        lines = lines_result.scalars().all()

        total_debit = sum(float(l.debit or 0) for l in lines)
        total_credit = sum(float(l.credit or 0) for l in lines)

        entries_data.append({
            "id": str(entry.id),
            "date": entry.entry_date.strftime("%Y-%m-%d") if entry.entry_date else None,
            "reference": entry.reference,
            "description": entry.description,
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
            "lines": [
                {
                    "account_code": l.account_code,
                    "label": l.label,
                    "debit": float(l.debit or 0),
                    "credit": float(l.credit or 0),
                }
                for l in lines
            ],
        })

    if not entries_data:
        return {"matches": [], "unmatched_entries": [], "stats": {"total_entries": 0, "matched": 0, "unmatched": 0}}

    # 2. Load all tenant documents
    docs_result = await db.execute(
        select(Document).where(Document.tenant_id == tenant_id)
    )
    docs = docs_result.scalars().all()

    docs_data = []
    for d in docs:
        docs_data.append({
            "id": str(d.id),
            "filename": d.filename,
            "doc_type": d.doc_type.value if d.doc_type else None,
            "extracted_montant": float(d.extracted_montant) if d.extracted_montant else None,
            "extracted_date": d.extracted_date,
            "extracted_reference": d.extracted_reference,
            "extracted_emetteur": d.extracted_emetteur,
            "extracted_destinataire": d.extracted_destinataire,
        })

    if not docs_data:
        # No documents at all → all entries are unmatched
        return {
            "matches": [],
            "unmatched_entries": [
                {"entry_id": e["id"], "reason": "Aucun document scanné disponible dans le système"}
                for e in entries_data
            ],
            "stats": {
                "total_entries": len(entries_data),
                "matched": 0,
                "unmatched": len(entries_data),
            },
        }

    # 3. Call LLM agent
    user_prompt = json.dumps({
        "journal_entries": entries_data,
        "available_documents": docs_data,
    }, ensure_ascii=False, indent=2)

    try:
        result = await invoke_json_agent(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=4096,
        )
        ai_result = result["parsed_json"]
    except Exception as exc:
        logger.error("journal_matcher_llm_error", error=str(exc))
        # Fallback: try rule-based matching
        ai_result = _rule_based_matching(entries_data, docs_data)

    matches = ai_result.get("matches", [])
    unmatched = ai_result.get("unmatched_entries", [])

    # 4. Apply matches — update source_doc_ids on journal entries
    matched_count = 0
    for m in matches:
        entry_id = m.get("entry_id")
        doc_ids = m.get("matched_doc_ids", [])
        if not entry_id or not doc_ids:
            continue

        entry_result = await db.execute(
            select(JournalEntry).where(
                JournalEntry.id == entry_id,
                JournalEntry.tenant_id == tenant_id,
            )
        )
        entry = entry_result.scalar_one_or_none()
        if entry:
            existing = entry.source_doc_ids or []
            merged = list(set(existing + doc_ids))
            entry.source_doc_ids = merged
            matched_count += 1

    await db.flush()

    return {
        "matches": matches,
        "unmatched_entries": unmatched,
        "stats": {
            "total_entries": len(entries_data),
            "matched": matched_count,
            "unmatched": len(unmatched),
        },
    }


def _rule_based_matching(
    entries: list[dict],
    docs: list[dict],
) -> dict[str, Any]:
    """Simple rule-based fallback when LLM is not available."""
    matches = []
    unmatched = []

    for entry in entries:
        best_doc = None
        best_score = 0.0
        entry_amount = entry["total_debit"]
        entry_ref = (entry.get("reference") or "").lower()
        entry_desc = (entry.get("description") or "").lower()

        for doc in docs:
            score = 0.0
            doc_amount = doc.get("extracted_montant")
            doc_ref = (doc.get("extracted_reference") or "").lower()
            doc_emetteur = (doc.get("extracted_emetteur") or "").lower()

            # Amount match (±5% tolerance)
            if doc_amount and entry_amount > 0:
                ratio = doc_amount / entry_amount if entry_amount > 0 else 0
                if 0.95 <= ratio <= 1.05:
                    score += 0.5
                elif 0.8 <= ratio <= 1.2:
                    score += 0.2

            # Reference match
            if doc_ref and (doc_ref in entry_ref or doc_ref in entry_desc):
                score += 0.3
            if entry_ref and (entry_ref in doc_ref):
                score += 0.3

            # Emitter in description
            if doc_emetteur and doc_emetteur in entry_desc:
                score += 0.2

            if score > best_score:
                best_score = score
                best_doc = doc

        if best_doc and best_score >= 0.3:
            matches.append({
                "entry_id": entry["id"],
                "matched_doc_ids": [best_doc["id"]],
                "confidence": round(min(best_score, 1.0), 2),
                "reasoning": f"Correspondance règle: score={best_score:.2f}",
            })
        else:
            unmatched.append({
                "entry_id": entry["id"],
                "reason": "Aucune correspondance suffisante trouvée (score < 0.3)",
            })

    return {"matches": matches, "unmatched_entries": unmatched}
