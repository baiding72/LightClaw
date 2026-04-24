# LightClaw 系统架构

LightClaw 是一个面向个人效率任务的轻量 Agent Runtime。当前目标不是实现完整在线 RL，而是把 tool-use、self-correction、GUI grounding、轨迹回流、评测和训练数据导出做成可运行闭环。

## Runtime

主链路保持现有结构：

```text
plan -> act -> observe -> verify -> retry/revise -> final
```

关键模块：

- `runtime/agent.py`：任务生命周期和主循环。
- `runtime/executor.py`：工具执行、参数校验、超时、异常捕获、action logging。
- `runtime/retry.py`：失败分析和 recovery trace。
- `runtime/state.py`：保存 tool_calls、actions、observations、errors、checkpoints。

新增统一 `AgentAction` schema 不替代旧 `ToolCall/ToolResult/StepEvent`，而是作为 runtime、eval、export 的标准动作 envelope。

## Gateway / Trajectory

Gateway 继续记录 task/step/error/gui action。轨迹以 JSONL 保存，后续导出器可把旧 step event 转换为统一 action：

```json
{
  "action_type": "tool_call",
  "tool_name": "write_note",
  "arguments": {"title": "总结", "content": "..."},
  "status": "success",
  "error_type": null,
  "latency_ms": 8,
  "trace_id": "traj_xxx"
}
```

## Verifier / Reward

`eval/reward.py` 提供 deterministic rule-based verifier，输出 breakdown：

- task_success
- tool_name_correct
- argument_correct
- format_valid
- recovery_success
- gui_grounding_hit
- redundant_tool_call_penalty
- policy_violation_penalty
- latency_cost_proxy

这些字段用于 eval report，也用于 GRPO/RL rollout export。

## GUI Grounding

当前实现是 `gui_grounding` baseline，而不是完整 GUI Agent：

- 输入：自然语言 instruction + DOM/selector candidates 或 mock bbox。
- 输出：selector、bbox、click point。
- 指标：point-in-box、bbox IoU、GUI action accuracy。

浏览器插件的 SoM screenshot / DOM observation 是后续扩展方向，README 不把它描述成完整自动化基准能力。

## Training Export

`training/exporter.py` 和 `scripts/export_training_data.py` 支持导出：

- SFT：成功 tool-use/self-correction/gui-grounding 轨迹。
- DPO：失败 action 作为 rejected，修正成功 action 作为 chosen。
- GRPO/RL rollout：prompt、candidate trajectories、reward breakdown、final score。

deterministic fixtures 会标注 `source=deterministic_fixture`，避免和真实实验结果混淆。
