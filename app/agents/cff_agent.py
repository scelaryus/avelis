"""CFF Agent — Detects RF3 invoices and calculates Cout Fiscal Fictif.
LangGraph graph: detect_rf3 -> validate_rates -> calculate_5_steps -> distribute -> verify_yamina"""
from typing import TypedDict, Annotated
from decimal import Decimal, ROUND_HALF_UP
from langgraph.graph import StateGraph, START, END
from app.agents.llm import get_llm

# ── State ────────────────────────────────────────────────────────────────────

class CffState(TypedDict):
    # Input
    montant_ht: float
    emitter_code: str
    receiver_code: str
    emitter_name: str
    receiver_name: str
    emitter_ibs_rate: float | None
    emitter_tap_rate: float | None
    emitter_ownership: list[dict]  # [{name, percentage}]
    # Computed
    tva: float
    tap: float
    ibs_base: float
    ibs: float
    stamp_duty: float
    cff_total: float
    distribution: list[dict]  # [{associate, pct, amount}]
    # Verification
    yamina_check: str  # PASS or FAIL
    error: str | None
    blocked: bool
    blocked_reason: str | None


# ── Nodes ────────────────────────────────────────────────────────────────────

def validate_rates(state: CffState) -> dict:
    """Check that emitter has IBS and TAP rates defined."""
    if state["emitter_ibs_rate"] is None or state["emitter_tap_rate"] is None:
        return {
            "blocked": True,
            "blocked_reason": f"Taux IBS/TAP non defini pour {state['emitter_name']}. FC-005 requis.",
            "error": "FC-005",
        }
    return {"blocked": False}


def calculate_5_steps(state: CffState) -> dict:
    """The real 5-step CFF calculation."""
    if state.get("blocked"):
        return {}
    ht = Decimal(str(state["montant_ht"]))
    ibs_rate = Decimal(str(state["emitter_ibs_rate"]))
    tap_rate = Decimal(str(state["emitter_tap_rate"]))

    def r2(v):
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Step 1: TVA
    tva = r2(ht * Decimal("19") / 100)
    # Step 2: TAP
    tap = r2(ht * tap_rate / 100)
    # Step 3: IBS base
    ibs_base = ht - tap
    # Step 4: IBS
    ibs = r2(ibs_base * ibs_rate / 100)
    # Step 5: Stamp duty
    ttc = ht + tva
    if ttc <= 20000:
        stamp = Decimal("0")
    else:
        stamp = min(r2(ttc * Decimal("2.5") / 100), Decimal("2500"))
    cff_total = tva + tap + ibs + stamp

    return {
        "tva": float(tva), "tap": float(tap),
        "ibs_base": float(ibs_base), "ibs": float(ibs),
        "stamp_duty": float(stamp), "cff_total": float(cff_total),
    }


