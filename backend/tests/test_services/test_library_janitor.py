import pytest
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import MediaMetadata
from app.models.base import Base
from app.services.library_janitor import LibraryJanitor


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class TestLibraryJanitorReal:
    """Integration tests for LibraryJanitor with real database."""

    @pytest.fixture
    async def engine(self):
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()

    @pytest.fixture
    async def session_factory(self, engine):
        return async_sessionmaker(engine, expire_on_commit=False)

    @pytest.mark.asyncio
    async def test_get_cold_media_empty(self, session_factory):
        """Test get_cold_media returns empty when all media recently played."""
        async with session_factory() as session:
            media = MediaMetadata(
                jellyfin_id="media-1",
                title="Recent Movie",
                type="Movie",
                last_played_at=datetime.utcnow() - timedelta(days=1),
            )
            session.add(media)
            await session.commit()

        janitor = LibraryJanitor(session_factory)
        result = await janitor.get_cold_media(months=6)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_cold_media_never_played(self, session_factory):
        """Test get_cold_media returns media never played."""
        async with session_factory() as session:
            media = MediaMetadata(
                jellyfin_id="media-1",
                title="Never Played Movie",
                type="Movie",
                last_played_at=None,
            )
            session.add(media)
            await session.commit()

        janitor = LibraryJanitor(session_factory)
        result = await janitor.get_cold_media(months=6)

        assert len(result) == 1
        assert result[0]["title"] == "Never Played Movie"
        assert result[0]["days_since_played"] is None

    @pytest.mark.asyncio
    async def test_get_cold_media_old_played(self, session_factory):
        """Test get_cold_media returns media played long ago."""
        async with session_factory() as session:
            media = MediaMetadata(
                jellyfin_id="media-1",
                title="Old Movie",
                type="Movie",
                last_played_at=datetime.utcnow() - timedelta(days=200),
            )
            session.add(media)
            await session.commit()

        janitor = LibraryJanitor(session_factory)
        result = await janitor.get_cold_media(months=6)

        assert len(result) == 1
        assert result[0]["title"] == "Old Movie"
        assert result[0]["days_since_played"] is not None

    @pytest.mark.asyncio
    async def test_get_cold_media_mixed(self, session_factory):
        """Test get_cold_media filters correctly."""
        async with session_factory() as session:
            recent = MediaMetadata(jellyfin_id="recent", title="Recent", type="Movie", last_played_at=datetime.utcnow() - timedelta(days=1))
            old = MediaMetadata(jellyfin_id="old", title="Old", type="Movie", last_played_at=datetime.utcnow() - timedelta(days=200))
            never = MediaMetadata(jellyfin_id="never", title="Never", type="Movie", last_played_at=None)
            session.add_all([recent, old, never])
            await session.commit()

        janitor = LibraryJanitor(session_factory)
        result = await janitor.get_cold_media(months=6)

        assert len(result) == 2
        titles = [r["title"] for r in result]
        assert "Old" in titles
        assert "Never" in titles

    @pytest.mark.asyncio
    async def test_get_cold_count_correct(self, session_factory):
        """Test get_cold_count returns correct number."""
        async with session_factory() as session:
            media = [
                MediaMetadata(jellyfin_id=f"m{i}", title=f"Media {i}", type="Movie", last_played_at=None if i < 3 else datetime.utcnow() - timedelta(days=1))
                for i in range(5)
            ]
            session.add_all(media)
            await session.commit()

        janitor = LibraryJanitor(session_factory)
        result = await janitor.get_cold_count(months=6)

        assert result == 3