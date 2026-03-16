from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings


def get_async_database_url() -> str:
    """Convert to an asyncpg URL and drop unsupported query parameters."""
    url = get_settings().DATABASE_URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    parsed = make_url(url)
    cleaned_query = dict(parsed.query)
    cleaned_query.pop("sslmode", None)
    cleaned_query.pop("channel_binding", None)

    return str(parsed.set(query=cleaned_query))


def get_async_engine_kwargs() -> dict:
    """Map common libpq SSL options to asyncpg-compatible connect_args."""
    parsed = make_url(get_settings().DATABASE_URL)
    sslmode = (parsed.query.get("sslmode") or "").lower()

    if sslmode in {"require", "verify-ca", "verify-full"}:
        return {"connect_args": {"ssl": "require"}}

    return {}


engine = create_async_engine(get_async_database_url(), echo=False, **get_async_engine_kwargs())
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
