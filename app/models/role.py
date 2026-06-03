"""
GFI v7.0 — Role: system-wide role definitions.

15 core roles + 3 HR sub-roles = 18 roles.
Roles are system reference data (no company_id).
A user is assigned a role within a specific company via user_role.

Escalation levels support the DRH hierarchy:
  Assistante RH (1) -> Charge (2) -> DRH (3) -> DAF/DG (4) -> PDG (5)
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class Role(Base):
    __tablename__ = "role"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    code = Column(String(40), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # ── Scope ────────────────────────────────────────────────────────────
    # Which module this role primarily belongs to (NULL = cross-module)
    module_scope = Column(String(40), nullable=True)
    is_system = Column(Boolean, nullable=False, server_default="true")

    # ── Escalation ───────────────────────────────────────────────────────
    # Higher level = more authority. NULL = not in escalation chain.
    escalation_level = Column(Integer, nullable=True)

    # ── Timestamps ───────────────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    # ── Relationships ────────────────────────────────────────────────────
    permissions = relationship(
        "RolePermission", back_populates="role", lazy="select"
    )

    def __repr__(self):
        return f"<Role {self.code}>"
