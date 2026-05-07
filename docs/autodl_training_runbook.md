# AutoDL GPU Training Runbook

This guide explains how to move LightClaw from local data preparation to a real GPU box such as AutoDL. It still separates **implemented data preparation** from **actual model training results**.

## Recommended Order

```text
1. Local/AutoDL data pipeline
   collect trajectories -> distill -> export SFT/DPO/GRPO -> SPA-style dense reward

2. SFT LoRA
   base instruct model -> LightClaw tool-use / safe-stop / self-correction behavior cloning

3. DPO LoRA
   SFT checkpoint -> chosen/rejected correction pairs

4. SPA-style RL preparation
   ppo_ready.jsonl -> future PPO/GRPO trainer

5. Evaluation
   deterministic eval first; live/browser eval must be reported separately
```

For a single 5090-class GPU, start with a small model first:

- Safer first run: `Qwen/Qwen2.5-1.5B-Instruct`
- Better but heavier: `Qwen/Qwen2.5-3B-Instruct`
- Avoid starting with 7B+ until the pipeline is confirmed.

## AutoDL Environment

Use an image with recent CUDA/PyTorch support for your rented GPU. For RTX 5090 / Blackwell-class cards, avoid old CUDA 12.1 images. Prefer an AutoDL image that already includes a recent PyTorch build, or install a matching PyTorch wheel from the official PyTorch selector.

Inside AutoDL:

```bash
git clone <your-LightClaw-repo-url> LightClaw
cd LightClaw/backend
uv sync
uv run pytest
```

If `uv` is not installed:

```bash
pip install uv
```

## Prepare Data

```bash
cd /root/LightClaw/backend

uv run python ../scripts/run_training_pipeline.py

uv run python ../scripts/train_stub.py \
  --input-dir data/training_pipeline/latest/exports \
  --spa-dir data/training_pipeline/latest/spa \
  --dry-run
```

Expected output includes:

- `sft.jsonl`
- `dpo.jsonl`
- `grpo.jsonl`
- `self_correction.jsonl`
- `ppo_ready.jsonl`

## Install Training Dependencies

Use a fresh virtualenv/conda env if possible. Minimal training dependencies:

```bash
pip install -U "transformers>=4.46" "datasets>=3.0" "trl>=0.12" "peft>=0.13" accelerate bitsandbytes sentencepiece protobuf
```

If PyTorch is missing or incompatible with the GPU, install PyTorch according to the official PyTorch command for the CUDA version available on AutoDL.

## SFT LoRA

```bash
cd /root/LightClaw/backend

python ../scripts/train_trl_sft.py \
  --model Qwen/Qwen2.5-1.5B-Instruct \
  --dataset data/training_pipeline/latest/exports/sft.jsonl \
  --output-dir data/checkpoints/qwen25_1p5b_lightclaw_sft \
  --max-seq-length 4096 \
  --epochs 1 \
  --batch-size 1 \
  --grad-accum 8 \
  --lr 2e-5
```

For 3B:

```bash
python ../scripts/train_trl_sft.py \
  --model Qwen/Qwen2.5-3B-Instruct \
  --dataset data/training_pipeline/latest/exports/sft.jsonl \
  --output-dir data/checkpoints/qwen25_3b_lightclaw_sft \
  --max-seq-length 4096 \
  --epochs 1 \
  --batch-size 1 \
  --grad-accum 8 \
  --lr 2e-5
```

## DPO LoRA

Use the SFT checkpoint as the starting point:

```bash
python ../scripts/train_trl_dpo.py \
  --model data/checkpoints/qwen25_1p5b_lightclaw_sft \
  --dataset data/training_pipeline/latest/exports/dpo.jsonl \
  --output-dir data/checkpoints/qwen25_1p5b_lightclaw_dpo \
  --epochs 1 \
  --batch-size 1 \
  --grad-accum 8 \
  --lr 5e-6 \
  --beta 0.1
```

## SPA-style RL

Current repository status:

- Implemented: `ppo_ready.jsonl` with dense rewards.
- Not implemented: real PPO/GRPO optimizer update.

Validate the prepared rollout data:

```bash
uv run python ../scripts/prepare_spa_training_data.py \
  --input-dir data/training_pipeline/latest/exports \
  --output-dir data/training_pipeline/latest/spa

uv run python ../scripts/train_stub.py \
  --input-dir data/training_pipeline/latest/exports \
  --spa-dir data/training_pipeline/latest/spa \
  --dry-run
```

Next implementation step would be a real TRL/verl trainer that reads:

```text
data/training_pipeline/latest/spa/ppo_ready.jsonl
```

and uses `dense_rewards` as the per-step reward signal.

## Evaluation

Always run deterministic eval after training to confirm the repo pipeline still works:

```bash
uv run python ../scripts/run_eval.py --mode deterministic
```

For real model evaluation, add a separate script that loads the checkpoint and runs held-out tasks. Do not mix deterministic fixture numbers with real model metrics.

## What You Can Claim

Safe claim:

> Implemented a complete training-data pipeline and started SFT/DPO LoRA experiments on AutoDL using LightClaw tool-use, self-correction, GUI grounding and SPA-style dense reward data.

Only claim model improvement after you run held-out evaluation and record the exact model, data split, checkpoint and metric.
