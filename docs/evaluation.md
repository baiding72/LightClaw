# Evaluation

LightClaw 提供两种评测模式：

- `deterministic`：默认模式，使用固定 fixtures，不需要 LLM key，适合 CI、本地 demo 和导出链路验证。
- `live`：调用现有 Agent runtime 和真实工具/LLM，结果取决于模型、网页和环境。

## 命令

```bash
cd backend
uv run python ../scripts/run_eval.py --mode deterministic
```

输出：

```text
backend/data/eval_reports/latest.json
backend/data/eval_reports/latest.md
```

## 指标

| 指标 | 含义 |
| --- | --- |
| `task_success_rate` | 成功完成任务的比例 |
| `tool_execution_success_rate` | 成功 action / 总 action |
| `recovery_rate` | 失败后成功修复的比例 |
| `invalid_tool_call_rate` | 非法 JSON / 非对象参数等格式错误占比 |
| `wrong_args_rate` | 参数缺失、类型错误、enum 错误占比 |
| `policy_violation_rate` | 违反 runtime policy 的 action 占比 |
| `gui_grounding_accuracy` | GUI grounding selector/point/bbox 命中率 |
| `avg_steps` | 平均步骤数 |
| `avg_latency` | 平均延迟 |

## Self-correction 指标

| 指标 | 含义 | 作用 |
| --- | --- | --- |
| `correction_attempt_rate` | 有 attempt-feedback-revision 样本的任务占比 | 衡量系统是否捕获到可训练的修复链路 |
| `recovery_success_rate` | 修正后成功的样本占比 | 衡量修复动作是否真正改善结果 |
| `over_correction_rate` | 原 action 正确却被错误修改的比例 | 防止模型学会“为了修正而修正” |
| `first_error_type_distribution` | 首个错误类型分布 | 定位 wrong_args、wrong_tool、GUI miss 等主要问题 |
| `revision_valid_rate` | revision action 可执行且成功的比例 | 衡量修正动作本身是否健康 |
| `revision_improves_reward_rate` | revision 后 reward 高于 attempt 的比例 | 衡量修正是否带来可度量收益 |

## Failure Analysis

`latest.json` 包含 `failure_analysis`，按 `error_type` 统计数量、占比，并为每类保留 1-3 个 sample case。每个 case 包含 task_id、trace_id、actions、reward_breakdown 和 failure_reason，便于定位“为什么失败、如何修复”。

## Reward Breakdown

`RuleBasedVerifier` 会为轨迹输出：

- `task_success`
- `tool_name_correct`
- `argument_correct`
- `format_valid`
- `recovery_success`
- `gui_grounding_hit`
- `redundant_tool_call_penalty`
- `policy_violation_penalty`
- `latency_cost_proxy`
- `final_score`

这些字段用于 eval report 和 GRPO/RL rollout 数据。

## 注意

deterministic report 只证明链路可运行、schema 正确、指标稳定可复现；不能写成真实模型实验结果。真实网页/LLM 评测必须使用 `--mode live` 并单独标注环境、模型和样本来源。
