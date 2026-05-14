from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.media import MediaMetadata
from app.models.playback import PlaybackSession
from app.models.user import User

router = APIRouter()


@router.get("/sessions/active")
async def get_active_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PlaybackSession)
        .where(PlaybackSession.ended_at.is_(None))
        .where(PlaybackSession.media_id.isnot(None))
        .order_by(PlaybackSession.started_at.desc())
    )
    sessions = result.scalars().all()
    output = []
    for s in sessions:
        user = await db.get(User, s.user_id)
        media = await db.get(MediaMetadata, s.media_id) if s.media_id else None
        output.append(
            {
                "id": s.id,
                "session_id": s.jellyfin_session_id,
                "user": user.name if user else "Unknown",
                "media": media.title if media else "Unknown",
                "media_type": media.type if media else None,
                "device": s.device_name,
                "client": s.client_name,
                "is_transcoding": s.is_transcoding,
                "transcode_reason": s.transcode_reason,
                "play_method": s.play_method,
                "started_at": s.started_at.isoformat() if s.started_at else None,
            }
        )
    return output


@router.get("/sessions/history")
async def get_session_history(
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    user_name: str | None = Query(None, alias="user"),
    media_title: str | None = Query(None, alias="media"),
    db: AsyncSession = Depends(get_db),
):
    q = select(PlaybackSession).where(PlaybackSession.ended_at.isnot(None))

    if user_name:
        subq = select(User.id).where(User.name.ilike(f"%{user_name}%"))
        q = q.where(PlaybackSession.user_id.in_(subq))
    if media_title:
        subq = select(MediaMetadata.id).where(
            MediaMetadata.title.ilike(f"%{media_title}%")
        )
        q = q.where(PlaybackSession.media_id.in_(subq))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.order_by(desc(PlaybackSession.ended_at))
    q = q.offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    sessions = result.scalars().all()

    output = []
    for s in sessions:
        user = await db.get(User, s.user_id)
        media = await db.get(MediaMetadata, s.media_id) if s.media_id else None
        output.append(
            {
                "id": s.id,
                "user": user.name if user else "Unknown",
                "media": media.title if media else "Unknown",
                "media_id": media.id if media else None,
                "type": media.type if media else None,
                "duration": s.duration_seconds,
                "device": s.device_name,
                "play_method": s.play_method,
                "is_transcoding": s.is_transcoding,
                "transcode_reason": s.transcode_reason,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            }
        )

    return {"items": output, "total": total, "page": page, "per_page": limit}


@router.get("/stats/overview")
async def get_stats_overview(db: AsyncSession = Depends(get_db)):
    user_count = (await db.execute(select(func.count(User.id)))).scalar()
    media_count = (await db.execute(select(func.count(MediaMetadata.id)))).scalar()
    movie_count = (
        await db.execute(
            select(func.count(MediaMetadata.id)).where(MediaMetadata.type == "Movie")
        )
    ).scalar()
    episode_count = (
        await db.execute(
            select(func.count(MediaMetadata.id)).where(MediaMetadata.type == "Episode")
        )
    ).scalar()

    episodes = (
        await db.execute(
            select(MediaMetadata.title).where(MediaMetadata.type == "Episode")
        )
    ).scalars().all()

    show_titles = set()
    for title in episodes:
        parts = title.split(" - S")
        if parts[0]:
            show_titles.add(parts[0])
    show_count = len(show_titles)

    active_count = (
        await db.execute(
            select(func.count(PlaybackSession.id)).where(
                PlaybackSession.ended_at.is_(None),
                PlaybackSession.media_id.isnot(None),
            )
        )
    ).scalar()
    return {
        "total_users": user_count,
        "total_media": media_count,
        "total_movies": movie_count,
        "total_shows": show_count,
        "total_episodes": episode_count,
        "active_sessions": active_count,
    }


@router.get("/stats/plays-over-time")
async def get_plays_over_time(
    days: int = Query(30, ge=1, le=365), db: AsyncSession = Depends(get_db)
):
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(PlaybackSession.ended_at).label("date"),
            func.count(PlaybackSession.id).label("plays"),
        )
        .where(
            PlaybackSession.ended_at.isnot(None),
            PlaybackSession.ended_at >= since,
        )
        .group_by(func.date(PlaybackSession.ended_at))
        .order_by("date")
    )
    return [{"date": str(row.date), "plays": row.plays} for row in result]


@router.get("/stats/top-media")
async def get_top_media(
    limit: int = Query(10, ge=1, le=50), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(
            MediaMetadata.id,
            MediaMetadata.title,
            MediaMetadata.type,
            func.count(PlaybackSession.id).label("plays"),
        )
        .join(PlaybackSession, PlaybackSession.media_id == MediaMetadata.id)
        .where(PlaybackSession.ended_at.isnot(None))
        .group_by(MediaMetadata.id)
        .order_by(desc("plays"))
        .limit(limit)
    )
    return [
        {"id": row.id, "title": row.title, "type": row.type, "plays": row.plays}
        for row in result
    ]


@router.get("/stats/transcode-breakdown")
async def get_transcode_breakdown(db: AsyncSession = Depends(get_db)):
    active = await db.execute(
        select(
            User.name,
            PlaybackSession.transcode_reason,
            PlaybackSession.device_name,
            PlaybackSession.client_name,
            MediaMetadata.title,
        )
        .join(User, PlaybackSession.user_id == User.id)
        .outerjoin(MediaMetadata, PlaybackSession.media_id == MediaMetadata.id)
        .where(
            PlaybackSession.ended_at.is_(None),
            PlaybackSession.is_transcoding.is_(True),
        )
    )

    historical_raw = await db.execute(
        select(
            PlaybackSession.transcode_reason,
            func.count(PlaybackSession.id).label("count"),
        )
        .where(
            PlaybackSession.is_transcoding.is_(True),
            PlaybackSession.transcode_reason.isnot(None),
        )
        .group_by(PlaybackSession.transcode_reason)
        .order_by(desc("count"))
    )

    user_raw = await db.execute(
        select(
            User.name,
            func.count(PlaybackSession.id).label("count"),
        )
        .join(User, PlaybackSession.user_id == User.id)
        .where(
            PlaybackSession.is_transcoding.is_(True),
            PlaybackSession.ended_at.isnot(None),
        )
        .group_by(User.name)
        .order_by(desc("count"))
        .limit(10)
    )

    return {
        "active": [
            {
                "user": row.name,
                "reason": row.transcode_reason,
                "device": row.device_name,
                "client": row.client_name,
                "media": row.title,
            }
            for row in active
        ],
        "reason_breakdown": [
            {"reason": row.transcode_reason, "count": row.count}
            for row in historical_raw
        ],
        "top_transcoders": [
            {"user": row.name, "count": row.count} for row in user_raw
        ],
    }
