"""GFI Platform - ExtractionAgent (AI).

Extracts structured entities from OCR blocks + images with evidence anchors.
"""
import json
import uuid
import structlog
from app.services.llm_graph import invoke_json_agent
from app.schemas.artifacts import (
    WorkflowState, NodeResult, ExtractedEntitySet, ExtractedField,
    EvidenceAnchorSchema,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)

# Required fields by document type
REQUIRED_FIELDS = {
    "INVOICE": [
        "supplier_name", "supplier_tax_id", "invoice_number", "invoice_date",
        "total_ht", "total_tva", "total_ttc", "currency",
    ],
    "RECEIPT": [
        "vendor_name", "receipt_date", "total_amount", "currency",
    ],
    "CONTRACT": [
        "party_a", "party_b", "contract_date", "subject", "total_amount",
    ],
    "BANK_STATEMENT": [
        "bank_name", "account_number", "statement_date",
        "opening_balance", "closing_balance",
    ],
    "PAYROLL": [
        "employee_name", "period", "gross_salary", "net_salary",
    ],
    "ADV_CONTRACT": [
        "client_name", "contract_number", "date", "total_amount",
    ],
    "ADV_PAYMENT": [
        "client_name", "payment_ref", "payment_date", "amount",
    ],
    "CHEQUE": [
        "emetteur", "beneficiaire", "montant", "date", "banque", "numero_cheque",
    ],
    "DEVIS": [
        "client_name", "devis_number", "date", "total_ht", "total_tva", "total_ttc", "currency",
    ],
    "BON_COMMANDE": [
        "client_name", "commande_number", "date", "total_amount", "currency",
    ],
    "BON_LIVRAISON": [
        "client_name", "livraison_number", "date", "reference_commande",
    ],
    "QUITTANCE": [
        "emetteur", "destinataire", "montant", "date", "objet",
    ],
    "AVOIR": [
        "supplier_name", "avoir_number", "date", "total_ht", "total_tva", "total_ttc", "currency",
    ],
    "BULLETIN_PAIE": [
        "employee_name", "mois", "annee", "salaire_base", "salaire_brut",
        "salaire_net", "cnas_salarie", "irg",
    ],
    "ATTESTATION": [
        "employee_name", "objet", "date",
    ],
    "OTHER": [],
}

# Extraction prompt template
EXTRACTION_SYSTEM_PROMPT = """You are a financial document extraction engine. Output ONLY valid JSON matching the schema below. No prose outside JSON.

Schema:
{
  "doc_id": "string",
  "doc_type": "string",
  "fields": [
    {
      "field_name": "string",
      "value": "any",
      "confidence": 0.0-1.0,
      "evidence_anchor": {
        "doc_id": "string",
        "page": int,
        "bbox": [x0, y0, x1, y1],
        "text_snippet": "string"
      }
    }
  ],
  "missing_fields": [{"field_name": "string", "reason": "string"}],
  "line_items": [{"description": "string", "quantity": number, "unit_price": number, "amount": number}]
}"""

