import logging
from datetime import datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.media import MediaMetadata
from app.models.playback import PlaybackSession
from app.models.user import User

logger = logging.getLogger(__name__)


class LibraryJanitor:
    def __init__(self, db_factory: async_sessionmaker):
        self.db_factory = db_factory

    async def get_cold_media(self, months: int = 6) -> list[dict]:
        cutoff = datetime.utcnow() - timedelta(days=months * 30)
        async with self.db_factory() as db:
            result = await db.execute(
                select(MediaMetadata)
                .where(
                    MediaMetadata.last_played_at.is_(None)
                    | (MediaMetadata.last_played_at < cutoff),
                )
                .order_by(MediaMetadata.last_played_at.asc(nullsfirst=True))
                .limit(100)
            )
            items = []
            for m in result.scalars().all():
                if m.last_played_at:
                    days = (datetime.utcnow() - m.last_played_at).days
                else:
                    days = None
                items.append(
                    {
                        "id": m.id,
                        "title": m.title,
                        "type": m.type,
                        "year": m.year,
                        "play_count": m.play_count,
                        "last_played_at": m.last_played_at.isoformat()
                        if m.last_played_at
                        else None,
                        "days_since_played": days,
                        "added_at": m.added_at.isoformat() if m.added_at else None,
                        "size_bytes": m.size_bytes,
                        "runtime_ticks": m.runtime_ticks,
                    }
                )
            return items

    async def get_cold_count(self, months: int = 6) -> int:
        cutoff = datetime.utcnow() - timedelta(days=months * 30)
        async with self.db_factory() as db:
            return (
                await db.execute(
                    select(func.count(MediaMetadata.id)).where(
                        MediaMetadata.last_played_at.is_(None)
                        | (MediaMetadata.last_played_at < cutoff),
                    )
                )
            ).scalar() or 0

    async def get_user_stats(self) -> list[dict]:
        async with self.db_factory() as db:
            users_raw = await db.execute(
                select(
                    User.id,
                    User.name,
                    User.last_seen_at,
                    User.play_count,
                    func.count(PlaybackSession.id).label("total_plays"),
                    func.sum(
                        PlaybackSession.is_transcoding.cast(
                            type_=__import__("sqlalchemy").Integer  # type: ignore
                        )
                    ).label("transcodes"),
                )
                .outerjoin(
                    PlaybackSession, PlaybackSession.user_id == User.id
                )
                .group_by(User.id)
                .order_by(desc("total_plays"))
            )

            output = []
            for row in users_raw:
                device_result = await db.execute(
                    select(
                        PlaybackSession.device_name,
                        func.count(PlaybackSession.id).label("count"),
                    )
                    .where(
                        PlaybackSession.user_id == row.id,
                        PlaybackSession.device_name.isnot(None),
                    )
                    .group_by(PlaybackSession.device_name)
                    .order_by(desc("count"))
                    .limit(5)
                )
                devices = [
                    {"name": d.device_name, "count": d.count}
                    for d in device_result
                ]

                output.append(
                    {
                        "id": row.id,
                        "name": row.name,
                        "last_seen": row.last_seen_at.isoformat()
                        if row.last_seen_at
                        else None,
                        "play_count": row.play_count,
                        "total_plays": row.total_plays or 0,
                        "transcodes": row.transcodes or 0,
                        "transcode_ratio": round(
                            (row.transcodes or 0) / max(row.total_plays or 0, 1), 2
                        ),
                        "devices": devices,
                    }
                )
            return output
