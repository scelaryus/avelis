"""GFI Platform - Graph definitions for all workflow types.

Graph A: Document → OCR → Extraction → Ledger → Controls → Commit
Graph B: ADV → Accounting
Graph C: HR → Cost center
"""
from app.orchestrator.engine import OrchestrationGraph
from app.agents import (
    ingest, render, segment, text_layer, ocr, ocr_merge,
    doc_type_router, extraction, normalization, verification,
    matching, ledger_structuring, anomaly,
    cost_center, packaging, commit, module_router,
    adv_agents, hr_agents,
)


def build_document_to_ledger_graph() -> OrchestrationGraph:
    """Graph A — full document-to-ledger pipeline."""
    g = OrchestrationGraph("document_to_ledger")

    # Add nodes
    g.add_node("ingest", ingest.run, "Accept & hash documents")
    g.add_node("render", render.run, "Render PDF pages to images")
    g.add_node("segment", segment.run, "Detect page segments/regions")
    g.add_node("text_layer_detect", text_layer.detect, "Check for embedded text layer")
    g.add_node("text_layer_parse", text_layer.parse, "Parse embedded text to blocks")
    g.add_node("ocr", ocr.run, "Run OCR on page images", parallel_key="page")
    g.add_node("ocr_merge", ocr_merge.run, "Merge text layer + OCR blocks")
    g.add_node("doc_type_router", doc_type_router.run, "Classify document type")
    g.add_node("extraction", extraction.run, "AI extraction of entities")
    g.add_node("normalization", normalization.run, "Normalize extracted entities")
    g.add_node("verification", verification.run, "Self-check & arithmetic verification")
    g.add_node("matching", matching.run, "Match entities to DB records")
    g.add_node("ledger_structuring", ledger_structuring.run, "Build journal proposals")
    g.add_node("anomaly", anomaly.run, "Detect anomalies & fraud")
    g.add_node("cost_center", cost_center.run, "Compute cost center allocations")
    g.add_node("packaging", packaging.run, "Build submission package")
    g.add_node("commit", commit.run, "Validate & commit")
    g.add_node("module_router", module_router.run, "Route to ADV/Comptabilité/HR")

    # Wire edges (linear pipeline with branches)
    g.add_edge("ingest", "render")
    g.add_edge("render", "segment")
    g.add_edge("segment", "text_layer_detect")

    # Conditional: if text layer reliable → parse, else → OCR
    g.add_edge("text_layer_detect", "text_layer_parse",
               condition=lambda s, r: _has_text_layer(s))
    g.add_edge("text_layer_detect", "ocr",
               condition=lambda s, r: not _has_text_layer(s))

    # Both paths merge
    g.add_edge("text_layer_parse", "ocr_merge")
    g.add_edge("ocr", "ocr_merge")

    # Continue pipeline
    g.add_edge("ocr_merge", "doc_type_router")
    g.add_edge("doc_type_router", "extraction")
    g.add_edge("extraction", "normalization")
    g.add_edge("normalization", "verification")
    g.add_edge("verification", "matching")
    g.add_edge("matching", "ledger_structuring")
    g.add_edge("ledger_structuring", "anomaly")
    g.add_edge("anomaly", "cost_center")
    g.add_edge("cost_center", "packaging")
    g.add_edge("packaging", "commit")
    g.add_edge("commit", "module_router")

    g.set_entry("ingest")
    return g


def build_adv_graph() -> OrchestrationGraph:
    """Graph B — ADV → Accounting."""
    g = OrchestrationGraph("adv")

    g.add_node("adv_ingest", adv_agents.ingest, "Ingest ADV data")
    g.add_node("adv_normalize", adv_agents.normalize, "Normalize ADV terms")
    g.add_node("adv_verification", adv_agents.verify, "ADV controls")
    g.add_node("adv_ledger", adv_agents.ledger_structuring, "ADV ledger proposals")
    g.add_node("anomaly", anomaly.run, "Detect anomalies")
    g.add_node("commit", commit.run, "Validate & commit")

    g.add_edge("adv_ingest", "adv_normalize")
    g.add_edge("adv_normalize", "adv_verification")
    g.add_edge("adv_verification", "adv_ledger")
    g.add_edge("adv_ledger", "anomaly")
    g.add_edge("anomaly", "commit")

    g.set_entry("adv_ingest")
    return g


def build_hr_graph() -> OrchestrationGraph:
    """Graph C — HR → Cost center."""
    g = OrchestrationGraph("hr")

    g.add_node("hr_employee_ops", hr_agents.employee_ops, "HR employee operations")
    g.add_node("hr_payroll", hr_agents.payroll_proposal, "Generate payroll proposals")
    g.add_node("hr_verification", hr_agents.verify, "HR verification")
    g.add_node("commit", commit.run, "Validate & commit")
    g.add_node("cost_center", cost_center.run, "Cost center snapshot")

    g.add_edge("hr_employee_ops", "hr_payroll")
    g.add_edge("hr_payroll", "hr_verification")
    g.add_edge("hr_verification", "commit")
    g.add_edge("commit", "cost_center")

    g.set_entry("hr_employee_ops")
    return g


def _has_text_layer(state) -> bool:
    """Check if the workflow state indicates a reliable text layer."""
    for node_artifacts in state.artifacts.values():
        for aid in node_artifacts:
            if "text_layer" in str(aid).lower():
                return True
    return False


GRAPH_REGISTRY = {
    "document_to_ledger": build_document_to_ledger_graph,
    "adv": build_adv_graph,
    "hr": build_hr_graph,
}
