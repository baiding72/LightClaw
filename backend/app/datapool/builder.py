"""
DataPool 构建器

从原始轨迹构建数据池样本
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.enums import FailureType, SampleType, TrajectoryType
from app.core.logger import logger
from app.schemas.datapool import (
    DataPoolSampleCreate,
    GUIGroundingSample,
    SelfCorrectionSample,
    ToolUseSample,
)
from app.schemas.trajectory import Trajectory, TrajectoryStep


class DataPoolBuilder:
    """数据池构建器"""

    def __init__(self, output_dir: Optional[str] = None):
        from app.core.config import get_settings
        self.settings = get_settings()
        self.output_dir = Path(output_dir or self.settings.datapool_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_from_trajectory(
        self,
        trajectory: Trajectory,
    ) -> list[DataPoolSampleCreate]:
        """
        从轨迹构建样本

        根据轨迹内容生成不同类型的样本
        """
        samples = []

        # 确定轨迹类型
        trajectory_type = self._determine_trajectory_type(trajectory)

        # 提取工具使用样本
        tool_use_samples = self._extract_tool_use_samples(trajectory, trajectory_type)
        samples.extend(tool_use_samples)

        # 提取自我纠正样本
        if trajectory.failure_types:
            correction_samples = self._extract_correction_samples(trajectory, trajectory_type)
            samples.extend(correction_samples)

        # 提取 GUI grounding 样本
        gui_samples = self._extract_gui_samples(trajectory, trajectory_type)
        samples.extend(gui_samples)

        return samples

    def _determine_trajectory_type(self, trajectory: Trajectory) -> TrajectoryType:
        """确定轨迹类型"""
        if trajectory.final_outcome == "success":
            return TrajectoryType.SUCCESS
        elif any(
            ft in [FailureType.REPAIR_SUCCESS.value, FailureType.REPAIR_FAILED.value]
            for ft in trajectory.failure_types
        ):
            return TrajectoryType.REPAIR
        else:
            return TrajectoryType.FAILURE

    def _extract_tool_use_samples(
        self,
        trajectory: Trajectory,
        trajectory_type: TrajectoryType,
    ) -> list[DataPoolSampleCreate]:
        """提取工具使用样本"""
        samples = []

        for i, step in enumerate(trajectory.steps):
            if not step.chosen_tool:
                continue

            # 构建状态摘要
            state_summary = self._build_state_summary(trajectory, i)

            # 构建样本
            sample = DataPoolSampleCreate(
                sample_type=SampleType.TOOL_USE,
                trajectory_type=trajectory_type,
                task_id=trajectory.task_id,
                step_ids=[f"step_{i}"],
                content={
                    "instruction": trajectory.user_instruction,
                    "state_summary": state_summary,
                    "available_tools": step.available_tools or [],
                    "chosen_tool": step.chosen_tool,
                    "tool_args": step.tool_args,
                    "tool_result": step.tool_result,
                    "thought": step.thought,
                },
                screenshot_paths=[step.screenshot_path] if step.screenshot_path else None,
            )
            samples.append(sample)

        return samples

    def _extract_correction_samples(
        self,
        trajectory: Trajectory,
        trajectory_type: TrajectoryType,
    ) -> list[DataPoolSampleCreate]:
        """提取自我纠正样本"""
        samples = []

        # 找到失败步骤和对应的成功修复步骤
        for i, step in enumerate(trajectory.steps):
            if step.status == "failed" and step.error_type:
                # 查找后续是否成功
                corrected_step = None
                for j in range(i + 1, len(trajectory.steps)):
                    next_step = trajectory.steps[j]
                    if next_step.chosen_tool and next_step.status == "success":
                        corrected_step = next_step
                        break

                if corrected_step:
                    sample = DataPoolSampleCreate(
                        sample_type=SampleType.SELF_CORRECTION,
                        trajectory_type=TrajectoryType.REPAIR,
                        task_id=trajectory.task_id,
                        step_ids=[f"step_{i}", f"step_{trajectory.steps.index(corrected_step)}"],
                        failure_type=FailureType(step.error_type) if step.error_type else None,
                        content={
                            "instruction": trajectory.user_instruction,
                            "failed_action": step.chosen_tool,
                            "failed_args": step.tool_args,
                            "error_type": step.error_type,
                            "error_message": step.error_message,
                            "corrected_action": corrected_step.chosen_tool,
                            "corrected_args": corrected_step.tool_args,
                        },
                        screenshot_paths=[
                            s for s in [step.screenshot_path, corrected_step.screenshot_path]
                            if s
                        ] or None,
                    )
                    samples.append(sample)

        return samples

    def _extract_gui_samples(
        self,
        trajectory: Trajectory,
        trajectory_type: TrajectoryType,
    ) -> list[DataPoolSampleCreate]:
        """提取 GUI grounding 样本"""
        samples = []

        # GUI 工具列表
        gui_tools = {"click", "type_text", "select_option", "scroll"}

        for i, step in enumerate(trajectory.steps):
            if step.chosen_tool not in gui_tools:
                continue

            if not step.screenshot_path:
                continue

            # 提取目标元素
            target_element = None
            if step.tool_args:
                target_element = step.tool_args.get("selector", "")

            sample = DataPoolSampleCreate(
                sample_type=SampleType.GUI_GROUNDING,
                trajectory_type=trajectory_type,
                task_id=trajectory.task_id,
                step_ids=[f"step_{i}"],
                content={
                    "instruction": trajectory.user_instruction,
                    "screenshot_path": step.screenshot_path,
                    "action_type": step.chosen_tool,
                    "target_element": target_element,
                    "action_args": step.tool_args,
                },
                screenshot_paths=[step.screenshot_path],
            )
            samples.append(sample)

        return samples

    def _build_state_summary(self, trajectory: Trajectory, step_index: int) -> str:
        """构建状态摘要"""
        # 收集之前的步骤信息
        previous_steps = trajectory.steps[:step_index]
        summary_parts = []

        if previous_steps:
            last_step = previous_steps[-1]
            if last_step.observation:
                summary_parts.append(last_step.observation)

        if not summary_parts:
            summary_parts.append("任务开始")

        return " | ".join(summary_parts)

    def save_samples(
        self,
        samples: list[DataPoolSampleCreate],
        output_file: Optional[str] = None,
    ) -> str:
        """保存样本到文件"""
        if not samples:
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_file or f"samples_{timestamp}.jsonl"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample.model_dump(), ensure_ascii=False, default=str) + "\n")

        logger.info(f"Saved {len(samples)} samples to {filepath}")
        return str(filepath)
