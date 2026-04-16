"""
LLM Prompt 模板

定义 Agent 运行时使用的各种 prompt
"""

SYSTEM_PROMPT = """你是一个智能助手，帮助用户完成各种任务。

你有以下能力：
1. 信息检索：搜索网页、打开网页、读取页面内容
2. 内容整理：提取关键信息、写入笔记
3. 待办管理：创建待办事项、设置截止时间和优先级
4. 日程管理：创建日历事件
5. 网页交互：点击、输入、选择、提交表单

在执行任务时，请：
1. 仔细理解用户的需求
2. 制定清晰的执行计划
3. 按步骤执行，每步只调用一个工具
4. 观察执行结果，必要时进行调整
5. 如果遇到错误，尝试修复或调整策略

当前可用工具：
{tools_description}

当前状态：
{state_summary}

请根据用户指令和当前状态，选择合适的工具执行下一步操作。
"""

PLANNING_PROMPT = """分析以下任务，制定执行计划。

用户指令：{instruction}

当前状态：
{state_summary}

可用工具：
{tools_description}

请输出：
1. 任务理解（简要描述任务目标）
2. 执行计划（列出主要步骤）
3. 预期结果（描述成功完成后的状态）

保持简洁，每部分不超过 3 行。
"""

REFLECTION_PROMPT = """上一步操作遇到了问题，请分析原因并尝试修复。

用户指令：{instruction}
当前状态：{state_summary}
执行的工具：{tool_name}
工具参数：{tool_args}
错误类型：{error_type}
错误信息：{error_message}

请分析：
1. 可能的原因
2. 建议的修复方案
3. 下一步应该执行的操作

如果需要重试，请说明修改后的参数。
如果需要换用其他工具，请说明原因和新工具。
如果认为任务无法完成，请说明原因。
"""

OBSERVATION_PROMPT = """根据工具执行结果，总结当前状态变化。

执行的步骤：{step_index}
工具：{tool_name}
结果：{tool_result}

请用 1-2 句话总结：
1. 当前步骤完成了什么
2. 状态有什么变化
3. 还需要做什么
"""

SUMMARY_PROMPT = """任务已完成，请总结执行结果。

用户指令：{instruction}
执行步骤数：{total_steps}
失败重试次数：{retry_count}

请用 2-3 句话总结：
1. 是否完成了用户的指令
2. 主要完成了哪些操作
3. 有哪些需要注意的问题
"""


def format_tools_description(tools: list[dict]) -> str:
    """格式化工具描述"""
    lines = []
    for tool in tools:
        params = tool.get("parameters", {}).get("properties", {})
        required = tool.get("parameters", {}).get("required", [])

        param_strs = []
        for name, schema in params.items():
            req = " (必需)" if name in required else ""
            param_strs.append(f"  - {name}{req}: {schema.get('description', '')}")

        lines.append(f"- {tool['name']}: {tool['description']}")
        if param_strs:
            lines.extend(param_strs)

    return "\n".join(lines)
