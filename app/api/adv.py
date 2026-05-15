"""GFI Platform - ADV (Ventes) API router."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form, Header
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.core import User, AuditLog
from app.models.adv import Client, Contract, Receivable, Payment
from app.auth.dependencies import get_current_user, require_role
from app.schemas.api import (
    ClientCreate, ClientResponse,
    ContractCreate, ContractResponse,
    PaymentCreate, PaymentResponse,
    ReceivableCreate, ReceivableResponse,
)

router = APIRouter(tags=["ADV - Sales Administration"])


# ── Clients ────────────────────────────────────────────────────────

@router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    body: ClientCreate,
    file: Optional[UploadFile] = File(None, description="Pièce justificative (CIN, registre commerce)"),
    user: User = Depends(require_role("admin", "accountant", "sales")),
    db: AsyncSession = Depends(get_db),
):
    """Create a client record. Proof document is verified by AI if provided."""
    # Auto-generate code if not provided
    if not body.code:
        # CLI-XXXXXX based on count
        result = await db.execute(select(func.count(Client.id)).where(Client.tenant_id == user.tenant_id))
        count = result.scalar() or 0
        body.code = f"CLI-{count + 1:04d}"

    # AI proof verification if document provided
    if file and file.filename:
        from app.services.proof_verifier import verify_proof
        proof = await verify_proof(
            file, "creer_client",
            {"client_name": body.name, "action_detail": f"Création client {body.code}"},
            user.tenant_id, user.id, db,
        )
        if not proof["verified"]:
            raise HTTPException(400, f"BLOCAGE : Document non conforme — {proof['rejection_reason']}")

    client = Client(
        tenant_id=user.tenant_id,
        code=body.code,
        name=body.name,
        legal_name=body.legal_name,
        tax_id=body.tax_id,
        ice=body.ice,
        address=body.address,
        city=body.city,
        email=body.email,
        phone=body.phone,
        payment_terms_days=body.payment_terms_days,
        account_code=body.account_code,
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
    )
    db.add(client)
    await db.flush()

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="client_create",
        entity_type="client",
        entity_id=str(client.id),
    ))
    await db.commit()
    await db.refresh(client)

    return ClientResponse(
        id=client.id,
        code=client.code,
        name=client.name,
        legal_name=client.legal_name,
        tax_id=client.tax_id,
        ice=client.ice,
        address=client.address,
        email=client.email,
        phone=client.phone,
        payment_terms_days=client.payment_terms_days,
        is_active=client.is_active,
        entreprise_id=client.entreprise_id,
        projet_id=client.projet_id,
        created_at=client.created_at,
    )


@router.get("/clients", response_model=list[ClientResponse])
async def list_clients(
    projet_id: Optional[str] = Query(None),
    entreprise_id: Optional[str] = Query(None),
    x_entreprise_id: Optional[str] = Header(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List clients — scoped to active entreprise."""
    query = select(Client).where(Client.tenant_id == user.tenant_id)
    ent_filter = entreprise_id or x_entreprise_id
    if projet_id:
        query = query.where(Client.projet_id == projet_id)
    if ent_filter:
        query = query.where(Client.entreprise_id == ent_filter)
    result = await db.execute(query.order_by(Client.name))
    clients = result.scalars().all()
    return [
        ClientResponse(
            id=c.id, code=c.code, name=c.name, legal_name=c.legal_name,
            tax_id=c.tax_id, ice=c.ice, address=c.address,
            email=c.email, phone=c.phone,
            payment_terms_days=c.payment_terms_days, is_active=c.is_active,
            entreprise_id=c.entreprise_id, projet_id=c.projet_id,
            created_at=c.created_at,
        )
        for c in clients
    ]


