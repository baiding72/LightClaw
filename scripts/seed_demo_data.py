#!/usr/bin/env python3
"""
演示数据初始化脚本

创建一些演示数据用于展示
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.db import setup_database, async_session_maker
from app.db.models import NoteModel, TodoModel, CalendarEventModel
from app.memory import MemoryManager
from datetime import datetime, timedelta


async def seed_notes():
    """创建演示笔记"""
    async with async_session_maker() as session:
        notes = [
            NoteModel(
                title="项目会议纪要",
                content="讨论了下一阶段的开发计划，重点是完善评测框架。",
            ),
            NoteModel(
                title="学习笔记 - LLM Agent",
                content="MiniClaw 风格 Agent 的核心组件：\n1. Planner\n2. Executor\n3. Observer\n4. Recovery Manager",
            ),
            NoteModel(
                title="待办整理",
                content="本周需要完成：\n- 完善前端页面\n- 添加更多内置任务\n- 编写文档",
            ),
        ]

        for note in notes:
            session.add(note)

        await session.commit()
        print(f"Created {len(notes)} notes")


async def seed_todos():
    """创建演示待办"""
    async with async_session_maker() as session:
        todos = [
            TodoModel(
                title="完成 LightClaw MVP",
                description="搭建完整的项目框架",
                deadline=datetime.now() + timedelta(days=7),
                priority="high",
                status="pending",
            ),
            TodoModel(
                title="编写评测脚本",
                description="创建评测运行脚本",
                deadline=datetime.now() + timedelta(days=3),
                priority="medium",
                status="pending",
            ),
            TodoModel(
                title="准备演示",
                description="准备项目演示材料",
                deadline=datetime.now() + timedelta(days=1),
                priority="low",
                status="pending",
            ),
        ]

        for todo in todos:
            session.add(todo)

        await session.commit()
        print(f"Created {len(todos)} todos")


async def seed_calendar_events():
    """创建演示日历事件"""
    async with async_session_maker() as session:
        events = [
            CalendarEventModel(
                title="团队周会",
                description="每周团队同步会议",
                start_time=datetime.now() + timedelta(days=1, hours=10),
                end_time=datetime.now() + timedelta(days=1, hours=11),
                location="会议室 A",
            ),
            CalendarEventModel(
                title="项目评审",
                description="LightClaw 项目评审",
                start_time=datetime.now() + timedelta(days=3, hours=14),
                end_time=datetime.now() + timedelta(days=3, hours=15),
                location="线上",
            ),
        ]

        for event in events:
            session.add(event)

        await session.commit()
        print(f"Created {len(events)} calendar events")


async def seed_memory():
    """创建演示记忆"""
    memory = MemoryManager()
    memory.add_long_term("user_preferences", {
        "language": "zh-CN",
        "timezone": "Asia/Shanghai",
    })
    memory.add_long_term("common_patterns", [
        "用户喜欢简洁的回复",
        "用户偏好使用中文",
    ])
    print("Created memory entries")


async def main():
    """主函数"""
    print("Seeding demo data...")

    # 初始化数据库
    await setup_database()

    # 创建演示数据
    await seed_notes()
    await seed_todos()
    await seed_calendar_events()
    await seed_memory()

    print("\nDone! Demo data has been created.")


if __name__ == "__main__":
    asyncio.run(main())
