"""Payroll Verification Agent — L2 semantic analysis of payslips.
LangGraph graph: pseudonymize -> analyze_coherence -> detect_anomalies -> generate_verdict"""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.agents.llm import get_llm


class PayrollState(TypedDict):
    # Input (already pseudonymized)
    employee_code: str  # EMPLOYEE_001 (never real name)
    entity_code: str
    department: str
    position: str
    cnas_regime: str
    salary_base: float
    prime_rendement: float
    gross: float
    cnas_employee: float
    irg_final: float
    net: float
    # Analysis results
    verdict: str  # PASS, FLAG, FAIL
    anomalies: list[dict]
    recommendation: str
    confidence: float
    error: str | None


def pseudonymize_check(state: PayrollState) -> dict:
    """Verify no personal data leaks into the state."""
    # In production: verify employee_code is pseudonymized
    if not state["employee_code"].startswith("EMP_"):
        return {"employee_code": f"EMP_{hash(state['employee_code']) % 10000:04d}"}
    return {}


def analyze_coherence(state: PayrollState) -> dict:
    """L2: LLM analyzes payslip coherence."""
    llm = get_llm(temperature=0, max_tokens=500)
    prompt = f"""Analyse ce bulletin de paie pseudonymise. Verifie la coherence globale.

Employe: {state['employee_code']}
Entite: {state['entity_code']} | Departement: {state['department']} | Poste: {state['position']}
Regime CNAS: {state['cnas_regime']}
Salaire base: {state['salary_base']:,.0f} DA
Prime rendement: {state['prime_rendement']:,.0f} DA ({state['prime_rendement']/state['salary_base']*100:.0f}% du base)
Brut: {state['gross']:,.0f} DA
CNAS salarie: {state['cnas_employee']:,.0f} DA ({state['cnas_employee']/state['gross']*100:.2f}% du brut)
IRG: {state['irg_final']:,.0f} DA
Net: {state['net']:,.0f} DA

Verifie:
1. Le salaire correspond-il au poste et departement?
2. La prime de rendement est-elle dans les limites normales (15-30%)?
3. Le taux CNAS correspond-il au regime (GENERAL=9%, BTPH=9.375%)?
4. Y a-t-il des elements inhabituels?

Reponds UNIQUEMENT en JSON:
{{"verdict": "PASS|FLAG|FAIL", "anomalies": [{{"type": "...", "severity": "low|medium|high", "description": "..."}}], "confidence": 0.9, "recommendation": "..."}}"""
    try:
        resp = llm.invoke(prompt)
        import json
        text = resp.content.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        data = json.loads(text)
        return {
            "verdict": data.get("verdict", "PASS"),
            "anomalies": data.get("anomalies", []),
            "confidence": data.get("confidence", 0.8),
            "recommendation": data.get("recommendation", ""),
        }
    except Exception as e:
        return {"verdict": "FLAG", "anomalies": [{"type": "LLM_ERROR", "severity": "low", "description": str(e)}],
                "confidence": 0.5, "recommendation": "L2 indisponible — validation manuelle requise"}


def build_payroll_graph():
    graph = StateGraph(PayrollState)
    graph.add_node("pseudonymize", pseudonymize_check)
    graph.add_node("analyze", analyze_coherence)

    graph.add_edge(START, "pseudonymize")
    graph.add_edge("pseudonymize", "analyze")
    graph.add_edge("analyze", END)

    return graph.compile()


payroll_graph = build_payroll_graph()


def run_payroll_l2(employee_code: str, entity_code: str, department: str, position: str,
                    cnas_regime: str, salary_base: float, prime_rendement: float,
                    gross: float, cnas_employee: float, irg_final: float, net: float) -> dict:
    """Run L2 semantic verification on a payslip."""
    initial: PayrollState = {
        "employee_code": f"EMP_{hash(employee_code) % 10000:04d}",
        "entity_code": entity_code, "department": department, "position": position,
        "cnas_regime": cnas_regime, "salary_base": salary_base,
        "prime_rendement": prime_rendement, "gross": gross,
        "cnas_employee": cnas_employee, "irg_final": irg_final, "net": net,
        "verdict": "", "anomalies": [], "recommendation": "", "confidence": 0, "error": None,
    }
    return payroll_graph.invoke(initial)
