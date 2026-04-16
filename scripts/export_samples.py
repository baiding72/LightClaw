#!/usr/bin/env python3
"""
训练样本导出脚本

从轨迹导出训练数据
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.datapool import DataPoolBuilder, DataPoolExporter
from app.gateway import TrajectoryPersistence
from app.schemas.trajectory import Trajectory, TrajectoryStep
from app.core.config import get_settings


async def main():
    """主函数"""
    print("="*60)
    print("LightClaw Training Data Export")
    print("="*60)

    settings = get_settings()

    # 初始化
    persistence = TrajectoryPersistence(settings.trajectories_dir)
    builder = DataPoolBuilder(settings.datapool_dir)
    exporter = DataPoolExporter(settings.exports_dir)

    # 列出轨迹
    trajectories = persistence.list_trajectories()
    print(f"\nFound {len(trajectories)} trajectories")

    if not trajectories:
        print("No trajectories found. Run some tasks first.")
        return

    # 加载并处理轨迹
    all_samples = []

    for traj_info in trajectories:
        print(f"\nProcessing: {traj_info['task_id']}")

        try:
            # 加载轨迹数据
            traj_data = persistence.load_trajectory(traj_info["path"])

            # 转换为 Trajectory 对象（简化版）
            # 实际实现需要完整的转换逻辑
            print(f"  - Loaded trajectory data")

        except Exception as e:
            print(f"  - Error: {e}")
            continue

    # 导出样本
    print("\n" + "="*60)
    print("Exporting samples...")
    print("="*60)

    # 演示：创建一些示例样本
    demo_samples = [
        {
            "sample_id": f"demo_tooluse_{i}",
            "sample_type": "tool_use",
            "trajectory_type": "success_trajectory",
            "task_id": f"demo_task_{i}",
            "step_ids": [f"step_{i}"],
            "content": {
                "instruction": f"Demo instruction {i}",
                "state_summary": "Initial state",
                "available_tools": ["add_todo", "write_note"],
                "chosen_tool": "add_todo",
                "tool_args": {"title": f"Task {i}"},
            },
        }
        for i in range(5)
    ]

    # 导出
    results = exporter.export_all(demo_samples)

    print("\nExport results:")
    for sample_type, filepath in results.items():
        if filepath:
            print(f"  - {sample_type}: {filepath}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
