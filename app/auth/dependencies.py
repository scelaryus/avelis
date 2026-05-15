"""GFI Platform - FastAPI dependencies for auth."""
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.core import User
from app.auth.security import decode_token

bearer_scheme = HTTPBearer()

ROLE_ALIASES: dict[str, str] = {
    "admin": "SUPER_ADMIN",
    "accountant": "DAF",
    "hr_manager": "RH",
    "sales": "COMMERCIAL",
    "employee": "EMPLOYE",
    "viewer": "VIEWER",
}


def _normalize_role_name(role: str) -> str:
    """Map legacy role names to canonical role identifiers."""
    return ROLE_ALIASES.get(role, role)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT, return User ORM object."""
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    # Attach active entreprise_id from JWT to user object for scoping
    user._active_entreprise_id = payload.get("entreprise_id")
    return user


def get_active_entreprise_id(
    user: User = Depends(get_current_user),
    x_entreprise_id: Optional[str] = Header(None),
) -> str | None:
    """Extract active entreprise_id from header or JWT."""
    return x_entreprise_id or getattr(user, "_active_entreprise_id", None)


def require_role(*allowed_roles: str):
    """Dependency factory: restrict access to users with given roles."""
    normalized_allowed_roles = {_normalize_role_name(role) for role in allowed_roles}

    async def _role_check(user: User = Depends(get_current_user)) -> User:
        user_role = _normalize_role_name(user.role)
        if user_role not in normalized_allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return _role_check


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Optionally extract user (for public endpoints that benefit from auth)."""
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    if payload is None:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
