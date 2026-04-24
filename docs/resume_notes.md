# Resume Notes

可用于简历的准确表述：

- 设计并实现轻量 Agent Runtime，围绕 `plan -> act -> observe -> verify -> retry/revise -> final` 组织工具调用、状态记录和错误恢复。
- 用 Pydantic 统一 `tool_call / self_correction / gui_grounding` action schema，支持参数校验、错误归因、latency logging 和 trajectory replay。
- 构建 rule-based verifier/reward，将 wrong-args、invalid-format、GUI miss、policy violation 等失败转化为可评测 reward breakdown。
- 实现 SFT / DPO / GRPO-ready JSONL 导出，能从成功轨迹和失败修复轨迹生成后训练数据样本。
- 实现 GUI grounding selector/bbox baseline 和 point-in-box、bbox IoU、GUI action accuracy 评测函数；当前定位为 baseline，不宣称完整 GUI Agent。
- 增加 data card 与 replay 脚本，对 DPO suspicious pair、GRPO low-signal group、over-correction 等数据质量问题做本地可复现检查。

不能夸大的部分：

- deterministic eval 是本地 fixture 验证，不是真实线上指标。
- 当前没有完成真实模型微调训练。
- GUI grounding 是 baseline/eval module，不是完整 OSWorld/Android 自动化系统。
- DPO/GRPO-ready 表示数据格式和质量检查已准备好，不等于已经验证了训练收益。
