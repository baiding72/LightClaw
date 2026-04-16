# LightClaw 数据流水线

## 概述

本文档描述从任务输入到训练数据导出的完整数据流水线。

## 流水线阶段

### 1. 任务输入

用户通过以下方式输入任务：
- 前端 Task Runner 页面
- API 调用
- 内置任务集

```python
# 示例：创建任务
POST /api/tasks
{
    "instruction": "创建一个待办事项",
    "category": "todo_calendar",
    "difficulty": "easy"
}
```

### 2. Agent 执行

Agent Runtime 执行任务，核心流程：

```python
# 简化的执行循环
while not completed:
    # 1. 规划
    decision = await planner.decide_next_action(state, tools)

    # 2. 执行
    result = await executor.execute(tool_name, tool_args)

    # 3. 观察
    observation = await observer.observe(result)

    # 4. 记录
    await gateway.log_step(...)

    # 5. 检查完成
    if should_stop:
        break
```

### 3. 日志记录

Gateway 记录每一步的详细信息：

```json
{
    "event_type": "step",
    "task_id": "task_xxx",
    "step_index": 1,
    "state_summary": "任务开始",
    "chosen_tool": "add_todo",
    "tool_args": {"title": "完成报告", "priority": "high"},
    "tool_result": {"success": true, "todo_id": "todo_xxx"},
    "latency_ms": 150,
    "token_usage": {"total": 100}
}
```

### 4. 轨迹存储

轨迹以 JSONL 格式存储：

```
data/trajectories/
    trajectory_task_001_20240101_120000.jsonl
    trajectory_task_002_20240101_120100.jsonl
    ...
```

每条轨迹包含：
- 任务信息
- 所有步骤
- 工具调用
- 错误信息
- 最终结果

### 5. 样本构建

DataPool Builder 从轨迹中提取样本：

```python
# Tool-use 样本
{
    "sample_type": "tool_use",
    "instruction": "创建待办事项",
    "state_summary": "任务开始",
    "available_tools": ["add_todo", "write_note"],
    "target_action": "add_todo",
    "target_args": {"title": "完成报告"}
}

# Self-correction 样本
{
    "sample_type": "self_correction",
    "failed_action": "click",
    "failed_args": {"selector": "#btn1"},
    "error_type": "gui_click_miss",
    "corrected_action": "click",
    "corrected_args": {"selector": "#btn2"}
}

# GUI Grounding 样本
{
    "sample_type": "gui_grounding",
    "screenshot_path": "screenshots/xxx.png",
    "action_type": "click",
    "target_element": "#submit-btn"
}
```

### 6. 数据导出

支持多种导出格式：

```bash
# 导出所有样本
python scripts/export_samples.py

# 输出文件
data/exports/
    tool_use_20240101.jsonl
    self_correction_20240101.jsonl
    gui_grounding_20240101.jsonl
```

### 7. 微调准备

导出的数据可直接用于微调：

- **Qwen2.5-3B-Instruct**: tool-use, self-correction
- **Qwen2-VL-2B-Instruct**: gui_grounding

## 数据质量

为保证数据质量，系统提供：

1. **失败类型标注**: 每个失败样本都有明确的失败类型
2. **样本筛选**: 支持按类型、难度等筛选
3. **验证规则**: 任务定义中包含自动验证规则
4. **统计分析**: 提供数据集统计信息

## 数据使用建议

### Tool-use 训练

适用于：
- 工具选择能力训练
- 参数填充能力训练
- 多步规划能力训练

建议模型：Qwen2.5-3B-Instruct, GLM-4-9B-Chat

### Self-correction 训练

适用于：
- 错误识别能力训练
- 纠错策略训练
- 重试规划训练

建议模型：Qwen2.5-3B-Instruct

### GUI Grounding 训练

适用于：
- GUI 元素定位训练
- 动作预测训练
- 视觉理解训练

建议模型：Qwen2-VL-2B-Instruct
