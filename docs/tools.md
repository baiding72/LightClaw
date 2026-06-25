# myClaw Tool 系统设计文档

## Tool 实现机制

### 不太常规的 Tool 实现

**1. `web_search` - 爬虫解析**
```python
@tool
def web_search(query: str, max_results: int = 5) -> str:
    # 用 urllib 抓 DuckDuckGo HTML
    # 正则解析 rel=nofollow 链接（DuckDuckGo 重定向 URL）
    # 解码 uddg= 参数得到真实 URL
    # 去重 + 截断
```

**2. `schedule_task` - 持久化调度**
```python
@tool
def schedule_task(target_time: str, description: str, repeat: str = None, repeat_count: int = None) -> str:
    # 存到 ~/.myclaw/tasks/tasks.json
    # 支持 repeat=daily/hourly/weekly + repeat_count
    # 生成 8 位短 UUID 作为 task_id
```

**3. `save_note/search_notes` - JSON 文件存储**
```python
# 每个 note 存一个 JSON 文件: ~/.myclaw/notes/<id>.json
note_data = {"id": "a9b879af", "title": "...", "content": "...", "created_at": "..."}
```

---

## Tool 管理/注册/调用/执行

### 1. 管理 - @tool 装饰器

```python
# myClaw/core/tools/base.py

def tool(func: Callable) -> FunctionTool:
    """装饰器：自动提取函数签名生成 schema"""

    # 1. 从函数签名提取参数
    parameters = _extract_parameters_from_signature(func)

    # 2. 包装成 FunctionTool
    return FunctionTool(
        func=func,
        name=func.__name__,
        description=func.__doc__.strip().split("\n")[0],  # 取第一行作为描述
        parameters=parameters,
    )
```

### 2. 注册 - ALL_TOOLS 列表

```python
# builtins.py 底部

ALL_TOOLS = [
    get_time,
    calculator,
    echo,
    web_search,
    read_url,
    schedule_task,
    list_tasks,
    ...  # 所有工具都注册在这里
]
```

### 3. 调用 - AgentHarness 初始化时

```python
# agent.py

class AgentHarness:
    def __init__(self, llm, tools=None, ...):
        # 如果没传入 tools，用 ALL_TOOLS
        self.tools = tools or ALL_TOOLS

        # 构建 schema 列表 + name->tool 映射
        self.tool_schemas = [t.get_schema() for t in self.tools]
        self.tool_map = {t.name: t for t in self.tools}

        # 构建 system prompt（注入工具描述）
```

### 4. 执行 - ReAct 循环中

```python
# agent.py run()

for turn in range(self.max_turns):
    messages = self._build_messages(state)

    # 调用 LLM，绑定 tools
    self.llm_with_tools = self.llm.bind_tools(self.tool_schemas)
    response = self.llm_with_tools.invoke(messages)

    # LLM 返回 tool_calls
    if response.tool_calls:
        for tc in response.tool_calls:
            tool_name = tc["name"]
            args = tc["args"]

            # 从 tool_map 找到工具，执行
            result = self.tool_map[tool_name].invoke(**args)

            # 结果加入 state.messages
            state.add_tool_result(tool_name, result, tool_call_id)
```

### 5. Schema 生成

```python
# base.py

class FunctionTool(BaseTool):
    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self._parameters["properties"],  # 从装饰器提取
                "required": self._parameters["required"],
            }
        }
```

---

## 如何拓展成 Skill（渐进式加载）

参考 Claude Code 和 Nanobot 的设计：

### 目标架构

```python
# 当前：所有工具平铺，注册时全部注入
ALL_TOOLS = [get_time, calculator, web_search, ...]  # 15 个

# 未来：分层 + 延迟加载
TOOLS = {
    "builtin": [get_time, calculator, echo],  # 始终加载
    "productivity": [web_search, read_url, save_note, ...],  # 按需
    "skills": {},  # 动态发现
}

# Skill 文件结构
skills/
  search_skill.py    # 包含 web_search, read_url 等
  office_skill.py    # 包含 file tools
  calendar_skill.py  # 包含 schedule_task 等
```

### 拓展步骤

1. **创建 Skill 目录** `myClaw/skills/`
2. **定义 Skill 接口** - 每个 skill 有 `name`, `description`, `tools[]`
3. **动态发现** - 从目录扫描 `.py` 文件，自动注册
4. **延迟加载** - 只在 system prompt 注入描述，调用时才加载完整代码
5. **MCP 集成** - 实现 MCP 客户端，从 MCP 服务器动态发现工具

