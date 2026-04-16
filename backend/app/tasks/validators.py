"""
任务验证器

验证任务执行结果
"""
from typing import Any, Optional

from app.core.logger import logger
from app.schemas.task import TaskDefinition, TaskValidationResult


class TaskValidator:
    """任务验证器"""

    def validate(
        self,
        task: TaskDefinition,
        execution_result: dict[str, Any],
    ) -> TaskValidationResult:
        """
        验证任务执行结果

        Args:
            task: 任务定义
            execution_result: 执行结果

        Returns:
            验证结果
        """
        checks = []
        total_checks = 0
        passed_checks = 0

        validation_rules = task.validation_rules

        # 检查笔记是否创建
        if validation_rules.get("check_note_exists"):
            total_checks += 1
            notes = execution_result.get("notes", [])
            check_passed = len(notes) > 0
            checks.append({
                "name": "note_exists",
                "passed": check_passed,
                "details": f"Found {len(notes)} notes",
            })
            if check_passed:
                passed_checks += 1

        # 检查待办是否创建
        if validation_rules.get("check_todo_exists"):
            total_checks += 1
            todos = execution_result.get("todos", [])
            check_passed = len(todos) > 0
            checks.append({
                "name": "todo_exists",
                "passed": check_passed,
                "details": f"Found {len(todos)} todos",
            })
            if check_passed:
                passed_checks += 1

        # 检查待办数量
        if "check_todo_count" in validation_rules:
            total_checks += 1
            expected_count = validation_rules["check_todo_count"]
            todos = execution_result.get("todos", [])
            actual_count = len(todos)
            check_passed = actual_count >= expected_count
            checks.append({
                "name": "todo_count",
                "passed": check_passed,
                "details": f"Expected {expected_count}, found {actual_count}",
            })
            if check_passed:
                passed_checks += 1

        # 检查日历事件
        if validation_rules.get("check_event_exists"):
            total_checks += 1
            events = execution_result.get("calendar_events", [])
            check_passed = len(events) > 0
            checks.append({
                "name": "event_exists",
                "passed": check_passed,
                "details": f"Found {len(events)} events",
            })
            if check_passed:
                passed_checks += 1

        # 检查截图
        if validation_rules.get("check_screenshot_exists"):
            total_checks += 1
            screenshots = execution_result.get("screenshots", [])
            check_passed = len(screenshots) > 0
            checks.append({
                "name": "screenshot_exists",
                "passed": check_passed,
                "details": f"Found {len(screenshots)} screenshots",
            })
            if check_passed:
                passed_checks += 1

        # 检查优先级
        if "check_priority" in validation_rules:
            total_checks += 1
            expected_priority = validation_rules["check_priority"]
            todos = execution_result.get("todos", [])
            check_passed = any(
                t.get("priority") == expected_priority for t in todos
            )
            checks.append({
                "name": "priority",
                "passed": check_passed,
                "details": f"Expected priority {expected_priority}",
            })
            if check_passed:
                passed_checks += 1

        # 检查最小笔记长度
        if "min_note_length" in validation_rules:
            total_checks += 1
            min_length = validation_rules["min_note_length"]
            notes = execution_result.get("notes", [])
            check_passed = any(
                len(n.get("content", "")) >= min_length for n in notes
            )
            checks.append({
                "name": "min_note_length",
                "passed": check_passed,
                "details": f"Minimum length {min_length}",
            })
            if check_passed:
                passed_checks += 1

        # 计算得分
        score = passed_checks / total_checks if total_checks > 0 else 0.0
        is_success = score >= 0.8  # 80% 通过即为成功

        return TaskValidationResult(
            is_success=is_success,
            score=score,
            checks=checks,
            error_message=None if is_success else "部分验证未通过",
        )

    def check_target_state(
        self,
        target_state: dict[str, Any],
        execution_result: dict[str, Any],
    ) -> dict[str, Any]:
        """检查目标状态"""
        results = {}

        for key, expected_value in target_state.items():
            actual_value = execution_result.get(key)

            if isinstance(expected_value, bool):
                results[key] = {
                    "expected": expected_value,
                    "actual": bool(actual_value),
                    "passed": bool(actual_value) == expected_value,
                }
            else:
                results[key] = {
                    "expected": expected_value,
                    "actual": actual_value,
                    "passed": actual_value == expected_value,
                }

        return results


class MockValidator(TaskValidator):
    """
    Mock 验证器

    用于演示目的，不做真实验证
    """

    def validate(
        self,
        task: TaskDefinition,
        execution_result: dict[str, Any],
    ) -> TaskValidationResult:
        """Mock 验证 - 总是返回成功"""
        # 检查是否有执行结果
        has_result = bool(execution_result)
        has_tools_called = len(execution_result.get("tool_calls", [])) > 0

        # 简单判断
        is_success = has_result and has_tools_called

        return TaskValidationResult(
            is_success=is_success,
            score=1.0 if is_success else 0.5,
            checks=[
                {
                    "name": "execution_completed",
                    "passed": has_result,
                    "details": "Task was executed",
                },
                {
                    "name": "tools_used",
                    "passed": has_tools_called,
                    "details": f"Used {len(execution_result.get('tool_calls', []))} tools",
                },
            ],
            error_message=None if is_success else "Task may not have been completed",
        )
