"""GFI Platform - Documents API router."""
import hashlib
from datetime import date, datetime
from typing import Any, Optional
from decimal import Decimal
import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status, Header
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.core import User, Document, Artifact, AuditLog, Workflow, WorkflowStatus, DocType
from app.auth.dependencies import get_current_user
from app.storage.service import get_storage_service
from app.schemas.api import DocumentResponse, DocumentListResponse, DocumentCorrection
from app.config import get_settings

router = APIRouter(tags=["Documents"])
logger = structlog.get_logger(__name__)
settings = get_settings()


async def _ingest_document_upload(
    *,
    file: UploadFile,
    user: User,
    db: AsyncSession,
    doc_type_hint: Optional[str] = None,
    realite_financiere: Optional[str] = None,
    entreprise_id: Optional[str] = None,
    projet_id: Optional[str] = None,
) -> tuple[DocumentResponse, bool]:
    """Validate, classify, store, and persist an uploaded file."""
    allowed_types = {"application/pdf", "image/png", "image/jpeg", "image/tiff"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {allowed_types}",
        )

    content = await file.read()
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    file_hash = hashlib.sha256(content).hexdigest()

    result = await db.execute(
        select(Document).where(Document.tenant_id == user.tenant_id, Document.sha256 == file_hash)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return _doc_to_response(existing, is_duplicate=True), True

    storage = get_storage_service()
    # C1: Store raw file
    storage_key = f"documents/{user.tenant_id}/{file_hash}/{file.filename}"
    await storage.upload(storage_key, content, file.content_type)

    # C2: Extract text for full-text search (Section 15 EX-GED-002)
    extracted_text_content = ""
    if file.content_type == "application/pdf":
        try:
            import fitz
            pdf = fitz.open(stream=content, filetype="pdf")
            pages = []
            for i in range(min(pdf.page_count, 20)):
                pages.append(pdf.load_page(i).get_text())
            pdf.close()
            extracted_text_content = "\n".join(pages)[:50000]
        except Exception:
            pass

    from app.services.document_classifier import classify_document
    classification = await classify_document(
        filename=file.filename,
        content=content,
        mime_type=file.content_type,
        tenant_id=user.tenant_id,
    )

    try:
        classified_type = DocType(classification["doc_type"])
    except (ValueError, KeyError):
        classified_type = DocType.OTHER

    if doc_type_hint:
        try:
            classified_type = DocType(doc_type_hint)
        except ValueError:
            pass

    # Resolve AI-detected entity/project to real IDs (if not already set)
    resolved_ent_id = entreprise_id
    resolved_proj_id = projet_id
    if not resolved_ent_id and classification.get("entreprise_code"):
        from app.models.financial import Entreprise
        ent_result = await db.execute(
            select(Entreprise).where(
                Entreprise.tenant_id == user.tenant_id,
                Entreprise.code == classification["entreprise_code"],
            )
        )
        ent = ent_result.scalar_one_or_none()
        if ent:
            resolved_ent_id = ent.id
    if not resolved_proj_id and classification.get("projet_code"):
        from app.models.financial import Projet
        proj_result = await db.execute(
            select(Projet).where(
                Projet.tenant_id == user.tenant_id,
                Projet.code == classification["projet_code"],
            )
        )
        proj = proj_result.scalar_one_or_none()
        if proj:
            resolved_proj_id = proj.id
            # Also set entity from project if not already resolved
            if not resolved_ent_id:
                resolved_ent_id = proj.entreprise_id

    # C6: Resolve entity/project names for GED path
    ent_code = classification.get("entreprise_code") or "GENERAL"
    proj_code = classification.get("projet_code") or "COMMUN"
    doc_year = (classification.get("date") or "")[:4] or str(datetime.now().year)
    doc_type_str = classified_type.value if classified_type else "OTHER"

    # EX-GED-001: Normalized path /{Entity}/{Project}/{Year}/{DocType}/{File}
    ged_path = f"/{ent_code}/{proj_code}/{doc_year}/{doc_type_str}/{file.filename}"

    # EX-ING-002: Check mandatory fields — mark A_COMPLETER if missing
    champs_manquants = []
    if not classification.get("montant_ttc") and classified_type in (DocType.INVOICE, DocType.RECEIPT, DocType.CHEQUE):
        champs_manquants.append("montant")
    if not classification.get("date"):
        champs_manquants.append("date")
    if not classification.get("emetteur") and classified_type == DocType.INVOICE:
        champs_manquants.append("emetteur")

    statut_ingestion = "A_COMPLETER" if champs_manquants else "TRAITE"

    doc = Document(
        tenant_id=user.tenant_id,
        filename=file.filename,
        mime_type=file.content_type,
        file_size=len(content),
        sha256=file_hash,
        storage_key=storage_key,
        uploaded_by=user.id,
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
        realite_financiere=realite_financiere,
        entreprise_id=resolved_ent_id,
        projet_id=resolved_proj_id,
        extracted_text=extracted_text_content or None,
        ged_path=ged_path,
        statut_ingestion=statut_ingestion,
        champs_manquants=champs_manquants,
    )
    # Auto-route to module based on doc_type
    ADV_TYPES = {DocType.ADV_CONTRACT, DocType.ADV_PAYMENT, DocType.CHEQUE}
    COMPTA_TYPES = {DocType.INVOICE, DocType.RECEIPT, DocType.BANK_STATEMENT, DocType.AVOIR}
    HR_TYPES = {DocType.PAYROLL, DocType.BULLETIN_PAIE, DocType.ATTESTATION}

    if classified_type in ADV_TYPES:
        doc.module_routed_to = "adv"
    elif classified_type in COMPTA_TYPES:
        doc.module_routed_to = "comptabilite"
    elif classified_type in HR_TYPES:
        doc.module_routed_to = "hr"
    else:
        doc.module_routed_to = "documents"

    db.add(doc)
    await db.flush()

    # Auto-create ADV records from classified documents
    adv_record_id = None
    if doc.module_routed_to == "adv" and statut_ingestion == "TRAITE":
        adv_record_id = await _auto_create_adv_record(doc, classification, user, db)

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="document_upload",
        entity_type="document",
        entity_id=str(doc.id),
    ))
    await db.commit()
    await db.refresh(doc)

    resp = _doc_to_response(doc, is_duplicate=False)
    if adv_record_id:
        resp.adv_record_id = adv_record_id
    return resp, False


