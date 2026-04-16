"""
DataPool 切分器

将轨迹切分为训练样本
"""
from typing import Any, Optional

from app.core.enums import FailureType, SampleType, TrajectoryType
from app.core.logger import logger
from app.schemas.trajectory import Trajectory


class TrajectorySplitter:
    """轨迹切分器"""

    def split_for_tool_use(
        self,
        trajectory: Trajectory,
    ) -> list[dict[str, Any]]:
        """
        切分为 tool-use 样本

        每个步骤成为一个独立样本
        """
        samples = []

        for i, step in enumerate(trajectory.steps):
            if not step.chosen_tool:
                continue

            sample = {
                "sample_id": f"tooluse_{trajectory.task_id}_{i}",
                "sample_type": SampleType.TOOL_USE.value,
                "trajectory_id": trajectory.trajectory_id,
                "task_id": trajectory.task_id,
                "instruction": trajectory.user_instruction,
                "step_index": i,
                "state_summary": self._get_state_summary(trajectory, i),
                "available_tools": step.available_tools or [],
                "previous_actions": self._get_previous_actions(trajectory, i),
                "target_action": step.chosen_tool,
                "target_args": step.tool_args or {},
                "is_success": step.status == "success",
                "error_type": step.error_type,
                "metadata": {
                    "trajectory_type": self._get_trajectory_type(trajectory),
                    "difficulty": trajectory.difficulty,
                    "category": trajectory.category,
                },
            }
            samples.append(sample)

        return samples

    def split_for_self_correction(
        self,
        trajectory: Trajectory,
    ) -> list[dict[str, Any]]:
        """
        切分为 self-correction 样本

        需要失败后修复的场景
        """
        samples = []

        # 找到失败-修复对
        failed_steps = []
        for i, step in enumerate(trajectory.steps):
            if step.status == "failed":
                failed_steps.append((i, step))

        for failed_idx, failed_step in failed_steps:
            # 查找后续成功的步骤
            corrected_step = None
            corrected_idx = None
            for j in range(failed_idx + 1, len(trajectory.steps)):
                step = trajectory.steps[j]
                if step.status == "success" and step.chosen_tool:
                    corrected_step = step
                    corrected_idx = j
                    break

            if corrected_step:
                sample = {
                    "sample_id": f"correction_{trajectory.task_id}_{failed_idx}",
                    "sample_type": SampleType.SELF_CORRECTION.value,
                    "trajectory_id": trajectory.trajectory_id,
                    "task_id": trajectory.task_id,
                    "instruction": trajectory.user_instruction,
                    "state_summary": self._get_state_summary(trajectory, failed_idx),
                    "available_tools": failed_step.available_tools or [],
                    "failed_action": failed_step.chosen_tool,
                    "failed_args": failed_step.tool_args or {},
                    "error_type": failed_step.error_type,
                    "error_message": failed_step.error_message,
                    "corrected_action": corrected_step.chosen_tool,
                    "corrected_args": corrected_step.tool_args or {},
                    "metadata": {
                        "failed_step_index": failed_idx,
                        "corrected_step_index": corrected_idx,
                        "recovery_successful": True,
                    },
                }
                samples.append(sample)

        return samples

    def split_for_gui_grounding(
        self,
        trajectory: Trajectory,
    ) -> list[dict[str, Any]]:
        """
        切分为 GUI grounding 样本

        需要截图和 GUI 操作
        """
        samples = []

        gui_tools = {"click", "type_text", "select_option", "scroll"}

        for i, step in enumerate(trajectory.steps):
            if step.chosen_tool not in gui_tools:
                continue

            if not step.screenshot_path:
                continue

            sample = {
                "sample_id": f"gui_{trajectory.task_id}_{i}",
                "sample_type": SampleType.GUI_GROUNDING.value,
                "trajectory_id": trajectory.trajectory_id,
                "task_id": trajectory.task_id,
                "instruction": trajectory.user_instruction,
                "screenshot_path": step.screenshot_path,
                "action_type": step.chosen_tool,
                "target_element": step.tool_args.get("selector", "") if step.tool_args else "",
                "action_args": step.tool_args,
                "is_success": step.status == "success",
                "metadata": {
                    "step_index": i,
                    "target_description": self._describe_target(step),
                },
            }
            samples.append(sample)

        return samples

    def _get_state_summary(self, trajectory: Trajectory, step_index: int) -> str:
        """获取状态摘要"""
        if step_index == 0:
            return "任务开始"

        previous_step = trajectory.steps[step_index - 1]
        if previous_step.observation:
            return previous_step.observation

        return f"步骤 {step_index} 后的状态"

    def _get_previous_actions(
        self,
        trajectory: Trajectory,
        step_index: int,
    ) -> list[dict[str, Any]]:
        """获取之前的动作列表"""
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

    def _get_trajectory_type(self, trajectory: Trajectory) -> str:
        """获取轨迹类型"""
        if trajectory.final_outcome == "success":
            return TrajectoryType.SUCCESS.value
        elif trajectory.recovery_attempts > 0 and trajectory.successful_recoveries > 0:
            return TrajectoryType.REPAIR.value
        else:
            return TrajectoryType.FAILURE.value

    def _describe_target(self, step: Any) -> str:
        """描述目标元素"""
        if not step.tool_args:
            return ""

        selector = step.tool_args.get("selector", "")
        if selector:
            return f"元素: {selector}"

        return ""
