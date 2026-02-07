import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from main import app
from shared.config import settings
from shared.dependencies import get_db
from shared.infrastructure.database import Base

import auth.infrastructure.models  # noqa: F401
import documents.infrastructure.models  # noqa: F401

TEST_DATABASE_URL = settings.DATABASE_URL.replace("/cms", "/cms_test")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def create_user_and_get_headers(client: AsyncClient, suffix: str = "") -> dict:
    """Register a user and return auth headers."""
    await client.post(
        "/api/auth/register",
        json={
            "username": f"testuser{suffix}",
            "email": f"test{suffix}@example.com",
            "first_name": "Test",
            "last_name": "User",
            "password": "secret123",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": f"test{suffix}@example.com", "password": "secret123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def auth_headers(client) -> dict:
    return await create_user_and_get_headers(client)


@pytest.fixture
async def db(test_engine):
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
async def override_db(test_engine):
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
