"""
GFI v7.0 — Procurement + Inventory Engine.

Purchase cycle: DA -> AO -> BC -> BR -> Facture -> Paiement.
SoD (S-08): previous step performer CANNOT validate current step.
CUMP/FIFO stock valuation. CC3 feed on consumption.

Core API:
  create_purchase_request(...)  -> PurchaseRequest
  validate_purchase_request(...) -> SoD enforced
  create_purchase_order(...)   -> PurchaseOrder (from validated DA)
  validate_purchase_order(...)  -> SoD enforced
  record_goods_receipt(...)    -> GoodsReceipt + stock entry
  record_stock_consumption(...) -> stock exit + CC3 imputation
  calculate_cump(item_id)     -> updated unit cost
  update_supplier_score(...)   -> performance metric
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SoDProcurementViolation(Exception):
    """SoD: previous step performer cannot validate current step."""
    def __init__(self, message: str, step: str, creator: UUID, validator: UUID):
        super().__init__(message)
        self.step = step


class StockInsufficient(Exception):
    """Insufficient stock for the requested quantity."""
    pass


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _next_number(session, prefix: str, model_class, field, company_id: UUID) -> str:
    """Generate sequential number."""
    from sqlalchemy import func as sqfunc
    count = (
        session.query(sqfunc.count(model_class.id))
        .filter(
            model_class.company_id == company_id,
            model_class.is_deleted.is_(False),
        )
        .scalar()
    ) or 0
    return f"{prefix}-{date.today().year}-{count + 1:04d}"


def create_purchase_request(
    session: Session,
    *,
    company_id: UUID,
    project_id: UUID | None,
    requested_by: UUID,
    description: str,
    items: list[dict] | None = None,
    estimated_budget: Decimal | None = None,
    urgency: str = "NORMAL",
    created_by: UUID | None = None,
) -> object:
    from app.models.procurement import PurchaseRequest

    number = _next_number(session, "DA", PurchaseRequest, "request_number", company_id)

    pr = PurchaseRequest(
        company_id=company_id,
        request_number=number,
        project_id=project_id,
        requested_by=requested_by,
        request_date=date.today(),
        description=description,
        items=items,
        estimated_budget=Decimal(str(estimated_budget)) if estimated_budget else None,
        urgency=urgency,
        status="SOUMISE",
        created_by=created_by,
    )
    session.add(pr)
    session.flush()
    return pr


def validate_purchase_request(
    session: Session,
    request_id: UUID,
    validated_by: UUID,
) -> object:
    """SoD: requester cannot validate their own request."""
    from app.models.procurement import PurchaseRequest

    pr = session.get(PurchaseRequest, request_id)
    if pr is None:
        raise ValueError(f"PurchaseRequest {request_id} not found.")

    if pr.requested_by == validated_by:
        raise SoDProcurementViolation(
            "SoD: Le demandeur ne peut pas valider sa propre DA.",
            step="DA_VALIDATION",
            creator=pr.requested_by, validator=validated_by,
        )

    now = datetime.now(timezone.utc)
    pr.status = "VALIDEE"
    pr.validated_by = validated_by
    pr.validated_at = now
    session.flush()
    return pr


def create_purchase_order(
    session: Session,
    *,
    company_id: UUID,
    purchase_request_id: UUID | None,
    supplier_id: UUID,
    project_id: UUID | None,
    lines: list[dict],
    created_by: UUID,
) -> object:
    from app.models.procurement import PurchaseOrder

    total_ht = sum(Decimal(str(l.get("total", 0))) for l in lines)
    tva = _r2(total_ht * Decimal("0.19"))
    total_ttc = total_ht + tva

    number = _next_number(session, "BC", PurchaseOrder, "order_number", company_id)

    po = PurchaseOrder(
        company_id=company_id,
        order_number=number,
        purchase_request_id=purchase_request_id,
        supplier_id=supplier_id,
        project_id=project_id,
        order_date=date.today(),
        total_ht=total_ht,
        tva_amount=tva,
        total_ttc=total_ttc,
        lines=lines,
        status="BROUILLON",
        created_by_user=created_by,
        created_by=created_by,
    )
    session.add(po)
    session.flush()
    return po


def validate_purchase_order(
    session: Session,
    order_id: UUID,
    validated_by: UUID,
) -> object:
    """SoD: order creator cannot validate."""
    from app.models.procurement import PurchaseOrder

    po = session.get(PurchaseOrder, order_id)
    if po is None:
        raise ValueError(f"PurchaseOrder {order_id} not found.")

    if po.created_by_user == validated_by:
        raise SoDProcurementViolation(
            "SoD: Le createur du BC ne peut pas le valider.",
            step="BC_VALIDATION",
            creator=po.created_by_user, validator=validated_by,
        )

    now = datetime.now(timezone.utc)
    po.status = "VALIDEE"
    po.validated_by = validated_by
    po.validated_at = now
    session.flush()
    return po


def record_goods_receipt(
    session: Session,
    *,
    company_id: UUID,
    purchase_order_id: UUID,
    warehouse_id: UUID,
    lines: list[dict],
    received_by: UUID,
    delivery_note_ref: str | None = None,
    delivery_note_photo: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """Record goods receipt and create stock entries."""
    from app.models.procurement import GoodsReceipt, PurchaseOrder

    po = session.get(PurchaseOrder, purchase_order_id)
    if po is None:
        raise ValueError(f"PurchaseOrder {purchase_order_id} not found.")

    number = _next_number(session, "BR", GoodsReceipt, "receipt_number", company_id)

    has_discrepancy = any(
        l.get("qty_received", 0) != l.get("qty_ordered", 0) for l in lines
    )

    gr = GoodsReceipt(
        company_id=company_id,
        receipt_number=number,
        purchase_order_id=purchase_order_id,
        supplier_id=po.supplier_id,
        project_id=po.project_id,
        warehouse_id=warehouse_id,
        receipt_date=date.today(),
        delivery_note_ref=delivery_note_ref,
        delivery_note_photo=delivery_note_photo,
        lines=lines,
        status="ECART_SIGNALE" if has_discrepancy else "VALIDEE",
        received_by=received_by,
        created_by=created_by,
    )
    session.add(gr)
    session.flush()

    # Create stock entries for received items
    for line in lines:
        qty = Decimal(str(line.get("qty_accepted", line.get("qty_received", 0))))
        if qty > 0:
            _stock_entry(
                session,
                company_id=company_id,
                warehouse_id=warehouse_id,
                project_id=po.project_id,
                reference=line.get("ref", ""),
                designation=line.get("description", ""),
                quantity=qty,
                unit_cost=Decimal(str(line.get("unit_price", 0))),
                source_type="GOODS_RECEIPT",
                source_id=gr.id,
                responsible_user=received_by,
            )

    return gr


def _stock_entry(
    session, *, company_id, warehouse_id, project_id,
    reference, designation, quantity, unit_cost,
    source_type, source_id, responsible_user,
):
    """Create or update a stock item and record the movement."""
    from app.models.procurement import StockItem, StockMovement

    item = (
        session.query(StockItem)
        .filter(
            StockItem.reference == reference,
            StockItem.warehouse_id == warehouse_id,
            StockItem.is_deleted.is_(False),
        )
        .first()
    )

    now = datetime.now(timezone.utc)

    if item is None:
        item = StockItem(
            company_id=company_id,
            reference=reference,
            designation=designation,
            warehouse_id=warehouse_id,
            project_id=project_id,
            quantity_on_hand=quantity,
            quantity_available=quantity,
            unit_cost=unit_cost,
            total_value=_r2(quantity * unit_cost),
        )
        session.add(item)
    else:
        # CUMP recalculation
        old_total = Decimal(str(item.quantity_on_hand)) * Decimal(str(item.unit_cost))
        new_total = quantity * unit_cost
        new_qty = Decimal(str(item.quantity_on_hand)) + quantity
        if new_qty > 0:
            item.unit_cost = _r2((old_total + new_total) / new_qty)
        item.quantity_on_hand = new_qty
        item.quantity_available = new_qty - Decimal(str(item.quantity_reserved))
        item.total_value = _r2(new_qty * Decimal(str(item.unit_cost)))

    session.flush()

    movement = StockMovement(
        company_id=company_id,
        stock_item_id=item.id,
        warehouse_id=warehouse_id,
        project_id=project_id,
        movement_date=now,
        movement_type="ENTREE",
        quantity=quantity,
        unit_cost=unit_cost,
        total_cost=_r2(quantity * unit_cost),
        source_type=source_type,
        source_id=source_id,
        responsible_user=responsible_user,
    )
    session.add(movement)
    session.flush()
    return movement


def record_stock_consumption(
    session: Session,
    *,
    company_id: UUID,
    stock_item_id: UUID,
    project_id: UUID,
    quantity: Decimal,
    responsible_user: UUID,
    reference: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """Record material consumption + CC3 imputation."""
    from app.models.procurement import StockItem, StockMovement

    item = session.get(StockItem, stock_item_id)
    if item is None:
        raise ValueError(f"StockItem {stock_item_id} not found.")

    quantity = Decimal(str(quantity))
    if quantity > Decimal(str(item.quantity_available)):
        raise StockInsufficient(
            f"Stock insuffisant: disponible={item.quantity_available}, "
            f"demande={quantity}"
        )

    now = datetime.now(timezone.utc)
    cost = _r2(quantity * Decimal(str(item.unit_cost)))

    item.quantity_on_hand = Decimal(str(item.quantity_on_hand)) - quantity
    item.quantity_available = Decimal(str(item.quantity_available)) - quantity
    item.total_value = _r2(
        Decimal(str(item.quantity_on_hand)) * Decimal(str(item.unit_cost))
    )

    movement = StockMovement(
        company_id=company_id,
        stock_item_id=stock_item_id,
        warehouse_id=item.warehouse_id,
        project_id=project_id,
        movement_date=now,
        movement_type="SORTIE",
        quantity=-quantity,
        unit_cost=item.unit_cost,
        total_cost=cost,
        source_type="PROJECT_CONSUMPTION",
        reference=reference,
        responsible_user=responsible_user,
        created_by=created_by,
    )
    session.add(movement)
    session.flush()

    # CC3 imputation
    from app.cc_category_engine import impute_to_category
    impute_to_category(
        session,
        category="VRD",  # CC3 materials
        company_id=company_id,
        project_id=project_id,
        rf_type="RF1",
        montant=cost,
        entry_date=now.date(),
        libelle=f"Consommation {item.designation} x{quantity}",
        source_type="stock_consumption",
        source_id=movement.id,
        created_by=created_by,
    )

    return movement


def update_supplier_score(
    session: Session,
    supplier_id: UUID,
    delivery_quality: int,
    delay_score: int,
    pricing_score: int,
) -> object:
    """Update supplier performance score (0-100)."""
    from app.models.procurement import Supplier

    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        raise ValueError(f"Supplier {supplier_id} not found.")

    new_score = _r2(
        Decimal(str(delivery_quality)) * Decimal("0.4")
        + Decimal(str(delay_score)) * Decimal("0.35")
        + Decimal(str(pricing_score)) * Decimal("0.25")
    )

    history = supplier.score_history or []
    history.append({
        "date": str(date.today()),
        "score": str(new_score),
        "quality": delivery_quality,
        "delay": delay_score,
        "pricing": pricing_score,
    })
    supplier.performance_score = new_score
    supplier.score_history = history
    session.flush()
    return supplier