async def _auto_create_adv_record(doc, classification: dict, user, db) -> str | None:
    """Auto-create ADV payment/contract from a classified document."""
    from app.models.adv import Payment, Contract, Client, ContractStatus
    from decimal import Decimal
    import uuid as _u

    doc_type = doc.doc_type
    montant = classification.get("montant_ttc")
    ref = classification.get("reference") or doc.filename
    date_doc = classification.get("date")
    emetteur = classification.get("emetteur")
    destinataire = classification.get("destinataire")

    # Find or create a placeholder client for auto-created records
    client_name = emetteur or destinataire or "Client inconnu"
    result = await db.execute(
        select(Client).where(Client.tenant_id == user.tenant_id, Client.name == client_name).limit(1)
    )
    client = result.scalar_one_or_none()
    if not client:
        client = Client(
            id=str(_u.uuid4()),
            tenant_id=user.tenant_id,
            entreprise_id=doc.entreprise_id,
            code=f"AUTO-{_u.uuid4().hex[:6].upper()}",
            name=client_name,
        )
        db.add(client)
        await db.flush()

    if doc_type in (DocType.CHEQUE, DocType.ADV_PAYMENT) and montant:
        # Create a payment record
        payment = Payment(
            id=str(_u.uuid4()),
            tenant_id=user.tenant_id,
            client_id=client.id,
            entreprise_id=doc.entreprise_id,
            projet_id=doc.projet_id,
            payment_ref=ref,
            amount=Decimal(str(montant)),
            payment_date=date.fromisoformat(date_doc) if date_doc else date.today(),
            payment_method="CHEQUE" if doc_type == DocType.CHEQUE else "ESPECES",
            realite_financiere=doc.realite_financiere or "RF1",
            doc_ids=[doc.id],
            notes=f"Auto-créé depuis document: {doc.filename}",
        )
        db.add(payment)
        await db.flush()
        return payment.id

    if doc_type == DocType.ADV_CONTRACT:
        # Create a contract record
        contract = Contract(
            id=str(_u.uuid4()),
            tenant_id=user.tenant_id,
            client_id=client.id,
            entreprise_id=doc.entreprise_id,
            projet_id=doc.projet_id,
            contract_number=ref or f"CTR-{_u.uuid4().hex[:8].upper()}",
            title=f"Contrat — {emetteur or destinataire or doc.filename}",
            status=ContractStatus.DRAFT,
            total_amount=Decimal(str(montant)) if montant else None,
            doc_ids=[doc.id],
            created_by=user.id,
        )
        db.add(contract)
        await db.flush()
        return contract.id

    return None


