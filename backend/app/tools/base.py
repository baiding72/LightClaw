"""
工具基类定义
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import FailureType
from app.schemas.tool import ToolParameter, ToolResult, ToolSchema


@dataclass
class ToolContext:
    """工具执行上下文"""
    task_id: str
    step_index: int
    trajectory_id: str
    screenshot_dir: Optional[str] = None
    browser_page: Optional[Any] = None  # Playwright Page 对象
    db_session: Optional[AsyncSession] = None


class BaseTool(ABC):
    """工具基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        """工具类别"""
        pass

    @property
    def parameters(self) -> list[ToolParameter]:
        """工具参数列表"""
        return []

    @property
    def return_type(self) -> str:
        """返回值类型"""
        return "object"

    @property
    def return_description(self) -> str:
        """返回值描述"""
        return "工具执行结果"

    @property
    def examples(self) -> list[dict[str, Any]]:
        """使用示例"""
        return []

    def get_schema(self) -> ToolSchema:
        """获取工具 Schema"""
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            return_type=self.return_type,
            return_description=self.return_description,
            examples=self.examples,
        )

    def get_openai_schema(self) -> dict[str, Any]:
        """获取 OpenAI 格式的工具定义"""
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    @abstractmethod
    async def execute(
        self,
        args: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        """
        执行工具

        Args:
            args: 工具参数
            context: 执行上下文

        Returns:
            工具执行结果
        """
        pass

    def validate_args(self, args: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        验证参数

        Args:
            args: 待验证的参数

        Returns:
            (是否有效, 错误信息)
        """
        for param in self.parameters:
            if param.required and param.name not in args:
                return False, f"Missing required parameter: {param.name}"

            if param.name in args:
                value = args[param.name]

                # 类型检查
                if param.type == "string" and not isinstance(value, str):
                    return False, f"Parameter {param.name} must be a string"
                elif param.type == "integer" and not isinstance(value, int):
                    return False, f"Parameter {param.name} must be an integer"
                elif param.type == "number" and not isinstance(value, (int, float)):
                    return False, f"Parameter {param.name} must be a number"
                elif param.type == "boolean" and not isinstance(value, bool):
                    return False, f"Parameter {param.name} must be a boolean"
                elif param.type == "array" and not isinstance(value, list):
                    return False, f"Parameter {param.name} must be an array"
                elif param.type == "object" and not isinstance(value, dict):
                    return False, f"Parameter {param.name} must be an object"

                # 枚举检查
                if param.enum and value not in param.enum:
                    return False, f"Parameter {param.name} must be one of {param.enum}"

                # 范围检查
                if param.min_value is not None and isinstance(value, (int, float)):
                    if value < param.min_value:
                        return False, f"Parameter {param.name} must be >= {param.min_value}"
                if param.max_value is not None and isinstance(value, (int, float)):
                    if value > param.max_value:
                        return False, f"Parameter {param.name} must be <= {param.max_value}"

        return True, None

    def create_success_result(
        self,
        result: Any,
        latency_ms: Optional[int] = None,
        screenshot_path: Optional[str] = None,
    ) -> ToolResult:
        """创建成功结果"""
        return ToolResult(
            success=True,
            result=result,
            latency_ms=latency_ms,
            screenshot_path=screenshot_path,
        )

    def create_error_result(
        self,
        error: str,
        error_type: FailureType = FailureType.TOOL_RUNTIME_ERROR,
        latency_ms: Optional[int] = None,
    ) -> ToolResult:
        """创建错误结果"""
        return ToolResult(
            success=False,
            error=error,
            error_type=error_type.value,
            latency_ms=latency_ms,
        )
