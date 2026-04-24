# LightClaw：面向个人效率管理的在线自进化轻量智能体

LightClaw 是一个本地可运行的轻量 Agent Runtime 项目，重点展示 Tool-use、Self-correction、GUI Grounding baseline、轨迹回流、评测和后训练数据导出。项目保持 FastAPI + React + SQLite 架构，核心测试和 deterministic demo 不依赖真实 LLM API key。

## 已实现能力

- **统一 Action Schema**：用 Pydantic 表达 `tool_call`、`ask_user`、`final_answer`、`revise/self_correction`、`gui_click/gui_grounding`。
- **Tool-use Executor**：工具参数校验、非法格式归因、运行异常捕获、超时控制、latency 统计和 action logging。
- **Self-correction 数据轨迹**：支持 `attempt -> feedback/error -> revised action` 的修复轨迹表达，可导出 DPO chosen/rejected pair。
- **Rule-based Verifier / Reward**：输出 task success、tool correctness、argument correctness、recovery、GUI hit、policy/redundancy penalty、latency proxy 等 breakdown。
- **GUI Grounding Baseline**：基于 DOM/selector candidates 的 rule-based selector/bbox/click point baseline，并提供 point-in-box、bbox IoU、GUI action accuracy 指标。
- **训练数据导出**：从真实轨迹或 deterministic fixtures 导出 SFT / DPO / GRPO JSONL。
- **Deterministic Eval**：无需 LLM key，稳定生成 `backend/data/eval_reports/latest.json`。
- **前端可视化**：Dashboard、Task Runner、DataPool、Evaluation 页面；Evaluation 页面可读取最新本地评测报告。

## 可运行 Demo

```bash
cd backend
uv sync

# 运行 deterministic demo，生成轨迹
uv run python ../scripts/run_demo_tasks.py --mock

# 运行 deterministic eval，生成 backend/data/eval_reports/latest.json
uv run python ../scripts/run_eval.py --mode deterministic

# 导出 SFT / DPO / GRPO 数据
uv run python ../scripts/export_training_data.py --fixtures

# 后端测试
uv run --with pytest --with pytest-asyncio pytest
```

前端：

```bash
cd frontend
npm install
npm run dev
```

后端：

```bash
cd backend
uv run python -m app.main
```

默认后端端口仍是 `8000`。如果本机已有服务占用 8000，请通过现有 `VITE_API_PROXY_TARGET` 或本地启动脚本切到其他端口。

## 目录说明

```text
backend/app/runtime/        Agent loop、executor、observer、recovery
backend/app/schemas/        Pydantic schemas，包括统一 action schema
backend/app/tools/          本地工具与浏览器动作工具
backend/app/gateway/        JSONL 轨迹事件记录
backend/app/eval/           deterministic eval、reward、report
backend/app/gui_grounding/  GUI grounding baseline 与指标
backend/app/training/       SFT/DPO/GRPO export helpers
frontend/src/pages/         React 可视化页面
scripts/                    demo、eval、export、校验脚本
docs/                       架构、评测、导出和简历说明
```

## 当前限制

- deterministic eval 使用固定 fixtures，只用于本地验证链路，不代表真实生产指标。
- GUI Grounding 目前是 selector/rule-based baseline，不是完整 OSWorld/Android Agent。
- 项目支持 OpenAI-compatible LLM 配置，但核心测试不依赖真实 key；live Agent 效果取决于模型和网页环境。
- 当前没有真实微调训练流程，只导出可供 TRL / verl / LLaMA-Factory 等框架继续使用的数据。

## 后续路线

- 接入更多真实轨迹，扩展 verifier 和 reward 权重。
- 将浏览器插件产生的 SoM screenshot + DOM observation 纳入 GUI grounding 数据集。
- 增加真实网页任务的 replay/eval fixture。
- 在外部训练框架中验证导出的 SFT/DPO/GRPO 数据。

## 文档

- [系统架构](docs/architecture.md)
- [数据流水线](docs/pipeline.md)
- [失败类型定义](docs/failure_taxonomy.md)
- [评测指标](docs/evaluation.md)
- [训练数据导出](docs/training_data_export.md)
- [简历描述参考](docs/resume_notes.md)
