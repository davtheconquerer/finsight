import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.media import MediaMetadata
from app.models.playback import PlaybackSession
from app.models.user import User

router = APIRouter()


@router.get("/media/{item_id}")
async def get_media_detail(item_id: int, db: AsyncSession = Depends(get_db)):
    media = await db.get(MediaMetadata, item_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    total_plays = (
        await db.execute(
            select(func.count(PlaybackSession.id)).where(
                PlaybackSession.media_id == media.id,
                PlaybackSession.ended_at.isnot(None),
            )
        )
    ).scalar()

    transcode_count = (
        await db.execute(
            select(func.count(PlaybackSession.id)).where(
                PlaybackSession.media_id == media.id,
                PlaybackSession.is_transcoding.is_(True),
                PlaybackSession.ended_at.isnot(None),
            )
        )
    ).scalar()

    sessions_result = await db.execute(
        select(PlaybackSession)
        .where(
            PlaybackSession.media_id == media.id,
            PlaybackSession.ended_at.isnot(None),
        )
        .order_by(desc(PlaybackSession.ended_at))
        .limit(50)
    )

    play_history = []
    for s in sessions_result.scalars().all():
        user = await db.get(User, s.user_id)
        play_history.append(
            {
                "user": user.name if user else "Unknown",
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "duration": s.duration_seconds,
                "play_method": s.play_method,
                "is_transcoding": s.is_transcoding,
                "transcode_reason": s.transcode_reason,
                "device": s.device_name,
            }
        )

    genres = json.loads(media.genres) if media.genres else []

    return {
        "id": media.id,
        "jellyfin_id": media.jellyfin_id,
        "title": media.title,
        "type": media.type,
        "year": media.year,
        "genres": genres,
        "runtime_ticks": media.runtime_ticks,
        "community_rating": media.community_rating,
        "path": media.path,
        "added_at": media.added_at.isoformat() if media.added_at else None,
        "total_plays": total_plays,
        "transcode_count": transcode_count,
        "transcode_ratio": round(transcode_count / total_plays, 2)
        if total_plays
        else 0,
        "play_history": play_history,
    }


@router.get("/library/stats")
async def get_library_stats(db: AsyncSession = Depends(get_db)):
    type_counts = await db.execute(
        select(MediaMetadata.type, func.count(MediaMetadata.id).label("count"))
        .group_by(MediaMetadata.type)
        .order_by(desc("count"))
    )

    return {
        "type_breakdown": [
            {"type": row.type, "count": row.count} for row in type_counts
        ],
    }
