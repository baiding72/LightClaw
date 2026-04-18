"""
LightClaw 主应用

面向个人效率管理的在线自进化轻量智能体
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.core.config import get_settings
from app.core.logger import logger
from app.db import setup_database
from app.browser import close_browser_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动
    logger.info("Starting LightClaw...")

    # 初始化数据库
    await setup_database()
    logger.info("Database initialized")

    yield

    # 关闭
    logger.info("Shutting down LightClaw...")

    # 关闭浏览器
    await close_browser_manager()


def create_app() -> FastAPI:
    """创建应用"""
    settings = get_settings()

    app = FastAPI(
        title="LightClaw",
        description="面向个人效率管理的在线自进化轻量智能体",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(api_router, prefix="/api")
    app.mount("/artifacts/screenshots", StaticFiles(directory=settings.screenshots_dir), name="screenshots")

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
    )
