"""Detection Agent — Discovers entities, flows, and anomalies in data.
LangGraph graph: scan_patterns -> detect_aliases -> detect_rf3 -> detect_anomalies -> generate_findings"""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.agents.llm import get_llm


class DetectionState(TypedDict):
    input_text: str  # Text to analyze (from document, label, etc.)
    context: str  # Where this text comes from
    # Results
    detected_aliases: list[dict]
    detected_entities: list[dict]
    detected_rf3: list[dict]
    detected_anomalies: list[dict]
    findings: list[dict]
    ai_analysis: str


def detect_aliases(state: DetectionState) -> dict:
    """Pattern 1-3: Detect company/project/associate aliases."""
    llm = get_llm(temperature=0, max_tokens=500)
    prompt = f"""Analyse ce texte pour detecter des alias de projets, entreprises ou personnes du Groupe GFI.

Texte: {state['input_text'][:1500]}
Contexte: {state['context']}

Alias connus:
- Projets: FOES=EDEN, Sahel/Les Jasmins=JASMIN, 02H/Bentala/Draria=LYS, 5H/Ami Djamel=IRENE, Cheraga=AUREA, Taoura=MOSQUEE
- Personnes: Hmed=Ahmed GFI, Mouh/Moh=Mohamed GFI, Lyazid/Bouabdellah=Yazid GFI
- Entreprises: AMENFORT/SARL AMENFORT=SARL-AMF, BAYTI/Novus=EURL-BAY

Detecte tous les alias dans le texte. Reponds en JSON:
{{"aliases": [{{"text_found": "...", "canonical": "...", "type": "project|person|company", "confidence": 0.9}}]}}"""
    try:
        resp = llm.invoke(prompt)
        import json
        text = resp.content.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        data = json.loads(text)
        return {"detected_aliases": data.get("aliases", [])}
    except:
        return {"detected_aliases": []}


def detect_anomalies(state: DetectionState) -> dict:
    """Pattern 4-14: Detect financial anomalies and suspicious patterns."""
    llm = get_llm(temperature=0, max_tokens=500)
    prompt = f"""Analyse ce texte pour detecter des anomalies financieres:

Texte: {state['input_text'][:1500]}
Contexte: {state['context']}

Cherche:
- Flux inter-projets (compte 580)
- Factures RF3 fictives (meme NIF emetteur/recepteur dans le groupe)
- Avances fournisseurs (compte 409)
- Prelevements associes (compte 455)
- Montants inhabituels
- Patterns de distribution 60/20/20/0

Reponds en JSON:
{{"anomalies": [{{"type": "inter_project_flow|rf3_detected|advance|withdrawal|unusual_amount", "description": "...", "confidence": 0.8, "severity": "info|warning|critical"}}]}}"""
    try:
        resp = llm.invoke(prompt)
        import json
        text = resp.content.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        data = json.loads(text)
        return {"detected_anomalies": data.get("anomalies", [])}
    except:
        return {"detected_anomalies": []}


def generate_findings(state: DetectionState) -> dict:
    """Compile all detections into actionable findings."""
    findings = []
    for a in state.get("detected_aliases", []):
        findings.append({"type": "ALIAS", "detail": a, "action": "RESOLVE_OR_CREATE"})
    for a in state.get("detected_anomalies", []):
        findings.append({"type": "ANOMALY", "detail": a, "action": "REVIEW_REQUIRED"})
    return {"findings": findings}


def build_detection_graph():
    graph = StateGraph(DetectionState)
    graph.add_node("detect_aliases", detect_aliases)
    graph.add_node("detect_anomalies", detect_anomalies)
    graph.add_node("generate_findings", generate_findings)

    graph.add_edge(START, "detect_aliases")
    graph.add_edge("detect_aliases", "detect_anomalies")
    graph.add_edge("detect_anomalies", "generate_findings")
    graph.add_edge("generate_findings", END)

    return graph.compile()


detection_graph = build_detection_graph()


def run_detection(input_text: str, context: str = "document") -> dict:
    initial: DetectionState = {
        "input_text": input_text, "context": context,
        "detected_aliases": [], "detected_entities": [], "detected_rf3": [],
        "detected_anomalies": [], "findings": [], "ai_analysis": "",
    }
    return detection_graph.invoke(initial)
