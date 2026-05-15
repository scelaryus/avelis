"""GFI Platform - DocTypeRouterAgent.

Classifies document type with high confidence and routes accordingly.
"""
import uuid
import re
import structlog
from app.schemas.artifacts import (
    WorkflowState, NodeResult, DocTypeClassification,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)

# Keyword patterns for document type classification
DOC_TYPE_PATTERNS = {
    "INVOICE": [
        r"factur[e|é]", r"invoice", r"n[°o]\s*facture", r"total\s*ttc",
        r"total\s*ht", r"tva", r"montant\s*dû", r"amount\s*due",
    ],
    "RECEIPT": [
        r"re[çc]u", r"receipt", r"ticket\s*de\s*caisse", r"bon\s*de\s*caisse",
    ],
    "CONTRACT": [
        r"contrat", r"contract", r"convention", r"accord", r"agreement",
    ],
    "BANK_STATEMENT": [
        r"relev[ée]\s*bancaire", r"bank\s*statement", r"solde", r"balance",
        r"d[ée]bit", r"cr[ée]dit", r"relev[ée]\s*de\s*compte",
    ],
    "PAYROLL": [
        r"bulletin\s*de\s*paie", r"fiche\s*de\s*paie", r"payslip",
        r"salaire\s*net", r"salaire\s*brut",
    ],
    "ADV_CONTRACT": [
        r"bon\s*de\s*commande", r"purchase\s*order", r"devis", r"quotation",
    ],
    "ADV_PAYMENT": [
        r"avis\s*de\s*paiement", r"payment\s*advice", r"bordereau",
    ],
}


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Classify document type from OCR text."""
    from sqlalchemy import select
    from app.models.core import Document, Artifact, ArtifactType

    artifacts_created = []

    # Get merged OCR artifacts
    ocr_ids = state.artifacts.get("ocr_merge", [])
    if not ocr_ids:
        # Fallback to direct OCR
        ocr_ids = state.artifacts.get("ocr", []) + state.artifacts.get("text_layer_parse", [])

    # Collect full text per document
    doc_texts: dict[str, str] = {}
    for ocr_id in ocr_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == ocr_id)
        )
        artifact = result.scalar_one_or_none()
        if not artifact:
            continue
        data = artifact.data
        doc_id = data.get("doc_id", "")
        blocks = data.get("blocks", [])

        text = " ".join([b.get("text", "") for b in blocks])
        doc_texts.setdefault(doc_id, "")
        doc_texts[doc_id] += " " + text

    # Classify each document
    for doc_id, full_text in doc_texts.items():
        doc_type, confidence, explanations = _classify(full_text.lower())

        classification = DocTypeClassification(
            doc_id=doc_id,
            doc_type=doc_type,
            confidence=confidence,
            explanations=explanations,
        )

        # Update document record
        result = await ctx.db_session.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if doc:
            from app.models.core import DocType
            try:
                doc.doc_type = DocType(doc_type)
            except ValueError:
                doc.doc_type = DocType.OTHER
            doc.doc_type_confidence = confidence

        # Store classification artifact
        artifact = Artifact(
            id=uuid.uuid4(),
            tenant_id=state.tenant_id,
            workflow_id=state.workflow_id,
            doc_id=doc_id,
            artifact_type=ArtifactType.EXTRACTED_ENTITY_SET,
            data={"doc_type_classification": classification.model_dump()},
            algo_version="v3.0-keywords",
        )
        ctx.db_session.add(artifact)
        artifacts_created.append(str(artifact.id))

        logger.info("doc_classified", doc_id=doc_id, doc_type=doc_type, confidence=confidence)

    await ctx.db_session.flush()

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=[])


def _classify(text: str) -> tuple[str, float, list[str]]:
    """Classify document type based on keyword patterns."""
    scores: dict[str, float] = {}
    explanations_map: dict[str, list[str]] = {}

    for doc_type, patterns in DOC_TYPE_PATTERNS.items():
        score = 0
        matches = []
        for pattern in patterns:
            found = re.findall(pattern, text, re.IGNORECASE)
            if found:
                score += len(found)
                matches.append(f"Matched '{pattern}' {len(found)}x")

        if score > 0:
            scores[doc_type] = score
            explanations_map[doc_type] = matches

    if not scores:
        return "OTHER", 0.1, ["No keyword matches found"]

    best_type = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = min(scores[best_type] / max(total, 1) * (1 + scores[best_type] / 10), 0.99)

    return best_type, round(confidence, 3), explanations_map.get(best_type, [])
