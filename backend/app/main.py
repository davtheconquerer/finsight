import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import async_session_factory, init_db
from app.routers import pages, sessions
from app.services.jellyfin_client import JellyfinClient
from app.services.watchdog import Watchdog

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

jellyfin_client: JellyfinClient | None = None
watchdog: Watchdog | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global jellyfin_client, watchdog

    logger.info("Starting FinSight...")
    await init_db()

    jellyfin_client = JellyfinClient(
        settings.jellyfin_url, settings.jellyfin_api_key
    )
    info = await jellyfin_client.validate()
    logger.info(
        "Connected to Jellyfin %s (%s)",
        info.get("Version"),
        info.get("ServerName"),
    )

    watchdog = Watchdog(
        jellyfin_client, async_session_factory, settings.poll_interval
    )
    await watchdog.start()

    yield

    if watchdog:
        await watchdog.stop()
    logger.info("FinSight shutdown complete.")


app = FastAPI(title="FinSight", version="0.1.0", lifespan=lifespan)

Path("app/static").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)
app.include_router(sessions.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "jellyfin": settings.jellyfin_url}
