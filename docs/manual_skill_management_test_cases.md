# Skill 管理手动测试用例

这些用例用于手动验证本轮关于 skill metadata、registry、工具列表展示和 help/run 约束的改动，并保留 trace/log 供后续审查。

## 准备工作

1. 保持本地客户端打开。当前 Tauri dev server 通常是 `http://127.0.0.1:1420/`。
2. 如果你想在「工具」视图里看到动态 skill，请使用「示例 Skill」里的内容创建 `workspace/office/skills/metadata_demo/SKILL.md`。
3. 如果创建 skill 前已经打开了「工具」视图，请在客户端里点击刷新，或重新打开该视图。

## 示例 Skill

创建 `workspace/office/skills/metadata_demo/SKILL.md`：

```markdown
---
name: metadata-demo
description: Demo skill for validating LightClaw skill metadata.
trigger: user asks to inspect skill metadata or run a metadata demo
do-not-trigger: user asks for browser automation or unrelated app debugging
user-invocable: true
disable-auto-invoke: false
argument-hint: <metadata demo request>
allowed-tools:
  - execute_office_shell
tags:
  - smoke
  - metadata
---

# Metadata Demo

Use this skill to verify that LightClaw loads skill metadata, shows the manual on `mode="help"`, and can run a sandboxed command on `mode="run"`.

Suggested command:

```bash
echo metadata-demo-ok
```
```

## 用例 1：工具视图展示动态 Skill Metadata

目标：验证 `list_agent_tools` 能返回动态 skill metadata，并且 UI 能正确展示。

步骤：

1. 打开左侧栏的「工具」视图。
2. 如有需要，点击刷新。
3. 找到 `metadata-demo` 工具卡片。
4. 确认卡片展示：
   - risk 为 `low`
   - permission 为 `tool:execute`
   - 显示 `user-invocable`
   - tags 包含 `smoke, metadata`
   - 参数包含 `mode` 和 `command`

期望证据：

- 截图，或记录 `metadata-demo` 卡片的关键字段。
- 客户端没有可见错误。

## 用例 2：聊天先读取 Skill Help，再执行 Run

目标：验证模型能先读取 skill manual，再执行建议命令。

输入提示词：

```text
使用 metadata-demo skill。先读取这个 skill 的 help，然后运行建议命令，最后告诉我工具返回了什么。
```

期望 trace：

- 出现一次 `metadata-demo` 的 `tool_call`，参数包含 `mode="help"`。
- 随后出现一次 `metadata-demo` 的 `tool_call`，参数包含 `mode="run"`。
- run 对应的 `tool_result` 包含 `metadata-demo-ok`。

期望回答：

- 回答中提到 `metadata-demo-ok`。

需要保留的日志证据：

- 客户端显示的 run path。
- trace 事件列表里能看到 help 和 run 两次工具调用。

## 用例 3：`blocked-tools` 能阻止 Run

目标：验证 `blocked-tools` 会限制当前 shell-backed run 路径。

修改示例 skill 的 frontmatter：

```yaml
blocked-tools:
  - execute_office_shell
```

删除或忽略 `allowed-tools`。

输入提示词：

```text
使用 metadata-demo skill。读取 help 后尝试运行 echo should-not-run，并告诉我结果。
```

期望 trace：

- `metadata-demo` 的 help 调用成功。
- `metadata-demo` 的 run 调用返回错误。
- run 结果包含 `blocked-tools` 和 `execute_office_shell`。
- 不应该出现 shell 实际执行后的 stdout `should-not-run`。

## 用例 4：`allowed-tools` 排除 Shell 时能阻止 Run

目标：验证当 `allowed-tools` 不包含 `execute_office_shell` 时，run 路径会被拒绝。

修改示例 skill 的 frontmatter：

```yaml
allowed-tools:
  - read_office_file
```

输入提示词：

```text
使用 metadata-demo skill。读取 help 后尝试运行 echo should-not-run，并告诉我结果。
```

期望 trace：

- `metadata-demo` 的 help 调用成功。
- `metadata-demo` 的 run 调用返回错误。
- run 结果包含 `allowed-tools` 和 `execute_office_shell`。

## 用例 5：已有内置工具仍然正常工作

目标：验证动态 skill 改动没有影响普通内置工具。

输入提示词：

```text
帮我算一下 25 * 48。
```

```text
看看 office 里有什么文件。
```

期望 trace：

- 计算提示词调用 `calculator`，并回答 `1200`。
- 文件查看提示词调用 `list_office_files`。
- 不应意外调用 `metadata-demo`。

## 跑完后发我什么

跑完后请发我：

1. 客户端里的 run log 路径，通常在 `runs/*.jsonl` 下。
2. 你实际跑了哪些用例。
3. 是否看到异常 UI 行为，或异常回答文本。

我会检查 trace 事件里的工具调用顺序、metadata 是否存在、policy gate 决策，以及工具结果是否符合预期。