def distribute(state: CffState) -> dict:
    """Distribute CFF using EMITTING company ownership percentages."""
    if state.get("blocked"):
        return {"distribution": []}
    cff = Decimal(str(state["cff_total"]))
    ownership = state["emitter_ownership"]
    dist = []
    distributed = Decimal("0")
    for i, o in enumerate(ownership):
        pct = Decimal(str(o["percentage"]))
        if i == len(ownership) - 1:
            amount = cff - distributed
        else:
            amount = (cff * pct / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            distributed += amount
        dist.append({
            "associate": o["name"], "pct": float(pct), "amount": float(amount),
        })
    return {"distribution": dist}


YAMINA_ZERO_ENTITIES = {"SARL-DBPI", "SARL-OC", "SARL-EP", "SARL-SEN", "EURL-BIM",
                         "SARL-M60", "SARL-ARC", "SCI-DEN", "SARL-AMF"}

def verify_yamina(state: CffState) -> dict:
    """Y5: Verify Yamina's CFF is 0 for entities where she's at 0%."""
    if state.get("blocked"):
        return {"yamina_check": "SKIPPED"}
    for d in state.get("distribution", []):
        if "yamina" in d["associate"].lower() and d["amount"] != 0:
            if state["emitter_code"] in YAMINA_ZERO_ENTITIES:
                return {
                    "yamina_check": "FAIL",
                    "blocked": True,
                    "blocked_reason": f"CRITICAL BUG Y5: Yamina CFF = {d['amount']} DA sur {state['emitter_code']}",
                    "error": "Y5_VIOLATION",
                }
    return {"yamina_check": "PASS"}


def ai_analysis(state: CffState) -> dict:
    """LLM analyzes the CFF result for anomalies."""
    if state.get("blocked"):
        return {}
    llm = get_llm(temperature=0, max_tokens=500)
    prompt = f"""Analyse ce calcul CFF (Cout Fiscal Fictif) pour une facture RF3 inter-groupe:
Emetteur: {state['emitter_name']} ({state['emitter_code']})
Recepteur: {state['receiver_name']} ({state['receiver_code']})
Montant HT: {state['montant_ht']:,.0f} DA
TVA: {state.get('tva',0):,.0f} DA | TAP: {state.get('tap',0):,.0f} DA | IBS: {state.get('ibs',0):,.0f} DA | Timbre: {state.get('stamp_duty',0):,.0f} DA
CFF Total: {state.get('cff_total',0):,.0f} DA
Distribution: {state.get('distribution',[])}

Reponds en JSON: {{"coherent": true/false, "anomalies": ["..."], "recommendation": "..."}}"""
    try:
        resp = llm.invoke(prompt)
        return {"ai_analysis": resp.content}
    except Exception as e:
        return {"ai_analysis": f"LLM unavailable: {e}"}


# ── Graph ────────────────────────────────────────────────────────────────────

def should_continue(state: CffState) -> str:
    if state.get("blocked"):
        return END
    return "calculate_5_steps"

def after_calc(state: CffState) -> str:
    if state.get("blocked"):
        return END
    return "distribute"

def build_cff_graph():
    graph = StateGraph(CffState)
    graph.add_node("validate_rates", validate_rates)
    graph.add_node("calculate_5_steps", calculate_5_steps)
    graph.add_node("distribute", distribute)
    graph.add_node("verify_yamina", verify_yamina)
    graph.add_node("ai_analysis", ai_analysis)

    graph.add_edge(START, "validate_rates")
    graph.add_conditional_edges("validate_rates", should_continue, {"calculate_5_steps": "calculate_5_steps", END: END})
    graph.add_edge("calculate_5_steps", "distribute")
    graph.add_edge("distribute", "verify_yamina")
    graph.add_conditional_edges("verify_yamina", lambda s: END if s.get("blocked") else "ai_analysis", {"ai_analysis": "ai_analysis", END: END})
    graph.add_edge("ai_analysis", END)

    return graph.compile()


# Singleton
cff_graph = build_cff_graph()


def run_cff_calculation(montant_ht: float, emitter_code: str, receiver_code: str,
                         emitter_name: str, receiver_name: str,
                         emitter_ibs_rate: float | None, emitter_tap_rate: float | None,
                         emitter_ownership: list[dict]) -> dict:
    """Run the full CFF graph and return results."""
    initial_state: CffState = {
        "montant_ht": montant_ht,
        "emitter_code": emitter_code, "receiver_code": receiver_code,
        "emitter_name": emitter_name, "receiver_name": receiver_name,
        "emitter_ibs_rate": emitter_ibs_rate, "emitter_tap_rate": emitter_tap_rate,
        "emitter_ownership": emitter_ownership,
        "tva": 0, "tap": 0, "ibs_base": 0, "ibs": 0, "stamp_duty": 0, "cff_total": 0,
        "distribution": [], "yamina_check": "", "error": None, "blocked": False, "blocked_reason": None,
    }
    result = cff_graph.invoke(initial_state)
    return result
