import csv
import io
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory, get_db
from app.models.media import MediaMetadata
from app.models.playback import PlaybackSession
from app.models.user import User
from app.services.library_janitor import LibraryJanitor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/library/cold-media")
async def get_cold_media(
    months: int = Query(settings.cold_media_months, ge=1, le=120),
):
    janitor = LibraryJanitor(async_session_factory)
    items = await janitor.get_cold_media(months)
    return {"items": items, "count": len(items), "threshold_months": months}


@router.get("/library/cold-media/export")
async def export_cold_media_csv(
    months: int = Query(settings.cold_media_months, ge=1, le=120),
):
    janitor = LibraryJanitor(async_session_factory)
    items = await janitor.get_cold_media(months)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Title", "Type", "Year", "Play Count", "Days Since Played", "Runtime (min)"]
    )
    for item in items:
        runtime = (
            round(item["runtime_ticks"] / 600000000, 1)
            if item["runtime_ticks"]
            else ""
        )
        writer.writerow(
            [
                item["title"],
                item["type"],
                item["year"] or "",
                item["play_count"],
                item["days_since_played"] if item["days_since_played"] is not None else "Never",
                runtime,
            ]
        )

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cold_media.csv"},
    )


@router.get("/users/stats")
async def get_user_stats():
    janitor = LibraryJanitor(async_session_factory)
    users = await janitor.get_user_stats()
    return users


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(db: AsyncSession = Depends(get_db)):
    user_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    media_count = (
        await db.execute(select(func.count(MediaMetadata.id)))
    ).scalar() or 0
    active_count = (
        await db.execute(
            select(func.count(PlaybackSession.id)).where(
                PlaybackSession.ended_at.is_(None)
            )
        )
    ).scalar() or 0

    janitor = LibraryJanitor(async_session_factory)
    cold_count = await janitor.get_cold_count(months=settings.cold_media_months)

    total_plays = (
        await db.execute(
            select(func.count(PlaybackSession.id)).where(
                PlaybackSession.ended_at.isnot(None)
            )
        )
    ).scalar() or 0

    total_transcodes = (
        await db.execute(
            select(func.count(PlaybackSession.id)).where(
                PlaybackSession.ended_at.isnot(None),
                PlaybackSession.is_transcoding.is_(True),
            )
        )
    ).scalar() or 0

    return (
        f"# HELP finsight_total_users Total users tracked\n"
        f"# TYPE finsight_total_users gauge\n"
        f"finsight_total_users {user_count}\n"
        f"# HELP finsight_total_media Total media items in library\n"
        f"# TYPE finsight_total_media gauge\n"
        f"finsight_total_media {media_count}\n"
        f"# HELP finsight_active_sessions Currently active playback sessions\n"
        f"# TYPE finsight_active_sessions gauge\n"
        f"finsight_active_sessions {active_count}\n"
        f"# HELP finsight_cold_media_items Media not played in {settings.cold_media_months} months\n"
        f"# TYPE finsight_cold_media_items gauge\n"
        f"finsight_cold_media_items {cold_count}\n"
        f"# HELP finsight_total_plays All-time playback count\n"
        f"# TYPE finsight_total_plays counter\n"
        f"finsight_total_plays {total_plays}\n"
        f"# HELP finsight_total_transcodes All-time transcode count\n"
        f"# TYPE finsight_total_transcodes counter\n"
        f"finsight_total_transcodes {total_transcodes}\n"
    )
