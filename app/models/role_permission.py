"""
GFI v7.0 — RolePermission: junction between Role and Permission.

System reference data (no company_id).
Maps which permissions each role has.
"""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class RolePermission(Base):
    __tablename__ = "role_permission"
    __table_args__ = (
        UniqueConstraint(
            "role_id", "permission_id",
            name="uq_role_permission_role_perm",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("role.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permission.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # ── Relationships ────────────────────────────────────────────────────
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission")

    def __repr__(self):
        return f"<RolePermission role={self.role_id} perm={self.permission_id}>"
