# LightClaw

LightClaw is a lightweight agent runtime and post-training data loop for tool-use, self-correction, and GUI grounding.

它不是一个已经训练完成的生产 Agent，而是一个可本地复现的工程闭环：统一动作 schema、工具执行、错误归因、修复轨迹、reward/verifier、数据导出和 eval dashboard。

```text
user task
  -> agent runtime
  -> tool executor
  -> verifier / reward
  -> trajectory pool
  -> SFT / DPO / GRPO export
  -> eval dashboard
```

主展示链路现在以 **Recruiting Safe Dry-run** 为中心：

```text
recruiting HTML fixture
  -> extract jobs / apply steps
  -> guard login/captcha/upload/submit
  -> safe trajectory
  -> replay
  -> eval recruiting metrics
  -> SFT / DPO / GRPO export + data card
```

## Implemented

- **Unified Action Schema**：Pydantic 表达 `tool_call`、`ask_user`、`final_answer`、`self_correction`、`gui_click/gui_grounding`。
- **Tool Executor**：参数校验、invalid-format/wrong-args 归因、异常捕获、timeout、latency 和 action logging。
- **Self-correction Loop Data**：构造 `attempt -> error/verifier feedback -> revision` 样本，并检测 over-correction。
- **Verifier / Reward**：输出 task success、tool correctness、argument correctness、recovery、GUI hit、policy/redundancy penalty 和 latency proxy。
- **Failure Analysis**：eval report 按 error_type 聚合失败，并保留可 replay sample case。
- **Training Export**：导出 SFT / DPO / GRPO / self-correction JSONL，并生成 data card。
- **GUI Grounding Baseline**：rule-based selector/bbox/click point baseline，含 point-in-box、bbox IoU、GUI action accuracy。
- **Recruiting Safe Dry-run**：离线招聘 HTML fixture 抽取岗位/申请步骤，遇到登录、验证码、上传、提交动作时安全停止并记录 stop reason。
- **Frontend Evaluation View**：React Evaluation 页面可展示 latest deterministic report 和 self-correction metrics。

## Deterministic Demo

deterministic demo 使用固定 fixtures，不依赖真实 LLM API key。它用于证明 schema、eval、export、replay 和 data-quality 检查链路可运行，不代表真实线上指标。

P0/P1 currently verified:

- P0 Recruiting safe dry-run records a safe flow instead of applying for jobs.
- P1 Tool skills are registered as coarse capabilities and concrete tools are loaded progressively.

Sample output:

```text
Task success rate: 87.50%
Tool execution success rate: 64.29%
Recovery rate: 80.00%
Wrong args rate: 7.14%
GUI grounding accuracy: 100.00%
Correction attempt rate: 75.00%
Recovery success rate: 83.33%
Over-correction rate: 16.67%
```

Recruiting safe dry-run sample:

```json
{
  "jobs_extracted_count": 2,
  "apply_flow_steps_count": 8,
  "blocked_by_login": true,
  "blocked_by_captcha": true,
  "safe_stop_count": 2,
  "stop_reason_distribution": {
    "login_required": 1,
    "captcha_blocked": 1,
    "safe_stop": 2
  },
  "safe_stop_rate": 1.0
}
```

Skill progressive loading sample:

```json
{
  "registered_skill_count": 5,
  "initial_loaded_tool_count": 0,
  "selected_skills": [
    "browser_gui_control",
    "information_retrieval",
    "structured_memory_write"
  ],
  "loaded_tool_count_after_selection": 12
}
```

Training export marks recruiting safety samples explicitly:

```json
{
  "sample_type": "recruiting_safe_stop",
  "safety_domain": "recruiting",
  "stop_reason_distribution": {
    "login_required": 1,
    "safe_stop": 1
  }
}
```

Examples:

- [eval_report_example.json](examples/eval_report_example.json)
- [data_card_example.json](examples/data_card_example.json)
- [replay_wrong_args_example.md](examples/replay_wrong_args_example.md)

## 5-minute Reproducibility

```bash
cd backend
uv sync

# 1. Collect safe recruiting trajectory from fixture
uv run python ../scripts/collect_recruiting_trajectories.py --mode fixture

# 2. Replay the recruiting safe-stop flow
uv run python ../scripts/replay_trace.py --trace-domain recruiting

# 3. Run deterministic eval, including recruiting metrics if the trace exists
uv run python ../scripts/run_eval.py --mode deterministic

# 4. Export SFT/DPO/GRPO/self-correction data with data card
uv run python ../scripts/export_training_data.py --fixtures --with-data-card --output-dir data/training_exports/latest

# 5. Replay one failure/correction case
uv run python ../scripts/replay_trace.py --fixture-case wrong_args

# 6. Dry-run exported training data
uv run python ../scripts/train_stub.py --input-dir data/training_exports/latest --dry-run

# 7. Prepare SPA-style dense reward data, no model training
uv run python ../scripts/prepare_spa_training_data.py --input-dir data/training_exports/latest --output-dir data/training_exports/latest_spa
uv run python ../scripts/train_stub.py --input-dir data/training_exports/latest --spa-dir data/training_exports/latest_spa --dry-run

# 8. Run tests
uv run --with pytest --with pytest-asyncio pytest
```

One-command reproducibility:

```bash
cd backend
uv run python ../scripts/run_all_checks.py
```

One-command interview showcase:

```bash
cd backend
uv run python ../scripts/run_showcase.py
```

Output:

```text
backend/data/showcase/latest/showcase.json
backend/data/showcase/latest/showcase.md
```

The frontend `演示` page reads `/api/eval/showcase/latest` and renders the same P0/P1/P2 chain in one place.

Training-preparation pipeline:

```bash
cd backend
uv run python ../scripts/run_training_pipeline.py
```

This runs trajectory collection, trajectory distillation, SFT/DPO/GRPO export, SPA-style dense reward preparation, and deterministic evaluation. It does not train model weights.

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## What This Project Is NOT

- Not a fully trained production agent.
- Not an OSWorld-level or Android-level GUI agent.
- Not claiming real online metrics from deployed users.
- Not launching LoRA/SFT/DPO/GRPO training inside this repo.
- Not requiring a real OpenAI-compatible key for core tests and deterministic demos.

## Roadmap

- Add more real trajectories and keep deterministic fixtures separate from live reports.
- Use browser-plugin SoM screenshots as GUI grounding samples.
- Connect exported JSONL to external TRL / LLaMA-Factory / verl training configs.
- Evaluate trained models on real task suites and report those results separately.

## Project Layout

```text
backend/app/runtime/        Agent loop, executor, observer, recovery
backend/app/schemas/        Pydantic schemas, including AgentAction
backend/app/eval/           deterministic eval, reward, reports
backend/app/gui_grounding/  GUI grounding baseline and metrics
backend/app/training/       SFT/DPO/GRPO export, replay, self-correction samples
frontend/src/pages/         React dashboard pages
scripts/                    reproducibility, export, replay, dry-run training
docs/                       architecture, evaluation, export, interview guide
examples/                   small checked-in output examples
```

## Docs

- [Architecture](docs/architecture.md)
- [Evaluation](docs/evaluation.md)
- [Training Data Export](docs/training_data_export.md)
- [Failure Taxonomy](docs/failure_taxonomy.md)
- [Interview Guide](docs/interview_guide.md)
- [Training Stub](docs/training_stub.md)
- [SPA-style Training Preparation](docs/spa_training_preparation.md)
- [AutoDL GPU Training Runbook](docs/autodl_training_runbook.md)
- [Resume Notes](docs/resume_notes.md)
