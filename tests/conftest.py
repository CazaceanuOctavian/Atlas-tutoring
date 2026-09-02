import os
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine as sync_create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import models  # noqa: F401 — registers all ORM classes with Base.metadata
import dependencies
from db.session import get_db
from main import create_app
from models.base import Base
from models.user import UserRole

ASYNC_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/atlas_test",
)
# psycopg2 is in requirements.txt; used only for sync fixture setup
SYNC_DB_URL = ASYNC_DB_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


# ---------------------------------------------------------------------------
# Session-scoped sync engine — no event loop involved, safe across all tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _sync_engine():
    eng = sync_create_engine(SYNC_DB_URL)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session", autouse=True)
def _create_tables(_sync_engine):
    Base.metadata.create_all(_sync_engine)


# ---------------------------------------------------------------------------
# User fixtures — sync so they never touch an event loop
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_user():
    """In-memory admin — auth deps are overridden, so it never needs to be in the DB."""
    user_id = uuid.uuid4()
    return SimpleNamespace(
        id=user_id,
        name="Test Admin",
        email=f"admin_{user_id.hex[:8]}@test.com",
        role=UserRole.admin,
    )


@pytest.fixture
def student_user(_sync_engine):
    """Student inserted into the DB (enrollment endpoints verify user existence)."""
    user_id = uuid.uuid4()
    email = f"student_{user_id.hex[:8]}@test.com"
    with _sync_engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, name, email, role)"
                " VALUES (:id, :name, :email, :role)"
            ),
            {"id": str(user_id), "name": "Test Student", "email": email, "role": "student"},
        )
        conn.commit()
    yield SimpleNamespace(id=user_id, name="Test Student", email=email, role=UserRole.student)
    with _sync_engine.connect() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)})
        conn.commit()


# ---------------------------------------------------------------------------
# HTTP client fixtures — each creates its own async engine in its own loop
# ---------------------------------------------------------------------------

def _build_app(user, override_get_db):
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[dependencies.get_current_user] = lambda: user
    app.dependency_overrides[dependencies.admin_only] = lambda: user
    app.dependency_overrides[dependencies.student_only] = lambda: user
    app.dependency_overrides[dependencies.professor_only] = lambda: user
    app.dependency_overrides[dependencies.enrolled_for_course] = lambda: user
    app.dependency_overrides[dependencies.enrolled_for_chapter] = lambda: user
    app.dependency_overrides[dependencies.enrolled_for_lecture] = lambda: user
    app.dependency_overrides[dependencies.enrolled_for_exercise] = lambda: user
    return app


@pytest_asyncio.fixture
async def admin_client(admin_user):
    eng = create_async_engine(ASYNC_DB_URL, echo=False)
    factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    async with AsyncClient(
        transport=ASGITransport(app=_build_app(admin_user, override_get_db)),
        base_url="http://test",
    ) as client:
        yield client

    await eng.dispose()


@pytest_asyncio.fixture
async def student_client(student_user):
    eng = create_async_engine(ASYNC_DB_URL, echo=False)
    factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    async with AsyncClient(
        transport=ASGITransport(app=_build_app(student_user, override_get_db)),
        base_url="http://test",
    ) as client:
        yield client

    await eng.dispose()
