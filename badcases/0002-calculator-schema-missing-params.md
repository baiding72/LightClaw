# Bad Case 0002: Calculator 工具 Schema 参数缺失

## 时间
2026-05-19

## 问题描述
`calculator` 工具第一次调用时，LLM 没有传递 `expression` 参数，导致调用失败：
```
Error: calculator() missing 1 required positional argument: 'expression'
```

## 根因分析

### 1. Schema 生成问题 (Tool 定义)

当前 `get_schema()` 只处理 `args_schema` 是 Pydantic model 的情况，
没有从 Python 函数签名中提取参数信息。

`calculator` 是用 `@tool` 装饰器从普通函数创建的：

```python
@tool
def calculator(expression: str) -> str:
    """..."""
    ...
```

**当前 Schema 输出**:
```json
{
  "name": "calculator",
  "description": "Evaluate a simple math expression.",
  "parameters": {
    "type": "object",
    "properties": {},   // ← 空！LLM 不知道参数结构
    "required": []
  }
}
```

**LLM 只看到**:
```
- calculator: Evaluate a simple math expression.
```

没有参数信息，LLM 可能不传参数就调用。

### 2. LLM Model 问题

MiniMax 模型在第一次推理时没有正确理解 `calculator` 需要 `expression` 参数。

## 影响
- 工具调用多走一轮（Turn 2 才传参成功）
- 浪费一次 LLM 调用
- 在复杂场景下可能多次重试

## 解决方案

### 方案 A: 增强 @tool 装饰器，自动从函数签名提取 schema

```python
import inspect

def tool(func: Callable) -> FunctionTool:
    sig = inspect.signature(func)
    params = {}
    required = []

    for name, param in sig.parameters.items():
        # 跳过无类型的参数 (如 *args, **kwargs)
        if param.annotation != inspect.Parameter.empty:
            param_type = "string"  # 简化处理
            params[name] = {"type": param_type}

    # 构建完整 schema
    schema = {
        "name": func.__name__,
        "description": func.__doc__.strip().split("\n")[0],
        "parameters": {
            "type": "object",
            "properties": params,
            "required": required,
        }
    }
```

### 方案 B: 在 System Prompt 中明确工具调用格式

```python
SYSTEM_PROMPT += """

IMPORTANT: When calling a tool, you MUST provide ALL required arguments.
- calculator: requires "expression" parameter, e.g., {"expression": "1+1"}
- echo: requires "message" parameter, e.g., {"message": "hello"}
```

### 方案 C: 使用 Pydantic ArgsSchema

```python
from pydantic import BaseModel

class CalculatorArgs(BaseModel):
    expression: str

@tool
def calculator(expression: str) -> str:
    ...
    return str(result)

calculator.args_schema = CalculatorArgs
```

## 验证方式

```python
# 验证 schema 完整性
harness = create_agent_harness(llm)
print(harness.tool_schemas)
# 应该看到:
# {"name": "calculator", ..., "parameters": {"properties": {"expression": {"type": "string"}}, "required": ["expression"]}}
```

## 状态
[x] 已修复 - 增强 @tool 装饰器，自动从函数签名提取 parameters