from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MediaMetadata(Base):
    __tablename__ = "media_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    jellyfin_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    type: Mapped[str] = mapped_column(String(32))
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    genres: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    runtime_ticks: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    community_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    play_count: Mapped[int] = mapped_column(Integer, default=0)
    path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    added_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_played_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    playback_sessions: Mapped[list["PlaybackSession"]] = relationship(
        back_populates="media"
    )
