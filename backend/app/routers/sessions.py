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
    limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PlaybackSession)
        .where(PlaybackSession.ended_at.isnot(None))
        .order_by(desc(PlaybackSession.ended_at))
        .limit(limit)
    )
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
                "type": media.type if media else None,
                "duration": s.duration_seconds,
                "device": s.device_name,
                "play_method": s.play_method,
                "is_transcoding": s.is_transcoding,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            }
        )
    return output


@router.get("/stats/overview")
async def get_stats_overview(db: AsyncSession = Depends(get_db)):
    user_count = (await db.execute(select(func.count(User.id)))).scalar()
    media_count = (await db.execute(select(func.count(MediaMetadata.id)))).scalar()
    active_count = (
        await db.execute(
            select(func.count(PlaybackSession.id)).where(
                PlaybackSession.ended_at.is_(None)
            )
        )
    ).scalar()
    return {
        "total_users": user_count,
        "total_media": media_count,
        "active_sessions": active_count,
    }
