import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, settings
from app.database import init_db
from app.models import User, MediaMetadata, PlaybackSession
from app.models.base import Base


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def enable_demo_mode():
    """Enable demo mode for all tests to skip Jellyfin connection."""
    with patch.object(settings, 'demo_mode', True):
        yield


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Test settings with demo mode enabled."""
    return Settings(
        jellyfin_url="http://localhost:8096",
        jellyfin_api_key="test-api-key",
        database_url=TEST_DATABASE_URL,
        poll_interval=30,
        cold_media_months=6,
        demo_mode=True,
        log_level="DEBUG",
    )


@pytest.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_session_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    """Create test session factory."""
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def test_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async with test_session_factory() as session:
        yield session


@pytest.fixture
def mock_jellyfin_client():
    """Mock Jellyfin client for testing."""
    client = AsyncMock()
    client.validate = AsyncMock(return_value={"Version": "10.8.0", "ServerName": "Test Server"})
    client.get_sessions = AsyncMock(return_value=[])
    client.get_users = AsyncMock(return_value=[])
    client.get_items = AsyncMock(return_value={"Items": [], "TotalRecordCount": 0})
    client.get_total_item_count = AsyncMock(return_value=0)
    return client


@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """Sample user data for testing."""
    return {
        "jellyfin_id": "user-123",
        "name": "Test User",
        "play_count": 10,
        "last_seen_at": "2026-01-01T00:00:00",
    }


@pytest.fixture
def sample_media_data() -> dict[str, Any]:
    """Sample media data for testing."""
    return {
        "jellyfin_id": "media-456",
        "title": "Test Movie",
        "type": "Movie",
        "genres": '["Action", "Adventure"]',
        "size_bytes": 1500000000,
        "added_at": "2025-01-01T00:00:00",
        "last_played_at": "2026-01-01T00:00:00",
    }


@pytest.fixture
def sample_session_data() -> dict[str, Any]:
    """Sample playback session data for testing."""
    return {
        "jellyfin_session_id": "session-123",
        "user_id": 1,
        "media_id": 1,
        "started_at": "2026-01-01T12:00:00",
        "ended_at": "2026-01-01T13:30:00",
        "is_transcoding": True,
        "transcode_reason": "Codec not supported",
        "play_method": "DirectPlay",
    }


@pytest.fixture
async def test_user(test_session: AsyncSession) -> User:
    """Create test user in database."""
    user = User(
        jellyfin_id="user-123",
        name="Test User",
        play_count=10,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
async def test_media(test_session: AsyncSession) -> MediaMetadata:
    """Create test media in database."""
    media = MediaMetadata(
        jellyfin_id="media-456",
        title="Test Movie",
        type="Movie",
        genres='["Action"]',
        size_bytes=1000000,
    )
    test_session.add(media)
    await test_session.commit()
    await test_session.refresh(media)
    return media