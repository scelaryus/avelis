"""GFI Platform - Auth API router.

Login flow:
  1. POST /login  — email + password → token + list of accessible entreprises
  2. POST /select-entreprise — pick an entreprise → scoped token
  If user has access to only 1 entreprise, step 1 auto-selects it.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.core import User, Tenant, AuditLog
from app.models.financial import Entreprise, Associe, EntrepriseAssocie
from app.models.hr import Employee
from app.auth.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.auth.dependencies import get_current_user
from app.schemas.api import (
    TokenResponse,
    UserResponse,
    UserCreate,
    CompanyResponse,
)

router = APIRouter(tags=["Authentication"])


def _canonical_role(role: str | None) -> str:
    from app.services.rbac import _normalize_role
    return _normalize_role(role or "viewer")


# ── Schemas ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str
    company_id: Optional[str] = None  # kept for backward compat, ignored


class SelectEntrepriseRequest(BaseModel):
    entreprise_id: str


class EntrepriseInfo(BaseModel):
    id: str
    code: Optional[str] = None
    raison_sociale: str
    forme_juridique: Optional[str] = None
    statut: Optional[str] = None
    role_principal: Optional[str] = None

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[UserResponse] = None
    entreprises: list[EntrepriseInfo] = []
    active_entreprise: Optional[EntrepriseInfo] = None
    company: Optional[dict] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_user_entreprises(
    user: User, db: AsyncSession
) -> list[Entreprise]:
    """Determine which entreprises a user can access.

    Rules:
      - admin / SUPER_ADMIN / DAF → all entreprises
      - user linked to an associé → entreprises where that associé has participation
      - user linked to an employee → employee's entite_juridique_id
      - fallback → all entreprises (so nobody is locked out)
    """
    from app.services.rbac import _normalize_role
    role = _normalize_role(user.role)

    # Admin/DAF sees everything
    if role in ("SUPER_ADMIN", "DAF") or user.role in ("admin", "SUPER_ADMIN", "DAF"):
        result = await db.execute(
            select(Entreprise)
            .where(Entreprise.tenant_id == user.tenant_id)
            .order_by(Entreprise.code)
        )
        return list(result.scalars().all())

    accessible_ids: set[str] = set()

    # 1. Check if user is linked to an employee with entite_juridique_id
    if user.employee_id:
        emp_result = await db.execute(
            select(Employee).where(Employee.id == user.employee_id)
        )
        emp = emp_result.scalar_one_or_none()
        if emp and emp.entite_juridique_id:
            accessible_ids.add(emp.entite_juridique_id)

    # 2. Check if user matches an associé (by email or name)
    assoc_result = await db.execute(
        select(Associe).where(
            Associe.tenant_id == user.tenant_id,
            Associe.is_active == True,
        )
    )
    associes = assoc_result.scalars().all()

    user_name = (user.full_name or "").upper()
    user_email = (user.email or "").lower()

    matching_associe_ids: list[str] = []
    for a in associes:
        full = f"{a.nom} {a.prenom or ''}".upper()
        if (a.email and a.email.lower() == user_email) or \
           (user_name and (user_name in full or full in user_name)):
            matching_associe_ids.append(a.id)

    if matching_associe_ids:
        ea_result = await db.execute(
            select(EntrepriseAssocie).where(
                EntrepriseAssocie.associe_id.in_(matching_associe_ids),
                EntrepriseAssocie.est_actif == True,
            )
        )
        for ea in ea_result.scalars().all():
            if float(ea.pourcentage or 0) > 0:
                accessible_ids.add(ea.entreprise_id)

    # 3. Fallback — if nothing found, give access to all
    if not accessible_ids:
        result = await db.execute(
            select(Entreprise)
            .where(Entreprise.tenant_id == user.tenant_id)
            .order_by(Entreprise.code)
        )
        return list(result.scalars().all())

    result = await db.execute(
        select(Entreprise)
        .where(Entreprise.id.in_(accessible_ids))
        .order_by(Entreprise.code)
    )
    return list(result.scalars().all())


def _entreprise_info(ent: Entreprise) -> EntrepriseInfo:
    return EntrepriseInfo(
        id=str(ent.id),
        code=ent.code,
        raison_sociale=ent.raison_sociale,
        forme_juridique=ent.forme_juridique,
        statut=ent.statut,
        role_principal=ent.role_principal,
    )


# ── Public: list companies for backward compat ──────────────────

@router.get("/companies", response_model=list[CompanyResponse])
async def list_companies(db: AsyncSession = Depends(get_db)):
    """List active companies (tenants) for backward compat."""
    result = await db.execute(
        select(Tenant).where(Tenant.is_active == True).order_by(Tenant.name)
    )
    tenants = result.scalars().all()
    return [
        CompanyResponse(
            id=str(t.id), name=t.name, code=t.code,
            logo_url=t.logo_url, description=t.description, is_active=t.is_active,
        )
        for t in tenants
    ]


# ── Login ────────────────────────────────────────────────────────

@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with email + password.

    Returns the user, a token, and the list of entreprises the user can access.
    If only 1 entreprise → auto-selects it and sets active_entreprise.
    """
    # Find user by email (across all tenants in this single-tenant system)
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides",
        )

    # Get accessible entreprises
    entreprises = await _get_user_entreprises(user, db)

    # Auto-select if only one
    active_ent = entreprises[0] if len(entreprises) == 1 else None
    active_ent_id = str(active_ent.id) if active_ent else None

    access_token = create_access_token(
        str(user.id), str(user.tenant_id), user.role,
        entreprise_id=active_ent_id,
    )
    refresh = create_refresh_token(
        str(user.id), str(user.tenant_id), user.role,
        entreprise_id=active_ent_id,
    )

    # Fetch tenant for company info
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = tenant_result.scalar_one_or_none()

    # Audit
    db.add(AuditLog(tenant_id=user.tenant_id, user_id=user.id, action="login"))
    await db.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh,
        token_type="bearer",
        user=UserResponse(
            id=user.id, email=user.email, full_name=user.full_name,
            role=_canonical_role(user.role), tenant_id=user.tenant_id,
            is_active=user.is_active, employee_id=user.employee_id,
        ),
        entreprises=[_entreprise_info(e) for e in entreprises],
        active_entreprise=_entreprise_info(active_ent) if active_ent else None,
        company={
            "id": str(tenant.id), "name": tenant.name,
            "code": tenant.code, "logo_url": tenant.logo_url,
        } if tenant else None,
    )


