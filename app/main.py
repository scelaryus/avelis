"""GFI Platform - FastAPI Application Entry Point."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import get_settings
from app.api import (
    documents, workflows, accounting, hr, adv, admin,
    auth as auth_router, cost_center, legal, spi, treasury,
    registry, imports, chantier, achats, ressources,
)
from app.api import finance_associes as finance_associes_router
from app.api import bim as bim_router
from app.api import mfa as mfa_router
from app.services.blocking_rules import BlockingError

settings = get_settings()


def _apply_sqlite_dev_patches() -> None:
    """Patch the SQLite dev schema forward when Alembic history is not SQLite-safe.

    The repository contains migrations that use PostgreSQL-only types, so local
    SQLite files can drift behind the ORM models. This helper keeps the dev DB
    compatible with the current app features that rely on newer columns.
    """
    from sqlalchemy import text as sa_text
    from app.database import sync_engine

    table_columns: dict[str, set[str]] = {}

    def load_columns(conn, table: str) -> set[str]:
        if table not in table_columns:
            rows = conn.execute(sa_text(f"PRAGMA table_info({table})")).fetchall()
            table_columns[table] = {row[1] for row in rows}
        return table_columns[table]

    def ensure_column(conn, table: str, column: str, sql_type: str) -> None:
        cols = load_columns(conn, table)
        if column not in cols:
            conn.execute(sa_text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
            cols.add(column)

    with sync_engine.begin() as conn:
        ensure_column(conn, "users", "mfa_secret", "VARCHAR(64)")
        ensure_column(conn, "users", "mfa_enabled", "BOOLEAN DEFAULT 0")
        ensure_column(conn, "employees", "user_id", "VARCHAR(36)")
        ensure_column(conn, "employees", "professional_address", "TEXT")
        ensure_column(conn, "employees", "activities", "TEXT")
        ensure_column(conn, "employees", "upcoming_activity_due_date", "DATE")
        ensure_column(conn, "employees", "is_active", "BOOLEAN DEFAULT 1")
        ensure_column(conn, "employees", "manager_id", "VARCHAR(36)")
        ensure_column(conn, "employees", "mentor_id", "VARCHAR(36)")
        ensure_column(conn, "employees", "company", "VARCHAR(255)")
        ensure_column(conn, "employees", "function_category", "VARCHAR(50)")

        ensure_column(conn, "hr_tasks", "approval_status", "VARCHAR(32) DEFAULT 'PENDING_ESTIMATE'")
        ensure_column(conn, "hr_tasks", "employee_estimated_time", "FLOAT")
        ensure_column(conn, "hr_tasks", "employee_estimated_price", "NUMERIC(18, 2)")
        ensure_column(conn, "hr_tasks", "estimated_at", "DATETIME")
        ensure_column(conn, "hr_tasks", "manager_final_time", "FLOAT")
        ensure_column(conn, "hr_tasks", "manager_final_price", "NUMERIC(18, 2)")
        ensure_column(conn, "hr_tasks", "manager_approved_at", "DATETIME")
        ensure_column(conn, "hr_tasks", "manager_approved_by", "VARCHAR(36)")
        ensure_column(conn, "hr_tasks", "proof_document_id", "VARCHAR(36)")
        ensure_column(conn, "hr_tasks", "proof_uploaded_at", "DATETIME")
        ensure_column(conn, "hr_tasks", "ai_score", "FLOAT")
        ensure_column(conn, "hr_tasks", "ai_note", "TEXT")
        ensure_column(conn, "hr_tasks", "ai_evaluated_at", "DATETIME")
        ensure_column(conn, "hr_tasks", "manager_validated", "BOOLEAN DEFAULT 0")
        ensure_column(conn, "hr_tasks", "manager_validated_at", "DATETIME")

        conn.execute(sa_text(
            """
            CREATE TABLE IF NOT EXISTS user_permissions (
                id VARCHAR(36) PRIMARY KEY,
                tenant_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                module VARCHAR(100) NOT NULL,
                can_read BOOLEAN NOT NULL DEFAULT 0,
                can_write BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, module)
            )
            """
        ))
        conn.execute(sa_text(
            "CREATE INDEX IF NOT EXISTS ix_user_permissions_user ON user_permissions (user_id)"
        ))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    import structlog
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )

    # ── Verify database connectivity ────────────────────────────────────
    from app.database import async_engine
    _is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    try:
        from sqlalchemy import text as sa_text
        async with async_engine.connect() as conn:
            if _is_sqlite:
                await conn.execute(sa_text("SELECT 1"))
            else:
                result = await conn.execute(sa_text("SELECT version()"))
                pg_version = result.scalar()
                structlog.get_logger().info("postgresql_connected", version=pg_version)
    except Exception as exc:
        structlog.get_logger().critical("database_connection_failed", error=str(exc))
        raise SystemExit(f"Database connection failed: {exc}") from exc

    # Auto-create tables (dev convenience — production uses Alembic)
    from app.database import Base
    import app.models.core       # noqa: F401
    import app.models.hr         # noqa: F401
    import app.models.adv        # noqa: F401
    import app.models.financial  # noqa: F401
    import app.models.legal      # noqa: F401
    import app.models.spi        # noqa: F401
    import app.models.treasury   # noqa: F401
    import app.models.registry   # noqa: F401
    import app.models.integrations  # noqa: F401
    import app.models.finance_associes  # noqa: F401
    import app.models.bim_edd    # noqa: F401

    if _is_sqlite or settings.ENVIRONMENT == "development":
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    if _is_sqlite:
        _apply_sqlite_dev_patches()

    # Seed default tenant + admin user if DB is empty
    from app.database import AsyncSessionLocal
    from app.models.core import Tenant, User
    from sqlalchemy import select
    import uuid
    from app.services.rbac import ROLE_ALIASES

    async with AsyncSessionLocal() as session:
        # Normalize legacy stored roles to canonical identifiers.
        existing_users = (await session.execute(select(User))).scalars().all()
        roles_updated = False
        for existing_user in existing_users:
            canonical_role = ROLE_ALIASES.get(existing_user.role)
            if canonical_role and canonical_role != existing_user.role:
                existing_user.role = canonical_role
                roles_updated = True
        if roles_updated:
            await session.commit()

        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none() is None:
            tenant_id = str(uuid.uuid4())
            tenant = Tenant(id=tenant_id, name="AVELIS PROMOTION", code="AVELIS", description="Société de promotion immobilière", settings={})
            session.add(tenant)

            from passlib.context import CryptContext
            pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
            admin_user = User(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                email="admin@gfi.ma",
                hashed_password=pwd.hash("admin123"),
                full_name="Admin",
                role="SUPER_ADMIN",
                is_active=True,
            )
            session.add(admin_user)
            await session.commit()
            print("=== Seeded admin user: admin@gfi.ma / admin123 ===")

    # ── Start APScheduler ───────────────────────────────────────────────
    from app.services.scheduler import scheduler, register_jobs
    register_jobs(scheduler)
    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── BlockingError global handler ────────────────────────────────────────
@app.exception_handler(BlockingError)
async def blocking_error_handler(request: Request, exc: BlockingError):
    return JSONResponse(
        status_code=422,
        content={"blocked": True, "message": str(exc), "payload": exc.payload},
    )

# Mount routers
app.include_router(auth_router.router, prefix="/api/v1/auth")
app.include_router(documents.router, prefix="/api/v1/documents")
app.include_router(workflows.router, prefix="/api/v1/workflows")
app.include_router(accounting.router, prefix="/api/v1/accounting")
app.include_router(hr.router, prefix="/api/v1/hr")
app.include_router(adv.router, prefix="/api/v1/adv")
app.include_router(admin.router, prefix="/api/v1/admin")
app.include_router(cost_center.router, prefix="/api/v1/cost-center")
app.include_router(legal.router, prefix="/api/v1/legal")
app.include_router(spi.router, prefix="/api/v1/spi")
app.include_router(treasury.router, prefix="/api/v1/treasury")
app.include_router(registry.router, prefix="/api/v1/registry")
app.include_router(imports.router, prefix="/api/v1/imports")
app.include_router(finance_associes_router.router, prefix="/api/v1/finance")
app.include_router(bim_router.router, prefix="/api/v1/bim")
app.include_router(mfa_router.router, prefix="/api/v1/auth/mfa")
app.include_router(chantier.router, prefix="/api/v1/chantier")
app.include_router(achats.router, prefix="/api/v1/achats")
app.include_router(ressources.router, prefix="/api/v1/ressources")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
