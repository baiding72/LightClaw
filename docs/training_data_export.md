# Training Data Export

LightClaw 当前实现训练数据导出，不实现真实微调训练。导出数据可供 TRL、verl、LLaMA-Factory 等框架继续使用。

## 命令

```bash
cd backend
uv run python ../scripts/export_training_data.py --fixtures
uv run python ../scripts/export_training_data.py --fixtures --with-data-card
```

输出目录：

```text
backend/data/exports/
  sft.jsonl
  dpo.jsonl
  grpo.jsonl
  self_correction.jsonl
  data_card.json
```

默认读取 `backend/data/trajectories/` 下真实 JSONL 轨迹；`--fixtures` 会额外加入 deterministic fixtures，并在 metadata 中标注 `source=deterministic_fixture`。

## SFT JSONL

用于成功 tool-use / self-correction / GUI grounding 轨迹。

```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "创建一个待办..."},
    {"role": "assistant", "content": "[{\"action_type\":\"tool_call\",...}]"}
  ],
  "metadata": {
    "task_id": "fixture_tool_use_success",
    "sample_type": "sft",
    "source": "deterministic_fixture"
  }
}
```

## DPO JSONL

兼容常见 preference dataset 格式：

```json
{
  "system": "你是一个集成在浏览器插件和本地工具运行时中的个人效率 Agent...",
  "prompt": "写一条笔记...",
  "chosen": "{\"action_type\":\"self_correction\",...}",
  "rejected": "{\"action_type\":\"tool_call\",\"status\":\"failed\",...}",
  "metadata": {
    "failure_type": "wrong_args",
    "source": "deterministic_fixture"
  }
}
```

`chosen` 是修正后成功的 action；`rejected` 是 wrong-tool、wrong-args、invalid-format、policy-violation、GUI-click-miss 等失败 action。

## GRPO / RL Rollout JSONL

```json
{
  "prompt": "点击保存按钮",
  "candidate_trajectories": [
    {
      "label": "rejected",
      "actions": [{"action_type": "tool_call", "status": "failed"}],
      "reward_breakdown": {"final_score": 0.57},
      "final_score": 0.57
    },
    {
      "label": "chosen",
      "actions": [{"action_type": "tool_call", "status": "failed"}, {"action_type": "self_correction", "status": "success"}],
      "reward_breakdown": {"final_score": 0.93},
      "final_score": 0.93
    }
  ],
  "reward_breakdown": {
    "task_success": 1.0,
    "tool_name_correct": 1.0,
    "argument_correct": 1.0,
    "format_valid": 1.0,
    "recovery_success": 1.0,
    "gui_grounding_hit": 1.0,
    "redundant_tool_call_penalty": 0.0,
    "policy_violation_penalty": 0.0,
    "latency_cost_proxy": 0.99,
    "final_score": 0.99
  },
  "final_score": 0.99,
  "metadata": {"source": "deterministic_fixture"}
}
```

每个 GRPO group 至少应包含两个 candidate。导出器会标记 `low_signal_group`，用于发现 candidate reward 全相同或候选数不足的低信号样本。

## Self-correction JSONL

```json
{
  "original_prompt": "写一条笔记...",
  "attempt_action": {"action_type": "tool_call", "status": "failed"},
  "observation": null,
  "error": "Missing required parameter: content",
  "verifier_feedback": "content 参数缺失",
  "error_type": "wrong_args",
  "revision_action": {"action_type": "self_correction", "status": "success"},
  "final_status": "success",
  "recovery_success": true,
  "over_correction": false,
  "trace_id": "fixture_self_correction",
  "task_id": "fixture_wrong_args_repair"
}
```

## Data Card

`--with-data-card` 会生成 `data_card.json`：

| 字段 | 含义 |
| --- | --- |
| `export_time` | 导出时间 |
| `source` | `trajectory`、`deterministic_fixture` 或混合来源 |
| `sft_count` | SFT 样本数 |
| `dpo_pair_count` | DPO pair 数 |
| `grpo_group_count` | GRPO group 数 |
| `self_correction_count` | self-correction 样本数 |
| `error_type_distribution` | 错误类型分布 |
| `action_type_distribution` | action 类型分布 |
| `avg_steps` | GRPO candidate 平均步数 |
| `chosen_reward_avg` | DPO chosen 平均 reward |
| `rejected_reward_avg` | DPO rejected 平均 reward |
| `invalid_sample_count` | suspicious pair + low-signal group 总数 |
| `schema_validation_pass_rate` | 质量检查通过率 |

DPO 检查：chosen 和 rejected 不能完全相同，chosen reward 应高于 rejected reward，并且 pair 必须有 `pair_reason`。

GRPO 检查：每组至少 2 个 candidate，reward 不能全相同，每个 candidate 必须带 `reward_breakdown`。

## 数据质量约束

- 不把 fixtures 当真实线上效果。
- 不导出无法解析的 action JSON。
- DPO pair 只在失败 action 后跟随成功修正 action 时生成。
- GUI grounding 当前使用 selector/bbox mock candidates，后续再接真实截图标注。
