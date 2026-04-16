"""
Tool-use 训练数据导出
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.enums import SampleType
from app.core.logger import logger
from app.schemas.trajectory import Trajectory
from app.training.dataset_schema import (
    ConversationDatasetSample,
    ConversationMessage,
    DatasetStatistics,
    ToolUseDatasetSample,
)


class ToolUseExporter:
    """Tool-use 数据导出器"""

    def __init__(self, output_dir: Optional[str] = None):
        from app.core.config import get_settings
        self.settings = get_settings()
        self.output_dir = Path(output_dir or self.settings.exports_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_samples(
        self,
        trajectories: list[Trajectory],
        output_file: Optional[str] = None,
    ) -> str:
        """
        导出 tool-use 样本

        Args:
            trajectories: 轨迹列表
            output_file: 输出文件名

        Returns:
            输出文件路径
        """
        samples = []

        for trajectory in trajectories:
            trajectory_samples = self._extract_samples_from_trajectory(trajectory)
            samples.extend(trajectory_samples)

        if not samples:
            logger.warning("No tool-use samples to export")
            return ""

        # 保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_file or f"tool_use_{timestamp}.jsonl"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample.model_dump(), ensure_ascii=False) + "\n")

        logger.info(f"Exported {len(samples)} tool-use samples to {filepath}")
        return str(filepath)

    def _extract_samples_from_trajectory(
        self,
        trajectory: Trajectory,
    ) -> list[ToolUseDatasetSample]:
        """从轨迹提取样本"""
        samples = []

        for i, step in enumerate(trajectory.steps):
            if not step.chosen_tool:
                continue

            # 构建状态摘要
            state_summary = self._build_state_summary(trajectory, i)

            # 构建之前的动作
            previous_actions = self._get_previous_actions(trajectory, i)

            sample = ToolUseDatasetSample(
                id=f"tooluse_{trajectory.task_id}_{i}",
                instruction=trajectory.user_instruction,
                state_summary=state_summary,
                available_tools=step.available_tools or [],
                previous_actions=previous_actions,
                target_action=step.chosen_tool,
                target_args=step.tool_args or {},
                is_positive=step.status == "success",
                metadata={
                    "trajectory_id": trajectory.trajectory_id,
                    "step_index": i,
                    "category": trajectory.category,
                    "difficulty": trajectory.difficulty,
                },
            )
            samples.append(sample)

        return samples

    def _build_state_summary(self, trajectory: Trajectory, step_index: int) -> str:
        """构建状态摘要"""
        if step_index == 0:
            return "任务开始"

        previous_step = trajectory.steps[step_index - 1]
        if previous_step.observation:
            return previous_step.observation

        return f"已完成 {step_index} 个步骤"

    def _get_previous_actions(
        self,
        trajectory: Trajectory,
        step_index: int,
    ) -> list[dict[str, Any]]:
        """获取之前的动作"""
        actions = []
        for i in range(max(0, step_index - 3), step_index):
            step = trajectory.steps[i]
            if step.chosen_tool:
                actions.append({
                    "tool": step.chosen_tool,
                    "args": step.tool_args,
                    "result": "success" if step.status == "success" else "failed",
                })
        return actions

    def export_as_conversation(
        self,
        trajectories: list[Trajectory],
        output_file: Optional[str] = None,
    ) -> str:
        """
        导出为对话格式

        用于微调模型的对话格式数据
        """
        samples = []

        for trajectory in trajectories:
            sample = self._convert_to_conversation(trajectory)
            if sample:
                samples.append(sample)

        if not samples:
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_file or f"tool_use_conversation_{timestamp}.jsonl"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample.model_dump(), ensure_ascii=False) + "\n")

        logger.info(f"Exported {len(samples)} conversation samples to {filepath}")
        return str(filepath)

    def _convert_to_conversation(
        self,
        trajectory: Trajectory,
    ) -> Optional[ConversationDatasetSample]:
        """转换为对话格式"""
        messages = [
            ConversationMessage(
                role="system",
                content="你是一个智能助手，帮助用户完成任务。",
            ),
            ConversationMessage(
                role="user",
                content=trajectory.user_instruction,
            ),
        ]

        # 添加每个步骤
        for step in trajectory.steps:
            if step.thought:
                messages.append(ConversationMessage(
                    role="assistant",
                    content=step.thought,
                    tool_calls=[{
                        "id": f"call_{step.step_index}",
                        "type": "function",
                        "function": {
                            "name": step.chosen_tool,
                            "arguments": json.dumps(step.tool_args or {}, ensure_ascii=False),
                        },
                    }] if step.chosen_tool else None,
                ))

            if step.tool_result:
                messages.append(ConversationMessage(
                    role="tool",
                    content=json.dumps(step.tool_result, ensure_ascii=False),
                ))

        if len(messages) < 3:
            return None

        return ConversationDatasetSample(
            id=f"conv_{trajectory.trajectory_id}",
            messages=messages,
            metadata={
                "task_id": trajectory.task_id,
                "final_outcome": trajectory.final_outcome,
            },
        )

    def get_statistics(
        self,
        samples: list[ToolUseDatasetSample],
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
            # 统计工具类型
            action = sample.target_action
            by_type[action] = by_type.get(action, 0) + 1

            # 统计类别
            category = sample.metadata.get("category", "unknown")
            by_category[category] = by_category.get(category, 0) + 1

            # 长度统计
            total_instruction_len += len(sample.instruction)
            total_action_len += len(sample.target_action)

        return DatasetStatistics(
            total_samples=len(samples),
            by_type=by_type,
            by_category=by_category,
            avg_instruction_length=total_instruction_len / len(samples),
            avg_action_length=total_action_len / len(samples),
        )
