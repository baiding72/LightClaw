"""
数据库初始化
"""
from pathlib import Path

from app.core.config import get_settings
from app.db.session import async_session_maker, engine, init_db


async def setup_database() -> None:
    """设置数据库"""
    # 确保数据目录存在
    settings = get_settings()
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

    # 创建表
    await init_db()

    # 创建必要的数据目录
    for dir_path in [
        settings.trajectories_dir,
        settings.screenshots_dir,
        settings.datapool_dir,
        settings.exports_dir,
        settings.eval_dir,
    ]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
