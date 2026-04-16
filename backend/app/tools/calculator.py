"""
计算器工具
"""
import time
import re
from typing import Any

from app.core.enums import FailureType
from app.schemas.tool import ToolParameter
from app.tools.base import BaseTool, ToolContext, ToolResult


class CalculatorTool(BaseTool):
    """计算器工具"""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "执行数学计算。支持加减乘除、幂运算等基本运算。"

    @property
    def category(self) -> str:
        return "utility"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="expression",
                type="string",
                description="数学表达式，如 '2 + 3 * 4' 或 '(10 - 5) / 2'",
                required=True,
            ),
        ]

    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        start_time = time.time()

        expression = args.get("expression", "")
        if not expression:
            return self.create_error_result(
                "计算表达式不能为空",
                FailureType.WRONG_ARGS,
            )

        # 安全检查：只允许数学字符
        allowed_chars = set("0123456789+-*/().% ")
        if not all(c in allowed_chars for c in expression):
            return self.create_error_result(
                "表达式包含非法字符，只允许数字和基本运算符",
                FailureType.WRONG_ARGS,
            )

        try:
            # 安全计算
            # 使用 eval 但限制为数学运算
            result = eval(expression, {"__builtins__": {}}, {})

            latency_ms = int((time.time() - start_time) * 1000)

            return self.create_success_result(
                {
                    "expression": expression,
                    "result": result,
                    "type": type(result).__name__,
                },
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return self.create_error_result(
                f"计算错误: {str(e)}",
                FailureType.WRONG_ARGS,
                latency_ms=latency_ms,
            )