# ── Select entreprise ───────────────────────────────────────────

@router.post("/select-entreprise")
async def select_entreprise(
    body: SelectEntrepriseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """After login, select an entreprise to work in. Returns a scoped token."""
    # Verify user has access to this entreprise
    entreprises = await _get_user_entreprises(user, db)
    ent_ids = {str(e.id) for e in entreprises}

    if body.entreprise_id not in ent_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès à cette entité",
        )

    # Find the entreprise
    ent = next(e for e in entreprises if str(e.id) == body.entreprise_id)

    access_token = create_access_token(
        str(user.id), str(user.tenant_id), user.role,
        entreprise_id=body.entreprise_id,
    )
    refresh = create_refresh_token(
        str(user.id), str(user.tenant_id), user.role,
        entreprise_id=body.entreprise_id,
    )

    # Fetch tenant
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = tenant_result.scalar_one_or_none()

    db.add(AuditLog(
        tenant_id=user.tenant_id, user_id=user.id,
        action=f"select_entreprise:{ent.code}",
    ))
    await db.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh,
        token_type="bearer",
        user=UserResponse(
            id=user.id, email=user.email, full_name=user.full_name,
            role=_canonical_role(user.role), tenant_id=user.tenant_id,
            is_active=user.is_active, employee_id=user.employee_id,
        ),
        entreprises=[_entreprise_info(e) for e in entreprises],
        active_entreprise=_entreprise_info(ent),
        company={
            "id": str(tenant.id), "name": tenant.name,
            "code": tenant.code, "logo_url": tenant.logo_url,
        } if tenant else None,
    )


# ── Refresh ──────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """Refresh access token."""
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = tenant_result.scalar_one_or_none()

    entreprise_id = payload.get("entreprise_id")
    access_token = create_access_token(
        str(user.id), str(user.tenant_id), user.role,
        entreprise_id=entreprise_id,
    )
    new_refresh_token = create_refresh_token(
        str(user.id), str(user.tenant_id), user.role,
        entreprise_id=entreprise_id,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id, email=user.email, full_name=user.full_name,
            role=_canonical_role(user.role), tenant_id=user.tenant_id,
            is_active=user.is_active, employee_id=user.employee_id,
        ),
        company={
            "id": str(tenant.id), "name": tenant.name,
            "code": tenant.code, "logo_url": tenant.logo_url,
        } if tenant else None,
    )


# ── Register ─────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user (requires existing tenant/company)."""
    result = await db.execute(select(Tenant).where(Tenant.id == body.tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    result = await db.execute(
        select(User).where(User.email == body.email, User.tenant_id == str(body.tenant_id))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        tenant_id=str(body.tenant_id),
        email=body.email,
        full_name=body.full_name,
        hashed_password=get_password_hash(body.password),
        role=_canonical_role(body.role),
        employee_id=str(body.employee_id) if body.employee_id else None,
    )
    db.add(user)
    await db.flush()

    db.add(AuditLog(tenant_id=user.tenant_id, user_id=user.id, action="register"))
    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id, email=user.email, full_name=user.full_name,
        role=_canonical_role(user.role), tenant_id=user.tenant_id,
        is_active=user.is_active, employee_id=user.employee_id,
    )


# ── Profile ──────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserResponse(
        id=user.id, email=user.email, full_name=user.full_name,
        role=_canonical_role(user.role), tenant_id=user.tenant_id,
        is_active=user.is_active, employee_id=user.employee_id,
    )


