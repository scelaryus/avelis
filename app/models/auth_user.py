"""
GFI v7.0 — AuthUser: system-wide user account.

auth_user is a root table (like company) — it does not carry company_id.
A user's access to specific companies is determined by the user_role junction.

Security features:
- password_hash: bcrypt hash, never stored in plain text
- failed_login_attempts + locked_until: brute-force protection
- must_change_password: forced rotation on first login or after reset
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class AuthUser(Base):
    __tablename__ = "auth_user"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # ── Identity ─────────────────────────────────────────────────────────
    username = Column(String(150), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    full_name = Column(String(255), nullable=True)

    # ── Authentication ───────────────────────────────────────────────────
    password_hash = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    last_login = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, nullable=False, server_default="0")
    locked_until = Column(DateTime(timezone=True), nullable=True)
    must_change_password = Column(
        Boolean, nullable=False, server_default="false"
    )

    # ── Timestamps ───────────────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ────────────────────────────────────────────────────
    roles = relationship("UserRole", back_populates="user", lazy="select")

    def __repr__(self):
        return f"<AuthUser {self.username}>"
