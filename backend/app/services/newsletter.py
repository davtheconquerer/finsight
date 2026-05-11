import logging
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import Date, cast, desc, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.media import MediaMetadata
from app.models.newsletter import NewsletterDigest
from app.models.playback import PlaybackSession
from app.models.user import User

logger = logging.getLogger(__name__)

TEMPLATE_DIR = "app/templates/email"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def get_week_range(dt: datetime | None = None) -> tuple[datetime, datetime]:
    if dt is None:
        dt = datetime.utcnow()
    monday = dt - timedelta(days=dt.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=7)
    return monday, sunday


class NewsletterGenerator:
    def __init__(self, db_factory: async_sessionmaker):
        self.db_factory = db_factory
        self.jinja = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=True,
        )

    async def generate(self, week_start: datetime, week_end: datetime) -> NewsletterDigest:
        data = await self._aggregate(week_start, week_end)
        html = self._render_html(data, week_start, week_end)

        async with self.db_factory() as db:
            existing = await db.execute(
                select(NewsletterDigest).where(
                    NewsletterDigest.week_start == week_start.date()
                )
            )
            digest = existing.scalar_one_or_none()
            if digest:
                digest.html_content = html
                digest.generated_at = datetime.utcnow()
            else:
                digest = NewsletterDigest(
                    week_start=week_start.date(),
                    week_end=week_end.date(),
                    html_content=html,
                )
                db.add(digest)
            await db.commit()
            await db.refresh(digest)
            logger.info("Newsletter generated for week %s — %s", week_start.date(), week_end.date())
            return digest

    async def get_latest(self) -> NewsletterDigest | None:
        async with self.db_factory() as db:
            result = await db.execute(
                select(NewsletterDigest).order_by(desc(NewsletterDigest.week_start)).limit(1)
            )
            return result.scalar_one_or_none()

    async def _aggregate(self, week_start: datetime, week_end: datetime) -> dict:
        async with self.db_factory() as db:
            new_media_result = await db.execute(
                select(MediaMetadata)
                .where(MediaMetadata.added_at >= week_start)
                .order_by(desc(MediaMetadata.added_at))
                .limit(20)
            )
            new_media = [
                {
                    "title": m.title,
                    "type": m.type,
                    "year": m.year,
                    "added_at": m.added_at.isoformat() if m.added_at else None,
                }
                for m in new_media_result.scalars().all()
            ]

            total_plays = (
                await db.execute(
                    select(func.count(PlaybackSession.id)).where(
                        PlaybackSession.ended_at >= week_start,
                        PlaybackSession.ended_at < week_end,
                        PlaybackSession.ended_at.isnot(None),
                    )
                )
            ).scalar() or 0

            total_transcodes = (
                await db.execute(
                    select(func.count(PlaybackSession.id)).where(
                        PlaybackSession.ended_at >= week_start,
                        PlaybackSession.ended_at < week_end,
                        PlaybackSession.ended_at.isnot(None),
                        PlaybackSession.is_transcoding.is_(True),
                    )
                )
            ).scalar() or 0

            plays_per_day_result = await db.execute(
                select(
                    cast(PlaybackSession.ended_at, Date).label("date"),
                    func.count(PlaybackSession.id).label("plays"),
                )
                .where(
                    PlaybackSession.ended_at >= week_start,
                    PlaybackSession.ended_at < week_end,
                    PlaybackSession.ended_at.isnot(None),
                )
                .group_by(cast(PlaybackSession.ended_at, Date))
                .order_by("date")
            )

            day_map = {row.date: row.plays for row in plays_per_day_result}
            plays_per_day = []
            for i in range(7):
                d = (week_start + timedelta(days=i)).date()
                plays_per_day.append({"date": WEEKDAYS[i], "plays": day_map.get(d, 0)})

            top_media_result = await db.execute(
                select(
                    MediaMetadata.title,
                    MediaMetadata.type,
                    func.count(PlaybackSession.id).label("plays"),
                )
                .join(PlaybackSession, PlaybackSession.media_id == MediaMetadata.id)
                .where(
                    PlaybackSession.ended_at >= week_start,
                    PlaybackSession.ended_at < week_end,
                    PlaybackSession.ended_at.isnot(None),
                )
                .group_by(MediaMetadata.id)
                .order_by(desc("plays"))
                .limit(10)
            )
            top_media = [
                {"title": row.title, "type": row.type, "plays": row.plays}
                for row in top_media_result
            ]

            top_users_result = await db.execute(
                select(
                    User.name,
                    func.count(PlaybackSession.id).label("plays"),
                )
                .join(User, PlaybackSession.user_id == User.id)
                .where(
                    PlaybackSession.ended_at >= week_start,
                    PlaybackSession.ended_at < week_end,
                    PlaybackSession.ended_at.isnot(None),
                )
                .group_by(User.name)
                .order_by(desc("plays"))
                .limit(5)
            )
            top_users = [
                {"name": row.name, "plays": row.plays}
                for row in top_users_result
            ]

            genre_raw = await db.execute(
                select(
                    MediaMetadata.genres,
                )
                .join(MediaMetadata, PlaybackSession.media_id == MediaMetadata.id)
                .where(
                    PlaybackSession.ended_at >= week_start,
                    PlaybackSession.ended_at < week_end,
                    PlaybackSession.ended_at.isnot(None),
                    MediaMetadata.genres.isnot(None),
                )
            )

            import json
            genre_counts: dict[str, int] = {}
            for row in genre_raw:
                try:
                    genres_list = json.loads(row.genres)
                    for g in genres_list:
                        genre_counts[g] = genre_counts.get(g, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass
            sorted_genres = sorted(genre_counts.items(), key=lambda x: -x[1])[:8]
            genre_breakdown = [{"name": g, "count": c} for g, c in sorted_genres]

            return {
                "total_plays": total_plays,
                "total_transcodes": total_transcodes,
                "new_media": new_media,
                "top_media": top_media,
                "top_users": top_users,
                "plays_per_day": plays_per_day,
                "genre_breakdown": genre_breakdown,
            }

    def _render_html(self, data: dict, week_start: datetime, week_end: datetime) -> str:
        template = self.jinja.get_template("digest.html")
        return template.render(
            week_start=week_start.strftime("%b %d"),
            week_end=week_end.strftime("%b %d, %Y"),
            total_plays=data["total_plays"],
            total_transcodes=data["total_transcodes"],
            new_media=data["new_media"],
            top_media=data["top_media"],
            top_users=data["top_users"],
            plays_per_day=data["plays_per_day"],
            genre_breakdown=data["genre_breakdown"],
        )
