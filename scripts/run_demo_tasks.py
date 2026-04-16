#!/usr/bin/env python3
"""
演示任务运行脚本

运行几个演示任务，生成轨迹和数据
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.runtime import Agent
from app.tasks.definitions import (
    INFO_EXTRACTION_TASKS,
    TODO_CALENDAR_TASKS,
    MULTI_STEP_TASKS,
)


async def run_demo_task(task_definition) -> dict:
    """运行单个演示任务"""
    print(f"\n{'='*60}")
    print(f"Running: {task_definition.task_id}")
    print(f"Instruction: {task_definition.instruction[:80]}...")
    print(f"{'='*60}")

    agent = Agent(task_id=f"demo_{task_definition.task_id}")

    try:
        result = await agent.run(
            instruction=task_definition.instruction,
            allowed_tools=task_definition.allowed_tools,
            task_definition=task_definition,
        )

        print(f"\nResult: {'✓ Success' if result.get('success') else '✗ Failed'}")
        print(f"Steps: {result.get('total_steps', 0)}")
        print(f"Tokens: {result.get('total_tokens', 0)}")

        return result

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return {"success": False, "error": str(e)}

    finally:
        await agent.close()


async def main():
    """主函数"""
    print("="*60)
    print("LightClaw Demo Tasks Runner")
    print("="*60)

    # 选择几个演示任务
    demo_tasks = [
        TODO_CALENDAR_TASKS[0],  # 简单待办
        TODO_CALENDAR_TASKS[1],  # 简单日历
        MULTI_STEP_TASKS[3],     # 计算并写入笔记
    ]

    results = []

    for task in demo_tasks:
        result = await run_demo_task(task)
        results.append({
            "task_id": task.task_id,
            "success": result.get("success", False),
        })

    # 打印汇总
    print("\n" + "="*60)
    print("Summary")
    print("="*60)

    success_count = sum(1 for r in results if r["success"])
    print(f"Total: {len(results)}")
    print(f"Success: {success_count}")
    print(f"Failed: {len(results) - success_count}")

    print("\nDemo tasks completed!")


if __name__ == "__main__":
    asyncio.run(main())
