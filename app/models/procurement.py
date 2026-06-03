"""
GFI v7.0 — Procurement + Inventory models.

Full purchase cycle: DA -> AO -> BC -> BR -> Facture -> Paiement.
SoD at each step: previous step performer cannot validate current step.
Multi-warehouse inventory with CUMP/FIFO valuation.
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Supplier(GFIBase, Base):
    """Supplier registry with performance scoring."""

    __tablename__ = "supplier"

    name = Column(String(255), nullable=False)
    nif = Column(String(30), nullable=True)
    rc = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(255), nullable=True)
    specialty = Column(String(100), nullable=True)
    bank_name = Column(String(100), nullable=True)
    bank_account = Column(String(50), nullable=True)
    # 0-100 based on delivery quality, delays, pricing
    performance_score = Column(Numeric(5, 2), nullable=False, server_default="50")
    score_history = Column(JSONB, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")

    def __repr__(self):
        return f"<Supplier {self.name} score={self.performance_score}>"


class PurchaseRequest(GFIBase, Base):
    """Demande d'Achat (DA) — initiates the procurement cycle."""

    __tablename__ = "purchase_request"

    request_number = Column(String(30), unique=True, nullable=False, index=True)
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    requested_by = Column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=False,
    )
    request_date = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    justification = Column(Text, nullable=True)
    estimated_budget = Column(Numeric(15, 2), nullable=True)
    urgency = Column(String(20), nullable=False, server_default="'NORMAL'")
    # NORMAL, URGENT, CRITICAL
    items = Column(JSONB, nullable=True)
    # BROUILLON, SOUMISE, VALIDEE, REJETEE, EN_COURS, TERMINEE
    status = Column(String(20), nullable=False, server_default="'BROUILLON'")
    validated_by = Column(UUID(as_uuid=True), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<PurchaseRequest {self.request_number} {self.status}>"


class PurchaseOrder(GFIBase, Base):
    """Bon de Commande (BC) — confirmed order to supplier."""

    __tablename__ = "purchase_order"

    order_number = Column(String(30), unique=True, nullable=False, index=True)
    purchase_request_id = Column(
        UUID(as_uuid=True), ForeignKey("purchase_request.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    supplier_id = Column(
        UUID(as_uuid=True), ForeignKey("supplier.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    order_date = Column(Date, nullable=False)
    expected_delivery = Column(Date, nullable=True)
    total_ht = Column(Numeric(15, 2), nullable=False)
    tva_amount = Column(Numeric(15, 2), nullable=False, server_default="0")
    total_ttc = Column(Numeric(15, 2), nullable=False)
    lines = Column(JSONB, nullable=False)
    # [{ref, description, qty, unit_price, total}]
    # BROUILLON, VALIDEE, ENVOYEE, PARTIELLEMENT_RECUE, RECUE, ANNULEE
    status = Column(String(30), nullable=False, server_default="'BROUILLON'")
    created_by_user = Column(UUID(as_uuid=True), nullable=False)
    validated_by = Column(UUID(as_uuid=True), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)

    supplier = relationship("Supplier")

    def __repr__(self):
        return f"<PurchaseOrder {self.order_number} {self.status}>"


class GoodsReceipt(GFIBase, Base):
    """Bon de Reception (BR) — material received from supplier."""

    __tablename__ = "goods_receipt"

    receipt_number = Column(String(30), unique=True, nullable=False, index=True)
    purchase_order_id = Column(
        UUID(as_uuid=True), ForeignKey("purchase_order.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    supplier_id = Column(
        UUID(as_uuid=True), ForeignKey("supplier.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True,
    )
    warehouse_id = Column(
        UUID(as_uuid=True), ForeignKey("warehouse.id", ondelete="RESTRICT"),
        nullable=False,
    )
    receipt_date = Column(Date, nullable=False, index=True)
    delivery_note_ref = Column(String(100), nullable=True)
    delivery_note_photo = Column(Text, nullable=True)
    lines = Column(JSONB, nullable=False)
    # [{ref, description, qty_ordered, qty_received, qty_accepted, reason_if_diff}]
    quality_check = Column(String(20), nullable=True)
    # CONFORME, NON_CONFORME, PARTIEL
    # BROUILLON, VALIDEE, ECART_SIGNALE
    status = Column(String(20), nullable=False, server_default="'BROUILLON'")
    received_by = Column(UUID(as_uuid=True), nullable=False)
    validated_by = Column(UUID(as_uuid=True), nullable=True)

    supplier = relationship("Supplier")

    def __repr__(self):
        return f"<GoodsReceipt {self.receipt_number} {self.status}>"


class Warehouse(GFIBase, Base):
    """Storage location — multi-warehouse per project."""

    __tablename__ = "warehouse"

    code = Column(String(20), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    address = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")

    def __repr__(self):
        return f"<Warehouse {self.code} {self.name}>"


class StockItem(GFIBase, Base):
    """Inventory item with CUMP/FIFO valuation."""

    __tablename__ = "stock_item"

    reference = Column(String(50), nullable=False, index=True)
    designation = Column(String(255), nullable=False)
    category = Column(String(50), nullable=True)
    unit = Column(String(20), nullable=False, server_default="'UNITE'")
    warehouse_id = Column(
        UUID(as_uuid=True), ForeignKey("warehouse.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    # ── Stock levels ─────────────────────────────────────────────────────
    quantity_on_hand = Column(Numeric(12, 3), nullable=False, server_default="0")
    quantity_reserved = Column(Numeric(12, 3), nullable=False, server_default="0")
    quantity_available = Column(Numeric(12, 3), nullable=False, server_default="0")
    # ── Valuation ────────────────────────────────────────────────────────
    valuation_method = Column(String(10), nullable=False, server_default="'CUMP'")
    # CUMP or FIFO
    unit_cost = Column(Numeric(15, 2), nullable=False, server_default="0")
    total_value = Column(Numeric(15, 2), nullable=False, server_default="0")
    # ── Thresholds ───────────────────────────────────────────────────────
    min_stock = Column(Numeric(12, 3), nullable=True)
    max_stock = Column(Numeric(12, 3), nullable=True)
    reorder_point = Column(Numeric(12, 3), nullable=True)
    # ── QR code ──────────────────────────────────────────────────────────
    qr_code = Column(String(100), nullable=True, unique=True)

    warehouse = relationship("Warehouse")

    def __repr__(self):
        return f"<StockItem {self.reference} qty={self.quantity_on_hand}>"


class StockMovement(GFIBase, Base):
    """Every stock entry/exit traced with full context."""

    __tablename__ = "stock_movement"

    stock_item_id = Column(
        UUID(as_uuid=True), ForeignKey("stock_item.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    warehouse_id = Column(
        UUID(as_uuid=True), ForeignKey("warehouse.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    movement_date = Column(DateTime(timezone=True), nullable=False, index=True)
    # ENTREE, SORTIE, TRANSFERT, AJUSTEMENT
    movement_type = Column(String(20), nullable=False)
    quantity = Column(Numeric(12, 3), nullable=False)
    unit_cost = Column(Numeric(15, 2), nullable=True)
    total_cost = Column(Numeric(15, 2), nullable=True)
    # ── Source ────────────────────────────────────────────────────────────
    source_type = Column(String(30), nullable=True)
    # GOODS_RECEIPT, PROJECT_CONSUMPTION, TRANSFER, ADJUSTMENT
    source_id = Column(UUID(as_uuid=True), nullable=True)
    reference = Column(String(100), nullable=True)
    responsible_user = Column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes = Column(Text, nullable=True)

    stock_item = relationship("StockItem")
    warehouse = relationship("Warehouse")

    def __repr__(self):
        return f"<StockMovement {self.movement_type} {self.quantity}>"
