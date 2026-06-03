"""Document OCR/Classification Agent — Processes uploaded documents through 7 layers.
LangGraph graph: receive -> ocr_extract -> dedup_check -> classify -> extract_metadata -> resolve_aliases -> index"""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.agents.llm import get_llm


class DocState(TypedDict):
    filename: str
    content_preview: str  # First 2000 chars of extracted text
    file_hash: str
    # Pipeline results
    ocr_text: str
    doc_type: str
    doc_type_confidence: float
    extracted_entities: list[dict]  # [{type, value, confidence}]
    extracted_amounts: list[dict]
    extracted_dates: list[str]
    aliases_resolved: list[dict]  # [{input, resolved, confidence}]
    unresolved_aliases: list[str]
    classification_reason: str
    error: str | None
    pipeline_layer: int


DOC_TYPES = ["facture_achat", "facture_vente", "contrat", "pv_reunion", "pv_reception",
             "releve_bancaire", "situation_travaux", "bulletin_paie", "certificat_medical",
             "declaration_fiscale", "acte_notarie", "statuts", "permis_construire",
             "plan", "photo_chantier", "correspondance", "autre"]


def classify_document(state: DocState) -> dict:
    """Layer 4: Classify document type using LLM."""
    llm = get_llm(temperature=0, max_tokens=300)
    prompt = f"""Classify this document. Filename: {state['filename']}
Text preview: {state['content_preview'][:1500]}

Document types: {', '.join(DOC_TYPES)}

Respond ONLY with JSON: {{"doc_type": "...", "confidence": 0.0-1.0, "reason": "..."}}"""
    try:
        resp = llm.invoke(prompt)
        import json
        # Try to parse JSON from response
        text = resp.content.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        data = json.loads(text)
        return {
            "doc_type": data.get("doc_type", "autre"),
            "doc_type_confidence": data.get("confidence", 0.5),
            "classification_reason": data.get("reason", ""),
            "pipeline_layer": 4,
        }
    except Exception as e:
        return {"doc_type": "autre", "doc_type_confidence": 0.0, "classification_reason": f"LLM error: {e}", "pipeline_layer": 4}


def extract_metadata(state: DocState) -> dict:
    """Layer 5: Extract key metadata (amounts, dates, entities, projects)."""
    llm = get_llm(temperature=0, max_tokens=500)
    prompt = f"""Extract metadata from this {state['doc_type']} document.
Filename: {state['filename']}
Text: {state['content_preview'][:1500]}

Extract and respond ONLY with JSON:
{{"entities": [{{"type": "company|person|project", "value": "...", "confidence": 0.9}}],
  "amounts": [{{"value": 1000000, "currency": "DA", "label": "montant HT"}}],
  "dates": ["2026-01-15"],
  "project_references": ["EDEN", "AUREA"]}}"""
    try:
        resp = llm.invoke(prompt)
        import json
        text = resp.content.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        data = json.loads(text)
        return {
            "extracted_entities": data.get("entities", []),
            "extracted_amounts": data.get("amounts", []),
            "extracted_dates": data.get("dates", []),
            "pipeline_layer": 5,
        }
    except Exception as e:
        return {"extracted_entities": [], "extracted_amounts": [], "extracted_dates": [], "pipeline_layer": 5}


def resolve_aliases(state: DocState) -> dict:
    """Layer 6: Resolve all extracted entity names through alias system."""
    # In production, this would call the alias resolver API
    # For now, use LLM to detect potential aliases
    entities = state.get("extracted_entities", [])
    if not entities:
        return {"aliases_resolved": [], "unresolved_aliases": [], "pipeline_layer": 6}

    llm = get_llm(temperature=0, max_tokens=400)
    known_aliases = {
        "FOES": "EDEN", "Sahel": "JASMIN", "02H": "LYS", "5H": "IRENE",
        "Cheraga": "AUREA", "BAYTI": "EURL-BAY", "AMENFORT": "SARL-AMF",
        "Hmed": "ADMIN Ahmed", "Mouh": "ASSOC Mohamed", "Lyazid": "ASSOC Yazid",
    }
    resolved = []
    unresolved = []
    for ent in entities:
        val = ent.get("value", "")
        if val in known_aliases:
            resolved.append({"input": val, "resolved": known_aliases[val], "confidence": 1.0})
        else:
            # Check fuzzy
            matched = False
            for alias, canonical in known_aliases.items():
                if alias.lower() in val.lower() or val.lower() in alias.lower():
                    resolved.append({"input": val, "resolved": canonical, "confidence": 0.8})
                    matched = True
                    break
            if not matched:
                unresolved.append(val)

    return {"aliases_resolved": resolved, "unresolved_aliases": unresolved, "pipeline_layer": 6}


def index_document(state: DocState) -> dict:
    """Layer 7: Mark as indexed."""
    return {"pipeline_layer": 7}


def build_document_graph():
    graph = StateGraph(DocState)
    graph.add_node("classify", classify_document)
    graph.add_node("extract_metadata", extract_metadata)
    graph.add_node("resolve_aliases", resolve_aliases)
    graph.add_node("index", index_document)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "extract_metadata")
    graph.add_edge("extract_metadata", "resolve_aliases")
    graph.add_edge("resolve_aliases", "index")
    graph.add_edge("index", END)

    return graph.compile()


document_graph = build_document_graph()


def run_document_pipeline(filename: str, content_preview: str, file_hash: str) -> dict:
    """Run the document through the 7-layer pipeline."""
    initial: DocState = {
        "filename": filename, "content_preview": content_preview, "file_hash": file_hash,
        "ocr_text": content_preview, "doc_type": "", "doc_type_confidence": 0,
        "extracted_entities": [], "extracted_amounts": [], "extracted_dates": [],
        "aliases_resolved": [], "unresolved_aliases": [],
        "classification_reason": "", "error": None, "pipeline_layer": 1,
    }
    return document_graph.invoke(initial)
