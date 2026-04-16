"""
LightClaw 日志配置
"""
import logging
import sys
from pathlib import Path

from app.core.config import get_settings


def setup_logging() -> logging.Logger:
    """配置日志"""
    settings = get_settings()

    # 创建日志目录
    log_dir = Path(settings.data_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # 配置根日志器
    logger = logging.getLogger("lightclaw")
    logger.setLevel(getattr(logging, settings.log_level.upper()))

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)

    # 文件处理器
    file_handler = logging.FileHandler(log_dir / "lightclaw.log")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# 全局日志器
logger = setup_logging()
