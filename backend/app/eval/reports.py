"""
评测报告生成
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.core.logger import logger
from app.schemas.eval import EvaluationResponse


class ReportGenerator:
    """报告生成器"""

    def __init__(self, output_dir: Optional[str] = None):
        from app.core.config import get_settings
        self.settings = get_settings()
        self.output_dir = Path(output_dir or self.settings.eval_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown_report(
        self,
        result: EvaluationResponse,
        output_file: Optional[str] = None,
    ) -> str:
        """生成 Markdown 报告"""
        report_lines = [
            f"# 评测报告: {result.eval_name}",
            "",
            f"- **评测 ID**: {result.eval_id}",
            f"- **执行时间**: {result.created_at}",
            f"- **任务数量**: {result.total_tasks}",
            "",
            "## 评测指标",
            "",
            "| 指标 | 值 |",
            "|------|------|",
            f"| 任务成功率 | {result.metrics.task_success_rate:.2%} |",
            f"| 工具执行成功率 | {result.metrics.tool_execution_success_rate:.2%} |",
            f"| 恢复率 | {result.metrics.recovery_rate:.2%} |",
            f"| GUI 操作准确率 | {result.metrics.gui_action_accuracy:.2%} |",
            f"| 平均延迟 | {result.metrics.avg_latency_ms:.0f} ms |",
            "",
            "## 任务详情",
            "",
        ]

        # 按类别分组
        by_category: dict[str, list] = {}
        for detail in result.details:
            cat = detail.task_id.split("_")[0] if "_" in detail.task_id else "other"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(detail)

        for category, details in by_category.items():
            report_lines.append(f"### {category.upper()}")
            report_lines.append("")
            report_lines.append("| 任务 | 成功 | 步骤数 | 延迟 |")
            report_lines.append("|------|------|--------|------|")

            for d in details:
                success_icon = "✓" if d.is_success else "✗"
                report_lines.append(
                    f"| {d.task_id} | {success_icon} | {d.steps_count} | {d.latency_ms}ms |"
                )

            report_lines.append("")

        # 失败分析
        failures = [d for d in result.details if not d.is_success]
        if failures:
            report_lines.append("## 失败分析")
            report_lines.append("")
            for f in failures:
                report_lines.append(f"- **{f.task_id}**: {', '.join(f.failure_types) if f.failure_types else '未知错误'}")
            report_lines.append("")

        report_content = "\n".join(report_lines)

        # 保存报告
        if output_file:
            filepath = self.output_dir / output_file
            filepath.write_text(report_content, encoding="utf-8")
            logger.info(f"Report saved: {filepath}")

        return report_content

    def generate_json_summary(
        self,
        result: EvaluationResponse,
    ) -> dict[str, Any]:
        """生成 JSON 摘要"""
        return {
            "eval_id": result.eval_id,
            "eval_name": result.eval_name,
            "timestamp": result.created_at.isoformat(),
            "total_tasks": result.total_tasks,
            "metrics": {
                "task_success_rate": result.metrics.task_success_rate,
                "tool_execution_success_rate": result.metrics.tool_execution_success_rate,
                "recovery_rate": result.metrics.recovery_rate,
                "gui_action_accuracy": result.metrics.gui_action_accuracy,
                "avg_latency_ms": result.metrics.avg_latency_ms,
            },
            "summary": {
                "successful_tasks": sum(1 for d in result.details if d.is_success),
                "failed_tasks": sum(1 for d in result.details if not d.is_success),
                "total_steps": sum(d.steps_count for d in result.details),
                "total_recoveries": sum(d.successful_recoveries for d in result.details),
            },
        }
