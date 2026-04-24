# Training Data Export

LightClaw 当前实现训练数据导出，不实现真实微调训练。导出数据可供 TRL、verl、LLaMA-Factory 等框架继续使用。

## 命令

```bash
cd backend
uv run python ../scripts/export_training_data.py --fixtures
```

输出目录：

```text
backend/data/exports/
  sft.jsonl
  dpo.jsonl
  grpo.jsonl
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
  "candidate_trajectories": [[{"action_type": "gui_grounding", "...": "..."}]],
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

## 数据质量约束

- 不把 fixtures 当真实线上效果。
- 不导出无法解析的 action JSON。
- DPO pair 只在失败 action 后跟随成功修正 action 时生成。
- GUI grounding 当前使用 selector/bbox mock candidates，后续再接真实截图标注。
