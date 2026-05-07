# Data Pipeline

LightClaw 的数据流水线围绕统一 `AgentAction` 展开。

```text
User Instruction
  -> Agent Runtime
  -> Executor / GUI Grounding Baseline
  -> Gateway JSONL Trajectory
  -> Trajectory Distillation
  -> Verifier / Reward
  -> SFT / DPO / GRPO Export
  -> SPA-style Dense Reward Preparation
  -> Evaluation Report
```

## 1. Runtime Action

每个动作至少包含：

```json
{
  "action_type": "tool_call",
  "tool_name": "write_note",
  "arguments": {"title": "总结", "content": "..."},
  "observation": {"note_id": 1},
  "status": "success",
  "error_type": null,
  "timestamp": "...",
  "step_id": "task:1",
  "trace_id": "traj_task"
}
```

## 2. Validation

工具调用先经过格式和参数校验：

- 非 JSON / 非 object：`invalid_format`
- 缺字段 / 类型错误：`wrong_args`
- 工具不存在：`wrong_tool`

失败会进入 action log，并可用于 self-correction 和 DPO rejected 样本。

## 3. Self-correction

典型轨迹：

```text
attempt failed action
  -> verifier/error feedback
  -> revised action
  -> success observation
```

修正必须基于 error/observation/verifier feedback。若 verifier 判断原 action 正确，则不生成无意义修正。

## 4. Eval / Reward

deterministic eval 使用固定 fixtures，可稳定复现：

```bash
cd backend
uv run python ../scripts/run_eval.py --mode deterministic
```

输出写入 `backend/data/eval_reports/latest.json`。

## 5. Training Export

```bash
cd backend
uv run python ../scripts/export_training_data.py --fixtures
```

输出：

- `sft.jsonl`
- `dpo.jsonl`
- `grpo.jsonl`

fixtures 会标注 `source=deterministic_fixture`，真实轨迹会标注 `source=trajectory`。

## 6. Training Pipeline

完整本地训练准备链路：

```bash
cd backend
uv run python ../scripts/run_training_pipeline.py
```

阶段：

1. `trajectory_collection`：从 recruiting fixture 收集 safe dry-run 轨迹，不登录、不上传、不提交。
2. `trajectory_distillation`：压缩 raw trace，截断 DOM，保留 action、observation、stop_reason、error_type。
3. `sft_dpo_grpo_export`：导出 SFT / DPO / GRPO / self-correction JSONL 和 data card。
4. `spa_rl_preparation`：生成 stepwise progress attribution、dense reward、`ppo_ready.jsonl`。
5. `evaluation`：运行 deterministic eval 并生成 report。

该 pipeline 只做数据准备，不启动真实 SFT/DPO/PPO/GRPO 训练。
