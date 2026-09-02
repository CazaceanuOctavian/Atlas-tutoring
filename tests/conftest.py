import os
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import models  # noqa: F401 — registers all ORM classes with Base.metadata
import dependencies
from db.session import get_db
from main import create_app
from models.base import Base
from models.user import User, UserRole

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/atlas_test",
)

_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_SessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _override_get_db():
    async with _SessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session():
    async with _SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession):
    user = User(
        name="Test Admin",
        email=f"admin_{uuid.uuid4().hex[:8]}@test.com",
        role=UserRole.admin,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user
    try:
        await db_session.execute(sa_delete(User).where(User.id == user.id))
        await db_session.commit()
    except Exception:
        await db_session.rollback()


@pytest_asyncio.fixture
async def student_user(db_session: AsyncSession):
    user = User(
        name="Test Student",
        email=f"student_{uuid.uuid4().hex[:8]}@test.com",
        role=UserRole.student,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user
    try:
        await db_session.execute(sa_delete(User).where(User.id == user.id))
        await db_session.commit()
    except Exception:
        await db_session.rollback()


def _build_client(user: User) -> AsyncClient:
    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[dependencies.get_current_user] = lambda: user
    app.dependency_overrides[dependencies.admin_only] = lambda: user
    app.dependency_overrides[dependencies.student_only] = lambda: user
    app.dependency_overrides[dependencies.professor_only] = lambda: user
    app.dependency_overrides[dependencies.enrolled_for_course] = lambda: user
    app.dependency_overrides[dependencies.enrolled_for_chapter] = lambda: user
    app.dependency_overrides[dependencies.enrolled_for_lecture] = lambda: user
    app.dependency_overrides[dependencies.enrolled_for_exercise] = lambda: user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def admin_client(admin_user: User):
    async with _build_client(admin_user) as client:
        yield client


@pytest_asyncio.fixture
async def student_client(student_user: User):
    async with _build_client(student_user) as client:
        yield client