@router.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get client details."""
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.tenant_id == user.tenant_id)
    )
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return ClientResponse(
        id=client.id, code=client.code, name=client.name, legal_name=client.legal_name,
        tax_id=client.tax_id, ice=client.ice, address=client.address,
        email=client.email, phone=client.phone,
        payment_terms_days=client.payment_terms_days, is_active=client.is_active,
        entreprise_id=client.entreprise_id, projet_id=client.projet_id,
        created_at=client.created_at,
    )


# ── Contracts ──────────────────────────────────────────────────────

@router.post("/contracts", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    body: ContractCreate,
    file: UploadFile = File(..., description="Contrat signé ou promesse de vente (obligatoire)"),
    user: User = Depends(require_role("admin", "accountant", "sales")),
    db: AsyncSession = Depends(get_db),
):
    """Create a contract. Proof document is mandatory and verified by AI."""
    if not file or not file.filename:
        raise HTTPException(400, "Un justificatif (contrat signé, promesse de vente) est obligatoire.")

    from app.services.proof_verifier import verify_proof
    proof = await verify_proof(
        file, "creer_contrat",
        {"montant": body.total_amount or 0, "action_detail": f"Contrat {body.contract_number}"},
        user.tenant_id, user.id, db,
    )
    if not proof["verified"]:
        raise HTTPException(400, f"BLOCAGE : Document non conforme — {proof['rejection_reason']}")

    contract = Contract(
        tenant_id=user.tenant_id,
        client_id=body.client_id,
        contract_number=body.contract_number,
        title=body.title,
        total_amount=body.total_amount,
        start_date=body.start_date,
        end_date=body.end_date,
        terms=body.terms,
        notes=body.notes,
        created_by=user.id,
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
    )
    db.add(contract)
    await db.flush()

    # Auto-create receivable (créance) from contract amount
    from app.models.adv import PaymentStatus
    from datetime import date as _date, timedelta
    if body.total_amount and body.total_amount > 0:
        due = body.end_date or (body.start_date + timedelta(days=90) if body.start_date else _date.today() + timedelta(days=90))
        receivable = Receivable(
            tenant_id=user.tenant_id,
            client_id=str(body.client_id),
            contract_id=contract.id,
            invoice_ref=f"CTR-{body.contract_number}",
            amount=body.total_amount,
            amount_paid=0,
            due_date=due,
            status=PaymentStatus.PENDING,
            entreprise_id=body.entreprise_id,
            projet_id=body.projet_id,
        )
        db.add(receivable)

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="contract_create",
        entity_type="contract",
        entity_id=str(contract.id),
    ))
    await db.commit()
    await db.refresh(contract)

    return ContractResponse(
        id=contract.id,
        client_id=contract.client_id,
        contract_number=contract.contract_number,
        title=contract.title,
        notes=contract.notes,
        total_amount=float(contract.total_amount) if contract.total_amount else None,
        start_date=contract.start_date,
        end_date=contract.end_date,
        status=contract.status.value if contract.status else None,
        entreprise_id=contract.entreprise_id,
        projet_id=contract.projet_id,
        created_at=contract.created_at,
    )


@router.get("/contracts", response_model=list[ContractResponse])
async def list_contracts(
    client_id: Optional[uuid.UUID] = Query(None),
    projet_id: Optional[str] = Query(None),
    entreprise_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List contracts, optionally filtered by project."""
    query = select(Contract).where(Contract.tenant_id == user.tenant_id)
    if client_id:
        query = query.where(Contract.client_id == client_id)
    if projet_id:
        query = query.where(Contract.projet_id == projet_id)
    if entreprise_id:
        query = query.where(Contract.entreprise_id == entreprise_id)
    result = await db.execute(query.order_by(Contract.created_at.desc()))
    contracts = result.scalars().all()
    return [
        ContractResponse(
            id=c.id,
            client_id=c.client_id,
            contract_number=c.contract_number,
            title=c.title,
            notes=c.notes,
            total_amount=float(c.total_amount) if c.total_amount else None,
            start_date=c.start_date,
            end_date=c.end_date,
            status=c.status.value if c.status else None,
            entreprise_id=c.entreprise_id,
            projet_id=c.projet_id,
            created_at=c.created_at,
        )
        for c in contracts
    ]


# ── Payments ───────────────────────────────────────────────────────

