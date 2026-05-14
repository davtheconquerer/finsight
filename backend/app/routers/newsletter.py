from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import _ScopedSessionFactory, get_db
from app.services.newsletter import NewsletterGenerator, get_week_range

router = APIRouter()


@router.get("/newsletter/preview", response_class=HTMLResponse)
async def preview_newsletter(db: AsyncSession = Depends(get_db)):
    gen = NewsletterGenerator(_ScopedSessionFactory(db))
    digest = await gen.get_latest()
    if not digest:
        return "<html><body><h1>No digest generated yet</h1></body></html>"
    return digest.html_content


@router.post("/newsletter/generate")
async def generate_newsletter(db: AsyncSession = Depends(get_db)):
    gen = NewsletterGenerator(_ScopedSessionFactory(db))
    week_start, week_end = get_week_range()
    week_start = week_start - timedelta(days=7)
    week_end = week_end - timedelta(days=7)
    digest = await gen.generate(week_start, week_end)
    return {
        "status": "ok",
        "week_start": str(digest.week_start),
        "week_end": str(digest.week_end),
        "generated_at": digest.generated_at.isoformat(),
    }


@router.get("/api/newsletter/latest")
async def get_latest_digest_info(db: AsyncSession = Depends(get_db)):
    gen = NewsletterGenerator(_ScopedSessionFactory(db))
    digest = await gen.get_latest()
    if not digest:
        return {"exists": False}
    return {
        "exists": True,
        "id": digest.id,
        "week_start": str(digest.week_start),
        "week_end": str(digest.week_end),
        "generated_at": digest.generated_at.isoformat(),
        "sent": digest.sent,
    }