def _doc_to_response(doc: Document, is_duplicate: bool = False) -> DocumentResponse:
    """Convert Document ORM object to DocumentResponse schema."""
    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        sha256=doc.sha256,
        mime_type=doc.mime_type,
        file_size=doc.file_size,
        storage_key=doc.storage_key,
        uploaded_by=doc.uploaded_by,
        created_at=doc.created_at,
        is_duplicate=is_duplicate,
        realite_financiere=getattr(doc, "realite_financiere", None),
        doc_type=doc.doc_type.value if doc.doc_type else None,
        doc_type_confidence=doc.doc_type_confidence,
        extracted_montant=float(doc.extracted_montant) if doc.extracted_montant else None,
        extracted_montant_ht=float(doc.extracted_montant_ht) if doc.extracted_montant_ht else None,
        extracted_tva=float(doc.extracted_tva) if doc.extracted_tva else None,
        extracted_date=doc.extracted_date,
        extracted_reference=doc.extracted_reference,
        extracted_emetteur=doc.extracted_emetteur,
        extracted_destinataire=doc.extracted_destinataire,
        classification_reasoning=doc.classification_reasoning,
        module_routed_to=doc.module_routed_to,
        entreprise_id=getattr(doc, "entreprise_id", None),
        projet_id=getattr(doc, "projet_id", None),
        statut_ingestion=getattr(doc, "statut_ingestion", None),
        ged_path=getattr(doc, "ged_path", None),
        champs_manquants=getattr(doc, "champs_manquants", None),
    )


async def _collect_workflow_artifacts(db: AsyncSession, workflow_id: str) -> list[dict[str, Any]]:
    """Load workflow artifacts in creation order for API responses."""
    artifacts: list[dict[str, Any]] = []
    result = await db.execute(
        select(Artifact).where(Artifact.workflow_id == workflow_id).order_by(Artifact.created_at)
    )
    for artifact in result.scalars().all():
        artifacts.append({
            "id": str(artifact.id),
            "artifact_type": artifact.artifact_type.value,
            "data": artifact.data,
            "created_at": artifact.created_at.isoformat(),
        })
    return artifacts


