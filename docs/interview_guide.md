# LightClaw Interview Guide

## 30 秒介绍

LightClaw 是一个轻量 Agent Runtime 和后训练数据闭环项目。它围绕 tool-use、self-correction 和 GUI grounding baseline，把用户任务执行过程记录成统一 action schema，再通过 verifier/reward 生成 failure analysis、SFT/DPO/GRPO-ready 数据和 deterministic eval report。核心测试和 demo 不依赖真实 LLM key。

## 2 分钟介绍

这个项目的重点不是做一个包装 prompt 的聊天机器人，而是把 Agent 执行过程工程化。Runtime 里每一步 action 都会被结构化记录，包括工具名、参数、observation、错误类型、latency、trace_id。Executor 负责参数校验、异常捕获和错误归因，Verifier/Reward 负责判断 action 是否正确、修复是否有效、是否过度修正。

在数据层，系统能从 trajectory 中构造 SFT 样本、DPO chosen/rejected pair、GRPO rollout-like candidate groups，以及 self-correction attempt-feedback-revision 样本。为了不伪造训练收益，仓库只做数据导出和 dry-run 校验，不启动真实微调。GUI 部分目前是 selector/bbox 的 rule-based baseline，用于评测 point-in-box、IoU 和 action accuracy，不宣称完整 GUI Agent。

## 核心技术链路

- **Action Schema**：统一 `tool_call / ask_user / final_answer / self_correction / gui_grounding`，让 runtime、eval 和 export 使用同一动作表示。
- **Tool Executor**：执行前做格式和参数校验，区分 `invalid_format`、`wrong_args`、`wrong_tool`、runtime error 和 timeout。
- **Verifier / Reward**：输出 reward breakdown，而不是单一分数，便于解释失败原因。
- **Self-correction**：从 attempt、error/verifier feedback、revision 构造修复轨迹，并检测 over-correction。
- **Failure Analysis**：按 error_type 聚合失败样本，每类保留 replay case。
- **SFT/DPO/GRPO Export**：导出后训练可用 JSONL，但不在仓库内训练模型。
- **GUI Grounding Baseline**：用 rule-based selector/bbox baseline 评估 GUI grounding 基本能力。

## 常见追问

### 为什么不能只做 prompt engineering？

Prompt 能改善单次输出，但很难系统性回答“哪一步错了、错因是什么、修复是否有效、能否转成训练数据”。LightClaw 把动作、错误和反馈结构化，使失败可以统计、回放和导出。

### 为什么要 SFT + DPO，而不是只用 DPO？

SFT 适合学习基础格式、工具调用和参数填充；DPO 适合学习偏好和错误修正，例如 rejected wrong_args 与 chosen corrected args。只用 DPO 容易缺少基础行为分布。

### GRPO 数据只是导出，和真实 GRPO 训练有什么区别？

当前只是 GRPO/RL-ready rollout 数据：prompt、candidate trajectories、reward breakdown 和 score。真实 GRPO 还需要在线采样、policy update、优势估计、训练框架和 GPU，本仓库没有声称完成这些。

### self-correction 如何避免越改越错？

系统显式检测 over-correction：如果原 action 已经正确，但 revision 改变了 tool、arguments 或 action type，就标记为负样本。Eval report 里有 `over_correction_rate`。

### deterministic eval 和真实线上指标有什么区别？

deterministic eval 是固定 fixtures，用来保证 schema、export、reward 和 replay 链路可复现；它不是线上模型成功率。真实指标必须在 live mode 和真实任务集上单独报告。

### GUI grounding 为什么只是 baseline？

完整 GUI Agent 需要真实截图数据、视觉模型、跨页面状态管理和大量交互评测。当前项目先实现 selector/bbox baseline 和指标，保证“可测、可解释”，不夸大成 OSWorld 级能力。

### 数据质量怎么保证？

导出时生成 data card，统计样本数、错误分布、action 分布、chosen/rejected reward、suspicious pair、low-signal GRPO group 和 schema validation pass rate。

### chosen/rejected 如何构造？

rejected 通常是失败 action，例如 wrong_args、wrong_tool、invalid_format、gui_click_miss；chosen 是紧随其后的成功 revision。pair 会记录 `pair_reason`。

### reward hacking 怎么防？

当前是 rule-based verifier，只用于 deterministic fixtures 和数据质检。它不能防所有 reward hacking。后续需要更强 verifier、人工抽检和真实任务集评测。

### 这个项目的工程难点在哪里？

难点在把 Agent 的非结构化执行过程转成稳定的数据闭环：统一 action schema、错误归因、修复轨迹构造、reward breakdown、DPO/GRPO 数据格式和可复现评测。
