"""
DataPool 导出器

导出训练数据
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.enums import FailureType, SampleType, TrajectoryType
from app.core.logger import logger


class DataPoolExporter:
    """数据池导出器"""

    def __init__(self, output_dir: Optional[str] = None):
        from app.core.config import get_settings
        self.settings = get_settings()
        self.output_dir = Path(output_dir or self.settings.exports_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_tool_use_samples(
        self,
        samples: list[dict[str, Any]],
        output_file: Optional[str] = None,
    ) -> str:
        """导出 tool-use 样本"""
        tool_use_samples = [
            s for s in samples
            if s.get("sample_type") == SampleType.TOOL_USE.value
        ]

        if not tool_use_samples:
            logger.warning("No tool-use samples to export")
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_file or f"tool_use_samples_{timestamp}.jsonl"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for sample in tool_use_samples:
                formatted = self._format_tool_use_sample(sample)
                f.write(json.dumps(formatted, ensure_ascii=False) + "\n")

        logger.info(f"Exported {len(tool_use_samples)} tool-use samples to {filepath}")
        return str(filepath)

    def export_self_correction_samples(
        self,
        samples: list[dict[str, Any]],
        output_file: Optional[str] = None,
    ) -> str:
        """导出 self-correction 样本"""
        correction_samples = [
            s for s in samples
            if s.get("sample_type") == SampleType.SELF_CORRECTION.value
        ]

        if not correction_samples:
            logger.warning("No self-correction samples to export")
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_file or f"self_correction_samples_{timestamp}.jsonl"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for sample in correction_samples:
                formatted = self._format_correction_sample(sample)
                f.write(json.dumps(formatted, ensure_ascii=False) + "\n")

        logger.info(f"Exported {len(correction_samples)} self-correction samples to {filepath}")
        return str(filepath)

    def export_gui_grounding_samples(
        self,
        samples: list[dict[str, Any]],
        output_file: Optional[str] = None,
    ) -> str:
        """导出 GUI grounding 样本"""
        gui_samples = [
            s for s in samples
            if s.get("sample_type") == SampleType.GUI_GROUNDING.value
            and s.get("screenshot_path")
        ]

        if not gui_samples:
            logger.warning("No GUI grounding samples to export")
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_file or f"gui_grounding_samples_{timestamp}.jsonl"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for sample in gui_samples:
                formatted = self._format_gui_sample(sample)
                f.write(json.dumps(formatted, ensure_ascii=False) + "\n")

        logger.info(f"Exported {len(gui_samples)} GUI grounding samples to {filepath}")
        return str(filepath)

    def export_all(
        self,
        samples: list[dict[str, Any]],
        output_dir: Optional[str] = None,
    ) -> dict[str, str]:
        """导出所有类型样本"""
        output_dir = Path(output_dir) if output_dir else self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        results = {
            "tool_use": self.export_tool_use_samples(
                samples, f"tool_use_{timestamp}.jsonl"
            ),
            "self_correction": self.export_self_correction_samples(
                samples, f"self_correction_{timestamp}.jsonl"
            ),
            "gui_grounding": self.export_gui_grounding_samples(
                samples, f"gui_grounding_{timestamp}.jsonl"
            ),
        }

        return results

    def _format_tool_use_sample(self, sample: dict[str, Any]) -> dict[str, Any]:
        """格式化 tool-use 样本"""
        return {
            "id": sample.get("sample_id", ""),
            "instruction": sample.get("instruction", ""),
            "state_summary": sample.get("state_summary", ""),
            "available_tools": sample.get("available_tools", []),
            "previous_actions": sample.get("previous_actions", []),
            "target_action": sample.get("target_action", ""),
            "target_args": sample.get("target_args", {}),
            "metadata": sample.get("metadata", {}),
        }

    def _format_correction_sample(self, sample: dict[str, Any]) -> dict[str, Any]:
        """格式化 self-correction 样本"""
        return {
            "id": sample.get("sample_id", ""),
            "instruction": sample.get("instruction", ""),
            "state_summary": sample.get("state_summary", ""),
            "available_tools": sample.get("available_tools", []),
            "failed_action": sample.get("failed_action", ""),
            "failed_args": sample.get("failed_args", {}),
            "error_type": sample.get("error_type", ""),
            "error_message": sample.get("error_message", ""),
            "corrected_action": sample.get("corrected_action", ""),
            "corrected_args": sample.get("corrected_args", {}),
            "metadata": sample.get("metadata", {}),
        }

    def _format_gui_sample(self, sample: dict[str, Any]) -> dict[str, Any]:
        """格式化 GUI grounding 样本"""
        return {
            "id": sample.get("sample_id", ""),
            "instruction": sample.get("instruction", ""),
            "screenshot_path": sample.get("screenshot_path", ""),
            "action_type": sample.get("action_type", ""),
            "target_element": sample.get("target_element", ""),
            "action_args": sample.get("action_args", {}),
            "target_description": sample.get("metadata", {}).get("target_description", ""),
        }
