"""
DataPool 过滤器
"""
from typing import Any, Optional

from app.core.enums import FailureType, SampleType, TrajectoryType


class DataPoolFilter:
    """数据池过滤器"""

    def __init__(
        self,
        sample_types: Optional[list[SampleType]] = None,
        trajectory_types: Optional[list[TrajectoryType]] = None,
        failure_types: Optional[list[FailureType]] = None,
        task_ids: Optional[list[str]] = None,
    ):
        self.sample_types = sample_types
        self.trajectory_types = trajectory_types
        self.failure_types = failure_types
        self.task_ids = task_ids

    def matches(self, sample: dict[str, Any]) -> bool:
        """检查样本是否匹配过滤条件"""
        # 样本类型
        if self.sample_types:
            sample_type = sample.get("sample_type")
            if sample_type not in [st.value for st in self.sample_types]:
                return False

        # 轨迹类型
        if self.trajectory_types:
            trajectory_type = sample.get("trajectory_type") or sample.get("metadata", {}).get("trajectory_type")
            if trajectory_type not in [tt.value for tt in self.trajectory_types]:
                return False

        # 失败类型
        if self.failure_types:
            failure_type = sample.get("failure_type") or sample.get("error_type")
            if failure_type not in [ft.value for ft in self.failure_types]:
                return False

        # 任务 ID
        if self.task_ids:
            task_id = sample.get("task_id")
            if task_id not in self.task_ids:
                return False

        return True

    def filter_samples(
        self,
        samples: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """过滤样本列表"""
        return [s for s in samples if self.matches(s)]


def filter_by_failure_type(
    samples: list[dict[str, Any]],
    failure_types: list[FailureType],
) -> list[dict[str, Any]]:
    """按失败类型过滤"""
    filter_obj = DataPoolFilter(failure_types=failure_types)
    return filter_obj.filter_samples(samples)


def filter_by_sample_type(
    samples: list[dict[str, Any]],
    sample_types: list[SampleType],
) -> list[dict[str, Any]]:
    """按样本类型过滤"""
    filter_obj = DataPoolFilter(sample_types=sample_types)
    return filter_obj.filter_samples(samples)


def filter_by_trajectory_type(
    samples: list[dict[str, Any]],
    trajectory_types: list[TrajectoryType],
) -> list[dict[str, Any]]:
    """按轨迹类型过滤"""
    filter_obj = DataPoolFilter(trajectory_types=trajectory_types)
    return filter_obj.filter_samples(samples)


def filter_gui_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """过滤 GUI 样本（必须有截图）"""
    return [
        s for s in samples
        if s.get("sample_type") == SampleType.GUI_GROUNDING.value
        and s.get("screenshot_path")
    ]


def filter_correction_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """过滤纠错样本（必须有失败和修复）"""
    return [
        s for s in samples
        if s.get("sample_type") == SampleType.SELF_CORRECTION.value
        and s.get("corrected_action")
    ]
