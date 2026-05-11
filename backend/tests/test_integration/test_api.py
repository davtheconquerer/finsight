"""
Integration tests for FinSight API endpoints.
These tests use a real test database and test the full application flow.
"""
import pytest
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import User, MediaMetadata, PlaybackSession, NewsletterDigest
from app.models.base import Base


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(test_engine):
    """Create session factory for tests."""
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def seed_data(session_factory):
    """Seed test data for integration tests."""
    async with session_factory() as session:
        users = [
            User(jellyfin_id="user-1", name="Alice", play_count=10),
            User(jellyfin_id="user-2", name="Bob", play_count=5),
        ]
        media = [
            MediaMetadata(
                jellyfin_id="movie-1",
                title="Action Movie",
                type="Movie",
                genres='["Action", "Adventure"]',
                year=2024,
                play_count=5,
                last_played_at=datetime.utcnow() - timedelta(days=2),
            ),
            MediaMetadata(
                jellyfin_id="movie-2",
                title="Drama Movie",
                type="Movie",
                genres='["Drama"]',
                year=2023,
                play_count=2,
                last_played_at=datetime.utcnow() - timedelta(days=100),
            ),
            MediaMetadata(
                jellyfin_id="episode-1",
                title="TV Show S1",
                type="Episode",
                genres='["Comedy"]',
                year=2024,
                play_count=3,
                last_played_at=datetime.utcnow() - timedelta(hours=1),
            ),
            MediaMetadata(
                jellyfin_id="cold-movie",
                title="Never Watched",
                type="Movie",
                last_played_at=None,
            ),
        ]
        session.add_all(users + media)
        await session.commit()

        await session.refresh(users[0])
        await session.refresh(users[1])
        await session.refresh(media[0])
        await session.refresh(media[1])
        await session.refresh(media[2])

        for i in range(5):
            s = PlaybackSession(
                jellyfin_session_id=f"int-session-{i}",
                user_id=users[0].id,
                media_id=media[0].id,
                started_at=datetime.utcnow() - timedelta(days=i * 2),
                ended_at=datetime.utcnow() - timedelta(days=i * 2) + timedelta(hours=2),
                is_transcoding=i % 2 == 0,
                transcode_reason="Codec not supported" if i % 2 == 0 else None,
                play_method="DirectPlay" if i % 2 == 0 else "Transcode",
                device_name="Living Room TV",
            )
            session.add(s)

        for i in range(2):
            s = PlaybackSession(
                jellyfin_session_id=f"int-session-bob-{i}",
                user_id=users[1].id,
                media_id=media[2].id,
                started_at=datetime.utcnow() - timedelta(days=i),
                ended_at=datetime.utcnow() - timedelta(days=i) + timedelta(hours=1),
                is_transcoding=False,
                play_method="DirectPlay",
                device_name="Phone",
            )
            session.add(s)

        active_session = PlaybackSession(
            jellyfin_session_id="int-active-1",
            user_id=users[0].id,
            media_id=media[0].id,
            started_at=datetime.utcnow() - timedelta(minutes=30),
            ended_at=None,
            is_transcoding=True,
            transcode_reason="4K output",
            play_method="Transcode",
            device_name="Living Room TV",
            client_name="Jellyfin Web",
        )
        session.add(active_session)

        digest = NewsletterDigest(
            week_start=date(2026, 1, 6),
            week_end=date(2026, 1, 12),
            html_content="<html><body>Previous Week Digest</body></html>",
        )
        session.add(digest)

        await session.commit()

    return session_factory


class TestIntegration:
    """Integration tests for the full application."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, seed_data):
        """Test health check endpoint."""
        from app.database import get_db

        session_factory = seed_data

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_overview_stats(self, seed_data):
        """Test overview stats with seeded data."""
        from app.database import get_db

        session_factory = seed_data

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.get("/api/stats/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 2
        assert data["total_media"] == 4
        assert data["active_sessions"] >= 1

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_library_breakdown(self, seed_data):
        """Test library type breakdown."""
        from app.database import get_db

        session_factory = seed_data

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.get("/api/library/stats")

        assert response.status_code == 200
        data = response.json()
        breakdown = data["type_breakdown"]
        types = {item["type"]: item["count"] for item in breakdown}
        assert types.get("Movie", 0) == 3
        assert types.get("Episode", 0) == 1

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_cold_media_detection(self, seed_data):
        """Test cold media detection."""
        from app.database import get_db

        session_factory = seed_data

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.get("/api/library/cold-media?months=6")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_top_media(self, seed_data):
        """Test top media endpoint."""
        from app.database import get_db

        session_factory = seed_data

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.get("/api/stats/top-media")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_transcode_breakdown(self, seed_data):
        """Test transcode breakdown."""
        from app.database import get_db

        session_factory = seed_data

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.get("/api/stats/transcode-breakdown")

        assert response.status_code == 200
        data = response.json()
        assert "active" in data
        assert "reason_breakdown" in data

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_newsletter_flow(self, seed_data):
        """Test newsletter generate and preview flow."""
        from app.database import get_db

        session_factory = seed_data

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.get("/api/newsletter/latest")
            assert response.status_code == 200
            data = response.json()
            assert data["exists"] is True

            response = client.post("/newsletter/generate")
            assert response.status_code == 200

            response = client.get("/newsletter/preview")
            assert response.status_code == 200

        app.dependency_overrides.clear()