### Skill 定义示例

```python
# myClaw/skills/search_skill.py

class SearchSkill:
    name = "search"
    description = "Web search and content reading for researching information"

    tools = [web_search, read_url]

    # 延迟加载：只返回描述，不加载实现
    @staticmethod
    def get_manifest():
        return {
            "name": "search",
            "description": "Web search and content reading...",
            "tools": [{"name": t.name, "description": t.description} for t in SearchSkill.tools]
        }
```

---

## 流程图

```
注册 (@tool)                  初始化 (create_agent_harness)
     │                              │
     ▼                              ▼
ALL_TOOLS = [              harness = AgentHarness(
  get_time,                     tools = tools or ALL_TOOLS
  calculator,                   tool_map = {t.name: t for t in tools}
  ...                           system_prompt += tool_descriptions
]

执行 (run loop)
     │
     ▼
LLM 返回 tool_calls
     │
     ▼
harness._execute_tool(name, args)
     │
     ├─── tool_map[name].invoke(**args)
     │
     └─── 返回结果 string
```

---

## 当前所有 Tools

```
P0 基础工具:
  get_time      - 获取当前时间
  calculator    - 数学计算
  echo          - 回显测试
  web_search    - 网页搜索
  read_url      - 读取网页内容

P1 文件操作:
  list_office_files  - 列出目录
  read_office_file   - 读取文件
  write_office_file  - 写入文件

P1 任务调度:
  schedule_task - 创建任务
  list_tasks    - 查看任务列表
  cancel_task   - 取消任务
  modify_task   - 修改任务

P1 笔记/Memory:
  save_note     - 保存笔记
  search_notes  - 搜索笔记
  read_note     - 读取笔记
  save_user_profile - 保存用户偏好
  read_user_profile - 读取用户偏好

P1 系统:
  get_system_info - 系统信息
```

---

## 数据存储位置

| 数据类型 | 存储位置 |
|---------|---------|
| Tasks | `~/.myclaw/tasks/tasks.json` |
| Notes | `~/.myclaw/notes/<note-id>.json` |
| User Profile | `~/.myclaw/profile.md` |
| Workspace Files | `workspace/office/` (沙盒) |

## Skill Frontmatter Metadata

Dynamic skills are loaded from two roots:

| Root | Purpose | Override behavior |
| --- | --- | --- |
| `skills/builtin/<skill-name>/SKILL.md` | Versioned built-in skills shipped with LightClaw. | Lower priority. |
| `workspace/office/skills/<skill-name>/SKILL.md` | User-editable workspace skills. | Overrides a built-in skill with the same `name`. |

LightClaw reads the frontmatter block, exposes each skill as one lazy tool, and loads the manual only when the model calls the skill with `mode="help"`.

Supported fields:

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `name` | string | folder name | Tool-safe skill name. |
| `description` | string | generated fallback | Short summary shown in the tool list. |
| `trigger` | string | empty | When the agent should consider this skill. |
| `do-not-trigger` | string | empty | When the agent should avoid this skill. |
| `user-invocable` | boolean | `true` | Whether users can explicitly request this skill. |
| `disable-auto-invoke` | boolean | `false` | Whether the agent should avoid automatic invocation. |
| `argument-hint` | string | empty | Short usage hint for user-facing skill lists. |
| `allowed-tools` | list | empty | Optional allow-list for the skill run backend. Empty means no extra restriction. |
| `blocked-tools` | list | empty | Optional deny-list for the skill run backend. |
| `tags` | list | empty | UI and routing labels. |

`allowed-tools` and `blocked-tools` are restrictions, not permission grants. In the current runtime, `mode="run"` can only use `execute_office_shell`, and that command still runs inside the office sandbox.

### Built-in Skill Seed Set

The first built-in migration intentionally includes Abu skills that are mostly instruction-driven and do not require Abu-only tools:

- `doc-coauthoring`
- `internal-comms`
- `reflect`
- `mermaid-diagram`
- `svg-diagram`
- `infographic`
- `html-widget`
- `alert-sop`
- `skill-creator`

These built-ins all block `execute_office_shell` initially, so they can be used to test routing, `mode="help"` loading, context boundaries, and UI visibility without expanding execution permissions.

Deferred Abu skills include browser automation, schedule/trigger, create-agent, document converters, and other skills that depend on Abu-specific tool APIs. Those should be migrated only after LightClaw has equivalent tools and permission scopes.