@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def record_payment(
    body: PaymentCreate,
    file: Optional[UploadFile] = File(None, description="Preuve de paiement (reçu, chèque, virement)"),
    user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """Record a client payment. Proof document verified by AI if provided."""
    if file and file.filename:
        from app.services.proof_verifier import verify_proof
        proof = await verify_proof(
            file, "enregistrer_paiement",
            {"montant": body.amount, "action_detail": f"Paiement {body.payment_ref or ''}"},
            user.tenant_id, user.id, db,
        )
        if not proof["verified"]:
            raise HTTPException(400, f"BLOCAGE : Preuve non conforme — {proof['rejection_reason']}")

    # Find receivable — explicit or auto-match by client
    receivable = None
    if body.receivable_id:
        result = await db.execute(
            select(Receivable).where(Receivable.id == body.receivable_id, Receivable.tenant_id == user.tenant_id)
        )
        receivable = result.scalar_one_or_none()
        if receivable is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Créance introuvable")
    else:
        # Auto-find oldest open receivable for this client
        result = await db.execute(
            select(Receivable).where(
                Receivable.client_id == str(body.client_id),
                Receivable.tenant_id == user.tenant_id,
                (Receivable.amount - Receivable.amount_paid) > 0,
            ).order_by(Receivable.due_date)
        )
        receivable = result.scalar_one_or_none()

    if receivable:
        remaining = float(receivable.amount) - float(receivable.amount_paid or 0)
        if body.amount > remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Le montant ({body.amount:,.2f} DA) dépasse le restant dû ({remaining:,.2f} DA)",
            )
        receivable.amount_paid = float(receivable.amount_paid or 0) + body.amount
        body.receivable_id = receivable.id

    payment = Payment(
        tenant_id=user.tenant_id,
        client_id=body.client_id,
        receivable_id=body.receivable_id,
        payment_ref=body.payment_ref,
        amount=body.amount,
        payment_date=body.payment_date,
        payment_method=body.payment_method,
        bank_ref=body.bank_ref,
        notes=body.notes,
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
        realite_financiere=body.realite_financiere,
    )
    db.add(payment)
    await db.flush()

    # Bridge: ADV Payment → Encaissement → CC imputation (automatic)
    if payment.entreprise_id:
        from app.services.adv_cc_bridge import create_encaissement_from_payment
        await create_encaissement_from_payment(
            payment, db, created_by=user.id,
        )

    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="payment_record",
        entity_type="payment",
    ))
    await db.commit()
    await db.refresh(payment)

    return PaymentResponse(
        id=payment.id,
        client_id=payment.client_id,
        amount=float(payment.amount),
        payment_date=payment.payment_date,
        payment_method=payment.payment_method,
        payment_ref=payment.payment_ref,
        entreprise_id=payment.entreprise_id,
        projet_id=payment.projet_id,
        created_at=payment.created_at,
    )


