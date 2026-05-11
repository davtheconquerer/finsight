import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import async_session_factory, init_db
from app.routers import janitor, media, newsletter, pages, sessions
from app.services.jellyfin_client import JellyfinClient
from app.services.newsletter import NewsletterGenerator, get_week_range
from app.services.watchdog import Watchdog

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

jellyfin_client: JellyfinClient | None = None
watchdog: Watchdog | None = None
newsletter_scheduler: asyncio.Task | None = None


async def _check_weekly_digest():
    """Auto-generate the weekly digest if it doesn't exist yet."""
    try:
        now = datetime.utcnow()
        if now.weekday() != 0:
            return
        week_start, week_end = get_week_range(now)
        gen = NewsletterGenerator(async_session_factory)
        existing = await gen.get_latest()
        if existing and existing.week_start == week_start.date():
            return
        await gen.generate(week_start, week_end)
        logger.info("Auto-generated weekly digest")
    except Exception as e:
        logger.warning("Weekly digest generation failed: %s", e)


async def _newsletter_loop():
    """Check hourly if a weekly digest needs generating."""
    while True:
        await _check_weekly_digest()
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global jellyfin_client, watchdog, newsletter_scheduler

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

    newsletter_scheduler = asyncio.create_task(_newsletter_loop())
    logger.info("Newsletter scheduler started")

    yield

    if newsletter_scheduler:
        newsletter_scheduler.cancel()
        try:
            await newsletter_scheduler
        except asyncio.CancelledError:
            pass
    if watchdog:
        await watchdog.stop()
    logger.info("FinSight shutdown complete.")


app = FastAPI(title="FinSight", version="0.1.0", lifespan=lifespan)

Path("app/static").mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)
app.include_router(newsletter.router)
app.include_router(sessions.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(janitor.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "jellyfin": settings.jellyfin_url}
