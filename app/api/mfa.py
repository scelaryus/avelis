# GAP 1 — INFRASTRUCTURE & DB — mfa.py
"""MFA (Multi-Factor Authentication) stub endpoints using TOTP (pyotp)."""
import pyotp

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User
from app.config import get_settings

settings = get_settings()
router = APIRouter(tags=["MFA"])


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    message: str


class MFAVerifyRequest(BaseModel):
    code: str


class MFAVerifyResponse(BaseModel):
    verified: bool
    message: str


@router.post("/setup", response_model=MFASetupResponse)
async def mfa_setup(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a TOTP secret and provisioning URI for the current user."""
    secret = pyotp.random_base32()
    # Store the secret on the user record (mfa_secret column)
    await db.execute(
        update(User).where(User.id == user.id).values(mfa_secret=secret, mfa_enabled=False)
    )
    await db.flush()

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.email, issuer_name=settings.MFA_ISSUER)

    return MFASetupResponse(
        secret=secret,
        provisioning_uri=uri,
        message="Scan the URI with your authenticator app, then verify with /mfa/verify",
    )


@router.post("/verify", response_model=MFAVerifyResponse)
async def mfa_verify(
    body: MFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Verify the TOTP code and enable MFA for the user."""
    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA not set up. Call /mfa/setup first.")

    totp = pyotp.TOTP(user.mfa_secret)
    if totp.verify(body.code, valid_window=1):
        await db.execute(
            update(User).where(User.id == user.id).values(mfa_enabled=True)
        )
        await db.flush()
        return MFAVerifyResponse(verified=True, message="MFA enabled successfully")
    else:
        return MFAVerifyResponse(verified=False, message="Invalid TOTP code. Try again.")
