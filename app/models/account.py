"""
GFI v7.0 — Account: SCF (Systeme Comptable Financier) chart of accounts.

The Algerian SCF chart of accounts follows the French PCG structure:
  Class 1: Capitaux propres
  Class 2: Immobilisations
  Class 3: Stocks
  Class 4: Tiers
  Class 5: Financiers
  Class 6: Charges
  Class 7: Produits

System reference data (no company_id — same chart for all entities).
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class Account(Base):
    __tablename__ = "account"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # ── Account identity ─────────────────────────────────────────────────
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    # SCF class: 1-7
    account_class = Column(Integer, nullable=False)
    # Account type for balance logic
    account_type = Column(String(20), nullable=False)
    # ACTIF, PASSIF, CHARGE, PRODUIT

    # ── Hierarchy ────────────────────────────────────────────────────────
    parent_code = Column(String(20), nullable=True)
    level = Column(Integer, nullable=False, server_default="1")
    is_detail = Column(Boolean, nullable=False, server_default="true")
    # Only detail accounts accept journal entries

    # ── Metadata ─────────────────────────────────────────────────────────
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    def __repr__(self):
        return f"<Account {self.code} — {self.name}>"
