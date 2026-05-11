import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.jellyfin_client import JellyfinClient, JellyfinError, AuthenticationError


class TestJellyfinClient:
    """Tests for JellyfinClient service."""

    @pytest.fixture
    def mock_http_response(self):
        """Create mock HTTP response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.raise_for_status = MagicMock()
        return response

    @pytest.mark.asyncio
    async def test_validate_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "Version": "10.8.0",
            "ServerName": "Test Server",
            "Id": "server-123",
        }

        client = JellyfinClient("http://localhost:8096", "test-api-key")
        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await client.validate()

        assert result["Version"] == "10.8.0"
        assert result["ServerName"] == "Test Server"

    @pytest.mark.asyncio
    async def test_validate_auth_failure(self):
        error_response = MagicMock()
        error_response.status_code = 401
        error_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
            "401",
            request=MagicMock(),
            response=error_response,
        ))

        client = JellyfinClient("http://localhost:8096", "invalid-key")
        with patch.object(client.client, "get", new=AsyncMock(side_effect=httpx.HTTPStatusError(
            "401", request=MagicMock(), response=error_response
        ))):
            with pytest.raises(AuthenticationError, match="Invalid Jellyfin API key"):
                await client.validate()

    @pytest.mark.asyncio
    async def test_validate_connection_error(self):
        client = JellyfinClient("http://localhost:8096", "test-api-key")
        with patch.object(client.client, "get", new=AsyncMock(side_effect=httpx.RequestError("Connection refused"))):
            with pytest.raises(JellyfinError, match="Cannot reach Jellyfin"):
                await client.validate()

    @pytest.mark.asyncio
    async def test_get_sessions(self):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"Id": "session-1", "UserId": "user-1", "NowPlayingItem": {"Name": "Test Movie"}},
        ]

        client = JellyfinClient("http://localhost:8096", "test-api-key")
        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await client.get_sessions()

        assert len(result) == 1
        assert result[0]["Id"] == "session-1"

    @pytest.mark.asyncio
    async def test_get_users(self):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"Id": "user-1", "Name": "Alice"},
            {"Id": "user-2", "Name": "Bob"},
        ]

        client = JellyfinClient("http://localhost:8096", "test-api-key")
        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await client.get_users()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_items(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Items": [{"Id": "item-1"}, {"Id": "item-2"}],
            "TotalRecordCount": 2,
        }

        client = JellyfinClient("http://localhost:8096", "test-api-key")
        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await client.get_items(limit=10, start_index=0)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_total_item_count(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"TotalRecordCount": 100}

        client = JellyfinClient("http://localhost:8096", "test-api-key")
        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await client.get_total_item_count()

        assert result == 100

    @pytest.mark.asyncio
    async def test_close(self):
        client = JellyfinClient("http://localhost:8096", "test-api-key")
        client.client.aclose = AsyncMock()
        await client.close()
        client.client.aclose.assert_called_once()