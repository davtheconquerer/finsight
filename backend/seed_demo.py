"""
Seed the database with realistic demo data so FinSight can run without a real Jellyfin server.

Usage:
    python seed_demo.py
    $env:DEMO_MODE="true"; uvicorn app.main:app --host 0.0.0.0 --port 8500
"""

import asyncio
import json
import random
from datetime import datetime, timedelta

from app.config import settings
from app.database import async_session_factory, engine, init_db
from app.models.base import Base
from app.models.media import MediaMetadata
from app.models.newsletter import NewsletterDigest
from app.models.playback import PlaybackSession
from app.models.user import User

DEMO_USERS = [
    "Alice Johnson",
    "Bob Smith",
    "Carol Davis",
    "Dave Wilson",
    "Eve Martinez",
    "Frank Lee",
]

DEMO_MOVIES = [
    ("The Last Horizon", 2023, "Movie", ["Sci-Fi", "Adventure"], 8.2, 72000000000),
    ("Midnight in Paris", 2022, "Movie", ["Romance", "Comedy"], 7.8, 54000000000),
    ("Crimson Tide Rising", 2024, "Movie", ["Action", "Thriller"], 7.5, 66000000000),
    ("The Garden of Dreams", 2021, "Movie", ["Drama", "Fantasy"], 8.5, 60000000000),
    ("Neon Nights", 2023, "Movie", ["Sci-Fi", "Drama"], 7.9, 69000000000),
    ("The Silent Witness", 2022, "Movie", ["Crime", "Mystery"], 8.1, 51000000000),
    ("Beyond the Veil", 2024, "Movie", ["Horror", "Thriller"], 7.3, 57000000000),
    ("Echoes of War", 2023, "Movie", ["War", "Drama"], 8.4, 78000000000),
    ("The Art of Letting Go", 2022, "Movie", ["Drama", "Romance"], 7.6, 48000000000),
    ("Velocity", 2024, "Movie", ["Action", "Sci-Fi"], 7.7, 63000000000),
    ("Whispers in the Dark", 2023, "Movie", ["Horror", "Mystery"], 7.1, 54000000000),
    ("The Iron Crown", 2022, "Movie", ["Fantasy", "Adventure"], 8.0, 72000000000),
    ("Summer Daze", 2023, "Movie", ["Comedy", "Romance"], 7.4, 45000000000),
    ("Operation Thunderbolt", 2024, "Movie", ["Action", "War"], 7.8, 69000000000),
    ("The Lost Kingdom", 2022, "Movie", ["Animation", "Adventure"], 8.3, 51000000000),
    ("Breaking Point", 2023, "Movie", ["Drama", "Thriller"], 7.9, 60000000000),
    ("Starlight Express", 2024, "Movie", ["Musical", "Drama"], 7.6, 66000000000),
    ("Digital Dreams", 2023, "Movie", ["Sci-Fi", "Drama"], 8.1, 57000000000),
    ("Rising Tides", 2024, "Movie", ["Drama", "Action"], 7.5, 63000000000),
    ("The Perfect Score", 2022, "Movie", ["Comedy", "Sport"], 7.3, 42000000000),
]

DEMO_SHOWS = {
    "Star Voyager": {
        "seasons": {
            1: [
                "Pilot",
                "The New Crew",
                "Dark Matter Rising",
                "First Contact",
                "The Nebula Protocol",
            ],
            2: [
                "Return to Andromeda",
                "The Lost Fleet",
                "Quantum Breach",
                "Empire's Edge",
                "Final Stand",
            ],
        }
    },
    "Criminal Minds: Cyber": {
        "seasons": {
            1: ["The Hack", "Dark Web", "Zero Day", "Phantom", "The Inside Man"],
        }
    },
    "The Crown & The Gun": {
        "seasons": {
            1: ["The Heist", "Royal Blood", "Smoke & Mirrors", "The Traitor", "Reckoning"],
        }
    },
}

TRANSCODE_REASONS = [
    None,
    None,
    None,
    None,
    None,
    None,
    "ContainerNotSupported",
    "AudioCodecNotSupported",
    "VideoCodecNotSupported",
    "SubtitleCodecNotSupported",
    "BitrateExceedsLimit",
    "DirectPlayError",
]

DEVICES = [
    ("Chrome", "Windows PC"),
    ("Safari", "MacBook Pro"),
    ("Jellyfin for Android", "Samsung Galaxy S24"),
    ("Jellyfin for Android TV", "NVIDIA Shield"),
    ("Jellyfin for iOS", "iPhone 15"),
    ("Jellyfin for Roku", "Roku Ultra"),
    ("Jellyfin for Apple TV", "Apple TV 4K"),
    ("Firefox", "Linux Desktop"),
    ("Edge", "Windows Laptop"),
    ("Jellyfin for LG TV", "LG OLED C3"),
]

PHONE_DEVICES = [
    ("Jellyfin for Android", "Samsung Galaxy S24"),
    ("Jellyfin for iOS", "iPhone 15"),
]

