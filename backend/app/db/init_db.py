"""
数据库初始化
"""
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine, init_db


async def setup_database() -> None:
    """设置数据库"""
    # 确保数据目录存在
    settings = get_settings()
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

    # 创建表
    await init_db()
    await _run_lightweight_migrations()

    # 创建必要的数据目录
    for dir_path in [
        settings.trajectories_dir,
        settings.screenshots_dir,
        settings.datapool_dir,
        settings.exports_dir,
        settings.eval_dir,
    ]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)


async def _run_lightweight_migrations() -> None:
    """为 SQLite 开发环境执行轻量迁移"""
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(tasks)"))
        columns = {row[1] for row in result.fetchall()}
        if "browser_context" not in columns:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN browser_context JSON"))
        if "scenario_type" not in columns:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN scenario_type VARCHAR(64)"))
        if "scenario_context" not in columns:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN scenario_context JSON"))
