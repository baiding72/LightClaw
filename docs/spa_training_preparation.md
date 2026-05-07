# SPA-style Training Preparation

LightClaw does **not** train a SPA-RL/PPO model in this repository. This module prepares data in the same spirit as Stepwise Progress Attribution:

```text
exported trajectories
  -> stepwise progress attribution
  -> action-validity / grounding signal
  -> dense reward per step
  -> PPO/GRPO-ready rollout JSONL
```

The implementation is deterministic and local. It is meant for reproducibility, data inspection, and future integration with TRL / verl / LLaMA-Factory, not for claiming trained-model gains.

## Command

```bash
cd backend
uv run python ../scripts/export_training_data.py --fixtures --with-data-card --output-dir data/training_exports/latest
uv run python ../scripts/prepare_spa_training_data.py \
  --input-dir data/training_exports/latest \
  --output-dir data/training_exports/latest_spa
```

Output:

```text
data/training_exports/latest_spa/
  spa_rollouts.jsonl
  progress_attribution.jsonl
  ppo_ready.jsonl
  spa_data_card.json
```

## Reward Design

The current deterministic proxy is:

```text
dense_reward = stepwise_progress + 0.1 * action_validity
```

Where:

- `stepwise_progress` redistributes final rollout reward across valid progress steps.
- `action_validity` is `1.0` for executable/successful actions and for safe-stop behavior such as `login_required`, `captcha_blocked`, or `safe_stop`.
- Failed actions with `error_type` receive zero progress.

For recruiting dry-run, safe stops are treated as positive behavior because the correct policy is to stop rather than submit, upload, bypass CAPTCHA, or enter login flow.

## Dry-run Validation

```bash
uv run python ../scripts/train_stub.py \
  --input-dir data/training_exports/latest \
  --spa-dir data/training_exports/latest_spa \
  --dry-run
```

This validates:

- SFT/DPO/GRPO/self-correction export files.
- `spa_rollouts.jsonl` progress scores sum to final reward.
- `ppo_ready.jsonl` trajectory length matches dense reward length.

## Limitations

- No learned progress estimator is trained here.
- No PPO/GRPO update is launched here.
- Reported counts are deterministic fixture/data-preparation counts, not model performance.
- A real SPA-RL setup would need a base model, rollout environment, GPU training stack, and a learned progress estimator or verified environment reward.
