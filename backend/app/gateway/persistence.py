"""
Gateway 持久化模块
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logger import logger


class TrajectoryPersistence:
    """轨迹持久化"""

    def __init__(self, output_dir: Optional[str] = None):
        self.settings = get_settings()
        self.output_dir = Path(output_dir or self.settings.trajectories_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_trajectory(
        self,
        task_id: str,
        trajectory_data: dict[str, Any],
    ) -> str:
        """保存轨迹"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trajectory_{task_id}_{timestamp}.jsonl"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json.dumps(trajectory_data, ensure_ascii=False, default=str) + "\n")

        logger.info(f"Trajectory saved: {filepath}")
        return str(filepath)

    def load_trajectory(self, filepath: str) -> dict[str, Any]:
        """加载轨迹"""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.loads(f.readline())

    def list_trajectories(self) -> list[dict[str, Any]]:
        """列出所有轨迹文件"""
        trajectories = []
        for filepath in sorted(self.output_dir.glob("trajectory_*.jsonl")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.loads(f.readline())
                    trajectories.append({
                        "path": str(filepath),
                        "task_id": data.get("task_id"),
                        "timestamp": data.get("timestamp"),
                        "final_outcome": data.get("final_outcome"),
                    })
            except Exception as e:
                logger.warning(f"Failed to read trajectory {filepath}: {e}")

        return trajectories

    def delete_trajectory(self, filepath: str) -> bool:
        """删除轨迹"""
        try:
            Path(filepath).unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to delete trajectory: {e}")
            return False
