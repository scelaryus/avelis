"""
GFI v7.0 — Document Generation Engine + Relance (Follow-up) System.

14 auto-generated document types with strict RF2 visibility rules.
Daily relance automation for missing client documents.

Core rules:
  RF2-S03: Attestation without amounts when RF2 not secured
  ENG-003: Decision d'affectation shows RF1 price ONLY
  RF2 recu interne: NEVER shown to client, NEVER on letterhead

Core API:
  generate_document(template_code, dossier_id, ...) -> GeneratedDocument
  initialize_relance_tracking(dossier_id, ...) -> list[RelanceTracker]
  run_daily_relance(today) -> relance stats
  get_dossier_documents(dossier_id) -> list (filtered by user role)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ═════════════════════════════════════════════════════════════════════════════
# 14 DOCUMENT TEMPLATE DEFINITIONS
# ═════════════════════════════════════════════════════════════════════════════

TEMPLATES = [
    # (code, name, category, client_visible, rf2_content, description)
    ("DEVIS", "Devis", "ADV", True, False,
     "RF1 price only. NEVER shows RF2."),
    ("ATTEST_RESERV_NO_RF2", "Attestation de reservation (RF2 non securise)", "ADV",
     True, False,
     "WITHOUT ANY AMOUNTS. Only: client name, lot ref, date. Rule RF2-S03."),
    ("ATTEST_RESERV_RF2_OK", "Attestation de reservation (RF2 securise)", "ADV",
     True, False,
     "Can include RF1 amounts only."),
    ("DECISION_AFFECTATION", "Decision d'affectation", "ADV",
     True, False,
     "RF1 price ONLY (ENG-003). Serves as Promesse de Vente."),
    ("GUIDE_TECHNIQUE", "Guide technique client", "ADV",
     True, False,
     "Technical lot specifications. Project-specific template."),
    ("ECHEANCIER_PDF", "Echeancier de paiement", "ADV",
     True, False,
     "Installment schedule. Credit: 20/15/35/25/5. FP: monthly."),
    ("DEMANDE_DEBLOCAGE", "Demande de deblocage", "CREDIT",
     False, False,
     "Expert report + dossier summary + tier amount. Sent to bank only."),
    ("ETAT_DETAILLE_PDF", "Etat detaille cheque notaire", "NOTAIRE",
     False, False,
     "Line-by-line cheque breakdown. Internal only."),
    ("FICHE_DEPOT_NOTAIRE", "Fiche de depot notaire", "NOTAIRE",
     False, False,
     "Document deposit checklist. Internal only."),
    ("PV_REMISE_CLES", "PV de remise des cles", "ADV",
     True, False,
     "Key handover. Signed by client + company. Template with observations."),
    ("RECU_RF1", "Recu de paiement RF1", "ADV",
     True, False,
     "Official receipt. Amount, date, reference."),
    ("RECU_RF2", "Recu interne RF2", "INTERNAL",
     False, True,
     "NEVER shown to client. NEVER on official letterhead. Internal tracking only."),
    ("RELANCE_IMPAYE", "Relance impaye", "ADV",
     True, False,
     "Escalating severity: J+7 friendly, J+14 firm, J+30 mise en demeure."),
    ("RAPPORT_SITUATION", "Rapport de situation dossier", "ADV",
     True, False,
     "Full summary filtered by user role. No RF2 for Agent Commercial."),
]


# ═════════════════════════════════════════════════════════════════════════════
# REQUIRED DOCUMENTS PER DOSSIER TYPE
# ═════════════════════════════════════════════════════════════════════════════

# (doc_type, doc_name, source, required_for, blocks_operation)
BASE_DOCUMENTS = [
    ("CIN", "Carte d'identite nationale", "CLIENT", "ALL", None),
    ("FICHE_FAMILIALE", "Fiche familiale", "CLIENT", "ALL", None),
]

CREDIT_DOCUMENTS = [
    ("ATTESTATION_TRAVAIL", "Attestation de travail", "CLIENT", "CREDIT", None),
    ("FICHES_PAIE", "3 dernieres fiches de paie", "CLIENT", "CREDIT", None),
    ("RELEVES_BANCAIRES", "Releves bancaires 6 mois", "CLIENT", "CREDIT", None),
    ("EXTRAIT_ROLE", "Extrait de role", "CLIENT", "CREDIT", None),
    ("CONTRAT_CREDIT_SIGNE", "Contrat de credit signe", "BANK", "CREDIT", "VSP"),
    ("CONTRAT_ENREGISTRE", "Contrat enregistre aux impots", "CLIENT", "CREDIT", "VSP"),
    ("ORDRES_VIREMENT_15", "Ordre virement 15%", "CLIENT", "CREDIT", "VSP"),
    ("ORDRES_VIREMENT_35", "Ordre virement 35%", "CLIENT", "CREDIT", "VSP"),
    ("ORDRES_VIREMENT_25", "Ordre virement 25%", "CLIENT", "CREDIT", "VSP"),
    ("RAPPORT_EXPERT_15", "Rapport expert palier 15%", "EXPERT", "CREDIT", "PALIER_15PCT"),
    ("RAPPORT_EXPERT_35", "Rapport expert palier 35%", "EXPERT", "CREDIT", "PALIER_35PCT"),
    ("RAPPORT_EXPERT_25", "Rapport expert palier 25%", "EXPERT", "CREDIT", "PALIER_25PCT"),
]

COMPANY_DOCUMENTS = [
    ("ACTE_PROPRIETE", "Acte de propriete terrain", "COMPANY", "CREDIT", None),
    ("PERMIS_CONSTRUIRE", "Permis de construire", "COMPANY", "CREDIT", None),
    ("ASSURANCE_CHANTIER", "Attestation assurance chantier", "COMPANY", "CREDIT", None),
]


def generate_document(
    session: Session,
    *,
    template_code: str,
    dossier_id: UUID | None,
    company_id: UUID,
    project_id: UUID | None = None,
    content_data: dict | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Generate a document from a template with dynamic field injection.
    Enforces RF2 visibility rules.
    """
    from app.models.document_generation import DocumentTemplate, GeneratedDocument

    template = (
        session.query(DocumentTemplate)
        .filter(
            DocumentTemplate.code == template_code,
            DocumentTemplate.is_deleted.is_(False),
        )
        .first()
    )
    if template is None:
        raise ValueError(f"Template '{template_code}' not found.")

    # RF2-S03: strip amounts from attestation if RF2 not secured
    if template_code == "ATTEST_RESERV_NO_RF2" and content_data:
        for key in list(content_data.keys()):
            if any(w in key.lower() for w in [
                "prix", "montant", "amount", "payment", "deposit",
                "acompte", "pourcent", "percent",
            ]):
                del content_data[key]

    now = datetime.now(timezone.utc)

    doc = GeneratedDocument(
        company_id=company_id,
        template_id=template.id,
        template_code=template_code,
        dossier_adv_id=dossier_id,
        project_id=project_id,
        generated_at=now,
        file_format="PDF",
        content_data=content_data or {},
        client_visible=template.client_visible,
        rf2_content=template.rf2_content,
        status="GENERE",
        created_by=created_by,
    )
    session.add(doc)
    session.flush()
    return doc


