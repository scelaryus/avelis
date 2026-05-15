"""AI-powered document classifier and amount extractor.

On upload, this service:
  1. Extracts raw text from PDFs (via PyMuPDF) or sends images via vision API
  2. Sends text/image + filename + known entities/associates to the LLM
  3. Returns: doc_type, montant, date, reference, parties, entity match, reasoning
"""
from __future__ import annotations

import base64
import json
import re
import structlog
from decimal import Decimal
from typing import Optional

logger = structlog.get_logger(__name__)

# Maximum characters of extracted text to send to LLM (keeps cost down)
_MAX_TEXT_CHARS = 6000

_SYSTEM_PROMPT = """\
You are a Document Classifier for the **Groupe Dendani**, a real-estate group in Algeria.
You receive the filename, extracted text (or scanned image), and the list of known
entities/associates/projects.

Your job is to:

1. CLASSIFY the document into exactly ONE of these types:
   INVOICE, RECEIPT, CONTRACT, BANK_STATEMENT, PAYROLL, ADV_CONTRACT,
   ADV_PAYMENT, CHEQUE, BON_COMMANDE, DEVIS, AVOIR, BULLETIN_PAIE,
   QUITTANCE, ATTESTATION, BON_LIVRAISON, OTHER

   Classification guide:
   - INVOICE (facture): supplier invoices, factures fournisseur
   - RECEIPT (reçu): payment receipts, reçus de paiement
   - CONTRACT: construction contracts, service contracts, contrats
   - BANK_STATEMENT (relevé bancaire): bank statements, relevés
   - PAYROLL: payroll summaries, états de paie
   - ADV_CONTRACT: real-estate sales contracts (actes de vente)
   - ADV_PAYMENT: buyer payment receipts for property purchases
   - CHEQUE: cheque copies, chèques
   - BON_COMMANDE: purchase orders, bons de commande
   - DEVIS: quotes, devis, estimations
   - AVOIR: credit notes, avoirs
   - BULLETIN_PAIE: individual pay slips, bulletins de paie
   - QUITTANCE: quittances de loyer, discharge receipts
   - ATTESTATION: certificates, attestations (fiscal, work, etc.)
   - BON_LIVRAISON: delivery notes, bons de livraison
   - OTHER: anything that doesn't fit above

2. EXTRACT the following if present (null if not found):
   - montant_ttc: total amount including tax (number)
   - montant_ht: amount before tax (number)
   - tva: TVA/tax amount (number)
   - date: document date (YYYY-MM-DD format)
   - reference: document reference number / invoice number / cheque number
   - emetteur: the issuer / sender / supplier name
   - destinataire: the recipient / buyer / client name

3. DETECT which known entity, project, and/or associate this document relates to.
   Match the emetteur/destinataire/content against the known entities and associates.
   - entreprise_code: the code of the matching entity (e.g. "ETS-DK", "SARL-DP") or null
   - projet_code: the code of the matching project (e.g. "JASMIN", "LYS") or null
   - associe_nom: the canonical name of the matching associate (e.g. "DENDANI Ahmed") or null
   Look for company names, NIF numbers, project names/aliases, and associate names/aliases
   in the document text. If you find matches for BOTH emetteur and destinataire among the
   group entities, this is likely an inter-company (RF3) document — note this in reasoning.

4. Provide a one-sentence reasoning for the classification.

IMPORTANT:
- Amounts should be plain numbers with NO currency symbols (e.g. 150000.00)
- For cheques, the montant_ttc is the cheque amount
- For invoices, extract both HT and TTC if visible
- If the text is empty or unreadable, classify based on filename patterns
- French and Arabic text are common — handle both
- For entity/project/associate matching, be flexible with name variations and aliases

Reply with a JSON object:
{
  "doc_type": "...",
  "confidence": 0.0-1.0,
  "montant_ttc": ...,
  "montant_ht": ...,
  "tva": ...,
  "date": "...",
  "reference": "...",
  "emetteur": "...",
  "destinataire": "...",
  "entreprise_code": "..." or null,
  "projet_code": "..." or null,
  "associe_nom": "..." or null,
  "reasoning": "..."
}
No markdown fences. No extra text.
"""


