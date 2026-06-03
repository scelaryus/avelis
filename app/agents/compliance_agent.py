"""Compliance Agent — Analyzes contracts and operations against Algerian legal rules.
LangGraph graph: load_rules -> evaluate_each_rule -> generate_alerts -> ai_summary"""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.agents.llm import get_llm


class ComplianceState(TypedDict):
    target_type: str  # contract, employee, purchase_order
    target_data: dict
    rules_to_check: list[dict]  # [{code, description, condition}]
    results: list[dict]  # [{rule_code, status: conforme|non_conforme, detail}]
    alerts: list[dict]
    ai_summary: str
    error: str | None


ALGERIAN_RULES = [
    {"code": "ALG-CDD-24M", "description": "CDD cumule > 24 mois", "target": "employee",
     "check": lambda d: d.get("contract_type") == "CDD" and d.get("total_cdd_months", 0) > 24},
    {"code": "ALG-PAY-90J", "description": "Delai paiement fournisseur > 90 jours", "target": "purchase_order",
     "check": lambda d: d.get("payment_delay_days", 0) > 90},
    {"code": "ALG-SNMG", "description": "Salaire < SNMG 20000 DA", "target": "employee",
     "check": lambda d: d.get("salary_base", 20000) < 20000},
    {"code": "ALG-RC-FRNR", "description": "Fournisseur sans registre de commerce", "target": "purchase_order",
     "check": lambda d: not d.get("supplier_rc")},
    {"code": "ALG-CTR-EXP", "description": "Contrat expire", "target": "contract",
     "check": lambda d: d.get("is_expired", False)},
    {"code": "ALG-DEP-1M", "description": "Depense > 1M DA sans visa juridique", "target": "purchase_order",
     "check": lambda d: d.get("amount", 0) > 1000000 and not d.get("legal_visa")},
]


def load_rules(state: ComplianceState) -> dict:
    """Load applicable rules for this target type."""
    applicable = [r for r in ALGERIAN_RULES if r["target"] == state["target_type"]]
    return {"rules_to_check": [{"code": r["code"], "description": r["description"]} for r in applicable]}


def evaluate_rules(state: ComplianceState) -> dict:
    """Evaluate each rule against the target data."""
    results = []
    alerts = []
    for rule in ALGERIAN_RULES:
        if rule["target"] != state["target_type"]:
            continue
        try:
            violated = rule["check"](state["target_data"])
            status = "non_conforme" if violated else "conforme"
            results.append({"rule_code": rule["code"], "status": status, "description": rule["description"]})
            if violated:
                alerts.append({
                    "rule_code": rule["code"], "severity": "critique" if "SNMG" in rule["code"] or "EXP" in rule["code"] else "majeur",
                    "description": rule["description"], "target": str(state["target_data"].get("name", "")),
                })
        except:
            results.append({"rule_code": rule["code"], "status": "erreur", "description": rule["description"]})
    return {"results": results, "alerts": alerts}


def ai_compliance_summary(state: ComplianceState) -> dict:
    """LLM generates a compliance summary."""
    if not state.get("alerts"):
        return {"ai_summary": "Aucune non-conformite detectee."}
    llm = get_llm(temperature=0, max_tokens=300)
    prompt = f"""Resume de conformite pour {state['target_type']}:
Donnees: {state['target_data']}
Alertes: {state['alerts']}
Genere un resume en francais (2-3 phrases) avec les actions correctives prioritaires."""
    try:
        resp = llm.invoke(prompt)
        return {"ai_summary": resp.content}
    except:
        return {"ai_summary": f"{len(state['alerts'])} non-conformite(s) detectee(s). Verification manuelle requise."}


def build_compliance_graph():
    graph = StateGraph(ComplianceState)
    graph.add_node("load_rules", load_rules)
    graph.add_node("evaluate", evaluate_rules)
    graph.add_node("ai_summary", ai_compliance_summary)

    graph.add_edge(START, "load_rules")
    graph.add_edge("load_rules", "evaluate")
    graph.add_edge("evaluate", "ai_summary")
    graph.add_edge("ai_summary", END)

    return graph.compile()


compliance_graph = build_compliance_graph()


def run_compliance_check(target_type: str, target_data: dict) -> dict:
    initial: ComplianceState = {
        "target_type": target_type, "target_data": target_data,
        "rules_to_check": [], "results": [], "alerts": [], "ai_summary": "", "error": None,
    }
    return compliance_graph.invoke(initial)
