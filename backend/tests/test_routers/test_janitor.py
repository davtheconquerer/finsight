import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import User, MediaMetadata, PlaybackSession
from app.models.base import Base


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class TestJanitorRouter:
    """Tests for janitor router endpoints."""

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
    async def test_get_cold_media_empty(self, setup_db):
        """Test cold media returns empty when all media is played."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/library/cold-media?months=6")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["count"] == 0

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_cold_media_with_items(self, setup_db):
        """Test cold media returns cold items."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async with session_factory() as session:
            old_media = MediaMetadata(
                jellyfin_id="media-old",
                title="Old Movie",
                type="Movie",
                last_played_at=datetime.utcnow() - timedelta(days=200),
            )
            recent_media = MediaMetadata(
                jellyfin_id="media-new",
                title="Recent Movie",
                type="Movie",
                last_played_at=datetime.utcnow() - timedelta(days=1),
            )
            never_played = MediaMetadata(
                jellyfin_id="media-never",
                title="Never Played",
                type="Movie",
                last_played_at=None,
            )
            session.add_all([old_media, recent_media, never_played])
            await session.commit()

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/library/cold-media?months=6")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        titles = [item["title"] for item in data["items"]]
        assert "Old Movie" in titles
        assert "Never Played" in titles

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_export_cold_media_csv(self, setup_db):
        """Test CSV export endpoint."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async with session_factory() as session:
            media = MediaMetadata(
                jellyfin_id="media-1",
                title="Test Movie",
                type="Movie",
                year=2024,
                play_count=0,
                last_played_at=None,
                runtime_ticks=7200000000,
            )
            session.add(media)
            await session.commit()

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/library/cold-media/export?months=6")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        content = response.text
        assert "Title" in content
        assert "Test Movie" in content

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_user_stats_empty(self, setup_db):
        """Test user stats returns empty when no users."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/users/stats")

        assert response.status_code == 200
        assert response.json() == []

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_user_stats_with_data(self, setup_db):
        """Test user stats with data."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async with session_factory() as session:
            user = User(
                jellyfin_id="user-1",
                name="Test User",
                play_count=10,
                last_seen_at=datetime.utcnow(),
            )
            media = MediaMetadata(
                jellyfin_id="media-1",
                title="Test Movie",
                type="Movie",
            )
            session.add_all([user, media])
            await session.commit()
            await session.refresh(user)
            await session.refresh(media)

            for i in range(3):
                s = PlaybackSession(
                    jellyfin_session_id=f"janitor-session-{i}",
                    user_id=user.id,
                    media_id=media.id,
                    started_at=datetime.utcnow() - timedelta(days=i),
                    ended_at=datetime.utcnow() - timedelta(days=i) + timedelta(hours=1),
                    is_transcoding=True,
                    device_name="Test Device",
                )
                session.add(s)
            await session.commit()

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/users/stats")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test User"
        assert data[0]["total_plays"] == 3
        assert data[0]["transcodes"] == 3
        assert data[0]["transcode_ratio"] == 1.0

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_metrics_prometheus_format(self, setup_db):
        """Test Prometheus metrics endpoint."""
        session_factory = async_sessionmaker(setup_db, expire_on_commit=False)

        async with session_factory() as session:
            user = User(jellyfin_id="user-1", name="Test User")
            media = MediaMetadata(jellyfin_id="media-1", title="Test Movie", type="Movie")
            session.add_all([user, media])
            await session.commit()
            await session.refresh(user)
            await session.refresh(media)

            active_session = PlaybackSession(
                jellyfin_session_id="metrics-active-1",
                user_id=user.id,
                media_id=media.id,
                started_at=datetime.utcnow(),
                ended_at=None,
            )
            session.add(active_session)
            await session.commit()

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/metrics")

        assert response.status_code == 200
        content = response.text
        assert "finsight_total_users" in content
        assert "finsight_total_media" in content
        assert "finsight_active_sessions" in content

        app.dependency_overrides.clear()