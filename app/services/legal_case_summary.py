"""Helpers to build AI-style summaries for legal cases from folder context."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Iterable

from app.config import get_settings
from app.services.llm_graph import invoke_json_agent

from app.models.core import Artifact, Document
from app.models.legal import LegalCase, LegalCaseFolder


def _clip(value: str, limit: int = 220) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _flatten(value, prefix: str = "") -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        lines: list[str] = []
        for key, child in value.items():
            child_prefix = f"{prefix}{key}." if prefix else f"{key}."
            lines.extend(_flatten(child, child_prefix))
        return lines
    if isinstance(value, list):
        lines: list[str] = []
        for idx, child in enumerate(value[:6]):
            lines.extend(_flatten(child, f"{prefix}{idx}."))
        return lines
    return [f"{prefix[:-1]}: {value}"] if prefix else [str(value)]


def summarize_case(
    case: LegalCase,
    folders: Iterable[LegalCaseFolder],
    documents: Iterable[Document],
    artifacts: Iterable[Artifact],
) -> dict:
    folder_list = list(folders)
    document_list = list(documents)
    artifact_list = list(artifacts)
    docs_by_folder: dict[str | None, list[Document]] = defaultdict(list)
    for document in document_list:
        docs_by_folder[getattr(document, "legal_folder_id", None)].append(document)

    artifact_snippets: dict[str, list[str]] = defaultdict(list)
    for artifact in artifact_list:
        if artifact.doc_id is None:
            continue
        flattened = _flatten(artifact.data)
        if flattened:
            artifact_snippets[artifact.doc_id].extend(flattened[:4])

    folder_summaries: list[str] = []
    for folder in sorted(folder_list, key=lambda item: (item.sort_order, item.name.lower())):
        folder_docs = docs_by_folder.get(folder.id, [])
        doc_names = ", ".join(doc.filename for doc in folder_docs[:4]) or "aucun document"
        folder_summaries.append(f"{folder.name}: {len(folder_docs)} document(s) ({doc_names})")

    extracted_points: list[str] = []
    for document in document_list[:6]:
        details = artifact_snippets.get(document.id, [])[:3]
        if details:
            extracted_points.append(f"{document.filename} — {_clip(' ; '.join(details), 240)}")
        else:
            extracted_points.append(f"{document.filename} — document disponible sans extraction détaillée.")

    headline_parts = [
        f"Dossier: {case.title}",
        f"Sens: {'contre nous' if case.direction.value == 'AGAINST_US' else 'contre des tiers'}",
        f"Statut: {case.status.value}",
    ]
    if case.opposing_party:
        headline_parts.append(f"Partie adverse: {case.opposing_party}")
    if case.court_name:
        headline_parts.append(f"Juridiction: {case.court_name}")

    summary = (
        ". ".join(headline_parts)
        + f". Le dossier contient {len(folder_list)} dossier(s) interne(s) et {len(document_list)} document(s)."
    )
    if folder_summaries:
        summary += " Répartition documentaire: " + " | ".join(folder_summaries[:6]) + "."
    if case.description:
        summary += " Contexte déclaré: " + _clip(case.description, 260)

    next_steps = [
        "Vérifier que chaque audience, mise en demeure, contrat et preuve soit rangé dans le bon dossier.",
        "Mettre à jour le statut du dossier après chaque nouvel évènement juridique.",
    ]
    if not document_list:
        next_steps.insert(0, "Ajouter les pièces principales au dossier pour permettre une synthèse plus précise.")
    elif not artifact_list:
        next_steps.insert(0, "Lancer le traitement IA des documents clés pour enrichir le résumé du dossier.")

    return {
        "summary": summary,
        "key_points": extracted_points[:8],
        "recommended_next_steps": next_steps[:4],
        "folder_count": len(folder_list),
        "document_count": len(document_list),
        "artifact_count": len(artifact_list),
        "ai_model": "heuristic-fallback",
        "context_snapshot": json.dumps({
            "folders": folder_summaries[:10],
            "documents": [doc.filename for doc in document_list[:10]],
        }, ensure_ascii=False),
    }


async def build_case_summary(
    case: LegalCase,
    folders: Iterable[LegalCaseFolder],
    documents: Iterable[Document],
    artifacts: Iterable[Artifact],
) -> dict:
    fallback = summarize_case(case, folders, documents, artifacts)
    settings = get_settings()
    if not settings.LLM_API_KEY:
        return fallback

    folder_list = list(folders)
    document_list = list(documents)
    artifact_list = list(artifacts)

    docs_by_folder: dict[str | None, list[Document]] = defaultdict(list)
    for document in document_list:
        docs_by_folder[getattr(document, "legal_folder_id", None)].append(document)

    folder_context = []
    for folder in sorted(folder_list, key=lambda item: (item.sort_order, item.name.lower())):
        folder_context.append(
            {
                "folder": folder.name,
                "description": folder.description,
                "documents": [doc.filename for doc in docs_by_folder.get(folder.id, [])[:12]],
            }
        )

    artifact_snippets = []
    for artifact in artifact_list[:24]:
        flattened = _flatten(artifact.data)
        if flattened:
            artifact_snippets.append({
                "doc_id": artifact.doc_id,
                "snippet": flattened[:6],
            })

    prompt_payload = {
        "case": {
            "title": case.title,
            "reference": case.reference,
            "direction": case.direction.value,
            "opposing_party": case.opposing_party,
            "court_name": case.court_name,
            "status": case.status.value,
            "description": case.description,
            "opened_on": case.opened_on.isoformat() if case.opened_on else None,
        },
        "folders": folder_context,
        "documents": [
            {
                "id": document.id,
                "filename": document.filename,
                "mime_type": document.mime_type,
                "created_at": document.created_at.isoformat() if document.created_at else None,
            }
            for document in document_list[:30]
        ],
        "artifact_context": artifact_snippets,
    }

    system_prompt = (
        "You summarize legal case folders for executive follow-up. "
        "Return strict JSON with keys: summary, key_points, recommended_next_steps. "
        "The summary must be in French, concise, factual, and grounded only in provided context. "
        "key_points must be an array of short French bullet strings. "
        "recommended_next_steps must be an array of short French action strings."
    )

    user_prompt = (
        "Analyse the following legal case folder context and produce an executive summary in French. "
        "Do not invent missing facts. Mention uncertainty when evidence is thin.\n\n"
        + json.dumps(prompt_payload, ensure_ascii=False)
    )

    try:
        result = await invoke_json_agent(
            system_prompt,
            user_prompt,
            temperature=min(settings.LLM_TEMPERATURE, 0.2),
            max_tokens=min(settings.LLM_MAX_TOKENS, 1200),
        )
        parsed = result["parsed_json"]
        return {
            "summary": parsed.get("summary") or fallback["summary"],
            "key_points": parsed.get("key_points") or fallback["key_points"],
            "recommended_next_steps": parsed.get("recommended_next_steps") or fallback["recommended_next_steps"],
            "folder_count": fallback["folder_count"],
            "document_count": fallback["document_count"],
            "artifact_count": fallback["artifact_count"],
            "ai_model": result.get("ai_model", settings.LLM_MODEL),
            "context_snapshot": fallback["context_snapshot"],
        }
    except Exception:
        return fallback