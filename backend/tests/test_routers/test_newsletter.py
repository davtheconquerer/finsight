import pytest
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import NewsletterDigest
from app.models.base import Base


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class TestNewsletterRouter:
    """Tests for newsletter router endpoints."""

    @pytest.fixture
    def test_engine(self):
        return create_async_engine(TEST_DATABASE_URL, echo=False)

    @pytest.fixture
    async def setup_db(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield test_engine
        await test_engine.dispose()

    @pytest.mark.asyncio
    async def test_preview_newsletter_no_digest(self, setup_db):
        """Test preview returns default when no digest exists."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/newsletter/preview")

        assert response.status_code == 200
        assert "No digest generated yet" in response.text

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_preview_newsletter_with_digest(self, setup_db):
        """Test preview returns HTML content."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async with session_factory() as session:
            digest = NewsletterDigest(
                week_start=date(2026, 1, 13),
                week_end=date(2026, 1, 19),
                html_content="<html><body><h1>Weekly Digest</h1></body></html>",
            )
            session.add(digest)
            await session.commit()

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/newsletter/preview")

        assert response.status_code == 200
        assert "Weekly Digest" in response.text

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_generate_newsletter(self, setup_db):
        """Test generate newsletter creates digest."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.post("/newsletter/generate")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "week_start" in data
        assert "week_end" in data

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_latest_digest_info_none(self, setup_db):
        """Test latest digest info returns not exists."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/newsletter/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is False

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_latest_digest_info_exists(self, setup_db):
        """Test latest digest info returns digest data."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async with session_factory() as session:
            digest = NewsletterDigest(
                week_start=date(2026, 1, 13),
                week_end=date(2026, 1, 19),
                html_content="<html>test</html>",
                sent=False,
            )
            session.add(digest)
            await session.commit()
            await session.refresh(digest)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/newsletter/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
        assert data["sent"] is False

        app.dependency_overrides.clear()