EXTRACTION_USER_PROMPT = """Extract structured entities from this {doc_type} document.

Required fields: {required_fields}

OCR blocks (text + bbox + confidence):
{ocr_blocks}

For EACH extracted field:
- Include the value exactly as found
- Set confidence (0..1)
- Include evidence_anchor with doc_id, page, bbox, and text_snippet
- If a required field is not found, list it in missing_fields with a reason

Return JSON only."""


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Extract structured entities from OCR blocks."""
    from sqlalchemy import select
    from app.models.core import Document, Artifact, ArtifactType

    artifacts_created = []
    errors = []

    # Get merged OCR artifacts
    ocr_ids = state.artifacts.get("ocr_merge", [])
    if not ocr_ids:
        ocr_ids = state.artifacts.get("ocr", [])

    # Get doc type classifications
    classification_ids = state.artifacts.get("doc_type_router", [])

    # Build OCR text map per document
    doc_ocr_data: dict[str, list[dict]] = {}
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
        page = data.get("page", 1)
        for block in blocks:
            block["_page"] = page
        doc_ocr_data.setdefault(doc_id, []).extend(blocks)

    # Get doc types
    doc_types: dict[str, str] = {}
    for cls_id in classification_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == cls_id)
        )
        artifact = result.scalar_one_or_none()
        if artifact and "doc_type_classification" in artifact.data:
            cls = artifact.data["doc_type_classification"]
            doc_types[cls["doc_id"]] = cls["doc_type"]

    # Extract per document
    for doc_id, ocr_blocks in doc_ocr_data.items():
        doc_type = doc_types.get(doc_id, "OTHER")
        required_fields = REQUIRED_FIELDS.get(doc_type, [])

        try:
            # Try AI extraction if LLM is configured
            if ctx.settings.LLM_API_KEY:
                entity_set = await _ai_extract(
                    doc_id, doc_type, required_fields, ocr_blocks, ctx
                )
            else:
                # Fallback: rule-based extraction
                entity_set = _rule_based_extract(doc_id, doc_type, required_fields, ocr_blocks)

            artifact = Artifact(
                id=uuid.uuid4(),
                tenant_id=state.tenant_id,
                workflow_id=state.workflow_id,
                doc_id=doc_id,
                artifact_type=ArtifactType.EXTRACTED_ENTITY_SET,
                data=entity_set.model_dump(),
                algo_version="v3.0",
            )
            ctx.db_session.add(artifact)
            artifacts_created.append(str(artifact.id))

            logger.info("extraction_complete", doc_id=doc_id, fields=len(entity_set.fields))

        except Exception as e:
            errors.append({"code": "EXTRACTION_ERROR", "message": f"Extraction failed for {doc_id}: {str(e)}"})

    await ctx.db_session.flush()

    if errors and not artifacts_created:
        return NodeResult(status="ERROR", artifacts_created=[], warnings=[], errors=errors)

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=errors)


async def _ai_extract(
    doc_id: str, doc_type: str, required_fields: list[str],
    ocr_blocks: list[dict], ctx: RunContext
) -> ExtractedEntitySet:
    """Extract using the shared LangChain/LangGraph LLM runtime."""

    blocks_text = json.dumps([
        {"text": b.get("text", ""), "bbox": b.get("bbox", []), "confidence": b.get("confidence", 0), "page": b.get("_page", 1)}
        for b in ocr_blocks
    ], ensure_ascii=False, indent=2)

    user_prompt = EXTRACTION_USER_PROMPT.format(
        doc_type=doc_type,
        required_fields=", ".join(required_fields),
        ocr_blocks=blocks_text,
    )

    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    result = await invoke_json_agent(
        messages[0]["content"],
        messages[1]["content"],
        temperature=ctx.settings.LLM_TEMPERATURE,
        max_tokens=ctx.settings.LLM_MAX_TOKENS,
    )
    extracted = result["parsed_json"]

    # Convert to schema
    fields = []
    for f in extracted.get("fields", []):
        anchor = None
        if f.get("evidence_anchor"):
            ea = f["evidence_anchor"]
            anchor = EvidenceAnchorSchema(
                doc_id=ea.get("doc_id", doc_id),
                page=ea.get("page", 1),
                bbox=ea.get("bbox", [0, 0, 1, 1]),
                text_snippet=ea.get("text_snippet"),
            )
        fields.append(ExtractedField(
            field_name=f["field_name"],
            value=f.get("value"),
            confidence=f.get("confidence", 0.5),
            evidence_anchor=anchor,
        ))

    return ExtractedEntitySet(
        doc_id=doc_id,
        doc_type=doc_type,
        fields=fields,
        missing_fields=extracted.get("missing_fields", []),
        line_items=extracted.get("line_items"),
    )


def _rule_based_extract(
    doc_id: str, doc_type: str, required_fields: list[str], ocr_blocks: list[dict]
) -> ExtractedEntitySet:
    """
    Rule-based extraction fallback when no LLM is configured.
    Uses keyword matching on OCR blocks.
    """
    import re

    fields = []
    missing = []
    full_text = " ".join([b.get("text", "") for b in ocr_blocks])

    # Extraction patterns per field
    patterns = {
        "supplier_name": r"(?:fournisseur|supplier|société|company)\s*[:\-]?\s*(.+?)(?:\n|$)",
        "invoice_number": r"(?:facture|invoice)\s*(?:n[°o]?|#|num[ée]ro)?\s*[:\-]?\s*([A-Z0-9\-/]+)",
        "invoice_date": r"(?:date)\s*(?:de\s*facture|facture)?\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
        "total_ht": r"(?:total\s*ht|montant\s*ht|sous[\-\s]total)\s*[:\-]?\s*([\d\s.,]+)",
        "total_tva": r"(?:tva|tax)\s*[:\-]?\s*([\d\s.,]+)",
        "total_ttc": r"(?:total\s*ttc|montant\s*ttc|net\s*[àa]\s*payer|total\s*dû)\s*[:\-]?\s*([\d\s.,]+)",
        "currency": r"(MAD|EUR|USD|DZD|DH|DA|€|\$)",
        "receipt_date": r"(?:date)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
        "total_amount": r"(?:total|montant)\s*[:\-]?\s*([\d\s.,]+)",
        "vendor_name": r"(?:vendeur|vendor|magasin|store)\s*[:\-]?\s*(.+?)(?:\n|$)",
    }

    for field_name in required_fields:
        pattern = patterns.get(field_name)
        if not pattern:
            missing.append({"field_name": field_name, "reason": "No extraction pattern defined"})
            continue

        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            # Find the OCR block containing this text for evidence anchor
            anchor = _find_evidence_anchor(doc_id, value, ocr_blocks)
            fields.append(ExtractedField(
                field_name=field_name,
                value=value,
                confidence=0.6,  # rule-based = lower confidence
                evidence_anchor=anchor,
            ))
        else:
            missing.append({"field_name": field_name, "reason": "Pattern not matched in OCR text"})

    return ExtractedEntitySet(
        doc_id=doc_id,
        doc_type=doc_type,
        fields=fields,
        missing_fields=missing,
    )


def _find_evidence_anchor(doc_id: str, value: str, ocr_blocks: list[dict]) -> EvidenceAnchorSchema | None:
    """Find the OCR block containing the extracted value."""
    value_lower = value.lower().strip()
    for block in ocr_blocks:
        block_text = block.get("text", "").lower()
        if value_lower in block_text or block_text in value_lower:
            return EvidenceAnchorSchema(
                doc_id=doc_id,
                page=block.get("_page", 1),
                bbox=block.get("bbox", [0, 0, 1, 1]),
                text_snippet=block.get("text", "")[:100],
            )
    return None
