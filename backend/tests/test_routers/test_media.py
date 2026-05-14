import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import User, MediaMetadata, PlaybackSession
from app.models.base import Base


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class TestMediaRouter:
    """Tests for media router endpoints."""

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
    async def test_get_media_detail_not_found(self, setup_db):
        """Test 404 when media not found."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/media/999")

        assert response.status_code == 404

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_media_detail(self, setup_db):
        """Test media detail endpoint."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async with session_factory() as session:
            user = User(jellyfin_id="user-1", name="Test User")
            media = MediaMetadata(
                jellyfin_id="media-1",
                title="Test Movie",
                type="Movie",
                genres='["Action", "Adventure"]',
                year=2024,
                runtime_ticks=7200000000,
            )
            session.add_all([user, media])
            await session.commit()
            await session.refresh(user)
            await session.refresh(media)

            play_session = PlaybackSession(
                jellyfin_session_id="media-play-1",
                user_id=user.id,
                media_id=media.id,
                started_at=datetime.utcnow() - timedelta(hours=2),
                ended_at=datetime.utcnow() - timedelta(hours=1),
                is_transcoding=False,
                play_method="DirectPlay",
                device_name="Test Device",
                duration_seconds=3600,
            )
            session.add(play_session)
            await session.commit()

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get(f"/api/media/{media.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Movie"
        assert data["type"] == "Movie"
        assert data["genres"] == ["Action", "Adventure"]
        assert data["year"] == 2024
        assert data["total_plays"] == 1
        assert len(data["play_history"]) == 1

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_library_stats_empty(self, setup_db):
        """Test library stats returns empty when no media."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/library/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["type_breakdown"] == []

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_library_stats_with_media(self, setup_db):
        """Test library stats with media."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async with session_factory() as session:
            movies = [
                MediaMetadata(jellyfin_id=f"m{i}", title=f"Movie {i}", type="Movie")
                for i in range(3)
            ]
            episodes = [
                MediaMetadata(jellyfin_id=f"e{i}", title=f"Episode {i}", type="Episode")
                for i in range(5)
            ]
            session.add_all(movies + episodes)
            await session.commit()

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/library/stats")

        assert response.status_code == 200
        data = response.json()
        assert len(data["type_breakdown"]) == 2
        movie_stats = next(s for s in data["type_breakdown"] if s["type"] == "Movie")
        assert movie_stats["count"] == 3

        app.dependency_overrides.clear()