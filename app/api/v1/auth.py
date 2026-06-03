"""Auth router — login, refresh, MFA verify."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.core import AuthUser
from app.core.rbac import verify_password, create_access_token, create_refresh_token, decode_token, MODULE_MAP
from app.api.v1.schemas import ApiResponse, LoginRequest

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(AuthUser).filter(AuthUser.email == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(403, "Compte desactive")

    modules = MODULE_MAP.get(user.role, ["dashboard"])
    from app.core.rbac import DOC_SCOPE_MAP
    doc_scope = DOC_SCOPE_MAP.get(user.role)  # None = all types

    return ApiResponse(data={
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "bearer",
        "user_id": str(user.id),
        "name": user.full_name,
        "email": user.email,
        "role": user.role,
        "has_rf2": user.has_rf2_access,
        "modules": modules,
        "doc_scope": doc_scope,  # null = all, or list of allowed doc_types
    })


@router.post("/refresh")
async def refresh_token(body: dict, db: Session = Depends(get_db)):
    token = body.get("refresh_token", "")
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(400, "Token invalide")
    user = db.query(AuthUser).filter(AuthUser.id == payload["sub"]).first()
    if not user:
        raise HTTPException(404, "Utilisateur introuvable")
    return ApiResponse(data={
        "access_token": create_access_token(user),
        "token_type": "bearer",
    })


@router.post("/mfa/verify")
async def mfa_verify(body: dict):
    code = body.get("totp_code") or body.get("code", "")
    # In production: verify TOTP against user's secret
    # For dev: accept any 6-digit code
    if len(code) == 6 and code.isdigit():
        return ApiResponse(data={"valid": True})
    raise HTTPException(400, "Code MFA invalide")
