"""GFI Platform - Integration models (Google Drive, external services)."""
import uuid
import enum
from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, ForeignKey,
    Enum as SAEnum, JSON, func, UniqueConstraint,
)
from app.database import Base


class IntegrationProvider(str, enum.Enum):
    GOOGLE_DRIVE = "GOOGLE_DRIVE"


class UserIntegration(Base):
    """Stores per-user OAuth2 tokens for external service integrations."""
    __tablename__ = "user_integrations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    provider = Column(SAEnum(IntegrationProvider), nullable=False)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    scopes = Column(String(500), nullable=True)
    provider_email = Column(String(255), nullable=True)  # e.g. Google account email
    is_active = Column(Boolean, default=True)
    metadata_ = Column("metadata", JSON, default={})
    connected_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_integration_provider"),
    )
