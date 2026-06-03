"""ADV Engagement Chain Agent — Automatic cascade after RF2 payment.
LangGraph graph: update_rf2 -> check_securized -> check_30pct_or_guarantee -> trigger_engagement -> generate_docs"""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.agents.llm import get_llm


class AdvChainState(TypedDict):
    dossier_numero: str
    type_paiement: str  # FONDS_PROPRES, CREDIT_BANCAIRE
    prix_rf1: float
    prix_rf2: float
    montant_rf2_securise: float
    total_paid: float
    fond_garantie_disponible: float
    montant_credit: float
    # Chain results
    rf2_securise: bool
    engagement_possible: bool
    blockers: list[str]
    actions_triggered: list[str]
    documents_generated: list[str]
    ai_recommendation: str


def update_rf2_status(state: AdvChainState) -> dict:
    """Step 1: Check if RF2 is now fully securized."""
    securise = state["montant_rf2_securise"] >= state["prix_rf2"]
    return {
        "rf2_securise": securise,
        "actions_triggered": ["RF2_STATUS_UPDATED"] if securise else [],
    }


def check_engagement_conditions(state: AdvChainState) -> dict:
    """Step 2: Check all engagement preconditions."""
    if not state["rf2_securise"]:
        return {
            "engagement_possible": False,
            "blockers": [f"RF2 non securise: {state['montant_rf2_securise']:,.0f}/{state['prix_rf2']:,.0f} DA"],
        }
    blockers = []
    if state["type_paiement"] == "FONDS_PROPRES":
        prix_reel = state["prix_rf1"] + state["prix_rf2"]
        required = prix_reel * 0.3
        if state["total_paid"] < required:
            blockers.append(f"30% non atteint: {state['total_paid']:,.0f}/{required:,.0f} DA")
    elif state["type_paiement"] == "CREDIT_BANCAIRE":
        if state["fond_garantie_disponible"] < state["montant_credit"]:
            blockers.append(f"Fond garantie insuffisant: {state['fond_garantie_disponible']:,.0f}/{state['montant_credit']:,.0f} DA")
    return {"engagement_possible": len(blockers) == 0, "blockers": blockers}


def trigger_engagement(state: AdvChainState) -> dict:
    """Step 3: If conditions met, trigger engagement actions."""
    if not state["engagement_possible"]:
        return {}
    actions = state.get("actions_triggered", []) + [
        "STATUS_CHANGE_ENGAGE",
        "GENERATE_DECISION_AFFECTATION",
        "GENERATE_GUIDE_TECHNIQUE",
        "GENERATE_ECHEANCIER",
        "NOTIFY_CLIENT",
        "NOTIFY_AGENT_COMMERCIAL",
    ]
    docs = ["Decision d'affectation (RF1 prix seulement)", "Guide technique client", "Echeancier de paiement"]
    if state["type_paiement"] == "CREDIT_BANCAIRE":
        actions.append("NOTIFY_BANQUE")
        docs.append("Dossier bancaire")
    return {"actions_triggered": actions, "documents_generated": docs}


def ai_recommend(state: AdvChainState) -> dict:
    """Step 4: AI generates recommendation based on chain result."""
    llm = get_llm(temperature=0, max_tokens=300)
    prompt = f"""Dossier ADV {state['dossier_numero']}:
Type: {state['type_paiement']}
RF2 securise: {state['rf2_securise']}
Engagement possible: {state['engagement_possible']}
Blockers: {state['blockers']}
Actions: {state['actions_triggered']}

Genere une recommandation courte (2-3 phrases) pour le gestionnaire ADV."""
    try:
        resp = llm.invoke(prompt)
        return {"ai_recommendation": resp.content}
    except:
        return {"ai_recommendation": "Recommandation IA indisponible"}


def build_adv_chain_graph():
    graph = StateGraph(AdvChainState)
    graph.add_node("update_rf2", update_rf2_status)
    graph.add_node("check_conditions", check_engagement_conditions)
    graph.add_node("trigger_engagement", trigger_engagement)
    graph.add_node("ai_recommend", ai_recommend)

    graph.add_edge(START, "update_rf2")
    graph.add_edge("update_rf2", "check_conditions")
    graph.add_conditional_edges("check_conditions",
        lambda s: "trigger_engagement" if s.get("engagement_possible") else "ai_recommend",
        {"trigger_engagement": "trigger_engagement", "ai_recommend": "ai_recommend"})
    graph.add_edge("trigger_engagement", "ai_recommend")
    graph.add_edge("ai_recommend", END)

    return graph.compile()


adv_chain_graph = build_adv_chain_graph()


def run_adv_chain(dossier_numero: str, type_paiement: str, prix_rf1: float, prix_rf2: float,
                   montant_rf2_securise: float, total_paid: float,
                   fond_garantie_disponible: float = 0, montant_credit: float = 0) -> dict:
    initial: AdvChainState = {
        "dossier_numero": dossier_numero, "type_paiement": type_paiement,
        "prix_rf1": prix_rf1, "prix_rf2": prix_rf2,
        "montant_rf2_securise": montant_rf2_securise, "total_paid": total_paid,
        "fond_garantie_disponible": fond_garantie_disponible, "montant_credit": montant_credit,
        "rf2_securise": False, "engagement_possible": False, "blockers": [],
        "actions_triggered": [], "documents_generated": [], "ai_recommendation": "",
    }
    return adv_chain_graph.invoke(initial)
