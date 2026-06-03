"""
GFI v7.0 — UserRole: per-company role assignment.

A user can have different roles in different companies.
This is the key multi-tenant authorization junction:
  "User X has role Y in company Z"

Uses GFIBase (has company_id) — financial table with soft-delete.
"""

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class UserRole(GFIBase, Base):
    __tablename__ = "user_role"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "role_id", "company_id",
            name="uq_user_role_user_role_company",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("role.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    user = relationship("AuthUser", back_populates="roles")
    role = relationship("Role")
    company = relationship("Company")

    def __repr__(self):
        return (
            f"<UserRole user={self.user_id} "
            f"role={self.role_id} company={self.company_id}>"
        )
