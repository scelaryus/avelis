"""
GFI v7.0 — Base model with mandatory system columns.

Every table carries: id, company_id, created_at, updated_at, created_by,
is_deleted, version.  Financial tables additionally block physical DELETE
via a database-level trigger (applied in migration).
"""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """Raw SQLAlchemy declarative base — no extra columns."""

    pass


class GFIBase:
    """
    Mixin that injects the 7 mandatory system columns onto every GFI table.

    Usage:
        class MyTable(GFIBase, Base):
            __tablename__ = "my_table"
            ...
    """

    # ── Primary key ──────────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Multi-tenant isolation ───────────────────────────────────────────
    @declared_attr
    def company_id(cls):
        return Column(
            UUID(as_uuid=True),
            ForeignKey("company.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )

    # ── Audit timestamps ─────────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Audit user ───────────────────────────────────────────────────────
    @declared_attr
    def created_by(cls):
        return Column(
            UUID(as_uuid=True),
            ForeignKey("auth_user.id", ondelete="SET NULL"),
            nullable=True,
        )

    # ── Soft delete ──────────────────────────────────────────────────────
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    # ── Optimistic locking ───────────────────────────────────────────────
    version = Column(Integer, nullable=False, server_default="1")
