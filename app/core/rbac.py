"""RBAC middleware — JWT auth + role checking + module-based access + RF2 filtering."""
import os
from hashlib import sha256
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.db import get_db
from app.models.core import AuthUser

SECRET_KEY = os.getenv("JWT_SECRET", "gfi-v7-secret-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = 60 * 24  # minutes

security = HTTPBearer(auto_error=False)

# ── Module access per role ────────────────────────────────────────────────────
# Each module key maps to sidebar sections and API route prefixes.
ALL_MODULES = [
    "dashboard", "foundation", "finance", "adv", "stock",
    "operations", "rh", "juridique", "ged", "system",
]

MODULE_MAP: dict[str, list[str]] = {
    "DAF":                ALL_MODULES,
    "ADMIN":              ALL_MODULES,
    "RESPONSABLE_ADV":    ["dashboard", "adv", "juridique", "finance", "ged"],
    "GESTIONNAIRE_ADV":   ["dashboard", "adv", "ged"],
    "AGENT_COMMERCIAL":   ["dashboard", "adv", "ged"],
    "GESTIONNAIRE_STOCK": ["dashboard", "stock", "ged"],
    "DRH":                ["dashboard", "rh", "ged"],
    "TRESORIER":          ["dashboard", "finance", "adv", "ged"],
    "COMPTABLE":          ["dashboard", "finance", "ged"],
}

# Document types each role can upload via GED
DOC_SCOPE_MAP: dict[str, list[str] | None] = {
    "DAF":                None,  # None = all types
    "ADMIN":              None,
    "RESPONSABLE_ADV":    ["FACTURE_FOURNISSEUR", "FACTURE_CLIENT", "BON_COMMANDE", "DEVIS",
                           "CONTRAT", "AVENANT_CONTRAT", "ACTE_NOTARIE", "SITUATION_TRAVAUX",
                           "PV_RECEPTION", "PV_CHANTIER", "RELEVE_BANCAIRE", "ACCORD_PRET", "AUTRE"],
    "GESTIONNAIRE_ADV":   ["FACTURE_FOURNISSEUR", "FACTURE_CLIENT", "BON_COMMANDE", "DEVIS",
                           "SITUATION_TRAVAUX", "PV_RECEPTION", "PV_CHANTIER", "AUTRE"],
    "AGENT_COMMERCIAL":   ["FACTURE_CLIENT", "BON_COMMANDE", "DEVIS", "AUTRE"],
    "GESTIONNAIRE_STOCK": ["BON_COMMANDE", "FACTURE_FOURNISSEUR", "PHOTO_CHANTIER", "AUTRE"],
    "DRH":                ["FICHE_PAIE", "CONTRAT", "AVENANT_CONTRAT", "RAPPORT_INTERNE",
                           "COURRIER", "AUTRE"],
    "TRESORIER":          ["RELEVE_BANCAIRE", "FACTURE_FOURNISSEUR", "FACTURE_CLIENT",
                           "ACCORD_PRET", "AUTRE"],
    "COMPTABLE":          ["FACTURE_FOURNISSEUR", "FACTURE_CLIENT", "RELEVE_BANCAIRE", "AUTRE"],
}


def create_access_token(user: AuthUser) -> str:
    modules = MODULE_MAP.get(user.role, ["dashboard"])
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "name": user.full_name,
        "rf2": user.has_rf2_access,
        "modules": modules,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user: AuthUser) -> str:
    payload = {
        "sub": str(user.id),
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expire")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token invalide")


def verify_password(plain: str, hashed: str) -> bool:
    return sha256(plain.encode()).hexdigest() == hashed


class CurrentUser:
    def __init__(self, user_id: str, email: str, role: str, name: str,
                 has_rf2: bool, modules: list[str] | None = None):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.name = name
        self.has_rf2 = has_rf2
        self.modules = modules or MODULE_MAP.get(role, ["dashboard"])
        self.doc_scope = DOC_SCOPE_MAP.get(role)  # None = all


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> CurrentUser:
    if not credentials:
        # Development fallback — return DAF user
        return CurrentUser("dev", "dev@gfi.dz", "DAF", "Dev User", True, ALL_MODULES)
    payload = decode_token(credentials.credentials)
    return CurrentUser(
        user_id=payload["sub"],
        email=payload["email"],
        role=payload["role"],
        name=payload["name"],
        has_rf2=payload.get("rf2", False),
        modules=payload.get("modules", MODULE_MAP.get(payload["role"], ["dashboard"])),
    )


def require_role(*allowed_roles):
    async def checker(user: CurrentUser = Depends(get_current_user)):
        if user.role not in allowed_roles and user.role != "DAF":
            raise HTTPException(403, f"Role {user.role} non autorise. Requis: {', '.join(allowed_roles)}")
        return user
    return checker


def require_module(*modules):
    """Check that the user has access to at least one of the specified modules."""
    async def checker(user: CurrentUser = Depends(get_current_user)):
        if not any(m in user.modules for m in modules):
            raise HTTPException(403, f"Acces interdit. Modules requis: {', '.join(modules)}. Votre acces: {', '.join(user.modules)}")
        return user
    return checker


def filter_rf2(data: dict, user: CurrentUser) -> dict:
    """Remove RF2 fields if user cannot see them."""
    if user.has_rf2:
        return data
    rf2_keys = {"rf2_price", "prix_rf2", "prix_vente_rf2", "montant_rf2", "rf2_status",
                "montant_rf2_securise", "rf2"}
    return {k: v for k, v in data.items() if k not in rf2_keys}
