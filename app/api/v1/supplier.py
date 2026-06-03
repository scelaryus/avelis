"""Router — Fournisseurs: suppliers, contracts, payments. Linked to stock & cost centers."""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.v1.deps import get_current_user, CurrentUser, get_db
from app.api.v1.schemas import ApiResponse, Meta
from app.models.core import (
    Supplier, SupplierContract, SupplierPayment,
    StockItem, StockMovement, Company, Project,
)

router = APIRouter(prefix="/suppliers", tags=["Fournisseurs"])


def _next_supplier_code(db):
    count = db.query(func.count(Supplier.id)).scalar() or 0
    return f"FRN-{count + 1:04d}"


def _next_contract_number(db):
    count = db.query(func.count(SupplierContract.id)).scalar() or 0
    return f"CTR-{count + 1:05d}"


# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIERS CRUD
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("")
async def list_suppliers(status: str | None = None, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    q = db.query(Supplier).filter(Supplier.is_deleted == False)
    if status:
        q = q.filter(Supplier.status == status)
    suppliers = q.order_by(Supplier.name).all()
    # KPIs
    total_contracts = db.query(func.coalesce(func.sum(SupplierContract.montant_ttc), 0)).filter(
        SupplierContract.is_deleted == False).scalar()
    total_paid = db.query(func.coalesce(func.sum(SupplierPayment.montant), 0)).filter(
        SupplierPayment.is_deleted == False, SupplierPayment.status == "ENCAISSE").scalar()
    return ApiResponse(data={
        "suppliers": [{
            "id": str(s.id), "code": s.code, "name": s.name,
            "contact_name": s.contact_name, "phone": s.phone, "email": s.email,
            "category": s.category, "status": s.status,
            "total_contracts": str(s.total_contracts or 0),
            "total_paid": str(s.total_paid or 0),
            "total_remaining": str(s.total_remaining or 0),
            "contracts_count": db.query(SupplierContract).filter(
                SupplierContract.supplier_id == s.id, SupplierContract.is_deleted == False).count(),
        } for s in suppliers],
        "kpis": {
            "total_suppliers": len(suppliers),
            "total_contracts_value": str(total_contracts),
            "total_paid": str(total_paid),
            "total_remaining": str(total_contracts - total_paid),
        },
    })


@router.post("")
async def create_supplier(body: dict, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    company = db.query(Company).first()
    if not company:
        raise HTTPException(400, "Aucune entreprise configuree")
    s = Supplier(
        company_id=company.id, code=_next_supplier_code(db),
        name=body["name"], contact_name=body.get("contact_name"),
        phone=body.get("phone"), email=body.get("email"),
        address=body.get("address"), nif=body.get("nif"),
        rc=body.get("rc"), rib=body.get("rib"),
        bank_name=body.get("bank_name"), category=body.get("category"),
    )
    db.add(s)
    db.commit()
    return ApiResponse(data={"id": str(s.id), "code": s.code, "name": s.name})


@router.get("/{supplier_id}")
async def get_supplier(supplier_id: str, db: Session = Depends(get_db),
                        user: CurrentUser = Depends(get_current_user)):
    s = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.is_deleted == False).first()
    if not s:
        raise HTTPException(404, "Fournisseur introuvable")
    contracts = db.query(SupplierContract).filter(
        SupplierContract.supplier_id == s.id, SupplierContract.is_deleted == False
    ).order_by(SupplierContract.created_at.desc()).all()
    payments = db.query(SupplierPayment).filter(
        SupplierPayment.supplier_id == s.id, SupplierPayment.is_deleted == False
    ).order_by(SupplierPayment.date_paiement.desc()).all()
    return ApiResponse(data={
        "id": str(s.id), "code": s.code, "name": s.name,
        "contact_name": s.contact_name, "phone": s.phone, "email": s.email,
        "address": s.address, "nif": s.nif, "rc": s.rc,
        "rib": s.rib, "bank_name": s.bank_name, "category": s.category,
        "status": s.status,
        "total_contracts": str(s.total_contracts or 0),
        "total_paid": str(s.total_paid or 0),
        "total_remaining": str(s.total_remaining or 0),
        "contracts": [{
            "id": str(c.id), "number": c.contract_number, "label": c.label,
            "montant_ht": str(c.montant_ht), "montant_ttc": str(c.montant_ttc),
            "status": c.status, "total_paid": str(c.total_paid or 0),
            "remaining": str(c.remaining or 0),
            "stock_items": c.stock_items_received or 0,
            "stock_value": str(c.stock_value_received or 0),
            "date_signature": c.date_signature.isoformat() if c.date_signature else None,
        } for c in contracts],
        "payments": [{
            "id": str(p.id), "montant": str(p.montant), "mode": p.mode_reglement,
            "reference": p.reference, "date": p.date_paiement.isoformat(),
            "status": p.status, "contract_number": None,
        } for p in payments],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{supplier_id}/contracts")
async def create_contract(supplier_id: str, body: dict, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    """Create a contract. Auto-calculates TVA and TTC. Adds to stock as resources."""
    s = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not s:
        raise HTTPException(404, "Fournisseur introuvable")

    montant_ht = Decimal(str(body["montant_ht"]))
    tva_rate = Decimal(str(body.get("tva_rate", "19.00")))
    montant_tva = (montant_ht * tva_rate / 100).quantize(Decimal("0.01"))
    montant_ttc = montant_ht + montant_tva

    c = SupplierContract(
        company_id=s.company_id, supplier_id=s.id,
        project_id=body.get("project_id"),
        contract_number=_next_contract_number(db),
        label=body["label"], description=body.get("description"),
        montant_ht=montant_ht, tva_rate=tva_rate,
        montant_tva=montant_tva, montant_ttc=montant_ttc,
        date_signature=body.get("date_signature"),
        date_debut=body.get("date_debut"), date_fin=body.get("date_fin"),
        remaining=montant_ttc,
        created_by=user.name,
    )
    db.add(c)

    # Update supplier totals
    s.total_contracts = (s.total_contracts or 0) + montant_ttc
    s.total_remaining = (s.total_remaining or 0) + montant_ttc

    # If stock items are specified, create them and link to contract
    stock_items = body.get("stock_items", [])
    stock_total = Decimal("0")
    for si in stock_items:
        from app.api.v1.stock import _next_item_code, _generate_barcode_value
        code = _next_item_code(db)
        barcode = _generate_barcode_value(code)
        qty = Decimal(str(si.get("quantity", 0)))
        price = Decimal(str(si.get("unit_price", 0)))
        total = (qty * price).quantize(Decimal("0.01"))
        item = StockItem(
            company_id=s.company_id, project_id=body.get("project_id"),
            code=code, barcode=barcode,
            name=si["name"], category=si.get("category", "AUTRE"),
            description=si.get("description"),
            quantity=qty, unit=si.get("unit", "UNITE"),
            unit_price=price, total_value=total,
            supplier_id=s.id, contract_id=c.id,
            created_by=user.name,
        )
        db.add(item)
        db.flush()
        if qty > 0:
            db.add(StockMovement(
                company_id=s.company_id, item_id=item.id,
                movement_type="ENTREE", quantity=qty,
                unit_price=price, total_value=total,
                reason=f"Contrat {c.contract_number} — {s.name}",
                created_by=user.name,
            ))
        stock_total += total

    c.stock_items_received = len(stock_items)
    c.stock_value_received = stock_total

    db.commit()
    return ApiResponse(data={
        "id": str(c.id), "number": c.contract_number,
        "montant_ttc": str(montant_ttc), "stock_items_created": len(stock_items),
        "stock_value": str(stock_total),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# PAYMENTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{supplier_id}/payments")
async def record_supplier_payment(supplier_id: str, body: dict, db: Session = Depends(get_db),
                                    user: CurrentUser = Depends(get_current_user)):
    """Record a payment to a supplier. Deducts from contract remaining."""
    s = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not s:
        raise HTTPException(404, "Fournisseur introuvable")

    montant = Decimal(str(body["montant"]))
    contract_id = body.get("contract_id")

    p = SupplierPayment(
        company_id=s.company_id, supplier_id=s.id,
        contract_id=contract_id,
        montant=montant, mode_reglement=body.get("mode_reglement", "CHEQUE"),
        reference=body.get("reference"),
        date_paiement=body.get("date_paiement", datetime.now(timezone.utc).date()),
        observations=body.get("observations"),
        proof_url=body.get("proof_url"),
        created_by=user.name,
    )
    db.add(p)

    # Update supplier totals
    s.total_paid = (s.total_paid or 0) + montant
    s.total_remaining = (s.total_remaining or 0) - montant

    # Update contract if linked
    projet_code = None
    if contract_id:
        c = db.query(SupplierContract).filter(SupplierContract.id == contract_id).first()
        if c:
            c.total_paid = (c.total_paid or 0) + montant
            c.remaining = (c.remaining or 0) - montant
            if c.project_id:
                proj = db.query(Project).get(c.project_id)
                projet_code = proj.code if proj else None

    # Impute to Centre de Cout (expense)
    from app.api.v1.cc_helpers import impute_cc
    comp = db.query(Company).get(s.company_id)
    impute_cc(
        db,
        entite_code=comp.code if comp else None,
        projet_code=projet_code,
        rf_type="RF1",
        montant=-montant,  # negative = expense/payment out
        label=f"Paiement fournisseur: {s.name} — {body.get('reference', '')}",
        source_type="ACHAT",
        source_doc_id=str(p.id),
    )

    db.commit()
    return ApiResponse(data={
        "id": str(p.id), "montant": str(montant),
        "supplier_remaining": str(s.total_remaining),
    })
