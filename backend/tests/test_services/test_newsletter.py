import pytest
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.newsletter import NewsletterGenerator, get_week_range


class TestNewsletterGenerator:
    """Tests for NewsletterGenerator service."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session that works as async context manager."""
        async def _create_session():
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            return mock_db

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=_create_session)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        return mock_cm

    @pytest.mark.asyncio
    async def test_get_week_range_current(self):
        """Test get_week_range returns correct Monday-Sunday range."""
        dt = datetime(2026, 1, 15, 12, 0, 0)  # Thursday
        monday, sunday = get_week_range(dt)

        assert monday.weekday() == 0
        assert sunday - monday == timedelta(days=7)

    @pytest.mark.asyncio
    async def test_get_week_range_none(self):
        """Test get_week_range with None returns current week."""
        monday, sunday = get_week_range(None)

        assert monday.weekday() == 0
        assert sunday - monday == timedelta(days=7)

    def test_render_html(self):
        """Test _render_html produces valid HTML."""
        mock_factory = AsyncMock()
        generator = NewsletterGenerator(mock_factory)

        data = {
            "total_plays": 10,
            "total_transcodes": 2,
            "new_media": [{"title": "Movie 1", "type": "Movie"}],
            "top_media": [{"title": "Movie 1", "type": "Movie", "plays": 5}],
            "top_users": [{"name": "Alice", "plays": 3}],
            "plays_per_day": [{"date": "Mon", "plays": 1}],
            "genre_breakdown": [{"name": "Action", "count": 5}],
        }

        week_start = datetime(2026, 1, 13)
        week_end = datetime(2026, 1, 20)

        html = generator._render_html(data, week_start, week_end)

        assert "Jan 13" in html
        assert "Jan 20, 2026" in html