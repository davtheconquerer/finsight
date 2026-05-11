import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.library_janitor import LibraryJanitor


class TestLibraryJanitor:
    """Tests for LibraryJanitor service."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session that works as async context manager."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        return mock_session

    @pytest.fixture
    def mock_db_factory(self, mock_db_session):
        """Create mock session factory that returns an async context manager."""
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db_session)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_factory = MagicMock()
        mock_factory.return_value = mock_cm
        return mock_factory

    @pytest.mark.asyncio
    async def test_get_cold_count(self, mock_db_factory):
        """Test get_cold_count returns correct count."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db_factory.return_value.__aenter__.return_value.execute = AsyncMock(return_value=mock_result)

        janitor = LibraryJanitor(mock_db_factory)
        result = await janitor.get_cold_count(months=6)

        assert result == 5

    @pytest.mark.asyncio
    async def test_get_user_stats_empty(self, mock_db_factory):
        """Test get_user_stats returns empty list when no users."""
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_db_factory.return_value.__aenter__.return_value.execute = AsyncMock(return_value=mock_result)

        janitor = LibraryJanitor(mock_db_factory)
        result = await janitor.get_user_stats()

        assert result == []