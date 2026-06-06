# myClaw 工具机制

## Tool Schema 生成

`@tool` 装饰器从函数签名自动提取参数 schema：

```python
# core/tools/base.py
def _extract_parameters_from_signature(func):
    sig = inspect.signature(func)
    properties = {}
    required = []
    for param_name, param in sig.parameters.items():
        json_type = "string"
        if param.annotation is int: json_type = "integer"
        elif param.annotation is float: json_type = "number"
        elif param.annotation is bool: json_type = "boolean"
        properties[param_name] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    return {"properties": properties, "required": required}
```

**生成的 OpenAI-compatible schema**:

```python
{
    "name": "calculator",
    "description": "Evaluate a math expression",
    "parameters": {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"]
    }
}
```

## Tool 分发绑定到 LLM

```python
# core/agent.py
self.tool_schemas = [t.get_schema() for t in self.tools]
self.llm_with_tools = self.llm.bind_tools(self.tool_schemas)
response = self.llm_with_tools.invoke(messages)
```

## Tool 执行与返回

```python
# core/agent.py _execute_tool()
try:
    clean_args = {k: v for k, v in args.items() if not k.startswith("_")}
    result = tool.invoke(**clean_args)
    return str(result) if result is not None else "Tool executed successfully", gate
except Exception as e:
    return f"Error: {str(e)}", gate
```

统一转为字符串返回。

## 调用流程

```
用户输入 → AgentHarness.run()
         ↓
    LLM 判断需要调用 tool → response.tool_calls
         ↓
    _execute_tool(tool_name, args)
         ↓
    Pre-validation (检查 required params)
         ↓
    tool.invoke(**clean_args) → 返回字符串
         ↓
    state.add_tool_message(name, content)
         ↓
    下一轮 ReAct，LLM 读取 tool result
```