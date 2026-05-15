"""AI-powered proof document verification for ADV transactions.

Every ADV interaction requires a justification document (image/PDF).
The AI analyzes it to verify consistency with the requested action.
If the proof doesn't match → the action is BLOCKED.
"""
import base64
import hashlib
import structlog
from decimal import Decimal
from typing import Optional
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Document
from app.storage.service import get_storage_service

logger = structlog.get_logger(__name__)

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/tiff"}


async def store_proof(
    file: UploadFile,
    tenant_id: str,
    user_id: str,
    module: str,
    db: AsyncSession,
) -> Document:
    """Validate, store, and create a Document record for a proof file."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Format non supporté: {file.content_type}. Acceptés: PDF, PNG, JPG, TIFF")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "Fichier trop volumineux (max 20 MB)")

    file_hash = hashlib.sha256(content).hexdigest()
    storage = get_storage_service()
    storage_key = f"documents/{tenant_id}/{module}/{file_hash}/{file.filename}"
    await storage.upload(storage_key, content, file.content_type)

    doc = Document(
        tenant_id=tenant_id,
        filename=file.filename,
        mime_type=file.content_type,
        file_size=len(content),
        sha256=file_hash,
        storage_key=storage_key,
        uploaded_by=user_id,
        module_routed_to=module,
    )
    db.add(doc)
    await db.flush()
    return doc


async def verify_proof(
    file: UploadFile,
    action: str,
    context: dict,
    tenant_id: str,
    user_id: str,
    db: AsyncSession,
) -> dict:
    """Store a proof document, run AI analysis, and verify consistency.

    Args:
        file: The uploaded proof document
        action: What the user is trying to do (e.g. "reserver_lot", "enregistrer_paiement")
        context: Details about the action (montant, client, lot_code, etc.)
        tenant_id: Current tenant
        user_id: Current user
        db: Database session

    Returns:
        {
            "document_id": str,
            "verified": bool,
            "ai_summary": str,
            "ai_extracted": dict,  # amounts, names, dates found in doc
            "rejection_reason": str | None,
        }

    Raises HTTPException if document format is invalid.
    """
    # Store the document
    doc = await store_proof(file, tenant_id, user_id, "adv", db)

    # Read content for AI
    content = await file.seek(0) or b""
    # Re-read since seek resets position
    await file.seek(0)
    content = await file.read()

    # AI analysis
    ai_result = await _analyze_proof(content, file.content_type, file.filename, action, context)

    verified = ai_result.get("consistent", False)
    rejection = None

    if not verified:
        rejection = ai_result.get("inconsistency_reason", "Le document ne correspond pas à l'action demandée")

    return {
        "document_id": doc.id,
        "verified": verified,
        "ai_summary": ai_result.get("summary", ""),
        "ai_extracted": {
            "montant": ai_result.get("montant_extrait"),
            "nom_client": ai_result.get("nom_client"),
            "date_document": ai_result.get("date_document"),
            "type_document": ai_result.get("type_document"),
        },
        "rejection_reason": rejection,
    }


async def _analyze_proof(
    content: bytes,
    mime_type: str,
    filename: str,
    action: str,
    context: dict,
) -> dict:
    """Send proof document to AI for verification against the requested action."""

    extracted_text = ""
    image_b64 = None
    image_mime = None

    if mime_type == "application/pdf":
        try:
            import fitz
            pdf = fitz.open(stream=content, filetype="pdf")
            pages = []
            for i in range(min(pdf.page_count, 3)):
                pages.append(pdf.load_page(i).get_text())
            pdf.close()
            extracted_text = "\n".join(pages)[:6000]
        except Exception:
            pass
        if not extracted_text.strip():
            try:
                import fitz
                pdf = fitz.open(stream=content, filetype="pdf")
                pix = pdf.load_page(0).get_pixmap(dpi=200)
                image_b64 = base64.b64encode(pix.tobytes("png")).decode()
                image_mime = "image/png"
                pdf.close()
            except Exception:
                pass
    else:
        image_b64 = base64.b64encode(content).decode()
        image_mime = mime_type

    if not extracted_text and not image_b64:
        return {"consistent": False, "inconsistency_reason": "Document illisible", "summary": ""}

    ACTION_LABELS = {
        "creer_client": "créer un nouveau client dans le système ADV",
        "creer_contrat": "créer un contrat de vente immobilière",
        "enregistrer_paiement": "enregistrer un paiement client",
        "reserver_lot": "réserver un lot immobilier (paiement SPOT)",
        "engager_lot": "engager un lot (signature de contrat de vente)",
        "paiement_lot": "enregistrer un paiement sur un dossier de vente",
        "livrer_lot": "livrer un lot (remise des clés)",
        "creer_tache_chantier": "créer une tâche de chantier dans le planning",
        "mise_a_jour_avancement": "mettre à jour l'avancement d'une tâche chantier",
        "creer_sous_traitant": "enregistrer un nouveau sous-traitant",
        "evaluer_sous_traitant": "évaluer la performance d'un sous-traitant",
        "situation_travaux": "créer une situation de travaux sous-traitant",
        "valider_situation_travaux": "valider une situation de travaux (génère écriture comptable)",
        "rapport_expert": "enregistrer un rapport d'expert de visite chantier",
        "valider_rapport_expert": "valider un rapport d'expert pour déblocage VSP",
    }

    system_prompt = f"""\
