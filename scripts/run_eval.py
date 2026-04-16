#!/usr/bin/env python3
"""
评测运行脚本

运行 benchmark 并输出结果
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.eval import EvaluationRunner, ReportGenerator
from app.tasks.definitions import ALL_TASKS


async def main():
    """主函数"""
    print("="*60)
    print("LightClaw Benchmark Runner")
    print("="*60)

    runner = EvaluationRunner()
    report_gen = ReportGenerator()

    # 运行评测
    eval_name = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\nRunning evaluation: {eval_name}")
    print(f"Total tasks: {len(ALL_TASKS)}")

    # 只运行部分任务作为演示
    # 实际使用时可以去掉 categories 限制
    result = await runner.run_evaluation(
        eval_name=eval_name,
        categories=["todo_calendar", "info_extraction"],
    )

    # 打印结果
    print("\n" + "="*60)
    print("Results")
    print("="*60)

    print(f"\nTask Success Rate: {result.metrics.task_success_rate:.2%}")
    print(f"Tool Execution Success Rate: {result.metrics.tool_execution_success_rate:.2%}")
    print(f"Recovery Rate: {result.metrics.recovery_rate:.2%}")
    print(f"GUI Action Accuracy: {result.metrics.gui_action_accuracy:.2%}")
    print(f"Average Latency: {result.metrics.avg_latency_ms:.0f}ms")

    # 生成报告
    print("\nGenerating report...")
    report = report_gen.generate_markdown_report(result)
    print(report)

    # 保存结果
    output_dir = Path("data/eval")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = output_dir / f"report_{timestamp}.md"
    report_file.write_text(report, encoding="utf-8")

    print(f"\nReport saved to: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
