"""GFI v7.0 — RBAC models with 15 GFI-specific roles.

Tables:
  - roles: 15 GFI-specific roles with permissions JSON
  - utilisateurs: users with associe_id + company_id (Row Level Security)
  - utilisateur_roles: M:N user↔role per enterprise
  - audit_log_gfi: audit log with realite_financiere tag
"""
import uuid
import enum
from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Date,
    ForeignKey, JSON, Index, UniqueConstraint, func,
)
from app.database import Base


# 15 GFI-specific roles
GFI_ROLES = [
    "PDG_SUPER_ADMIN",
    "CHARGE_MISSION",
    "DAF",
    "CHARGE_FINANCE",
    "MARKETING",
    "PROJECT_MANAGER",
    "TELECONSEILLERE",
    "RH",
    "ARCHIVISTE",
    "SECURITE",
    "MAGASINIER",
    "ACHATS",
    "OPERATIONS_TECH",
    "ARCHITECTE",
    "CHEF_PROJET_EXT",
]


class Role(Base):
    """GFI role definition with permissions JSON."""
    __tablename__ = "roles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(50), nullable=False, unique=True)
    libelle = Column(String(200), nullable=False)
    description = Column(Text)
    permissions = Column(JSON, nullable=False, default={})
    est_actif = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Utilisateur(Base):
    """GFI user with associate binding and company-level RLS."""
    __tablename__ = "utilisateurs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    associe_id = Column(String(36), ForeignKey("associes.id"))
    company_id = Column(String(36), ForeignKey("entreprises.id"))  # Row Level Security
    nom_complet = Column(String(300))
    email = Column(String(255))
    est_actif = Column(Boolean, default=True)
    derniere_connexion = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_utilisateur_company", "company_id"),
    )


class UtilisateurRole(Base):
    """M:N relationship between user and role, scoped by enterprise."""
    __tablename__ = "utilisateur_roles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    utilisateur_id = Column(String(36), ForeignKey("utilisateurs.id"), nullable=False)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"))
    date_attribution = Column(Date)
    est_actif = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("utilisateur_id", "role_id", "entreprise_id", name="uq_user_role_ent"),
    )


class AuditLogGFI(Base):
    """GFI audit log with realite_financiere tag and sensitivity flag."""
    __tablename__ = "audit_log_gfi"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    utilisateur_id = Column(String(36), ForeignKey("utilisateurs.id"))
    action = Column(String(100), nullable=False)
    entite_type = Column(String(100))
    entite_id = Column(String(36))
    realite_financiere = Column(String(4))  # RF1-RF4
    est_sensible = Column(Boolean, default=False)
    ancien_valeur = Column(JSON)
    nouveau_valeur = Column(JSON)
    hash_sha256 = Column(String(64))
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_audit_gfi_utilisateur", "utilisateur_id"),
        Index("ix_audit_gfi_entite", "entite_type", "entite_id"),
        Index("ix_audit_gfi_rf", "realite_financiere"),
    )