You are a document verifier for Groupe Dendani, an Algerian real-estate company.

ACTION REQUESTED: {ACTION_LABELS.get(action, action)}
CONTEXT: {_format_context(context)}

Your task:
1. Analyze the attached document (proof/justification for the action)
2. Extract: montant_extrait (amount in DA), nom_client, date_document, type_document
3. Verify CONSISTENCY between the document and the action:
   - If a montant is in the context, the document should mention a similar amount (±5% tolerance)
   - If a client name is in the context, it should match the document
   - The document type should be appropriate for the action
4. Return your verdict

Document types that are appropriate for each action:
- creer_client: CIN, registre commerce, attestation, fiche client
- creer_contrat: contrat signé, promesse de vente, acte notarié
- enregistrer_paiement: reçu, chèque, virement, attestation de paiement
- reserver_lot: reçu de paiement SPOT, chèque, quittance
- engager_lot: contrat signé, décision d'affectation, promesse de vente
- paiement_lot: reçu, chèque, relevé bancaire, virement
- livrer_lot: PV de remise des clés, attestation de livraison
- creer_tache_chantier: planning, bon de commande, contrat sous-traitant, ordre de service
- mise_a_jour_avancement: photo chantier, rapport d'avancement, PV de réunion
- creer_sous_traitant: registre commerce, NIF, attestation d'agrément, CACOBATPH
- evaluer_sous_traitant: rapport d'évaluation, PV de réception, photos, fiche d'évaluation
- situation_travaux: situation de travaux signée, attachement, décompte
- valider_situation_travaux: PV de validation signé, bon pour paiement
- rapport_expert: rapport d'expert signé, constat d'avancement, photos chantier
- valider_rapport_expert: PV de validation, attestation de conformité

Reply JSON only:
{{
  "consistent": true/false,
  "montant_extrait": number or null,
  "nom_client": "..." or null,
  "date_document": "YYYY-MM-DD" or null,
  "type_document": "...",
  "summary": "one sentence describing what the document is",
  "inconsistency_reason": "..." or null (explain WHY it's inconsistent if false)
}}
No markdown fences."""

    user_prompt = f"Document: {filename}\n"
    if extracted_text:
        user_prompt += f"\nText:\n\"\"\"\n{extracted_text}\n\"\"\""
    if image_b64:
        user_prompt += "\nAnalyze the attached document image."

    try:
        from app.services.llm_graph import invoke_json_agent
        result = await invoke_json_agent(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=512,
            image_b64=image_b64,
            image_mime=image_mime,
        )
        return result["parsed_json"]
    except Exception as exc:
        logger.error("proof_verification_failed", error=str(exc))
        # Fail closed — reject if AI is unavailable
        return {
            "consistent": False,
            "summary": f"Vérification IA indisponible ({exc}).",
            "inconsistency_reason": "Service de vérification IA indisponible. Veuillez réessayer.",
        }


def _format_context(ctx: dict) -> str:
    """Format context dict for the AI prompt."""
    parts = []
    if ctx.get("montant"):
        parts.append(f"Montant demandé: {ctx['montant']:,.2f} DA")
    if ctx.get("client_name"):
        parts.append(f"Client: {ctx['client_name']}")
    if ctx.get("lot_code"):
        parts.append(f"Lot: {ctx['lot_code']}")
    if ctx.get("projet"):
        parts.append(f"Projet: {ctx['projet']}")
    if ctx.get("action_detail"):
        parts.append(f"Détail: {ctx['action_detail']}")
    return "; ".join(parts) if parts else "Aucun contexte spécifique"
