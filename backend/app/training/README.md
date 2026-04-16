# Training Data Export

This module provides functionality for exporting training data from trajectories.

## Overview

LightClaw 支持导出以下类型的训练数据：

### 1. Tool-use 数据

用于训练模型的工具选择和参数填充能力。

**适用模型**: Qwen2.5-3B-Instruct, GLM-4-9B-Chat

**数据格式**:
```json
{
  "id": "tooluse_xxx_0",
  "instruction": "创建一个待办事项...",
  "state_summary": "任务开始",
  "available_tools": ["add_todo", "write_note"],
  "previous_actions": [],
  "target_action": "add_todo",
  "target_args": {"title": "完成报告", "priority": "high"},
  "is_positive": true
}
```

### 2. Self-correction 数据

用于训练模型的错误纠正能力。

**适用模型**: Qwen2.5-3B-Instruct

**数据格式**:
```json
{
  "id": "correction_xxx_0",
  "instruction": "...",
  "failed_action": "click",
  "failed_args": {"selector": "#btn1"},
  "error_type": "gui_click_miss",
  "error_message": "Element not found",
  "corrected_action": "click",
  "corrected_args": {"selector": "#btn2"}
}
```

### 3. GUI Grounding 数据

用于训练模型的 GUI 元素定位能力。

**适用模型**: Qwen2-VL-2B-Instruct

**数据格式**:
```json
{
  "id": "gui_xxx_0",
  "instruction": "点击提交按钮",
  "screenshot_path": "screenshots/xxx.png",
  "action_type": "click",
  "target_element": "#submit-btn",
  "target_description": "ID 为 submit-btn 的元素"
}
```

## 使用方法

```python
from app.training import ToolUseExporter, GUIGroundingExporter

# 导出 tool-use 数据
tool_exporter = ToolUseExporter()
tool_exporter.export_samples(trajectories)

# 导出 GUI grounding 数据
gui_exporter = GUIGroundingExporter()
gui_exporter.export_samples(trajectories)
```

## TODO

- [ ] 实现 bounding box 标注
- [ ] 支持更多模型格式
- [ ] 实现数据增强
- [ ] 添加数据质量检查