@router.get("/payments", response_model=list[PaymentResponse])
async def list_payments(
    client_id: Optional[uuid.UUID] = Query(None),
    projet_id: Optional[str] = Query(None),
    entreprise_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List payments, optionally filtered by project."""
    query = select(Payment).where(Payment.tenant_id == user.tenant_id)
    if client_id:
        query = query.where(Payment.client_id == client_id)
    if projet_id:
        query = query.where(Payment.projet_id == projet_id)
    if entreprise_id:
        query = query.where(Payment.entreprise_id == entreprise_id)
    result = await db.execute(query.order_by(Payment.payment_date.desc()))
    payments = result.scalars().all()
    return [
        PaymentResponse(
            id=p.id, client_id=p.client_id, amount=float(p.amount),
            payment_date=p.payment_date, payment_method=p.payment_method,
            payment_ref=p.payment_ref,
            entreprise_id=p.entreprise_id, projet_id=p.projet_id,
            created_at=p.created_at,
        )
        for p in payments
    ]


# ── Dashboard ──────────────────────────────────────────────────────

@router.get("/dashboard")
async def adv_dashboard(
    projet_id: Optional[str] = Query(None),
    entreprise_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """ADV module dashboard stats, optionally scoped by project."""
    from datetime import date
    from app.models.adv import ContractStatus

    # Build base filters
    client_filter = [Client.tenant_id == user.tenant_id]
    contract_filter = [Contract.tenant_id == user.tenant_id]
    recv_filter = [Receivable.tenant_id == user.tenant_id]
    payment_filter = [Payment.tenant_id == user.tenant_id]

    if projet_id:
        client_filter.append(Client.projet_id == projet_id)
        contract_filter.append(Contract.projet_id == projet_id)
        recv_filter.append(Receivable.projet_id == projet_id)
        payment_filter.append(Payment.projet_id == projet_id)
    if entreprise_id:
        client_filter.append(Client.entreprise_id == entreprise_id)
        contract_filter.append(Contract.entreprise_id == entreprise_id)
        recv_filter.append(Receivable.entreprise_id == entreprise_id)
        payment_filter.append(Payment.entreprise_id == entreprise_id)

    clients_count = (await db.execute(
        select(func.count()).select_from(Client).where(*client_filter)
    )).scalar()

    contracts_count = (await db.execute(
        select(func.count()).select_from(Contract).where(
            *contract_filter, Contract.status == ContractStatus.ACTIVE
        )
    )).scalar()

    total_receivable = (await db.execute(
        select(func.coalesce(func.sum(Receivable.amount - Receivable.amount_paid), 0))
        .where(*recv_filter)
    )).scalar()

    overdue_amount = (await db.execute(
        select(func.coalesce(func.sum(Receivable.amount - Receivable.amount_paid), 0))
        .where(
            *recv_filter,
            Receivable.due_date < date.today(),
            (Receivable.amount - Receivable.amount_paid) > 0,
        )
    )).scalar()

    total_paid = (await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(*payment_filter)
    )).scalar()

    return {
        "clients_count": clients_count,
        "active_contracts": contracts_count,
        "total_receivable": float(total_receivable),
        "overdue_amount": float(overdue_amount),
        "total_paid": float(total_paid),
        "projet_id": projet_id,
        "entreprise_id": entreprise_id,
    }


@router.get("/receivables")
async def list_receivables(
    client_id: Optional[uuid.UUID] = Query(None),
    projet_id: Optional[str] = Query(None),
    entreprise_id: Optional[str] = Query(None),
    overdue_only: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List receivables (créances), optionally filtered by project."""
    query = select(Receivable).where(Receivable.tenant_id == user.tenant_id)
    if client_id:
        query = query.where(Receivable.client_id == client_id)
    if projet_id:
        query = query.where(Receivable.projet_id == projet_id)
    if entreprise_id:
        query = query.where(Receivable.entreprise_id == entreprise_id)
    result = await db.execute(query.order_by(Receivable.due_date))
    receivables = result.scalars().all()

    from datetime import date

    # Get last payment date per receivable
    last_payment_q = await db.execute(
        select(Payment.receivable_id, func.max(Payment.payment_date).label("last_date"))
        .where(Payment.tenant_id == user.tenant_id)
        .group_by(Payment.receivable_id)
    )
    last_payment_map = {str(row[0]): row[1] for row in last_payment_q.all() if row[0]}

    items = []
    for r in receivables:
        remaining = float(r.amount) - float(r.amount_paid or 0)
        is_overdue = r.due_date and r.due_date < date.today() and remaining > 0
        if overdue_only and not is_overdue:
            continue
        last_pay = last_payment_map.get(str(r.id))
        items.append({
            "id": str(r.id),
            "client_id": str(r.client_id),
            "contract_id": str(r.contract_id) if r.contract_id else None,
            "invoice_ref": r.invoice_ref,
            "amount": float(r.amount),
            "amount_paid": float(r.amount_paid or 0),
            "remaining": remaining,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "status": r.status.value if r.status else None,
            "is_overdue": is_overdue,
            "last_payment_date": last_pay.isoformat() if last_pay else None,
            "entreprise_id": r.entreprise_id,
            "projet_id": r.projet_id,
        })
    return items
