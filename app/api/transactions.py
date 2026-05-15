"""GFI v7.0 — Transaction CRUD with mandatory RF1-RF4.

POST /transactions     — Create transaction (RF mandatory)
GET  /transactions     — List transactions with filters
GET  /transactions/{id} — Get single transaction
"""
import hashlib
import json
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.financial import (
    Transaction, RealiteFinanciere, TypeTransaction,
)

router = APIRouter(tags=["Transactions"])


class TransactionCreate(BaseModel):
    entreprise_id: str
    projet_id: Optional[str] = None
    realite_financiere: str = Field(..., pattern="^RF[1-4]$")
    type_transaction: str
    montant: float = Field(gt=0)
    date_transaction: str  # YYYY-MM-DD
    description: Optional[str] = None
    reference: Optional[str] = None
    compte_debit: Optional[str] = None
    compte_credit: Optional[str] = None


class TransactionResponse(BaseModel):
    id: str
    entreprise_id: str
    projet_id: Optional[str]
    realite_financiere: str
    type_transaction: str
    montant: float
    date_transaction: str
    hash_sha256: Optional[str]


@router.post("/", response_model=TransactionResponse)
async def create_transaction(body: TransactionCreate, db: AsyncSession = Depends(get_db)):
    """Create a transaction with mandatory RF1-RF4."""
    # Validate RF
    try:
        rf = RealiteFinanciere(body.realite_financiere)
    except ValueError:
        raise HTTPException(422, f"realite_financiere must be RF1, RF2, RF3, or RF4")

    try:
        tt = TypeTransaction(body.type_transaction)
    except ValueError:
        raise HTTPException(422, f"type_transaction invalid: {body.type_transaction}")

    txn_id = str(uuid.uuid4())

    # Compute SHA-256 hash
    hash_input = json.dumps({
        "id": txn_id,
        "entreprise_id": body.entreprise_id,
        "rf": body.realite_financiere,
        "montant": body.montant,
        "date": body.date_transaction,
    }, sort_keys=True)
    hash_val = hashlib.sha256(hash_input.encode()).hexdigest()

    txn = Transaction(
        id=txn_id,
        tenant_id="default",  # will be resolved from auth context
        entreprise_id=body.entreprise_id,
        projet_id=body.projet_id,
        realite_financiere=rf,
        type_transaction=tt,
        montant=body.montant,
        date_transaction=date.fromisoformat(body.date_transaction),
        description=body.description,
        reference=body.reference,
        compte_debit=body.compte_debit,
        compte_credit=body.compte_credit,
        hash_sha256=hash_val,
    )
    db.add(txn)
    await db.commit()

    return TransactionResponse(
        id=txn.id,
        entreprise_id=txn.entreprise_id,
        projet_id=txn.projet_id,
        realite_financiere=body.realite_financiere,
        type_transaction=body.type_transaction,
        montant=float(txn.montant),
        date_transaction=body.date_transaction,
        hash_sha256=hash_val,
    )


@router.get("/")
async def list_transactions(
    entreprise_id: Optional[str] = None,
    realite_financiere: Optional[str] = None,
    projet_id: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    x_entreprise_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """List transactions — auto-scoped to active entreprise."""
    q = select(Transaction).where(
        Transaction.is_deleted == False
    ).order_by(Transaction.date_transaction.desc())

    # Auto-scope to active entreprise from header
    ent_filter = entreprise_id or x_entreprise_id
    if ent_filter:
        q = q.where(Transaction.entreprise_id == ent_filter)
    if realite_financiere:
        q = q.where(Transaction.realite_financiere == realite_financiere)
    if projet_id:
        q = q.where(Transaction.projet_id == projet_id)

    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    txns = result.scalars().all()

    return [
        {
            "id": t.id,
            "entreprise_id": t.entreprise_id,
            "projet_id": t.projet_id,
            "realite_financiere": t.realite_financiere.value if t.realite_financiere else None,
            "type_transaction": t.type_transaction.value if t.type_transaction else None,
            "montant": float(t.montant),
            "date_transaction": str(t.date_transaction),
            "hash_sha256": t.hash_sha256,
        }
        for t in txns
    ]


@router.get("/{transaction_id}")
async def get_transaction(transaction_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single transaction."""
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(404, "Transaction introuvable")

    return {
        "id": txn.id,
        "entreprise_id": txn.entreprise_id,
        "projet_id": txn.projet_id,
        "realite_financiere": txn.realite_financiere.value if txn.realite_financiere else None,
        "type_transaction": txn.type_transaction.value if txn.type_transaction else None,
        "montant": float(txn.montant),
        "date_transaction": str(txn.date_transaction),
        "description": txn.description,
        "reference": txn.reference,
        "compte_debit": txn.compte_debit,
        "compte_credit": txn.compte_credit,
        "hash_sha256": txn.hash_sha256,
        "created_at": str(txn.created_at) if txn.created_at else None,
    }
