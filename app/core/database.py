from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Create async engine with psycopg (compatible with Python 3.13)
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://"),
    poolclass=NullPool,
    echo=settings.DEBUG,
    future=True,
    connect_args={"ssl": "require"}
)

# Create async session maker
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

Base = declarative_base()

async def get_db():
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()