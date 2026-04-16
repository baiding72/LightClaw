# LightClaw 失败类型定义

## 概述

本文档定义 LightClaw 系统中的失败类型分类体系。这些失败类型贯穿日志记录、数据池构建和评测分析。

## 失败类型枚举

### 工具相关失败

#### wrong_tool
**定义**: Agent 选择了错误的工具来完成任务。

**触发条件**:
- 调用的工具与当前任务不匹配
- 存在更合适的工具但未选择

**示例**:
```
任务: 创建日历事件
错误调用: add_todo (应该调用 add_calendar_event)
```

#### wrong_args
**定义**: 工具参数填写错误。

**触发条件**:
- 缺少必需参数
- 参数类型错误
- 参数值无效

**示例**:
```
调用: add_calendar_event
错误: start_time 格式错误 "2024/01/01" (应为 "2024-01-01 10:00")
```

#### tool_runtime_error
**定义**: 工具执行过程中发生运行时错误。

**触发条件**:
- 网络请求失败
- 文件操作失败
- 外部服务不可用

**示例**:
```
调用: open_url
错误: 连接超时
```

### GUI 相关失败

#### gui_click_miss
**定义**: 点击操作未命中目标元素。

**触发条件**:
- 选择器找不到元素
- 元素被遮挡
- 页面未完全加载

**示例**:
```
调用: click
选择器: #submit-btn
错误: Element not found
```

#### gui_wrong_element
**定义**: 点击了错误的元素。

**触发条件**:
- 选择器匹配到多个元素
- 选择了视觉相似但功能不同的元素

**示例**:
```
目标: 点击"提交"按钮
实际: 点击了"重置"按钮 (两个按钮样式相似)
```

#### gui_state_stale
**定义**: GUI 状态已过期（页面已变化）。

**触发条件**:
- 页面导航后选择器失效
- 动态内容更新
- 弹窗出现

**示例**:
```
选择器基于旧页面状态
页面已刷新，元素不再存在
```

#### state_loss_after_navigation
**定义**: 页面跳转后状态丢失。

**触发条件**:
- 导航到新页面后无法恢复上下文
- 表单数据在跳转后丢失

**示例**:
```
填写表单后点击链接
页面跳转，表单数据丢失
```

### 规划相关失败

#### planning_error
**定义**: 任务规划出现错误。

**触发条件**:
- 任务理解错误
- 步骤顺序错误
- 忽略重要约束

**示例**:
```
任务: 先搜索再创建待办
错误: 直接创建待办，跳过搜索步骤
```

#### observation_error
**定义**: 观察结果理解错误。

**触发条件**:
- 误判工具执行结果
- 忽略关键信息

**示例**:
```
工具返回错误信息
Agent 误认为执行成功
```

### 恢复相关

#### repair_success
**定义**: 失败后成功修复。

**触发条件**:
- 检测到错误
- 执行修复操作
- 任务最终成功

**示例**:
```
第一次调用失败 (wrong_args)
修正参数后重试成功
```

#### repair_failed
**定义**: 尝试修复但最终失败。

**触发条件**:
- 多次重试均失败
- 无法找到有效的修复策略

**示例**:
```
重试 3 次后仍然失败
任务标记为失败
```

## 失败类型属性

每种失败类型有以下属性：

| 类型 | 可恢复 | 需要 LLM 干预 | 需要 GUI 更新 |
|------|--------|---------------|---------------|
| wrong_tool | 是 | 是 | 否 |
| wrong_args | 是 | 是 | 否 |
| tool_runtime_error | 是 | 否 | 否 |
| gui_click_miss | 是 | 否 | 是 |
| gui_wrong_element | 是 | 是 | 是 |
| gui_state_stale | 是 | 否 | 是 |
| state_loss_after_navigation | 是 | 否 | 是 |
| planning_error | 是 | 是 | 否 |
| observation_error | 是 | 是 | 否 |

## 失败处理策略

### 自动重试
对于 `tool_runtime_error`、`gui_click_miss` 等可自动重试的错误：

```python
result = await executor.execute_with_retry(
    tool_name, tool_args,
    max_retries=3
)
```

### 参数修正
对于 `wrong_args`，由 RecoveryManager 分析并建议修正：

```python
fix = await recovery.suggest_args_fix(
    tool_name, tool_args, error
)
```

### 工具替换
对于 `wrong_tool`，重新规划选择正确的工具：

```python
alternative = await recovery.suggest_alternative_tool(
    wrong_tool, state
)
```

### GUI 重新定位
对于 GUI 相关失败，重新获取页面状态：

```python
await browser.refresh()
await take_screenshot()
```

## 统计分析

系统会统计各失败类型的分布：

```python
failure_distribution = {
    "wrong_tool": 5,
    "wrong_args": 12,
    "gui_click_miss": 8,
    "tool_runtime_error": 3,
}
```

这些统计用于：
- 识别 Agent 能力短板
- 指导数据增强方向
- 评估恢复策略效果
