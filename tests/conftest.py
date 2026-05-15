"""Test fixtures for GFI Platform integration tests.

Uses an in-memory SQLite database (async) for isolation.
"""
import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base

# Import all models so metadata is populated
import app.models.core  # noqa: F401
import app.models.hr  # noqa: F401
import app.models.financial  # noqa: F401
import app.models.spi  # noqa: F401
import app.models.treasury  # noqa: F401
import app.models.registry  # noqa: F401
import app.models.finance_associes  # noqa: F401
import app.models.bim_edd  # noqa: F401
import app.models.legal  # noqa: F401
import app.models.adv  # noqa: F401
import app.models.integrations  # noqa: F401


@pytest_asyncio.fixture
async def db():
    """Provide a clean async SQLite session per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def tenant_id():
    return str(uuid.uuid4())


@pytest.fixture
def user_id():
    return str(uuid.uuid4())
