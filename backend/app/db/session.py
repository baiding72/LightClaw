"""
数据库会话管理
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""
    pass


# 创建异步引擎
engine = create_async_engine(
    get_settings().database_url,
    echo=get_settings().app_debug,
)

# 创建会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
