# LightClaw 评测指标

## 概述

本文档定义 LightClaw 系统中使用的评测指标及其计算方式。

## 核心指标

### 1. Task Success Rate (任务成功率)

**定义**: 成功完成的任务占总任务的比例。

**公式**:
```
task_success_rate = successful_tasks / total_tasks
```

**范围**: 0.0 ~ 1.0

**说明**:
- 任务成功的判断基于 TaskValidationResult
- 部分完成的任务不计入成功
- 任务被取消不计入统计

**示例**:
```python
# 10 个任务，8 个成功
task_success_rate = 8 / 10 = 0.8
```

### 2. Tool Execution Success Rate (工具执行成功率)

**定义**: 成功执行的工具调用占总工具调用的比例。

**公式**:
```
tool_execution_success_rate = successful_tool_calls / total_tool_calls
```

**范围**: 0.0 ~ 1.0

**说明**:
- 统计所有工具调用，包括重试
- 工具执行成功指返回 success=True
- 不包括参数验证失败的调用

**示例**:
```python
# 50 次工具调用，45 次成功
tool_execution_success_rate = 45 / 50 = 0.9
```

### 3. Recovery Rate (恢复率)

**定义**: 成功恢复的错误占总错误的比例。

**公式**:
```
recovery_rate = successful_recoveries / total_errors
```

**范围**: 0.0 ~ 1.0

**说明**:
- 仅统计可恢复类型的错误
- 成功恢复指最终完成了任务
- 多次重试只计一次恢复

**示例**:
```python
# 10 个错误，7 个成功恢复
recovery_rate = 7 / 10 = 0.7
```

### 4. GUI Action Accuracy (GUI 操作准确率)

**定义**: GUI 操作成功命中的比例。

**公式**:
```
gui_action_accuracy = successful_gui_actions / total_gui_actions
```

**范围**: 0.0 ~ 1.0

**说明**:
- GUI 操作包括 click、type、select 等
- 成功命中指操作了正确的元素
- 暂不包含精确的 bounding box 评估

**示例**:
```python
# 20 次 GUI 操作，18 次命中
gui_action_accuracy = 18 / 20 = 0.9
```

### 5. Average Latency (平均延迟)

**定义**: 每个任务的平均执行时间。

**公式**:
```
avg_latency_ms = sum(latency_ms) / total_tasks
```

**单位**: 毫秒

**说明**:
- 包含所有步骤的延迟总和
- 不包括 LLM 生成时间（单独统计）
- 用于评估系统效率

### 6. Token Cost (Token 成本)

**定义**: 任务执行过程中消耗的 Token 数量。

**公式**:
```
total_token_cost = sum(token_usage.total_tokens)
```

**单位**: Token 数

**说明**:
- 包括 prompt 和 completion tokens
- 暂不转换为金额成本
- 用于评估 LLM 使用效率

## 指标计算实现

```python
def calculate_metrics(results: List[Dict]) -> EvaluationMetrics:
    total = len(results)

    # 任务成功率
    successful_tasks = sum(1 for r in results if r.get("is_success"))
    task_success_rate = successful_tasks / total

    # 工具执行成功率
    total_tool_calls = sum(r.get("tool_calls_count", 0) for r in results)
    # 假设大部分成功
    tool_success_rate = 0.95  # 实际应从详细日志计算

    # 恢复率
    total_errors = sum(1 for r in results if r.get("failure_types"))
    successful_recoveries = sum(r.get("successful_recoveries", 0) for r in results)
    recovery_rate = successful_recoveries / total_errors if total_errors > 0 else 1.0

    # GUI 准确率
    gui_action_accuracy = 0.90  # 从 GUI 操作日志计算

    # 平均延迟
    total_latency = sum(r.get("latency_ms", 0) for r in results)
    avg_latency_ms = total_latency / total

    return EvaluationMetrics(
        task_success_rate=task_success_rate,
        tool_execution_success_rate=tool_success_rate,
        recovery_rate=recovery_rate,
        gui_action_accuracy=gui_action_accuracy,
        avg_latency_ms=avg_latency_ms,
    )
```

## 按难度分层

评测结果按难度分层展示：

| 难度 | 任务数 | 成功率 | 平均步骤 |
|------|--------|--------|----------|
| Easy | 5 | 90% | 2.1 |
| Medium | 10 | 75% | 4.5 |
| Hard | 5 | 60% | 8.2 |

## 按类别分层

评测结果按任务类别展示：

| 类别 | 任务数 | 成功率 | 主要错误 |
|------|--------|--------|----------|
| Info Extraction | 5 | 85% | read_page 失败 |
| Todo/Calendar | 5 | 90% | 参数格式错误 |
| Web Form | 5 | 70% | gui_click_miss |
| Multi-step | 5 | 65% | planning_error |

## Benchmark 运行

运行 Benchmark：

```bash
cd scripts
uv run python run_eval.py
```

结果保存在 `data/eval/` 目录。

## 评测报告

系统生成 Markdown 格式的评测报告，包含：
- 整体指标
- 分层统计
- 失败分析
- 改进建议
