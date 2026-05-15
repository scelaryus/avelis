"""Legal case management models."""
import uuid
import enum

from sqlalchemy import Column, String, Text, Date, DateTime, ForeignKey, Enum as SAEnum, Integer, func

from app.database import Base


class LegalCaseDirection(str, enum.Enum):
    AGAINST_US = "AGAINST_US"
    AGAINST_OTHERS = "AGAINST_OTHERS"


class LegalCaseStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WON = "WON"
    LOST = "LOST"
    SETTLED = "SETTLED"
    CLOSED = "CLOSED"


class LegalCase(Base):
    __tablename__ = "legal_cases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    reference = Column(String(100), nullable=True)
    direction = Column(SAEnum(LegalCaseDirection), nullable=False)
    opposing_party = Column(String(255), nullable=True)
    court_name = Column(String(255), nullable=True)
    status = Column(SAEnum(LegalCaseStatus), nullable=False, default=LegalCaseStatus.OPEN)
    description = Column(Text, nullable=True)
    opened_on = Column(Date, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LegalCaseFolder(Base):
    __tablename__ = "legal_case_folders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("legal_cases.id"), nullable=False, index=True)
    parent_folder_id = Column(String(36), ForeignKey("legal_case_folders.id"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())