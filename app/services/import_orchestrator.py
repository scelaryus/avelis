"""GFI Platform - Import Orchestrator Service.

Handles bulk file import from PC folders or Google Drive.
Processes each file through the full AI pipeline:
  upload → classify → OCR → extract → normalize → verify → match → ledger → commit → route

Runs as a background task per ImportSession.
"""
import hashlib
import uuid
from datetime import datetime
import structlog

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.core import (
    Document, ImportSession, ImportSessionStatus, AuditLog, DocType,
    Workflow, WorkflowStatus,
)
from app.storage.service import get_storage_service
from app.orchestrator.engine import RunContext
from app.orchestrator.graphs import GRAPH_REGISTRY
from app.schemas.artifacts import WorkflowState

logger = structlog.get_logger(__name__)
settings = get_settings()

# Allowed MIME types for import
MIME_MAP = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


async def run_import_session(session_id: str):
    """
    Main entry point: process all files in an import session.
    Called as a background task after files are uploaded or downloaded from Google Drive.
    """
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(ImportSession).where(ImportSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            logger.error("import_session_not_found", session_id=session_id)
            return

        logger.info("import_session_started",
                     session_id=session_id,
                     total_files=session.nombre_fichiers,
                     source_type=session.source_type.value if session.source_type else "PC_FOLDER")

        # Get pending documents for this session
        result = await db.execute(
            select(Document).where(
                Document.import_session_id == session_id,
                Document.module_routed_to == None,  # not yet processed
            )
        )
        documents = result.scalars().all()

        if not documents:
            logger.warning("no_documents_to_process", session_id=session_id)
            session.statut = ImportSessionStatus.TERMINE
            session.completed_at = datetime.utcnow()
            await db.commit()
            return

        resultats = list(session.resultats or [])
        processed = session.fichiers_traites or 0
        errored = session.fichiers_erreur or 0

        for doc in documents:
            try:
                file_result = await _process_single_document(
                    db=db,
                    doc=doc,
                    tenant_id=session.tenant_id,
                    user_id=session.user_id,
                    session_id=session_id,
                )
                resultats.append(file_result)
                processed += 1

                if file_result.get("status") == "ERROR":
                    errored += 1

            except Exception as e:
                errored += 1
                processed += 1
                resultats.append({
                    "filename": doc.filename,
                    "doc_id": str(doc.id),
                    "status": "ERROR",
                    "error": str(e),
                    "doc_type": None,
                    "routed_to": None,
                })
                logger.exception("import_file_error",
                                 doc_id=str(doc.id),
                                 filename=doc.filename)

            # Update session progress
            session.fichiers_traites = processed
            session.fichiers_erreur = errored
            session.resultats = resultats
            await db.commit()

        # ── Fallback: ensure every classified doc gets system entries ──
        # If the full pipeline failed or didn't create module records,
        # create them from the Document's extracted_* fields.
        await _ensure_system_entries_for_session(
            db=db,
            session_id=session_id,
            tenant_id=session.tenant_id,
            user_id=session.user_id,
        )

        # Finalize session
        if errored == len(documents):
            session.statut = ImportSessionStatus.ERREUR
        elif errored > 0:
            session.statut = ImportSessionStatus.PARTIEL
        else:
            session.statut = ImportSessionStatus.TERMINE

        session.completed_at = datetime.utcnow()
        await db.commit()

        logger.info("import_session_completed",
                     session_id=session_id,
                     processed=processed,
                     errored=errored,
                     status=session.statut.value)


async def _process_single_document(
    *,
    db,
    doc: Document,
    tenant_id: str,
    user_id: str,
    session_id: str,
) -> dict:
    """Process a single document through the full AI pipeline."""
    doc_id = str(doc.id)

    logger.info("processing_import_document",
                doc_id=doc_id,
                filename=doc.filename,
                doc_type=doc.doc_type.value if doc.doc_type else "OTHER")

    # Create a workflow for this document
    workflow = Workflow(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        actor_user_id=user_id,
        status=WorkflowStatus.CREATED,
        graph_type="document_to_ledger",
        doc_ids=[doc_id],
    )
    db.add(workflow)
    await db.flush()

    # Build the graph
    graph_builder = GRAPH_REGISTRY.get("document_to_ledger")
    if not graph_builder:
        return {
            "filename": doc.filename,
            "doc_id": doc_id,
            "status": "ERROR",
            "error": "Graph 'document_to_ledger' not found",
            "doc_type": None,
            "routed_to": None,
        }

    graph = graph_builder()

    # Create workflow state
    state = WorkflowState(
        workflow_id=str(workflow.id),
        tenant_id=tenant_id,
        actor_user_id=user_id,
        doc_ids=[doc_id],
        status="CREATED",
        current_node="ingest",
        artifacts={},
        node_history=[],
        blocking_reasons=[],
        errors=[],
        warnings=[],
        decisions=[],
    )

    # Create run context
    storage = get_storage_service()
    ctx = RunContext(
        db_session=db,
        storage=storage,
        settings=settings,
        tenant_id=tenant_id,
        user_id=user_id,
        workflow_id=str(workflow.id),
    )

    # Execute the AI pipeline
    try:
        final_state = await graph.execute(state, ctx)
    except Exception as e:
        logger.exception("pipeline_execution_failed",
                         doc_id=doc_id, workflow_id=str(workflow.id))
        return {
            "filename": doc.filename,
            "doc_id": doc_id,
            "workflow_id": str(workflow.id),
            "status": "ERROR",
            "error": f"Pipeline execution failed: {str(e)}",
            "doc_type": doc.doc_type.value if doc.doc_type else None,
            "routed_to": None,
        }

    # Refresh the doc to get updated fields (module_routed_to set by module_router)
    await db.refresh(doc)

    status = "OK" if final_state.status in ("READY_TO_COMMIT", "COMMITTED", "RUNNING") else "ERROR"
    created_record_ids = list((final_state.artifacts or {}).get("module_router", []))
    journal_entry_ids = list((final_state.artifacts or {}).get("commit", []))

    return {
        "filename": doc.filename,
        "doc_id": doc_id,
        "workflow_id": str(workflow.id),
        "workflow_status": final_state.status,
        "status": status,
        "doc_type": doc.doc_type.value if doc.doc_type else "OTHER",
        "routed_to": doc.module_routed_to or "documents",
        "created_record_ids": created_record_ids,
        "journal_entry_ids": journal_entry_ids,
        "errors": final_state.errors if final_state.errors else None,
        "warnings": final_state.warnings if final_state.warnings else None,
    }


async def _ensure_system_entries_for_session(
    *,
    db,
    session_id: str,
    tenant_id: str,
    user_id: str,
) -> None:
    """Ensure every classified document in the session has system entries.

    After the pipeline runs, some documents may not have been fully processed
    (pipeline failures, LLM errors, etc.) but still have extracted_* fields
    from the classifier. This function creates ADV/accounting records from
    those fields as a fallback, so they always appear in the system.
    """
    from sqlalchemy import select
    from app.models.adv import Client, Contract, Receivable, Payment
    from app.models.adv import ContractStatus, PaymentStatus
    from sqlalchemy import func as sa_func
    from decimal import Decimal
    from datetime import date as date_type, timedelta

    # Doc types that should create ADV records
    ADV_DOC_TYPES = {
        "ADV_CONTRACT", "ADV_PAYMENT", "DEVIS", "BON_COMMANDE", "BON_LIVRAISON",
        "CONTRACT",
    }
    # Doc types that should create receivables (creances)
    RECEIVABLE_DOC_TYPES = {
        "INVOICE", "AVOIR", "QUITTANCE",
        "ADV_CONTRACT", "BON_COMMANDE", "CONTRACT",
    }
    # Doc types that should create payments
    PAYMENT_DOC_TYPES = {"ADV_PAYMENT", "RECEIPT", "BON_LIVRAISON"}

    result = await db.execute(
        select(Document).where(
            Document.import_session_id == session_id,
        )
    )
    documents = result.scalars().all()

    for doc in documents:
        doc_type = doc.doc_type.value if doc.doc_type else "OTHER"

        # Skip docs that already have system records (module_router already handled them)
        # Use cast-to-string LIKE search for JSON array column compatibility
        from sqlalchemy import cast, String
        doc_id_str = str(doc.id)

        existing_recv = await db.execute(
            select(Receivable.id).where(
                cast(Receivable.doc_ids, String).contains(doc_id_str)
            ).limit(1)
        )
        existing_contract = await db.execute(
            select(Contract.id).where(
                cast(Contract.doc_ids, String).contains(doc_id_str)
            ).limit(1)
        )
        existing_payment = await db.execute(
            select(Payment.id).where(
                cast(Payment.doc_ids, String).contains(doc_id_str)
            ).limit(1)
        )

        has_receivable = existing_recv.scalar_one_or_none() is not None
        has_contract = existing_contract.scalar_one_or_none() is not None
        has_payment = existing_payment.scalar_one_or_none() is not None

        needs_receivable = doc_type in RECEIVABLE_DOC_TYPES and not has_receivable
        needs_contract = doc_type in ADV_DOC_TYPES and not has_contract and doc_type not in PAYMENT_DOC_TYPES
        needs_payment = doc_type in PAYMENT_DOC_TYPES and not has_payment

        if not needs_receivable and not needs_contract and not needs_payment:
            continue

        # Extract data from Document fields
        amount = doc.extracted_montant
        if not amount or amount <= 0:
            amount = None

        doc_date_str = doc.extracted_date
        doc_date = None
        if doc_date_str:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    from datetime import datetime as dt
                    doc_date = dt.strptime(doc_date_str, fmt).date()
                    break
                except ValueError:
                    continue

        client_name = doc.extracted_emetteur or doc.extracted_destinataire or "Client Inconnu"
        reference = doc.extracted_reference

        # Find or create client
        client_result = await db.execute(
            select(Client).where(
                Client.tenant_id == tenant_id,
                sa_func.upper(Client.name) == client_name.upper(),
            )
        )
        client = client_result.scalar_one_or_none()
        if not client:
            client = Client(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                code=f"CLI-{str(uuid.uuid4())[:8].upper()}",
                name=client_name,
                is_active=True,
            )
            db.add(client)
            await db.flush()
            logger.info("fallback_auto_created_client", client_id=client.id, name=client_name)

        # Set module routing on doc if not yet set
        if not doc.module_routed_to:
            if doc_type in ADV_DOC_TYPES or doc_type in RECEIVABLE_DOC_TYPES:
                doc.module_routed_to = "adv"
            elif doc_type in PAYMENT_DOC_TYPES:
                doc.module_routed_to = "adv"

        try:
            # Create contract for contract-type docs
            if needs_contract:
                contract = Contract(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    client_id=client.id,
                    contract_number=reference or f"CTR-{str(uuid.uuid4())[:8].upper()}",
                    title=f"{doc_type} — {doc.filename}",
                    status=ContractStatus.ACTIVE if doc_type != "DEVIS" else ContractStatus.DRAFT,
                    total_amount=amount,
                    currency="DZD",
                    start_date=doc_date,
                    doc_ids=[str(doc.id)],
                    created_by=user_id,
                )
                db.add(contract)
                logger.info("fallback_created_contract", doc_id=str(doc.id),
                            contract_number=contract.contract_number)

            # Create receivable for invoice-type docs
            if needs_receivable and amount and amount > 0:
                due_date = doc_date + timedelta(days=30) if doc_date else date_type.today() + timedelta(days=30)
                receivable = Receivable(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    client_id=client.id,
                    invoice_ref=reference or f"FAC-{str(uuid.uuid4())[:8].upper()}",
                    amount=amount,
                    amount_paid=Decimal("0"),
                    currency="DZD",
                    due_date=due_date,
                    status=PaymentStatus.PENDING,
                    doc_ids=[str(doc.id)],
                )
                db.add(receivable)
                logger.info("fallback_created_receivable", doc_id=str(doc.id),
                            invoice_ref=receivable.invoice_ref, amount=float(amount))

            # Create payment for payment-type docs
            if needs_payment and amount and amount > 0:
                payment = Payment(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    client_id=client.id,
                    payment_ref=reference or f"PAY-{str(uuid.uuid4())[:8].upper()}",
                    amount=amount,
                    currency="DZD",
                    payment_date=doc_date or date_type.today(),
                    payment_method="import",
                    doc_ids=[str(doc.id)],
                )
                db.add(payment)
                logger.info("fallback_created_payment", doc_id=str(doc.id),
                            payment_ref=payment.payment_ref, amount=float(amount))

        except Exception as e:
            logger.warning("fallback_entry_creation_failed",
                           doc_id=str(doc.id), doc_type=doc_type, error=str(e))

    await db.commit()
    logger.info("fallback_system_entries_complete", session_id=session_id)


async def ingest_files_to_session(
    *,
    files_data: list[tuple[str, bytes, str]],  # [(filename, content, mime_type), ...]
    tenant_id: str,
    user_id: str,
    session_id: str,
    db,
) -> list[dict]:
    """
    Ingest multiple files into the system as Document records linked to an ImportSession.
    Returns per-file ingestion results.
    """
    from app.services.document_classifier import classify_document

    storage = get_storage_service()
    results = []
    duplicates = 0

    for filename, content, mime_type in files_data:
        try:
            # Hash for dedup
            file_hash = hashlib.sha256(content).hexdigest()

            # Check duplicate
            from sqlalchemy import select
            dup_result = await db.execute(
                select(Document).where(
                    Document.tenant_id == tenant_id,
                    Document.sha256 == file_hash,
                )
            )
            existing = dup_result.scalar_one_or_none()
            if existing:
                duplicates += 1
                results.append({
                    "filename": filename,
                    "doc_id": str(existing.id),
                    "status": "DUPLICATE",
                    "doc_type": existing.doc_type.value if existing.doc_type else None,
                })
                continue

            # Store the file
            storage_key = f"documents/{tenant_id}/{file_hash}/{filename}"
            await storage.upload(storage_key, content, mime_type)

            # Classify
            classification = await classify_document(
                filename=filename,
                content=content,
                mime_type=mime_type,
            )

            try:
                classified_type = DocType(classification["doc_type"])
            except (ValueError, KeyError):
                classified_type = DocType.OTHER

            # Create Document record
            doc = Document(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                filename=filename,
                mime_type=mime_type,
                file_size=len(content),
                sha256=file_hash,
                storage_key=storage_key,
                uploaded_by=user_id,
                doc_type=classified_type,
                doc_type_confidence=classification.get("confidence", 0.0),
                extracted_montant=classification.get("montant_ttc"),
                extracted_montant_ht=classification.get("montant_ht"),
                extracted_tva=classification.get("tva"),
                extracted_date=classification.get("date"),
                extracted_reference=classification.get("reference"),
                extracted_emetteur=classification.get("emetteur"),
                extracted_destinataire=classification.get("destinataire"),
                classification_reasoning=classification.get("reasoning"),
                import_session_id=session_id,
            )
            db.add(doc)
            await db.flush()

            results.append({
                "filename": filename,
                "doc_id": str(doc.id),
                "status": "INGESTED",
                "doc_type": classified_type.value,
                "confidence": classification.get("confidence", 0.0),
            })

            logger.info("import_file_ingested",
                         filename=filename,
                         doc_id=str(doc.id),
                         doc_type=classified_type.value,
                         session_id=session_id)

        except Exception as e:
            results.append({
                "filename": filename,
                "doc_id": None,
                "status": "ERROR",
                "error": str(e),
            })
            logger.exception("import_file_ingest_error",
                             filename=filename, session_id=session_id)

    # Update session counts
    from sqlalchemy import select
    result = await db.execute(
        select(ImportSession).where(ImportSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session:
        session.fichiers_dupliques = duplicates

    await db.commit()

    return results
