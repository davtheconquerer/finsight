import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import User, MediaMetadata, PlaybackSession
from app.models.base import Base


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    return engine


@pytest.fixture
async def test_db(test_engine):
    """Create test database and tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await test_engine.dispose()


@pytest.fixture
def client(test_engine):
    """Create test client with overridden database dependency."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[__import__("app.database", fromlist=["get_db"]).get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


class TestSessionsRouter:
    """Tests for sessions router endpoints."""

    @pytest.mark.asyncio
    async def test_get_active_sessions_empty(self, test_engine):
        """Test active sessions returns empty when no sessions."""
        session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/sessions/active")

        assert response.status_code == 200
        assert response.json() == []

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_active_sessions_with_data(self, test_engine):
        """Test active sessions returns sessions when present."""
        session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

        async with session_factory() as session:
            user = User(jellyfin_id="user-1", name="Test User")
            media = MediaMetadata(jellyfin_id="media-1", title="Test Movie", type="Movie")
            session.add_all([user, media])
            await session.commit()
            await session.refresh(user)
            await session.refresh(media)

            session_obj = PlaybackSession(
                jellyfin_session_id="session-active-1",
                user_id=user.id,
                media_id=media.id,
                started_at=datetime.utcnow(),
                ended_at=None,
                device_name="Test Device",
                client_name="Test Client",
                is_transcoding=True,
                transcode_reason="Codec not supported",
                play_method="Transcode",
            )
            session.add(session_obj)
            await session.commit()

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/sessions/active")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user"] == "Test User"
        assert data[0]["media"] == "Test Movie"
        assert data[0]["is_transcoding"] is True

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_session_history_empty(self, test_engine):
        """Test session history returns empty when no history."""
        session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/sessions/history")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_session_history_pagination(self, test_engine):
        """Test session history pagination."""
        session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

        async with session_factory() as session:
            user = User(jellyfin_id="user-1", name="Test User")
            media = MediaMetadata(jellyfin_id="media-1", title="Test Movie", type="Movie")
            session.add_all([user, media])
            await session.commit()
            await session.refresh(user)
            await session.refresh(media)

            for i in range(25):
                s = PlaybackSession(
                    jellyfin_session_id=f"session-{i}",
                    user_id=user.id,
                    media_id=media.id,
                    started_at=datetime.utcnow() - timedelta(days=i),
                    ended_at=datetime.utcnow() - timedelta(days=i) + timedelta(hours=1),
                    device_name="Device",
                )
                session.add(s)
            await session.commit()

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/sessions/history?page=1&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] == 25
        assert data["page"] == 1
        assert data["per_page"] == 10

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_stats_overview(self, test_engine):
        """Test stats overview endpoint."""
        session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

        async with session_factory() as session:
            user = User(jellyfin_id="user-1", name="Test User")
            media = MediaMetadata(jellyfin_id="media-1", title="Test Movie", type="Movie")
            session.add_all([user, media])
            await session.commit()

            active_session = PlaybackSession(
                jellyfin_session_id="active-session-1",
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
            response = c.get("/api/stats/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 1
        assert data["total_media"] == 1
        assert data["active_sessions"] == 1

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_plays_over_time_empty(self, test_engine):
        """Test plays over time returns empty when no data."""
        session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/stats/plays-over-time?days=30")

        assert response.status_code == 200
        assert response.json() == []

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_plays_over_time_with_data(self, test_engine):
        """Test plays over time returns correct data."""
        session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

        async with session_factory() as session:
            user = User(jellyfin_id="user-1", name="Test User")
            media = MediaMetadata(jellyfin_id="media-1", title="Test Movie", type="Movie")
            session.add_all([user, media])
            await session.commit()
            await session.refresh(user)
            await session.refresh(media)

            play_session = PlaybackSession(
                jellyfin_session_id="session-play-1",
                user_id=user.id,
                media_id=media.id,
                started_at=datetime.utcnow() - timedelta(days=5),
                ended_at=datetime.utcnow() - timedelta(days=5) + timedelta(hours=2),
            )
            session.add(play_session)
            await session.commit()

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/stats/plays-over-time?days=30")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_top_media(self, test_engine):
        """Test top media endpoint."""
        session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

        async with session_factory() as session:
            user = User(jellyfin_id="user-1", name="Test User")
            media = MediaMetadata(jellyfin_id="media-1", title="Test Movie", type="Movie")
            session.add_all([user, media])
            await session.commit()
            await session.refresh(user)
            await session.refresh(media)

            for i in range(5):
                s = PlaybackSession(
                    jellyfin_session_id=f"top-media-session-{i}",
                    user_id=user.id,
                    media_id=media.id,
                    started_at=datetime.utcnow() - timedelta(days=i),
                    ended_at=datetime.utcnow(),
                )
                session.add(s)
            await session.commit()

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/stats/top-media")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Movie"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_transcode_breakdown_empty(self, test_engine):
        """Test transcode breakdown returns empty when no transcode data."""
        session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        from app.database import get_db
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            response = c.get("/api/stats/transcode-breakdown")

        assert response.status_code == 200
        data = response.json()
        assert data["active"] == []
        assert data["reason_breakdown"] == []
        assert data["top_transcoders"] == []

        app.dependency_overrides.clear()