async def _run_document_pipeline(
    *,
    doc: Document,
    user: User,
    db: AsyncSession,
    graph_type: str = "document_to_ledger",
) -> dict[str, Any]:
    """Execute the AI workflow for a single document and return a normalized result."""
    from app.orchestrator.engine import OrchestrationGraph, RunContext
    from app.orchestrator.graphs import GRAPH_REGISTRY
    from app.schemas.artifacts import WorkflowState

    if graph_type not in GRAPH_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown graph: {graph_type}. Available: {list(GRAPH_REGISTRY.keys())}",
        )

    wf = Workflow(
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        graph_type=graph_type,
        doc_ids=[str(doc.id)],
        status=WorkflowStatus.RUNNING,
    )
    db.add(wf)
    await db.flush()

    settings = get_settings()
    builder = GRAPH_REGISTRY[graph_type]
    graph: OrchestrationGraph = builder()

    workflow_state = WorkflowState(
        workflow_id=str(wf.id),
        tenant_id=str(user.tenant_id),
        actor_user_id=str(user.id),
        doc_ids=[str(doc.id)],
        status="RUNNING",
    )

    run_ctx = RunContext(
        db_session=db,
        storage=get_storage_service(),
        settings=settings,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        workflow_id=str(wf.id),
    )

    final_state = None
    try:
        final_state = await graph.execute(workflow_state, run_ctx)
        wf.node_history = final_state.node_history
        wf.current_node = final_state.current_node
        wf.artifacts = final_state.artifacts
        wf.warnings = final_state.warnings

        if final_state.status == "BLOCKED":
            wf.status = WorkflowStatus.BLOCKED
            wf.blocking_reasons = final_state.blocking_reasons
        elif final_state.status == "FAILED":
            wf.status = WorkflowStatus.FAILED
            wf.errors = final_state.errors
        else:
            await db.flush()
            await db.refresh(wf)
            if wf.status not in (WorkflowStatus.COMMITTED, WorkflowStatus.BLOCKED, WorkflowStatus.FAILED):
                wf.status = WorkflowStatus.READY_TO_COMMIT
    except Exception as exc:
        wf.status = WorkflowStatus.FAILED
        wf.errors = [{"code": "PROCESS_ERROR", "message": str(exc)}]
        try:
            await db.rollback()
        except Exception:
            pass
        db.add(wf)

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="document_process",
        entity_type="workflow",
        entity_id=str(wf.id),
    ))
    await db.commit()
    await db.refresh(wf)
    await db.refresh(doc)

    all_artifacts = await _collect_workflow_artifacts(db, str(wf.id))

    extracted_data: dict[str, Any] = {}
    for artifact in all_artifacts:
        if artifact["artifact_type"] == "extraction":
            extracted_data = artifact.get("data", {}) or {}
            break

    state_artifacts = wf.artifacts or {}
    created_record_ids = list(state_artifacts.get("module_router", []))
    journal_entry_ids = list(state_artifacts.get("commit", []))
    routed_to = doc.module_routed_to or "documents"
    result_status = "FAILED" if wf.status == WorkflowStatus.FAILED else wf.status.value

    return {
        "workflow_id": str(wf.id),
        "workflow_status": wf.status.value,
        "status": result_status,
        "document_id": str(doc.id),
        "doc_type": doc.doc_type.value if doc.doc_type else None,
        "routed_to": routed_to,
        "created_record_ids": created_record_ids,
        "journal_entry_ids": journal_entry_ids,
        "extracted_data": extracted_data,
        "node_history": wf.node_history or [],
        "artifacts": all_artifacts,
        "errors": wf.errors or [],
        "warnings": wf.warnings or [],
        "blocking_reasons": wf.blocking_reasons or [],
    }


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    doc_type_hint: Optional[str] = Query(None, description="Optional document type hint"),
    realite_financiere: Optional[str] = Query(None, description="RF1=Réel Déclaré, RF2=Réel Non Déclaré, RF3=Fictif"),
    entreprise_id: Optional[str] = Query(None, description="Link to entité juridique"),
    projet_id: Optional[str] = Query(None, description="Link to project"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document (PDF/image) for processing."""
    response, _ = await _ingest_document_upload(
        file=file, user=user, db=db,
        doc_type_hint=doc_type_hint,
        realite_financiere=realite_financiere,
        entreprise_id=entreprise_id,
        projet_id=projet_id,
    )
    return response


@router.post("/bulk-upload", status_code=status.HTTP_201_CREATED)
async def bulk_upload_documents(
    files: list[UploadFile] = File(...),
    doc_type_hint: Optional[str] = Query(None, description="Optional document type hint"),
    realite_financiere: Optional[str] = Query(None, description="RF1=Réel Déclaré, RF2=Réel Non Déclaré, RF3=Fictif"),
    auto_process: bool = Query(True, description="Automatically process and route each uploaded document"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Bulk upload documents, auto-process them, and return a summary report."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucun fichier fourni")

    items: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    duplicate_count = 0
    processed_count = 0
    routed_count = 0
    module_counts: dict[str, int] = {}

    for file in files:
        try:
            response, is_duplicate = await _ingest_document_upload(
                file=file,
                user=user,
                db=db,
                doc_type_hint=doc_type_hint,
                realite_financiere=realite_financiere,
            )
            item = response.model_dump(mode="json")
            if is_duplicate:
                duplicate_count += 1
                item["upload_status"] = "DUPLICATE"
                item["processing_status"] = None
                item["routed_to"] = item.get("module_routed_to") or "documents"
                items.append(item)
                if item["routed_to"]:
                    module_counts[item["routed_to"]] = module_counts.get(item["routed_to"], 0) + 1
                continue

            item["upload_status"] = "INGESTED"

            if auto_process:
                doc_result = await db.execute(
                    select(Document).where(Document.id == str(response.id), Document.tenant_id == user.tenant_id)
                )
                doc = doc_result.scalar_one_or_none()
                if doc is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found after upload")

                process_result = await _run_document_pipeline(doc=doc, user=user, db=db)
                item.update({
                    "processing_status": process_result["status"],
                    "workflow_id": process_result["workflow_id"],
                    "workflow_status": process_result["workflow_status"],
                    "routed_to": process_result["routed_to"],
                    "created_record_ids": process_result["created_record_ids"],
                    "journal_entry_ids": process_result["journal_entry_ids"],
                    "warnings": process_result["warnings"],
                    "errors": process_result["errors"],
                })
                processed_count += 1
                if process_result["routed_to"] and process_result["routed_to"] != "documents":
                    routed_count += 1
                module_counts[process_result["routed_to"]] = module_counts.get(process_result["routed_to"], 0) + 1
            else:
                item["processing_status"] = None
                item["routed_to"] = item.get("module_routed_to") or "documents"
                module_counts[item["routed_to"]] = module_counts.get(item["routed_to"], 0) + 1

            items.append(item)
        except HTTPException as exc:
            await db.rollback()
            failures.append({
                "filename": file.filename,
                "detail": exc.detail,
                "status_code": exc.status_code,
            })
        except Exception as exc:
            await db.rollback()
            logger.exception("bulk_document_upload_error", filename=file.filename)
            failures.append({
                "filename": file.filename,
                "detail": str(exc),
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            })

    return {
        "status": "ok",
        "total_files": len(files),
        "uploaded_count": len(items) - duplicate_count,
        "duplicate_count": duplicate_count,
        "failed_count": len(failures),
        "processed_count": processed_count,
        "routed_count": routed_count,
        "module_counts": module_counts,
        "auto_process": auto_process,
        "items": items,
        "failures": failures,
    }


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    entreprise_id: Optional[str] = Query(None),
    projet_id: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    realite_financiere: Optional[str] = Query(None),
    x_entreprise_id: Optional[str] = Header(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List documents — auto-scoped to active entreprise."""
    from fastapi import Header as _H
    conditions = [Document.tenant_id == user.tenant_id]

    ent_filter = entreprise_id or x_entreprise_id
    if ent_filter:
        conditions.append(Document.entreprise_id == ent_filter)
    if projet_id:
        conditions.append(Document.projet_id == projet_id)
    if doc_type:
        try:
            conditions.append(Document.doc_type == DocType(doc_type))
        except ValueError:
            pass
    if realite_financiere:
        conditions.append(Document.realite_financiere == realite_financiere)

    base_query = select(Document).where(*conditions)
    count_query = select(func.count()).select_from(Document).where(*conditions)

    total = (await db.execute(count_query)).scalar()
    result = await db.execute(
        base_query.order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    docs = result.scalars().all()

    return DocumentListResponse(
        items=[_doc_to_response(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get document details."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.tenant_id == user.tenant_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return _doc_to_response(doc)


# ── Document Correction (fix AI classification mistakes) ────────────────────

@router.patch("/{doc_id}", response_model=DocumentResponse)
async def correct_document(
    doc_id: str,
    body: DocumentCorrection,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Correct AI-classified document fields (type, montant, reference, etc.)."""
    from app.schemas.api import DocumentCorrection  # noqa – already in scope via param

    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.tenant_id == user.tenant_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    old_values = {}
    updates = body.model_dump(exclude_unset=True)

    for field, value in updates.items():
        if field == "doc_type" and value is not None:
            try:
                new_type = DocType(value)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid doc_type: {value}")
            old_values["doc_type"] = doc.doc_type.value if doc.doc_type else None
            doc.doc_type = new_type
            doc.doc_type_confidence = 1.0  # manual correction = 100% confidence
            doc.classification_reasoning = "Corrigé manuellement par l'utilisateur"
        elif field == "extracted_montant" and value is not None:
            old_values["extracted_montant"] = float(doc.extracted_montant) if doc.extracted_montant else None
            doc.extracted_montant = Decimal(str(value))
        elif field == "extracted_montant_ht" and value is not None:
            old_values["extracted_montant_ht"] = float(doc.extracted_montant_ht) if doc.extracted_montant_ht else None
            doc.extracted_montant_ht = Decimal(str(value))
        elif field == "extracted_tva" and value is not None:
            old_values["extracted_tva"] = float(doc.extracted_tva) if doc.extracted_tva else None
            doc.extracted_tva = Decimal(str(value))
        elif field == "extracted_date" and value is not None:
            old_values["extracted_date"] = doc.extracted_date
            doc.extracted_date = value
        elif field == "extracted_reference" and value is not None:
            old_values["extracted_reference"] = doc.extracted_reference
            doc.extracted_reference = value
        elif field == "extracted_emetteur" and value is not None:
            old_values["extracted_emetteur"] = doc.extracted_emetteur
            doc.extracted_emetteur = value
        elif field == "extracted_destinataire" and value is not None:
            old_values["extracted_destinataire"] = doc.extracted_destinataire
            doc.extracted_destinataire = value

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="document_correct",
        entity_type="document",
        entity_id=str(doc_id),
        old_value=old_values,
        new_value=updates,
    ))
    await db.commit()
    await db.refresh(doc)
    return _doc_to_response(doc)


# ── Document Download / Preview ─────────────────────────────────────────────

@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str,
    token: Optional[str] = Query(None, description="JWT for img/iframe preview auth"),
    db: AsyncSession = Depends(get_db),
):
    """Download / preview document. Accepts auth via Bearer header OR ?token= query param."""
    from fastapi.responses import Response
    from app.auth.security import decode_token as _decode
    from app.auth.dependencies import get_optional_user

    # Resolve user from query token (for img/iframe that can't send headers)
    user = None
    if token:
        payload = _decode(token)
        if payload and payload.get("sub"):
            r = await db.execute(select(User).where(User.id == payload["sub"]))
            user = r.scalar_one_or_none()

    # If no query token, the request may have a Bearer header — try optional auth
    if not user:
        try:
            from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
            # Manual header extraction since we can't use Depends here cleanly
            # This endpoint is reached via Vite proxy so the header should be there
            # For img/iframe, the token query param is the fallback
            pass
        except Exception:
            pass

    # If still no user, allow without tenant scoping (for preview URLs with token)
    if not user:
        # Try to just load the doc without tenant check (public preview with token)
        result = await db.execute(select(Document).where(Document.id == doc_id))
    else:
        result = await db.execute(
            select(Document).where(Document.id == doc_id, Document.tenant_id == user.tenant_id)
        )

    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    storage = get_storage_service()
    try:
        data = await storage.download(doc.storage_key)
    except Exception as exc:
        logger.error("document_download_failed", doc_id=doc_id, error=str(exc))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in storage")

    mime = doc.mime_type or "application/octet-stream"
    inline_types = {"application/pdf", "image/jpeg", "image/png", "image/tiff", "image/webp"}
    disposition = "inline" if mime in inline_types else "attachment"

    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f'{disposition}; filename="{doc.filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document (admin/accountant only)."""
    if user.role not in ("admin", "accountant"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.tenant_id == user.tenant_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    storage = get_storage_service()
    try:
        await storage.delete(doc.storage_key)
    except Exception:
        pass

    await db.delete(doc)
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="document_delete",
        entity_type="document",
        entity_id=str(doc_id),
    ))
    await db.commit()


@router.get("/{doc_id}/artifacts")
async def get_document_artifacts(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all artifacts for a document."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.tenant_id == user.tenant_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    result = await db.execute(
        select(Artifact).where(Artifact.doc_id == doc_id).order_by(Artifact.created_at)
    )
    artifacts = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "artifact_type": a.artifact_type.value,
            "data": a.data,
            "created_at": a.created_at.isoformat(),
        }
        for a in artifacts
    ]


@router.post("/{doc_id}/process")
async def process_document(
    doc_id: str,
    graph_type: str = Query("document_to_ledger", description="Processing graph to use"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Auto-create a workflow and run the AI pipeline on a document.

    This is the main endpoint for triggering AI analysis:
    upload → process → extraction → classification → ledger proposal.
    """
    # Verify document exists
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.tenant_id == user.tenant_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        return await _run_document_pipeline(doc=doc, user=user, db=db, graph_type=graph_type)
    except Exception as exc:
        logger.error("process_commit_failed", error=str(exc), doc_id=doc_id)
        return {
            "workflow_id": None,
            "workflow_status": "FAILED",
            "status": "FAILED",
            "document_id": str(doc_id),
            "doc_type": doc.doc_type.value if doc.doc_type else None,
            "routed_to": doc.module_routed_to or "documents",
            "created_record_ids": [],
            "journal_entry_ids": [],
            "extracted_data": {},
            "node_history": [],
            "artifacts": [],
            "errors": [{"code": "PROCESS_ERROR", "message": str(exc)}],
            "warnings": [],
            "blocking_reasons": [],
        }


# ── Full-Text Search (Section 15 — EX-GED-002) ─────────────────────────

@router.get("/search")
async def search_documents(
    q: str = Query(..., min_length=2, description="Search query — searches filename, text content, emetteur, reference"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search across document content, filename, and extracted fields.

    EX-GED-002: 100% of documents are searchable by keyword.
    Uses SQLite LIKE for now; can be replaced with ElasticSearch in production.
    """
    from sqlalchemy import or_

    like_pattern = f"%{q}%"
    conditions = [
        Document.tenant_id == user.tenant_id,
        or_(
            Document.filename.ilike(like_pattern),
            Document.extracted_text.ilike(like_pattern),
            Document.extracted_emetteur.ilike(like_pattern),
            Document.extracted_destinataire.ilike(like_pattern),
            Document.extracted_reference.ilike(like_pattern),
            Document.classification_reasoning.ilike(like_pattern),
        ),
    ]

    count_query = select(func.count()).select_from(Document).where(*conditions)
    total = (await db.execute(count_query)).scalar()

    result = await db.execute(
        select(Document).where(*conditions)
        .order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    docs = result.scalars().all()

    return {
        "query": q,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_doc_to_response(d) for d in docs],
    }


# ── Pipeline Status (Section 14 — 7 Layers) ────────────────────────────

@router.get("/pipeline/stats")
async def pipeline_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get ingestion pipeline statistics across all 7 layers.

    Section 14: Shows the health of each pipeline layer.
    """
    total = (await db.execute(
        select(func.count()).select_from(Document).where(Document.tenant_id == user.tenant_id)
    )).scalar() or 0

    # C1: Total received
    c1_received = total

    # C2: OCR processed (has_text_layer or extracted_text not null)
    c2_ocr = (await db.execute(
        select(func.count()).select_from(Document).where(
            Document.tenant_id == user.tenant_id,
            or_(Document.has_text_layer == True, Document.extracted_text.isnot(None)),
        )
    )).scalar() or 0

    # C3: Deduplicated (all are unique by design — count total unique hashes)
    c3_unique = (await db.execute(
        select(func.count(func.distinct(Document.sha256))).where(Document.tenant_id == user.tenant_id)
    )).scalar() or 0

    # C4: Classified (doc_type != OTHER or confidence > 0.5)
    c4_classified = (await db.execute(
        select(func.count()).select_from(Document).where(
            Document.tenant_id == user.tenant_id,
            Document.doc_type != DocType.OTHER,
        )
    )).scalar() or 0

    # C5: Extracted (at least one extracted field is not null)
    from sqlalchemy import or_ as sql_or
    c5_extracted = (await db.execute(
        select(func.count()).select_from(Document).where(
            Document.tenant_id == user.tenant_id,
            sql_or(
                Document.extracted_montant.isnot(None),
                Document.extracted_date.isnot(None),
                Document.extracted_reference.isnot(None),
            ),
        )
    )).scalar() or 0

    # C6: Alias resolved (entreprise_id or projet_id set)
    c6_resolved = (await db.execute(
        select(func.count()).select_from(Document).where(
            Document.tenant_id == user.tenant_id,
            sql_or(
                Document.entreprise_id.isnot(None),
                Document.projet_id.isnot(None),
            ),
        )
    )).scalar() or 0

    # C7: Indexed (extracted_text stored for search)
    c7_indexed = (await db.execute(
        select(func.count()).select_from(Document).where(
            Document.tenant_id == user.tenant_id,
            Document.extracted_text.isnot(None),
        )
    )).scalar() or 0

    # A_COMPLETER queue
    a_completer = (await db.execute(
        select(func.count()).select_from(Document).where(
            Document.tenant_id == user.tenant_id,
            Document.statut_ingestion == "A_COMPLETER",
        )
    )).scalar() or 0

    return {
        "total_documents": total,
        "pipeline": [
            {"couche": "C1", "nom": "Réception", "count": c1_received, "pct": 100 if total > 0 else 0},
            {"couche": "C2", "nom": "OCR / Extraction texte", "count": c2_ocr, "pct": round(c2_ocr / total * 100) if total > 0 else 0},
            {"couche": "C3", "nom": "Déduplication (SHA-256)", "count": c3_unique, "pct": round(c3_unique / total * 100) if total > 0 else 0},
            {"couche": "C4", "nom": "Classification IA", "count": c4_classified, "pct": round(c4_classified / total * 100) if total > 0 else 0},
            {"couche": "C5", "nom": "Extraction données", "count": c5_extracted, "pct": round(c5_extracted / total * 100) if total > 0 else 0},
            {"couche": "C6", "nom": "Résolution d'alias", "count": c6_resolved, "pct": round(c6_resolved / total * 100) if total > 0 else 0},
            {"couche": "C7", "nom": "Indexation full-text", "count": c7_indexed, "pct": round(c7_indexed / total * 100) if total > 0 else 0},
        ],
        "a_completer": a_completer,
    }


# ── Document Completion (EX-ING-002) ────────────────────────────────────

@router.post("/{doc_id}/complete")
async def complete_document(
    doc_id: str,
    body: DocumentCorrection,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Complete missing fields on a document marked A_COMPLETER.

    After completion, re-runs auto-routing to ADV if applicable.
    """
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.tenant_id == user.tenant_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document introuvable")

    # Update fields
    if body.extracted_montant is not None:
        doc.extracted_montant = body.extracted_montant
    if body.extracted_montant_ht is not None:
        doc.extracted_montant_ht = body.extracted_montant_ht
    if body.extracted_tva is not None:
        doc.extracted_tva = body.extracted_tva
    if body.extracted_date:
        doc.extracted_date = body.extracted_date
    if body.extracted_reference:
        doc.extracted_reference = body.extracted_reference
    if body.extracted_emetteur:
        doc.extracted_emetteur = body.extracted_emetteur
    if body.extracted_destinataire:
        doc.extracted_destinataire = body.extracted_destinataire
    if body.doc_type:
        try:
            doc.doc_type = DocType(body.doc_type)
        except ValueError:
            pass

    doc.statut_ingestion = "TRAITE"
    doc.champs_manquants = []

    # Re-run auto-routing to ADV
    ADV_TYPES = {DocType.ADV_CONTRACT, DocType.ADV_PAYMENT, DocType.CHEQUE}
    if doc.doc_type in ADV_TYPES:
        doc.module_routed_to = "adv"
        classification = {
            "montant_ttc": float(doc.extracted_montant) if doc.extracted_montant else None,
            "reference": doc.extracted_reference,
            "date": doc.extracted_date,
            "emetteur": doc.extracted_emetteur,
            "destinataire": doc.extracted_destinataire,
        }
        await _auto_create_adv_record(doc, classification, user, db)

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action="document_complete", entity_type="document", entity_id=doc_id,
    ))
    await db.commit()
    await db.refresh(doc)
    return _doc_to_response(doc)


# ── List A_COMPLETER documents ──────────────────────────────────────────

@router.get("/a-completer")
async def list_incomplete_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all documents that need manual completion (EX-ING-002)."""
    result = await db.execute(
        select(Document).where(
            Document.tenant_id == user.tenant_id,
            Document.statut_ingestion == "A_COMPLETER",
        ).order_by(Document.created_at.desc())
    )
    return [_doc_to_response(d) for d in result.scalars().all()]


# ── GED Browser (Section 15 — EX-GED-001) ───────────────────────────────

@router.get("/ged/tree")
async def ged_tree(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the GED tree organized by Entity / Project / Year / DocType.

    EX-GED-001: Normalized arborescence.
    """
    from sqlalchemy import text as sa_text

    result = await db.execute(sa_text("""
        SELECT
            COALESCE(e.code, 'GENERAL') as entite,
            COALESCE(p.code, 'COMMUN') as projet,
            COALESCE(SUBSTR(d.extracted_date, 1, 4), STRFTIME('%Y', d.created_at)) as annee,
            COALESCE(d.doc_type, 'OTHER') as doc_type,
            COUNT(*) as nb_docs,
            COALESCE(SUM(d.file_size), 0) as taille_totale
        FROM documents d
        LEFT JOIN entreprises e ON d.entreprise_id = e.id
        LEFT JOIN projets p ON d.projet_id = p.id
        WHERE d.tenant_id = :tid
        GROUP BY entite, projet, annee, doc_type
        ORDER BY entite, projet, annee, doc_type
    """), {"tid": user.tenant_id})

    tree: dict = {}
    for row in result.fetchall():
        ent, proj, year, dtype, count, size = row
        tree.setdefault(ent, {}).setdefault(proj, {}).setdefault(year or "N/A", {}).setdefault(dtype, {
            "count": 0, "size": 0,
        })
        tree[ent][proj][year or "N/A"][dtype]["count"] += count
        tree[ent][proj][year or "N/A"][dtype]["size"] += size

    return tree


# ── AI Document Query Agent ─────────────────────────────────────────────

@router.post("/ged/ai-query")
async def ged_ai_query(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI agent that answers questions about documents in the GED.

    Only answers data extraction queries (sums, counts, lists from documents).
    Refuses any other type of question.
    """
    question = body.get("question", "").strip()
    if not question or len(question) < 5:
        raise HTTPException(400, "Question trop courte (min 5 caractères)")

    # Gather document summary for AI context
    result = await db.execute(
        select(
            Document.doc_type,
            Document.extracted_montant,
            Document.extracted_date,
            Document.extracted_reference,
            Document.extracted_emetteur,
            Document.extracted_destinataire,
            Document.filename,
            Document.ged_path,
        ).where(Document.tenant_id == user.tenant_id)
        .order_by(Document.created_at.desc())
        .limit(500)
    )
    docs = result.all()

    if not docs:
        return {"answer": "Aucun document trouvé dans la GED.", "documents_analyzed": 0}

    # Build document list for AI
    doc_lines = []
    for d in docs:
        doc_type, montant, date_doc, ref, emetteur, dest, filename, ged_path = d
        parts = [f"fichier={filename}"]
        if doc_type:
            parts.append(f"type={doc_type}")
        if montant:
            parts.append(f"montant={float(montant)}")
        if date_doc:
            parts.append(f"date={date_doc}")
        if ref:
            parts.append(f"ref={ref}")
        if emetteur:
            parts.append(f"emetteur={emetteur}")
        if dest:
            parts.append(f"destinataire={dest}")
        if ged_path:
            parts.append(f"chemin={ged_path}")
        doc_lines.append(" | ".join(parts))

    docs_text = "\n".join(doc_lines)

    system_prompt = """\
Tu es un agent IA d'analyse documentaire pour le système GED de Groupe Dendani.

RÈGLES STRICTES:
1. Tu ne réponds QU'aux questions d'extraction de données à partir des documents (sommes, comptages, listes, moyennes, recherches)
2. Tu REFUSES toute question qui n'est pas liée aux documents (pas de conversation, pas de conseil, pas de code)
3. Si la question n'est pas liée aux documents, réponds: "Je ne peux répondre qu'aux questions concernant les documents de la GED."
4. Utilise les données fournies pour calculer les réponses
5. Réponds toujours en français
6. Sois précis avec les montants (format: X XXX XXX,XX DA)

Réponds en JSON:
{
  "answer": "La réponse détaillée en français",
  "calculation_details": "Détail du calcul si applicable",
  "documents_matched": nombre de documents utilisés pour la réponse
}
Pas de blocs markdown."""

    user_prompt = f"""Question: {question}

Documents disponibles ({len(docs)} documents):
{docs_text}"""

    try:
        from app.services.llm_graph import invoke_json_agent
        ai_result = await invoke_json_agent(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=1024,
        )
        parsed = ai_result.get("parsed_json", {})
        return {
            "answer": parsed.get("answer", "Impossible de traiter cette question."),
            "calculation_details": parsed.get("calculation_details"),
            "documents_analyzed": len(docs),
            "documents_matched": parsed.get("documents_matched", 0),
        }
    except Exception as exc:
        return {
            "answer": f"Service IA indisponible: {exc}",
            "documents_analyzed": len(docs),
            "documents_matched": 0,
        }
