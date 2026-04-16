# LightClaw 训练数据导出

## 概述

本文档描述 LightClaw 系统的训练数据导出格式和使用方法。

## 数据类型

### 1. Tool-use 数据

**用途**: 训练模型的工具选择和参数填充能力。

**适用模型**: Qwen2.5-3B-Instruct, GLM-4-9B-Chat

**数据格式**:

```json
{
    "id": "tooluse_task_001_0",
    "instruction": "创建一个待办事项，标题为完成项目报告，截止日期为下周五，优先级为高",
    "state_summary": "任务开始",
    "available_tools": ["add_todo", "write_note", "add_calendar_event"],
    "previous_actions": [],
    "target_action": "add_todo",
    "target_args": {
        "title": "完成项目报告",
        "deadline": "2024-01-19",
        "priority": "high"
    },
    "is_positive": true,
    "metadata": {
        "trajectory_id": "traj_task_001",
        "step_index": 0,
        "category": "todo_calendar",
        "difficulty": "easy"
    }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 样本唯一标识 |
| instruction | string | 用户指令 |
| state_summary | string | 当前状态摘要 |
| available_tools | list | 可用工具列表 |
| previous_actions | list | 之前的动作历史 |
| target_action | string | 正确的工具名 |
| target_args | dict | 正确的参数 |
| is_positive | bool | 是否为正样本 |
| metadata | dict | 元数据 |

### 2. Self-correction 数据

**用途**: 训练模型的错误识别和纠正能力。

**适用模型**: Qwen2.5-3B-Instruct

**数据格式**:

```json
{
    "id": "correction_task_002_0",
    "instruction": "在表单页面填写邮箱并提交",
    "state_summary": "已打开表单页面",
    "available_tools": ["click", "type_text", "take_screenshot"],
    "failed_action": "click",
    "failed_args": {
        "selector": "#submit-btn"
    },
    "error_type": "gui_click_miss",
    "error_message": "Element not found: #submit-btn",
    "corrected_action": "click",
    "corrected_args": {
        "selector": "button[type='submit']"
    },
    "metadata": {
        "failed_step_index": 3,
        "corrected_step_index": 4,
        "recovery_successful": true
    }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| failed_action | string | 失败的工具调用 |
| failed_args | dict | 失败的参数 |
| error_type | string | 错误类型 |
| error_message | string | 错误信息 |
| corrected_action | string | 修正后的工具调用 |
| corrected_args | dict | 修正后的参数 |

### 3. GUI Grounding 数据

**用途**: 训练模型的 GUI 元素定位和动作预测能力。

**适用模型**: Qwen2-VL-2B-Instruct

**数据格式**:

```json
{
    "id": "gui_task_003_2",
    "instruction": "点击提交按钮",
    "screenshot_path": "screenshots/task_003_step2.png",
    "action_type": "click",
    "target_element": "#submit-btn",
    "target_description": "页面底部的蓝色提交按钮",
    "bounding_box": {
        "x": 450,
        "y": 600,
        "width": 100,
        "height": 40
    },
    "action_args": {
        "selector": "#submit-btn"
    },
    "is_success": true,
    "metadata": {
        "step_index": 2,
        "url": "https://example.com/form"
    }
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| screenshot_path | string | 截图文件路径 |
| action_type | string | 动作类型 (click/type/select) |
| target_element | string | 目标元素选择器 |
| target_description | string | 目标元素描述 |
| bounding_box | dict | 目标区域坐标 (可选) |

## 导出脚本

使用 `scripts/export_samples.py` 导出数据：

```bash
cd scripts
uv run python export_samples.py
```

输出文件：
```
data/exports/
    tool_use_20240101_120000.jsonl
    self_correction_20240101_120000.jsonl
    gui_grounding_20240101_120000.jsonl
```

## 数据筛选

支持按以下条件筛选：

```python
# 只导出失败轨迹的样本
exporter.export_samples(
    trajectory_types=[TrajectoryType.FAILURE, TrajectoryType.REPAIR]
)

# 只导出特定错误类型
exporter.export_samples(
    failure_types=[FailureType.GUI_CLICK_MISS, FailureType.WRONG_ARGS]
)
```

## Qwen-VL 格式

GUI 数据支持导出为 Qwen-VL 微调格式：

```json
{
    "id": "gui_xxx",
    "image": "screenshots/xxx.png",
    "conversations": [
        {
            "from": "human",
            "value": "<image>\n点击提交按钮\n请定位需要操作的元素。"
        },
        {
            "from": "assistant",
            "value": "需要执行 click 操作，目标元素: #submit-btn"
        }
    ],
    "action_type": "click",
    "target_element": "#submit-btn"
}
```

## 数据质量保证

### 样本验证

1. **完整性检查**: 确保必需字段存在
2. **格式验证**: 确保参数格式正确
3. **路径检查**: 确保截图文件存在

### 去重

```python
# 按 instruction + action 去重
unique_samples = deduplicate(samples, key=lambda x: (x.instruction, x.target_action))
```

### 平衡

```python
# 平衡正负样本
balanced_samples = balance_samples(samples, ratio=0.5)
```

## 使用建议

### Tool-use 微调

1. 收集至少 1000 条高质量样本
2. 正负样本比例建议 7:3
3. 覆盖所有工具类型
4. 包含不同难度的任务

### Self-correction 微调

1. 重点关注常见错误类型
2. 包含成功和失败的修复案例
3. 修复策略多样化

### GUI Grounding 微调

1. 截图分辨率保持一致
2. 包含不同页面类型
3. 目标元素多样化
4. 添加 bounding box 标注（后续）

## 局限性

当前版本存在以下局限：

1. **Bounding box**: 暂未实现精确的 bounding box 标注
2. **截图质量**: 依赖 Playwright 截图，可能有渲染差异
3. **数据量**: 需要运行更多任务积累数据
4. **验证机制**: 部分样本验证规则简化
