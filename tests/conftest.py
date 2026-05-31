"""Shared test fixtures for the Email Context test suite.

Provides:
  - In-memory SQLite database (no external dependencies)
  - Pre-seeded test data (firm, accountants, client, emails)
  - Async HTTP client with overridden DB dependency
  - Token generation helper for authenticated requests
"""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import Accountant, Client, Email, Firm
from app.services.auth_service import create_access_token, hash_password

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def seeded_db(db_session: AsyncSession):
    """Seed test data and return references to created entities."""
    firm = Firm(name="Test Firm")
    db_session.add(firm)
    await db_session.flush()

    admin = Accountant(
        firm_id=firm.id,
        email="admin@test.com",
        full_name="Test Admin",
        hashed_password=hash_password("password123"),
        role="firm_admin",
    )
    accountant = Accountant(
        firm_id=firm.id,
        email="user@test.com",
        full_name="Test User",
        hashed_password=hash_password("password123"),
        role="accountant",
    )
    superuser = Accountant(
        firm_id=firm.id,
        email="super@test.com",
        full_name="Super User",
        hashed_password=hash_password("password123"),
        role="superuser",
    )
    db_session.add_all([admin, accountant, superuser])
    await db_session.flush()

    client = Client(firm_id=firm.id, name="Test Client", email="client@example.com")
    db_session.add(client)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    emails = []
    for i in range(10):
        email = Email(
            client_id=client.id,
            sender_email=f"sender{i}@test.com",
            sender_name=f"Sender {i}",
            recipients=[{"name": "Test Client", "email": "client@example.com"}],
            subject=f"Test Email {i}",
            body=f"This is test email body number {i}. It discusses tax matters.",
            sent_at=now - __import__("datetime").timedelta(days=10 - i),
        )
        emails.append(email)
    db_session.add_all(emails)
    await db_session.commit()

    return {
        "firm": firm,
        "admin": admin,
        "accountant": accountant,
        "superuser": superuser,
        "client": client,
        "emails": emails,
    }


@pytest_asyncio.fixture
async def async_client(db_engine):
    """Create an async test client with overridden DB dependency."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


def make_token(
    accountant_id: uuid.UUID, firm_id: uuid.UUID, role: str = "accountant"
) -> str:
    return create_access_token(accountant_id, firm_id, role)
