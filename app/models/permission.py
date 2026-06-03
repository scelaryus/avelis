"""
GFI v7.0 — Permission: granular access control entries.

Permissions follow the pattern: module.action
  e.g., rf1.read, rf2.write, cff.validate, cc.write

System reference data (no company_id).
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class Permission(Base):
    __tablename__ = "permission"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    code = Column(String(60), unique=True, nullable=False)
    module = Column(String(40), nullable=False)
    action = Column(String(30), nullable=False)
    description = Column(Text, nullable=True)

    # ── Timestamps ───────────────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    def __repr__(self):
        return f"<Permission {self.code}>"
