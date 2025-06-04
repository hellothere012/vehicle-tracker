from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.engine.url import make_url
from src.config import settings
import os

DATABASE_URL = settings.DATABASE_URL

# Ensure the directory for a SQLite database exists
url = make_url(DATABASE_URL)
if url.drivername.startswith("sqlite") and url.database:
    os.makedirs(os.path.dirname(url.database), exist_ok=True)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def create_db_tables():
    from src.models.vehicle import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
