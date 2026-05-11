import logging

import httpx

logger = logging.getLogger(__name__)


class JellyfinError(Exception):
    pass


class AuthenticationError(JellyfinError):
    pass


class JellyfinClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-Emby-Token": self.api_key},
            timeout=30,
        )

    async def validate(self) -> dict:
        try:
            resp = await self.client.get("/System/Info")
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError(
                    "Invalid Jellyfin API key — check JELLYFIN_API_KEY"
                )
            raise JellyfinError(f"Jellyfin API error: {e}")
        except httpx.RequestError as e:
            raise JellyfinError(
                f"Cannot reach Jellyfin at {self.base_url}: {e}"
            )

        info = resp.json()
        logger.info(
            "Connected to Jellyfin %s (%s)",
            info.get("Version"),
            info.get("ServerName"),
        )
        return info

    async def get_sessions(self) -> list[dict]:
        resp = await self.client.get("/Sessions")
        resp.raise_for_status()
        return resp.json()

    async def get_users(self) -> list[dict]:
        resp = await self.client.get("/Users")
        resp.raise_for_status()
        return resp.json()

    async def get_items(self, limit: int = 100, start_index: int = 0) -> list[dict]:
        params = {
            "Recursive": "true",
            "IncludeItemTypes": "Movie,Episode",
            "Fields": "Path,Genres,CommunityRating,DateCreated,ProductionYear,RuntimeTicks",
            "Limit": limit,
            "StartIndex": start_index,
        }
        resp = await self.client.get("/Items", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("Items", [])

    async def get_total_item_count(self) -> int:
        params = {
            "Recursive": "true",
            "IncludeItemTypes": "Movie,Episode",
            "Limit": 1,
        }
        resp = await self.client.get("/Items", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("TotalRecordCount", 0)

    async def close(self):
        await self.client.aclose()
