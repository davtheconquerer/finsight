import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models.base import Base

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


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
