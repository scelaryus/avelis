"""
GFI v7.0 — Client: real estate buyer/prospect.

Clients are scoped per company (GFIBase). A client buying across
multiple entities would have separate records per entity.
"""

from sqlalchemy import Column, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class Client(GFIBase, Base):
    __tablename__ = "client"

    # ── Identity ─────────────────────────────────────────────────────────
    full_name = Column(String(255), nullable=False)
    phone = Column(String(30), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    nif_client = Column(String(30), nullable=True)

    # ── CRM stage ────────────────────────────────────────────────────────
    # PROSPECT, QUALIFIE, ACHETEUR, LIVRE
    crm_status = Column(String(20), nullable=False, server_default="'PROSPECT'")
    source = Column(String(50), nullable=True)  # how the client found us

    # ── Documents checklist ──────────────────────────────────────────────
    documents_status = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<Client {self.full_name}>"
