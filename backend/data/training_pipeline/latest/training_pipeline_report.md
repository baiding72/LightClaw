# LightClaw Training Pipeline

Generated at: `2026-05-05T01:50:01.120811`
Status: `passed`
Training status: `data_preparation_only_no_model_training`

## Stages

### trajectory_collection

- Status: `passed`
- Purpose: Collect safe dry-run recruiting traces without login/upload/submit.

### trajectory_distillation

- Status: `passed`
- Purpose: Compact raw traces into training-oriented trajectory records.

### sft_dpo_grpo_export

- Status: `passed`
- Purpose: Export SFT/DPO/GRPO/self-correction JSONL with data card.

### spa_rl_preparation

- Status: `passed`
- Purpose: Prepare SPA-style progress attribution and PPO-ready dense reward rollouts.

### evaluation

- Status: `passed`
- Purpose: Run deterministic eval over tool-use, self-correction and GUI grounding fixtures.

## Real Training Order

- SFT on successful distilled trajectories and tool-use messages
- DPO on chosen/rejected correction pairs
- SPA-style RL using ppo_ready.jsonl dense_rewards in PPO/GRPO trainer
- Evaluate on deterministic fixtures first, then separately on live/browser tasks

## Non-claims

- No model weights are trained by this pipeline.
- No real online success-rate improvement is claimed.
- No GPU or external LLM API key is required.
