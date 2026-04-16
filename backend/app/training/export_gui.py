"""
GUI Grounding 训练数据导出
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.enums import SampleType
from app.core.logger import logger
from app.schemas.trajectory import Trajectory
from app.training.dataset_schema import (
    DatasetStatistics,
    GUIGroundingDatasetSample,
)


class GUIGroundingExporter:
    """GUI Grounding 数据导出器"""

    def __init__(self, output_dir: Optional[str] = None):
        from app.core.config import get_settings
        self.settings = get_settings()
        self.output_dir = Path(output_dir or self.settings.exports_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_samples(
        self,
        trajectories: list[Trajectory],
        output_file: Optional[str] = None,
        copy_screenshots: bool = True,
    ) -> str:
        """
        导出 GUI grounding 样本

        Args:
            trajectories: 轨迹列表
            output_file: 输出文件名
            copy_screenshots: 是否复制截图到输出目录

        Returns:
            输出文件路径
        """
        samples = []

        for trajectory in trajectories:
            trajectory_samples = self._extract_samples_from_trajectory(trajectory)
            samples.extend(trajectory_samples)

        if not samples:
            logger.warning("No GUI grounding samples to export")
            return ""

        # 复制截图
        if copy_screenshots:
            samples = self._copy_screenshots(samples)

        # 保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_file or f"gui_grounding_{timestamp}.jsonl"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample.model_dump(), ensure_ascii=False) + "\n")

        logger.info(f"Exported {len(samples)} GUI grounding samples to {filepath}")
        return str(filepath)

    def _extract_samples_from_trajectory(
        self,
        trajectory: Trajectory,
    ) -> list[GUIGroundingDatasetSample]:
        """从轨迹提取 GUI 样本"""
        samples = []

        gui_tools = {"click", "type_text", "select_option", "scroll"}

        for i, step in enumerate(trajectory.steps):
            if step.chosen_tool not in gui_tools:
                continue

            if not step.screenshot_path:
                continue

            # 提取目标元素
            target_element = ""
            if step.tool_args:
                target_element = step.tool_args.get("selector", "")

            # 构建样本
            sample = GUIGroundingDatasetSample(
                id=f"gui_{trajectory.task_id}_{i}",
                instruction=trajectory.user_instruction,
                screenshot_path=step.screenshot_path,
                action_type=step.chosen_tool,
                target_element=target_element,
                target_description=self._describe_target(step),
                action_args=step.tool_args,
                is_success=step.status == "success",
                metadata={
                    "trajectory_id": trajectory.trajectory_id,
                    "step_index": i,
                    "category": trajectory.category,
                    "difficulty": trajectory.difficulty,
                },
            )
            samples.append(sample)

        return samples

    def _describe_target(self, step: Any) -> str:
        """描述目标元素"""
        if not step.tool_args:
            return ""

        selector = step.tool_args.get("selector", "")
        if selector:
            # 简单描述
            if selector.startswith("#"):
                return f"ID 为 {selector[1:]} 的元素"
            elif selector.startswith("."):
                return f"类名为 {selector[1:]} 的元素"
            else:
                return f"选择器 {selector} 对应的元素"

        return ""

    def _copy_screenshots(
        self,
        samples: list[GUIGroundingDatasetSample],
    ) -> list[GUIGroundingDatasetSample]:
        """复制截图到输出目录"""
        import shutil

        screenshots_dir = self.output_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        updated_samples = []

        for sample in samples:
            src_path = Path(sample.screenshot_path)
            if src_path.exists():
                # 复制文件
                dst_path = screenshots_dir / src_path.name
                shutil.copy2(src_path, dst_path)

                # 更新路径
                updated_sample = sample.model_copy(update={
                    "screenshot_path": str(dst_path),
                })
                updated_samples.append(updated_sample)
            else:
                updated_samples.append(sample)

        return updated_samples

    def export_for_qwen_vl(
        self,
        trajectories: list[Trajectory],
        output_file: Optional[str] = None,
    ) -> str:
        """
        导出为 Qwen-VL 格式

        适用于 Qwen2-VL 微调
        """
        samples = []

        for trajectory in trajectories:
            trajectory_samples = self._extract_samples_from_trajectory(trajectory)
            for sample in trajectory_samples:
                qwen_sample = self._convert_to_qwen_vl_format(sample)
                if qwen_sample:
                    samples.append(qwen_sample)

        if not samples:
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_file or f"qwen_vl_gui_{timestamp}.jsonl"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

        logger.info(f"Exported {len(samples)} Qwen-VL samples to {filepath}")
        return str(filepath)

    def _convert_to_qwen_vl_format(
        self,
        sample: GUIGroundingDatasetSample,
    ) -> Optional[dict[str, Any]]:
        """转换为 Qwen-VL 格式"""
        return {
            "id": sample.id,
            "image": sample.screenshot_path,
            "conversations": [
                {
                    "from": "human",
                    "value": f"<image>\n{sample.instruction}\n请定位需要操作的元素。",
                },
                {
                    "from": "assistant",
                    "value": f"需要执行 {sample.action_type} 操作，目标元素: {sample.target_element}",
                },
            ],
            "action_type": sample.action_type,
            "target_element": sample.target_element,
        }

    def get_statistics(
        self,
        samples: list[GUIGroundingDatasetSample],
    ) -> DatasetStatistics:
        """获取数据集统计"""
        if not samples:
            return DatasetStatistics(
                total_samples=0,
                by_type={},
                by_category={},
                avg_instruction_length=0.0,
                avg_action_length=0.0,
            )

        by_type: dict[str, int] = {}
        by_category: dict[str, int] = {}
        total_instruction_len = 0
        total_action_len = 0

        for sample in samples:
            # 统计动作类型
            action = sample.action_type
            by_type[action] = by_type.get(action, 0) + 1

            # 统计类别
            category = sample.metadata.get("category", "unknown")
            by_category[category] = by_category.get(category, 0) + 1

            # 长度统计
            total_instruction_len += len(sample.instruction)
            total_action_len += len(sample.action_type)

        return DatasetStatistics(
            total_samples=len(samples),
            by_type=by_type,
            by_category=by_category,
            avg_instruction_length=total_instruction_len / len(samples),
            avg_action_length=total_action_len / len(samples),
        )
