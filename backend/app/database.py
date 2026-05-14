import os
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.base import Base

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class _ScopedSessionFactory:
    """Wraps an AsyncSession to conform to the async_sessionmaker protocol.

    Used to inject a DI-managed session into services that expect a session
    factory (e.g. LibraryJanitor, NewsletterGenerator) without letting them
    close the underlying session.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    def __call__(self) -> "AsyncSession":
        return self

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *exc_info: Any) -> None:
        pass  # Session lifecycle is managed by the caller (DI / FastAPI)


async def init_db():
    from app.models import user  # noqa: F401
    from app.models import media  # noqa: F401
    from app.models import playback  # noqa: F401
    from app.models import webhook  # noqa: F401
    from app.models import newsletter  # noqa: F401

    os.makedirs("data", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session_factory() as session:
        yield session
