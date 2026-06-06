"""Base tool infrastructure for myClaw - Custom implementation without LangChain."""

from abc import ABC, abstractmethod
from typing import Any, Callable
import inspect


class BaseTool(ABC):
    """Abstract base class for myClaw tools.

    Subclasses must implement the `_run` method for synchronous execution.
    Supports both sync and async execution.
    """

    name: str
    description: str
    args_schema: type | None = None

    @abstractmethod
    def _run(self, **kwargs: Any) -> Any:
        """Execute the tool synchronously.

        Args:
            **kwargs: Tool arguments.

        Returns:
            Tool result.
        """
        raise NotImplementedError("Subclasses must implement _run")

    def invoke(self, args: dict | None = None, **kwargs: Any) -> Any:
        """Synchronous tool invocation.

        Args:
            args: Dict of arguments (alternative to kwargs).
            **kwargs: Keyword arguments.
        """
        if args is not None:
            return self._run(**args)
        return self._run(**kwargs)

    async def ainvoke(self, **kwargs: Any) -> Any:
        """Asynchronous tool invocation."""
        import asyncio
        return await asyncio.to_thread(self._run, **kwargs)

    def get_schema(self) -> dict[str, Any]:
        """Get the tool schema for LLM binding."""
        schema = {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            }
        }

        # Try Pydantic model first
        if self.args_schema and hasattr(self.args_schema, "model_fields"):
            for field_name, field_info in self.args_schema.model_fields.items():
                schema["parameters"]["properties"][field_name] = {
                    "type": "string",
                    "description": field_info.description or "",
                }
                if field_info.is_required():
                    schema["parameters"]["required"].append(field_name)

        return schema


class FunctionTool(BaseTool):
    """A tool created from a plain function."""

    def __init__(self, func: Callable, name: str, description: str, parameters: dict):
        self._func = func
        self.name = name
        self.description = description
        self._parameters = parameters  # Store extracted parameters

    def _run(self, **kwargs: Any) -> Any:
        return self._func(**self._coerce_kwargs(kwargs))

    def _coerce_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Coerce simple JSON scalar strings to annotated Python types."""
        sig = inspect.signature(self._func)
        coerced = dict(kwargs)
        for name, param in sig.parameters.items():
            if name not in coerced:
                continue
            value = coerced[name]
            if value is None:
                continue
            try:
                if param.annotation is int and isinstance(value, str):
                    coerced[name] = int(value)
                elif param.annotation is float and isinstance(value, str):
                    coerced[name] = float(value)
                elif param.annotation is bool and isinstance(value, str):
                    coerced[name] = value.lower() in {"1", "true", "yes", "on"}
            except ValueError:
                continue
        return coerced

    def get_schema(self) -> dict[str, Any]:
        """Get the tool schema with parameters extracted from function signature."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self._parameters.get("properties", {}),
                "required": self._parameters.get("required", []),
            }
        }


def _extract_parameters_from_signature(func: Callable) -> dict:
    """Extract parameter schema from a function's type hints."""
    sig = inspect.signature(func)
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        # Skip *args and **kwargs
        if param_name in ('args', 'kwargs'):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        json_type = "string"
        if param.annotation != inspect.Parameter.empty:
            if param.annotation is int:
                json_type = "integer"
            elif param.annotation is float:
                json_type = "number"
            elif param.annotation is bool:
                json_type = "boolean"

        properties[param_name] = {
            "type": json_type,
        }
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "properties": properties,
        "required": required,
    }


def tool(func: Callable) -> FunctionTool:
    """Decorator to create a tool from a function.

    Automatically extracts parameter schema from function signature.

    Usage:
        @tool
        def get_time() -> str:
            '''Get the current time.'''
            return datetime.now().isoformat()

        @tool
        def calculator(expression: str) -> str:
            '''Evaluate a math expression.

            Args:
                expression: The math expression to evaluate.
            '''
            return str(eval(expression, {"__builtins__": {}}, {}))
    """
    func_name = func.__name__
    func_doc = func.__doc__ or ""

    # Get first line of description
    if func_doc.strip():
        first_line = func_doc.strip().split("\n")[0]
    else:
        first_line = func_name

    # Extract parameters from function signature
    parameters = _extract_parameters_from_signature(func)

    return FunctionTool(
        func=func,
        name=func_name,
        description=first_line,
        parameters=parameters,
    )
