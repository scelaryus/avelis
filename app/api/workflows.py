"""GFI Platform - Workflows API router."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.core import User, Document, Workflow, WorkflowStatus, AuditLog
from app.auth.dependencies import get_current_user, require_role
from app.orchestrator.engine import OrchestrationGraph, RunContext
from app.orchestrator.graphs import GRAPH_REGISTRY
from app.storage.service import get_storage_service
from app.schemas.api import WorkflowResponse, WorkflowListResponse
from app.schemas.artifacts import WorkflowState
from app.config import get_settings

router = APIRouter(tags=["Workflows"])


def _wf_to_response(wf: Workflow) -> WorkflowResponse:
    return WorkflowResponse(
        id=wf.id,
        status=wf.status.value,
        graph_type=wf.graph_type,
        doc_ids=wf.doc_ids or [],
        artifacts=wf.artifacts or {},
        blocking_reasons=wf.blocking_reasons or [],
        errors=wf.errors or [],
        warnings=wf.warnings or [],
        current_node=wf.current_node,
        node_history=wf.node_history or [],
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    document_id: str,
    graph_type: str = "document_to_ledger",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create and start a new processing workflow for a document."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.tenant_id == user.tenant_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if graph_type not in GRAPH_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown graph: {graph_type}. Available: {list(GRAPH_REGISTRY.keys())}",
        )

    wf = Workflow(
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        graph_type=graph_type,
        doc_ids=[str(document_id)],
        status=WorkflowStatus.CREATED,
    )
    db.add(wf)
    await db.flush()

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="workflow_create",
        entity_type="workflow",
        entity_id=str(wf.id),
    ))
    await db.commit()
    await db.refresh(wf)

    return _wf_to_response(wf)


@router.post("/{workflow_id}/run", response_model=WorkflowResponse)
async def run_workflow(
    workflow_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute a workflow through the orchestration graph."""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == user.tenant_id)
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    if wf.status in (WorkflowStatus.COMMITTED, WorkflowStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow already in terminal state: {wf.status.value}",
        )

    # load first document
    doc_id = wf.doc_ids[0] if wf.doc_ids else None
    doc = None
    file_bytes = b""
    if doc_id:
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()
        if doc:
            storage = get_storage_service()
            file_bytes = await storage.download(doc.storage_key)

    # build graph and execute
    builder = GRAPH_REGISTRY[wf.graph_type]
    graph: OrchestrationGraph = builder()

    settings = get_settings()

    # Construct proper WorkflowState and RunContext
    workflow_state = WorkflowState(
        workflow_id=str(wf.id),
        tenant_id=str(user.tenant_id),
        actor_user_id=str(user.id),
        doc_ids=wf.doc_ids or [],
        status="RUNNING",
        artifacts=wf.artifacts or {},
        blocking_reasons=[],
        errors=[],
        warnings=[],
        decisions=wf.decisions if hasattr(wf, 'decisions') and wf.decisions else [],
        current_node=None,
        node_history=wf.node_history or [],
    )

    run_ctx = RunContext(
        db_session=db,
        storage=get_storage_service(),
        settings=settings,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        workflow_id=str(wf.id),
    )

    wf.status = WorkflowStatus.RUNNING
    await db.commit()

    try:
        final_state = await graph.execute(workflow_state, run_ctx)
        wf.node_history = final_state.node_history
        wf.current_node = final_state.current_node
        wf.artifacts = final_state.artifacts

        if final_state.status == "BLOCKED":
            wf.status = WorkflowStatus.BLOCKED
            wf.blocking_reasons = final_state.blocking_reasons
        elif final_state.status == "FAILED":
            wf.status = WorkflowStatus.FAILED
            wf.errors = final_state.errors
        elif final_state.status == "READY_TO_COMMIT":
            wf.status = WorkflowStatus.READY_TO_COMMIT
        else:
            wf.status = WorkflowStatus.READY_TO_COMMIT

        wf.warnings = final_state.warnings
    except Exception as e:
        wf.status = WorkflowStatus.FAILED
        wf.errors = [{"code": "WORKFLOW_EXCEPTION", "message": str(e)}]

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="workflow_run",
        entity_type="workflow",
        entity_id=str(wf.id),
    ))
    await db.commit()
    await db.refresh(wf)

    return _wf_to_response(wf)


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List workflows for current tenant."""
    base = select(Workflow).where(Workflow.tenant_id == user.tenant_id)
    count_base = select(func.count()).select_from(Workflow).where(Workflow.tenant_id == user.tenant_id)

    if status_filter:
        try:
            ws = WorkflowStatus(status_filter)
            base = base.where(Workflow.status == ws)
            count_base = count_base.where(Workflow.status == ws)
        except ValueError:
            pass

    total = (await db.execute(count_base)).scalar()
    result = await db.execute(
        base.order_by(Workflow.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    wfs = result.scalars().all()

    return WorkflowListResponse(
        items=[_wf_to_response(w) for w in wfs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get workflow details."""
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == user.tenant_id)
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    return _wf_to_response(wf)


@router.post("/{workflow_id}/resolve")
async def resolve_anomaly(
    workflow_id: str,
    anomaly_id: str,
    resolution_action: str,
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Apply a resolution to a workflow anomaly."""
    from app.models.core import AnomalyRecord

    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.tenant_id == user.tenant_id)
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    result = await db.execute(select(AnomalyRecord).where(AnomalyRecord.id == anomaly_id))
    anomaly = result.scalar_one_or_none()
    if anomaly is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anomaly not found")

    anomaly.is_resolved = True
    anomaly.resolved_by = user.id
    anomaly.resolution = {"action": resolution_action}

    # check if all anomalies resolved
    result = await db.execute(
        select(func.count()).select_from(AnomalyRecord).where(
            AnomalyRecord.workflow_id == workflow_id,
            AnomalyRecord.is_resolved == False,
        )
    )
    remaining = result.scalar()
    if remaining == 0 and wf.status == WorkflowStatus.BLOCKED:
        wf.status = WorkflowStatus.CREATED  # ready for re-run

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="anomaly_resolve",
        entity_type="anomaly",
        entity_id=str(anomaly_id),
    ))
    await db.commit()

    return {"status": "resolved", "remaining_anomalies": remaining}