def generate_attestation_reservation(
    session: Session,
    *,
    dossier_id: UUID,
    company_id: UUID,
    rf2_secured: bool,
    client_name: str,
    lot_ref: str,
    project_name: str,
    prix_rf1: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Generate the appropriate attestation based on RF2 status.
    RF2-S03: no amounts if RF2 not secured.
    """
    if rf2_secured:
        return generate_document(
            session,
            template_code="ATTEST_RESERV_RF2_OK",
            dossier_id=dossier_id,
            company_id=company_id,
            content_data={
                "client_name": client_name,
                "lot_ref": lot_ref,
                "project_name": project_name,
                "prix_rf1": prix_rf1,
                "date_reservation": str(date.today()),
            },
            created_by=created_by,
        )
    else:
        # RF2-S03: absolutely NO amounts
        return generate_document(
            session,
            template_code="ATTEST_RESERV_NO_RF2",
            dossier_id=dossier_id,
            company_id=company_id,
            content_data={
                "client_name": client_name,
                "lot_ref": lot_ref,
                "date_reservation": str(date.today()),
            },
            created_by=created_by,
        )


def generate_decision_affectation(
    session: Session,
    *,
    dossier_id: UUID,
    company_id: UUID,
    client_name: str,
    lot_ref: str,
    project_name: str,
    entity_name: str,
    prix_rf1: str,
    delivery_date: str | None = None,
    payment_conditions: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    ENG-003: Decision d'affectation shows RF1 price ONLY.
    Also serves as Promesse de Vente.
    """
    return generate_document(
        session,
        template_code="DECISION_AFFECTATION",
        dossier_id=dossier_id,
        company_id=company_id,
        content_data={
            "client_name": client_name,
            "lot_ref": lot_ref,
            "project_name": project_name,
            "entity_name": entity_name,
            "prix_vente": prix_rf1,  # RF1 ONLY — never RF2
            "date_livraison": delivery_date,
            "conditions_paiement": payment_conditions,
            "date_engagement": str(date.today()),
        },
        created_by=created_by,
    )


def get_dossier_documents(
    session: Session,
    dossier_id: UUID,
    *,
    user_has_rf2: bool = False,
) -> list:
    """
    Get all documents for a dossier, filtered by user's RF2 access.
    Agent Commercial gets NO RF2 documents at all.
    """
    from app.models.document_generation import GeneratedDocument

    query = session.query(GeneratedDocument).filter(
        GeneratedDocument.dossier_adv_id == dossier_id,
        GeneratedDocument.is_deleted.is_(False),
    )

    if not user_has_rf2:
        query = query.filter(GeneratedDocument.rf2_content.is_(False))

    return query.order_by(GeneratedDocument.generated_at.desc()).all()


# ═════════════════════════════════════════════════════════════════════════════
# RELANCE (FOLLOW-UP) ENGINE
# ═════════════════════════════════════════════════════════════════════════════

def initialize_relance_tracking(
    session: Session,
    *,
    dossier_id: UUID,
    company_id: UUID,
    type_paiement: str,
    created_by: UUID | None = None,
) -> list:
    """Create relance trackers for all required documents on a dossier."""
    from app.models.document_generation import RelanceTracker

    today = date.today()
    docs = list(BASE_DOCUMENTS)

    if type_paiement in ("CREDIT_BANCAIRE", "MIXTE"):
        docs.extend(CREDIT_DOCUMENTS)
        docs.extend(COMPANY_DOCUMENTS)

    trackers = []
    for doc_type, doc_name, source, req_for, blocks in docs:
        tracker = RelanceTracker(
            company_id=company_id,
            dossier_adv_id=dossier_id,
            document_type=doc_type,
            document_name=doc_name,
            source=source,
            required_since=today,
            status="REQUIS",
            blocks_operation=blocks,
            created_by=created_by,
        )
        session.add(tracker)
        trackers.append(tracker)

    session.flush()
    return trackers


def run_daily_relance(
    session: Session,
    today: date | None = None,
) -> dict:
    """
    Daily relance job (08:00). Processes all pending document relances.
    Escalation: J+3 -> J+7 -> J+14 -> J+30 (BLOQUANT).
    """
    from app.models.document_generation import RelanceTracker

    if today is None:
        today = date.today()

    now = datetime.now(timezone.utc)
    stats = {
        "relance_j3": 0, "relance_j7": 0, "relance_j14": 0,
        "bloquant_j30": 0, "total_processed": 0,
    }

    pending = (
        session.query(RelanceTracker)
        .filter(
            RelanceTracker.status.in_(["REQUIS", "RELANCE_J3", "RELANCE_J7", "RELANCE_J14"]),
            RelanceTracker.is_deleted.is_(False),
        )
        .all()
    )

    for tracker in pending:
        days = (today - tracker.required_since).days
        stats["total_processed"] += 1

        if days >= 30 and tracker.relance_j30_at is None:
            tracker.status = "BLOQUANT"
            tracker.relance_j30_at = now
            tracker.relance_count += 1
            stats["bloquant_j30"] += 1

        elif days >= 14 and tracker.relance_j14_at is None:
            tracker.status = "RELANCE_J14"
            tracker.relance_j14_at = now
            tracker.relance_count += 1
            stats["relance_j14"] += 1

        elif days >= 7 and tracker.relance_j7_at is None:
            tracker.status = "RELANCE_J7"
            tracker.relance_j7_at = now
            tracker.relance_count += 1
            stats["relance_j7"] += 1

        elif days >= 3 and tracker.relance_j3_at is None:
            tracker.status = "RELANCE_J3"
            tracker.relance_j3_at = now
            tracker.relance_count += 1
            stats["relance_j3"] += 1

    session.flush()
    return stats


def mark_document_received(
    session: Session,
    *,
    tracker_id: UUID,
    file_path: str | None = None,
) -> object:
    """Mark a tracked document as received."""
    from app.models.document_generation import RelanceTracker

    tracker = session.get(RelanceTracker, tracker_id)
    if tracker is None:
        raise ValueError(f"RelanceTracker {tracker_id} not found.")

    tracker.status = "RECU"
    tracker.received_date = date.today()
    tracker.file_path = file_path
    session.flush()
    return tracker


def get_blocking_documents(
    session: Session,
    dossier_id: UUID,
    operation: str,
) -> list:
    """
    Get all documents that are missing and BLOCK a specific operation.
    Returns list of missing RelanceTracker items.
    """
    from app.models.document_generation import RelanceTracker

    return (
        session.query(RelanceTracker)
        .filter(
            RelanceTracker.dossier_adv_id == dossier_id,
            RelanceTracker.blocks_operation == operation,
            RelanceTracker.status.in_(["REQUIS", "RELANCE_J3", "RELANCE_J7",
                                        "RELANCE_J14", "BLOQUANT"]),
            RelanceTracker.is_deleted.is_(False),
        )
        .all()
    )