@router.get("/me/company")
async def get_my_company(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get the current user's company (tenant) info."""
    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return {
        "id": str(tenant.id), "name": tenant.name,
        "code": tenant.code, "logo_url": tenant.logo_url,
        "description": tenant.description,
    }


@router.get("/me/entreprise")
async def get_my_entreprise(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's active entreprise from JWT."""
    from app.auth.security import decode_token as dt
    # We need the raw token to read entreprise_id — the user object doesn't have it
    # This is a workaround; ideally we'd pass it from the dependency
    entreprises = await _get_user_entreprises(user, db)
    return {
        "entreprises": [_entreprise_info(e).model_dump() for e in entreprises],
    }


@router.get("/me/menu")
async def get_my_menu(user: User = Depends(get_current_user)):
    """Return menu items based on user role (supports old + new roles)."""
    from app.services.rbac import _normalize_role
    role = _normalize_role(user.role)

    all_items = [
        {"key": "dashboard", "label": "Dashboard", "path": "/dashboard", "icon": "HomeIcon",
         "roles": {"admin", "accountant", "hr_manager", "sales", "viewer", "employee",
                   "SUPER_ADMIN", "DAF", "RH", "COMMERCIAL", "VIEWER", "EMPLOYE",
                   "BIM", "ADV", "NOTAIRE", "JURIDIQUE", "DIRECTION", "MARKETING"}},
        {"key": "documents", "label": "Documents (GED)", "path": "/documents", "icon": "DocumentTextIcon",
         "roles": {"admin", "accountant", "hr_manager",
                   "SUPER_ADMIN", "DAF", "RH", "DIRECTION"}},
        {"key": "accounting", "label": "Comptabilité", "path": "/accounting", "icon": "BanknotesIcon",
         "roles": {"admin", "accountant", "SUPER_ADMIN", "DAF"}},
        {"key": "hr", "label": "RH & Paie", "path": "/hr", "icon": "UserGroupIcon",
         "roles": {"admin", "hr_manager", "SUPER_ADMIN", "RH"}},
        {"key": "adv", "label": "ADV & Trésorerie", "path": "/adv", "icon": "ChartBarIcon",
         "roles": {"admin", "sales", "accountant", "SUPER_ADMIN", "COMMERCIAL", "DAF", "ADV"}},
        {"key": "legal", "label": "Juridique", "path": "/legal", "icon": "ScaleIcon",
         "roles": {"admin", "accountant", "SUPER_ADMIN", "DAF", "JURIDIQUE"}},
        {"key": "cost-center", "label": "Centre de Coût", "path": "/cost-center", "icon": "CalculatorIcon",
         "roles": {"admin", "accountant", "SUPER_ADMIN", "DAF", "DIRECTION"}},
        {"key": "spi", "label": "SPI 360°", "path": "/spi", "icon": "PresentationChartBarIcon",
         "roles": {"admin", "hr_manager", "SUPER_ADMIN", "RH", "DIRECTION", "DAF"}},
        {"key": "spi-employee", "label": "Mes Tâches & Plans", "path": "/spi", "icon": "ClipboardDocumentListIcon",
         "roles": {"employee", "EMPLOYE", "sales", "COMMERCIAL"}},
        {"key": "chantiers", "label": "Projets & Chantiers", "path": "/chantiers", "icon": "CubeIcon",
         "roles": {"admin", "SUPER_ADMIN", "DAF", "DIRECTION", "PROJECT_MANAGER", "OPERATIONS_TECH", "ARCHITECTE", "CHEF_PROJET_EXT"}},
        {"key": "ressources", "label": "Ressources", "path": "/ressources", "icon": "CubeIcon",
         "roles": {"admin", "accountant", "SUPER_ADMIN", "DAF", "MAGASINIER", "ACHATS", "DIRECTION"}},
        {"key": "workflows-dendani", "label": "Workflows Dendani", "path": "/workflows-dendani", "icon": "ArrowsRightLeftIcon",
         "roles": {"admin", "SUPER_ADMIN", "DAF"}},
        {"key": "admin", "label": "Administration", "path": "/admin", "icon": "Cog6ToothIcon",
         "roles": {"admin", "SUPER_ADMIN"}},
    ]
    return [
        {"key": item["key"], "label": item["label"], "path": item["path"], "icon": item["icon"]}
        for item in all_items
        if user.role in item["roles"] or role in item["roles"]
    ]