NON_PHONE_DEVICES = [
    ("Chrome", "Windows PC"),
    ("Safari", "MacBook Pro"),
    ("Jellyfin for Android TV", "NVIDIA Shield"),
    ("Jellyfin for Roku", "Roku Ultra"),
    ("Jellyfin for Apple TV", "Apple TV 4K"),
    ("Firefox", "Linux Desktop"),
    ("Edge", "Windows Laptop"),
    ("Jellyfin for LG TV", "LG OLED C3"),
]

PLAY_METHODS = ["DirectPlay", "DirectPlay", "DirectPlay", "DirectStream", "Transcode"]


def random_date(days_back: int) -> datetime:
    now = datetime.utcnow()
    offset = random.random() * days_back * 86400
    return now - timedelta(seconds=offset)


def build_media_list() -> list[dict]:
    items = []
    idx = 0
    now = datetime.utcnow()

    never_played_indices = random.sample(range(len(DEMO_MOVIES)), 3)

    for i, (title, year, typ, genres, rating, ticks) in enumerate(DEMO_MOVIES):
        added = now - timedelta(days=random.randint(30, 365))

        if i in never_played_indices:
            last_played = None
        else:
            played = added + timedelta(days=random.randint(1, min(30, (now - added).days)))
            last_played = played

        items.append(
            {
                "jellyfin_id": f"movie-demo-{idx:04d}",
                "title": title,
                "type": typ,
                "year": year,
                "genres": json.dumps(genres),
                "runtime_ticks": ticks,
                "community_rating": rating,
                "play_count": 0,
                "path": f"/media/Movies/{title} ({year})/{title}.mkv",
                "added_at": added,
                "last_played_at": last_played,
                "size_bytes": random.randint(2_000_000_000, 15_000_000_000),
            }
        )
        idx += 1

    for show_name, show_data in DEMO_SHOWS.items():
        for season_num, episodes in show_data["seasons"].items():
            for ep_title in episodes:
                added = now - timedelta(days=random.randint(14, 180))
                ep_num = int(random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
                items.append(
                    {
                        "jellyfin_id": f"episode-demo-{idx:04d}",
                        "title": f"{show_name} - S{season_num:02d}E{ep_num:02d} - {ep_title}",
                        "type": "Episode",
                        "year": 2024,
                        "genres": json.dumps(["Drama"]),
                        "runtime_ticks": random.randint(1200000000, 3600000000),
                        "community_rating": round(random.uniform(6.5, 9.0), 1),
                        "play_count": 0,
                        "path": f"/media/TV/{show_name}/Season {season_num:02d}/{ep_title}.mkv",
                        "added_at": added,
                        "last_played_at": added + timedelta(days=random.randint(0, min(14, (now - added).days)))
                        if random.random() > 0.1
                        else None,
                        "size_bytes": random.randint(300_000_000, 1_500_000_000),
                    }
                )
                idx += 1

    return items


async def seed():
    await init_db()
    print("Database initialized.")

    async with async_session_factory() as db:
        existing = (await db.execute(__import__("sqlalchemy").select(User))).scalars().first()
        if existing:
            print("Database already has data — dropping and recreating...")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

    print("Seeding users...")
    user_objects = []
    for i, name in enumerate(DEMO_USERS):
        u = User(
            jellyfin_id=f"user-demo-{i:04d}",
            name=name,
            is_active=True,
            last_seen_at=random_date(7),
            play_count=0,
        )
        user_objects.append(u)

    async with async_session_factory() as db:
        db.add_all(user_objects)
        await db.commit()
        for u in user_objects:
            await db.refresh(u)

    print(f"  Created {len(user_objects)} users")

    print("Seeding media...")
    media_items = build_media_list()
    media_objects = []
    for m in media_items:
        obj = MediaMetadata(**m)
        media_objects.append(obj)

    async with async_session_factory() as db:
        db.add_all(media_objects)
        await db.commit()
        for obj in media_objects:
            await db.refresh(obj)

    print(f"  Created {len(media_objects)} media items")

    print("Seeding cold media (for library janitor)...")
    now = datetime.utcnow()

    days_min = 250
    days_max = 340

    cold_media = [
        MediaMetadata(
            jellyfin_id="cold-movie-1",
            title="Forgotten Classic",
            type="Movie",
            year=2024,
            genres='["Drama"]',
            runtime_ticks=6300000000,
            community_rating=8.5,
            play_count=0,
            path="/media/Movies/Forgotten Classic.mkv",
            added_at=now - timedelta(days=random.randint(days_min, days_max)),
            last_played_at=None,
            size_bytes=800000000,
        ),
        MediaMetadata(
            jellyfin_id="cold-movie-2",
            title="Old Documentary",
            type="Movie",
            year=2024,
            genres='["Documentary"]',
            runtime_ticks=5400000000,
            community_rating=7.2,
            play_count=1,
            path="/media/Movies/Old Documentary.mkv",
            added_at=now - timedelta(days=random.randint(days_min, days_max)),
            last_played_at=now - timedelta(days=random.randint(days_min, days_max)),
            size_bytes=600000000,
        ),
        MediaMetadata(
            jellyfin_id="cold-movie-3",
            title="Obscure Foreign Film",
            type="Movie",
            year=2024,
            genres='["Drama", "Foreign"]',
            runtime_ticks=8100000000,
            community_rating=7.8,
            play_count=0,
            path="/media/Movies/Obscure Foreign Film.mkv",
            added_at=now - timedelta(days=random.randint(days_min, days_max)),
            last_played_at=None,
            size_bytes=900000000,
        ),
        MediaMetadata(
            jellyfin_id="cold-series-1",
            title="Abandoned Series S1",
            type="Episode",
            year=2024,
            genres='["Comedy"]',
            runtime_ticks=1800000000,
            play_count=0,
            path="/media/TV/Abandoned Series/Season 1/Episode 1.mkv",
            added_at=now - timedelta(days=random.randint(days_min, days_max)),
            last_played_at=None,
            size_bytes=400000000,
        ),
        MediaMetadata(
            jellyfin_id="cold-movie-4",
            title="Early 2000s Flick",
            type="Movie",
            year=2024,
            genres='["Action"]',
            runtime_ticks=6900000000,
            community_rating=6.5,
            play_count=2,
            path="/media/Movies/Early 2000s Flick.mkv",
            added_at=now - timedelta(days=random.randint(days_min, days_max)),
            last_played_at=now - timedelta(days=random.randint(days_min, days_max)),
            size_bytes=700000000,
        ),
    ]
    async with async_session_factory() as db:
        db.add_all(cold_media)
        await db.commit()

    print(f"  Created {len(cold_media)} cold media items")

    print("Seeding playback sessions...")
    sessions = []
    now = datetime.utcnow()

    user_devices = {}
    for user in user_objects:
        phone = random.choice(PHONE_DEVICES)
        other_devices = random.sample(NON_PHONE_DEVICES, 2)
        user_devices[user.id] = [phone] + other_devices

    active_streams_created = {user.id: False for user in user_objects}

    for _ in range(400):
        user = random.choice(user_objects)
        user_device_list = user_devices[user.id]
        client, device = random.choice(user_device_list)

        media = random.choice(media_objects)
        started = random_date(365)
        duration = random.randint(300, max(600, int(media.runtime_ticks // 10000000) if media.runtime_ticks else 3600))
        ended = started + timedelta(seconds=duration)
        if ended > now:
            ended = now
            duration = int((ended - started).total_seconds())

        is_active = False
        if not active_streams_created[user.id] and random.random() < 0.06:
            is_active = True
            active_streams_created[user.id] = True
            ended = None
            duration = None

        play_method = random.choice(PLAY_METHODS)
        is_transcoding = play_method == "Transcode"
        reason = random.choice(TRANSCODE_REASONS) if is_transcoding else None

        session = PlaybackSession(
            jellyfin_session_id=f"session-demo-{_:04d}",
            user_id=user.id,
            media_id=media.id,
            started_at=started,
            ended_at=ended,
            duration_seconds=duration,
            device_name=device,
            client_name=client,
            is_transcoding=is_transcoding,
            transcode_reason=reason,
            play_method=play_method,
            ip_address=f"192.168.1.{random.randint(2, 254)}",
        )
        sessions.append(session)

    async with async_session_factory() as db:
        db.add_all(sessions)
        await db.commit()

    print(f"  Created {len(sessions)} playback sessions")

    print("Updating play counts...")
    async with async_session_factory() as db:
        from sqlalchemy import func as sa_func, select as sa_select

        for user in user_objects:
            count = (
                await db.execute(
                    sa_select(sa_func.count(PlaybackSession.id)).where(
                        PlaybackSession.user_id == user.id,
                        PlaybackSession.ended_at.isnot(None),
                    )
                )
            ).scalar() or 0
            user.play_count = count

        for media in media_objects:
            count = (
                await db.execute(
                    sa_select(sa_func.count(PlaybackSession.id)).where(
                        PlaybackSession.media_id == media.id,
                        PlaybackSession.ended_at.isnot(None),
                    )
                )
            ).scalar() or 0
            media.play_count = count

        await db.commit()

    print("Generating sample newsletter digest...")
    from app.services.newsletter import NewsletterGenerator, get_week_range

    week_start, week_end = get_week_range(now - timedelta(days=7))
    gen = NewsletterGenerator(async_session_factory)
    await gen.generate(week_start, week_end)

    print("Seeding complete!")
    print()
    print("Now run the app with demo mode:")
    print("  $env:DEMO_MODE=\"true\"; uvicorn app.main:app --host 0.0.0.0 --port 8500")


if __name__ == "__main__":
    asyncio.run(seed())
