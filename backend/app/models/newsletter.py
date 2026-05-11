from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NewsletterDigest(Base):
    __tablename__ = "newsletter_digests"

    id: Mapped[int] = mapped_column(primary_key=True)
    week_start: Mapped[datetime] = mapped_column(Date)
    week_end: Mapped[datetime] = mapped_column(Date)
    html_content: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
