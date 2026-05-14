import asyncio
import json
import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.media import MediaMetadata
from app.models.playback import PlaybackSession
from app.models.user import User
from app.services.jellyfin_client import JellyfinClient

logger = logging.getLogger(__name__)


class Watchdog:
    def __init__(
        self, client: JellyfinClient, db_factory: async_sessionmaker, poll_interval: int
    ):
        self.client = client
        self.db_factory = db_factory
        self.poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("Watchdog started (interval=%ds)", self.poll_interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.client.close()
        logger.info("Watchdog stopped")

    async def _run(self):
        cycle = 0
        while self._running:
            try:
                await self._poll_sessions()
                if cycle % 10 == 0:
                    await self._poll_users()
                if cycle % 60 == 0:
                    await self._poll_library()
                cycle += 1
            except Exception as e:
                logger.error("Watchdog cycle error: %s", e)
            await asyncio.sleep(self.poll_interval)

    async def _ensure_user(self, db, jellyfin_id: str, name: str) -> User:
        result = await db.execute(select(User).where(User.jellyfin_id == jellyfin_id))
        user = result.scalar_one_or_none()
        now = datetime.utcnow()
        if user:
            user.name = name
            user.last_seen_at = now
        else:
            user = User(
                jellyfin_id=jellyfin_id, name=name, last_seen_at=now
            )
            db.add(user)
        return user

    async def _ensure_media(self, db, item: dict) -> MediaMetadata | None:
        item_id = item.get("Id")
        if not item_id:
            return None
        result = await db.execute(
            select(MediaMetadata).where(MediaMetadata.jellyfin_id == item_id)
        )
        media = result.scalar_one_or_none()
        genres = item.get("Genres", [])
        if media:
            media.title = item.get("Name", media.title)
            media.type = item.get("Type", media.type)
            media.year = item.get("ProductionYear", media.year)
            if genres:
                media.genres = json.dumps(genres)
            media.runtime_ticks = item.get("RunTimeTicks", media.runtime_ticks)
            media.community_rating = item.get(
                "CommunityRating", media.community_rating
            )
            media.path = item.get("Path", media.path)
        else:
            media = MediaMetadata(
                jellyfin_id=item_id,
                title=item.get("Name", "Unknown"),
                type=item.get("Type", "Unknown"),
                year=item.get("ProductionYear"),
                genres=json.dumps(genres) if genres else None,
                runtime_ticks=item.get("RunTimeTicks"),
                community_rating=item.get("CommunityRating"),
                path=item.get("Path"),
            )
            db.add(media)
        return media

    async def _poll_sessions(self):
        try:
            sessions = await self.client.get_sessions()
        except Exception as e:
            logger.warning("Failed to poll sessions: %s", e)
            return

        active_ids: set[str] = set()
        async with self.db_factory() as db:
            for s in sessions:
                session_id = s.get("Id")
                user_id = s.get("UserId")
                if not session_id or not user_id:
                    continue

                user = await self._ensure_user(
                    db, user_id, s.get("UserName", "Unknown")
                )

                now_playing = s.get("NowPlayingItem")
                media_id = None
                if now_playing:
                    media = await self._ensure_media(db, now_playing)
                    if media:
                        media_id = media.id

                result = await db.execute(
                    select(PlaybackSession).where(
                        PlaybackSession.jellyfin_session_id == session_id,
                        PlaybackSession.ended_at.is_(None),
                    )
                )
                existing = result.scalar_one_or_none()

                transcode_info = s.get("TranscodingInfo") or {}
                transcode_reasons = transcode_info.get("TranscodeReasons", [])

                if not media_id:
                    # Client is connected but not playing anything
                    if existing:
                        # Close any previously active session
                        existing.ended_at = datetime.utcnow()
                        if existing.started_at:
                            existing.duration_seconds = int(
                                (datetime.utcnow() - existing.started_at).total_seconds()
                            )
                        # Update the associated media's last_played_at
                        if existing.media_id:
                            m = await db.get(MediaMetadata, existing.media_id)
                            if m:
                                m.last_played_at = existing.ended_at
                    continue

                active_ids.add(session_id)

                if existing:
                    existing.media_id = media_id
                    existing.is_transcoding = bool(transcode_info)
                    existing.transcode_reason = (
                        ", ".join(transcode_reasons) if transcode_reasons else None
                    )
                    existing.play_method = s.get("PlayState", {}).get("PlayMethod", existing.play_method)
                    existing.device_name = s.get("DeviceName", existing.device_name)
                    existing.client_name = s.get("Client", existing.client_name)
                else:
                    session = PlaybackSession(
                        jellyfin_session_id=session_id,
                        user_id=user.id,
                        media_id=media_id,
                        started_at=datetime.utcnow(),
                        device_name=s.get("DeviceName"),
                        client_name=s.get("Client"),
                        is_transcoding=bool(transcode_info),
                        transcode_reason=", ".join(transcode_reasons)
                        if transcode_reasons
                        else None,
                        play_method=s.get("PlayState", {}).get("PlayMethod"),
                        ip_address=s.get("RemoteEndPoint"),
                    )
                    db.add(session)

            if active_ids:
                stmt = (
                    update(PlaybackSession)
                    .where(
                        PlaybackSession.ended_at.is_(None),
                        ~PlaybackSession.jellyfin_session_id.in_(active_ids),
                    )
                    .values(ended_at=datetime.utcnow())
                )
                await db.execute(stmt)

            await db.commit()

    async def _poll_users(self):
        try:
            users = await self.client.get_users()
        except Exception as e:
            logger.warning("Failed to poll users: %s", e)
            return

        async with self.db_factory() as db:
            for u in users:
                uid = u.get("Id")
                if not uid:
                    continue
                await self._ensure_user(db, uid, u.get("Name", "Unknown"))
            await db.commit()

    async def _poll_library(self):
        try:
            total = await self.client.get_total_item_count()
        except Exception as e:
            logger.warning("Failed to get library count: %s", e)
            return

        async with self.db_factory() as db:
            for offset in range(0, total, 100):
                try:
                    items = await self.client.get_items(
                        limit=100, start_index=offset
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to poll library page %d: %s", offset, e
                    )
                    continue
                for item in items:
                    await self._ensure_media(db, item)
            await db.commit()
        logger.info("Library poll complete (%d items)", total)