def _extract_pdf_text(content: bytes) -> str:
    """Extract text from PDF using PyMuPDF (fitz). Returns first N chars."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=content, filetype="pdf")
        pages_text = []
        for page_num in range(min(doc.page_count, 5)):  # first 5 pages max
            page = doc.load_page(page_num)
            pages_text.append(page.get_text())
        doc.close()
        full = "\n---PAGE BREAK---\n".join(pages_text)
        return full[:_MAX_TEXT_CHARS]
    except Exception as exc:
        logger.warning("pdf_text_extraction_failed", error=str(exc))
        return ""


def _extract_text_from_filename(filename: str) -> dict:
    """Attempt basic classification from filename patterns alone."""
    fn_lower = filename.lower()
    hints = {}

    # Amount patterns in filenames like "facture_15000DA.pdf"
    amt_match = re.search(r'(\d[\d\s.,]*\d)\s*(?:da|dzd|eur|€)', fn_lower)
    if amt_match:
        raw = amt_match.group(1).replace(" ", "").replace(",", ".")
        try:
            hints["montant_hint"] = float(raw)
        except ValueError:
            pass

    # Doc type hints from filename
    type_hints = {
        "facture": "INVOICE",
        "invoice": "INVOICE",
        "recu": "RECEIPT",
        "receipt": "RECEIPT",
        "contrat": "CONTRACT",
        "contract": "CONTRACT",
        "cheque": "CHEQUE",
        "chèque": "CHEQUE",
        "releve": "BANK_STATEMENT",
        "relevé": "BANK_STATEMENT",
        "bon_commande": "BON_COMMANDE",
        "bon commande": "BON_COMMANDE",
        "bc_": "BON_COMMANDE",
        "devis": "DEVIS",
        "avoir": "AVOIR",
        "bulletin": "BULLETIN_PAIE",
        "fiche_paie": "BULLETIN_PAIE",
        "paie": "BULLETIN_PAIE",
        "quittance": "QUITTANCE",
        "attestation": "ATTESTATION",
        "bon_livraison": "BON_LIVRAISON",
        "bl_": "BON_LIVRAISON",
        "acte_vente": "ADV_CONTRACT",
        "acte": "ADV_CONTRACT",
    }
    for keyword, doc_type in type_hints.items():
        if keyword in fn_lower:
            hints["filename_type"] = doc_type
            break

    return hints


async def _get_reference_context(tenant_id: str) -> str:
    """Build a context block listing known entities, projects, and associates."""
    from app.database import AsyncSessionLocal
    from sqlalchemy import select, text

    lines = []
    try:
        async with AsyncSessionLocal() as db:
            # Entities
            rows = await db.execute(text(
                "SELECT code, raison_sociale, forme_juridique, statut "
                "FROM entreprises WHERE tenant_id = :tid ORDER BY code"
            ), {"tid": tenant_id})
            ents = rows.fetchall()
            if ents:
                lines.append("KNOWN ENTITIES (Groupe Dendani):")
                for e in ents:
                    lines.append(f"  - {e[0]}: {e[1]} ({e[2]}) [{e[3]}]")

            # Projects
            rows = await db.execute(text(
                "SELECT p.code, p.nom, e.code "
                "FROM projets p JOIN entreprises e ON p.entreprise_id = e.id "
                "WHERE p.tenant_id = :tid ORDER BY p.code"
            ), {"tid": tenant_id})
            projs = rows.fetchall()
            if projs:
                lines.append("\nKNOWN PROJECTS:")
                for p in projs:
                    lines.append(f"  - {p[0]}: {p[1]} (entity: {p[2]})")

            # Associates
            rows = await db.execute(text(
                "SELECT nom, prenom, ordre_priorite, est_fondateur "
                "FROM associes WHERE tenant_id = :tid ORDER BY ordre_priorite"
            ), {"tid": tenant_id})
            assocs = rows.fetchall()
            if assocs:
                lines.append("\nKNOWN ASSOCIATES:")
                for a in assocs:
                    founder = " [FONDATEUR]" if a[3] else ""
                    lines.append(f"  - {a[0]} {a[1] or ''}{founder}")

    except Exception as exc:
        logger.warning("reference_context_fetch_failed", error=str(exc))

    return "\n".join(lines)


async def classify_document(
    filename: str,
    content: bytes,
    mime_type: str,
    tenant_id: str | None = None,
) -> dict:
    """Classify a document and extract key data using AI.

    Returns dict with: doc_type, confidence, montant_ttc, montant_ht, tva,
    date, reference, emetteur, destinataire, entreprise_code, projet_code,
    associe_nom, reasoning
    """
    _IMAGE_MIMES = {
        "image/jpeg", "image/jpg", "image/png", "image/tiff",
        "image/bmp", "image/webp", "image/gif",
    }

    from app.services.llm_graph import invoke_json_agent

    # Extract text depending on type
    extracted_text = ""
    image_b64: str | None = None
    image_mime_for_vision: str | None = None

    if mime_type == "application/pdf":
        extracted_text = _extract_pdf_text(content)
    elif mime_type in _IMAGE_MIMES:
        image_b64 = base64.b64encode(content).decode("utf-8")
        image_mime_for_vision = mime_type
        logger.info("image_encoded_for_vision", filename=filename, mime=mime_type,
                     size_kb=len(content) // 1024)

    filename_hints = _extract_text_from_filename(filename)

    # Build reference context with known entities/projects/associates
    reference_context = ""
    if tenant_id:
        try:
            reference_context = await _get_reference_context(tenant_id)
        except Exception:
            pass

    user_prompt = f"Filename: {filename}\n"
    if filename_hints:
        user_prompt += f"Filename analysis hints: {json.dumps(filename_hints)}\n"
    if reference_context:
        user_prompt += f"\n{reference_context}\n"
    if image_b64:
        user_prompt += (
            "\nI am attaching the scanned document image. "
            "Please analyze the image carefully to classify the document "
            "and extract any amounts, dates, references, and party names visible. "
            "Also match the emetteur/destinataire against the known entities and associates above."
        )
    elif extracted_text:
        user_prompt += f"\nExtracted text (first {len(extracted_text)} chars):\n\"\"\"\n{extracted_text}\n\"\"\""
        user_prompt += "\nMatch the content against the known entities, projects, and associates listed above."
    else:
        user_prompt += "\nNo text could be extracted. Classify based on filename only."

    try:
        result = await invoke_json_agent(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=1024,
            image_b64=image_b64,
            image_mime=image_mime_for_vision,
        )
        data = result["parsed_json"]

        # Normalize doc_type to valid enum value
        doc_type = (data.get("doc_type") or "OTHER").upper().strip()
        valid_types = {
            "INVOICE", "RECEIPT", "CONTRACT", "BANK_STATEMENT", "PAYROLL",
            "ADV_CONTRACT", "ADV_PAYMENT", "CHEQUE", "BON_COMMANDE", "DEVIS",
            "AVOIR", "BULLETIN_PAIE", "QUITTANCE", "ATTESTATION",
            "BON_LIVRAISON", "OTHER",
        }
        if doc_type not in valid_types:
            doc_type = "OTHER"

        return {
            "doc_type": doc_type,
            "confidence": float(data.get("confidence", 0.5)),
            "montant_ttc": _to_decimal(data.get("montant_ttc")),
            "montant_ht": _to_decimal(data.get("montant_ht")),
            "tva": _to_decimal(data.get("tva")),
            "date": data.get("date") or None,
            "reference": data.get("reference") or None,
            "emetteur": data.get("emetteur") or None,
            "destinataire": data.get("destinataire") or None,
            "entreprise_code": data.get("entreprise_code") or None,
            "projet_code": data.get("projet_code") or None,
            "associe_nom": data.get("associe_nom") or None,
            "reasoning": data.get("reasoning") or "AI classification",
        }

    except Exception as exc:
        logger.error("document_classification_failed", error=str(exc))
        # Fallback: use filename hints
        return {
            "doc_type": filename_hints.get("filename_type", "OTHER"),
            "confidence": 0.3,
            "montant_ttc": filename_hints.get("montant_hint"),
            "montant_ht": None,
            "tva": None,
            "date": None,
            "reference": None,
            "emetteur": None,
            "destinataire": None,
            "entreprise_code": None,
            "projet_code": None,
            "associe_nom": None,
            "reasoning": f"Fallback classification from filename (AI failed: {exc})",
        }


def _to_decimal(value) -> Optional[Decimal]:
    """Convert a value to Decimal, returning None if invalid."""
    if value is None:
        return None
    try:
        d = Decimal(str(value))
        if d <= 0:
            return None
        return d
    except Exception:
        return None
