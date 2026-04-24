# Training Stub

LightClaw 目前只完成数据闭环与格式导出，不在仓库内启动真实训练。

真实 SFT / DPO / GRPO 训练需要额外准备：

- GPU 资源
- base model，例如 Qwen/DeepSeek 系列可训练权重
- TRL、LLaMA-Factory 或 verl 配置
- tokenizer、chat template、训练超参和模型保存策略

## Dry-run

先导出数据：

```bash
cd backend
uv run python ../scripts/export_training_data.py --fixtures --with-data-card --output-dir data/training_exports/latest
```

再运行 dry-run：

```bash
uv run python ../scripts/train_stub.py --input-dir data/training_exports/latest --dry-run
```

脚本会读取并校验：

- `sft.jsonl`
- `dpo.jsonl`
- `grpo.jsonl`
- `self_correction.jsonl`
- `data_card.json`

输出 `ready for SFT/DPO/GRPO training` 只表示数据格式和基础质量检查通过，不表示已经完成训练或验证训练收益。

## How to Connect Later

- SFT：将 `sft.jsonl` 的 `messages` 映射到 supervised fine-tuning trainer。
- DPO：将 `dpo.jsonl` 的 `system/prompt/chosen/rejected` 接到 preference trainer。
- GRPO / verl：将 `grpo.jsonl` 的 candidate trajectories 和 reward breakdown 作为 rollout/reward fixture。

本仓库不引入大型训练依赖，避免让核心 demo 依赖 GPU 或真实 API key。
