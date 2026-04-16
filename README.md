# LightClaw：面向个人效率管理的在线自进化轻量智能体

一个轻量级的 MiniClaw 风格 Agent 系统，支持在线轨迹回流、数据池管理、定向增强数据导出、统一评测和前端可视化展示。

## 系统能力

- **Agent Runtime**: MiniClaw 风格轻量 runtime，包含 planning、acting、observing、retry、replan
- **工具系统**: 搜索、浏览器、文件、笔记、待办、日历等工具
- **轨迹回流**: 记录 tool call、GUI observation、error trace
- **数据池**: 成功/失败/修复轨迹管理，样本切分与导出
- **评测框架**: task_success_rate、tool_execution_success_rate、recovery_rate、gui_action_accuracy
- **前端可视化**: Dashboard、TaskRunner、Memory、DataPool、Evaluation 页面

## 技术选型

### 后端
- Python 3.11
- FastAPI + Pydantic
- SQLAlchemy + SQLite
- Playwright（浏览器自动化）
- uv 包管理

### 前端
- React + TypeScript
- Vite
- Tailwind CSS

## 本地启动

### 环境准备

```bash
# 安装 uv（Python 包管理器）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装 Node.js（前端）
# 参考 https://nodejs.org/
```

### 后端启动

```bash
cd backend
uv sync
cp .env.example .env
# 编辑 .env 配置 LLM API
uv run python -m app.main
```

后端 API 运行在 http://localhost:8000

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端运行在 http://localhost:5173

### 运行演示任务

```bash
cd scripts
uv run python run_demo_tasks.py
```

### 运行评测

```bash
cd scripts
uv run python run_eval.py
```

## 目录说明

```
lightclaw/
├── backend/           # Python 后端
│   ├── app/
│   │   ├── api/       # FastAPI 路由
│   │   ├── core/      # 配置、枚举、日志
│   │   ├── db/        # 数据库模型
│   │   ├── schemas/   # Pydantic 模型
│   │   ├── llm/       # LLM 适配器
│   │   ├── runtime/   # Agent 运行时
│   │   ├── memory/    # 记忆系统
│   │   ├── tools/     # 工具实现
│   │   ├── browser/   # 浏览器自动化
│   │   ├── gateway/   # 日志收集
│   │   ├── datapool/  # 数据池
│   │   ├── tasks/     # 任务定义
│   │   ├── eval/      # 评测框架
│   │   └── training/  # 训练数据导出
│   └── tests/         # 测试
├── frontend/          # React 前端
├── scripts/           # 工具脚本
├── data/              # 数据存储
├── docs/              # 文档
└── examples/          # 演示示例
```

## 示例任务

项目内置 20+ 任务，覆盖：

- **信息整理类**: 从网页提取信息写入笔记
- **待办/日程管理类**: 创建待办、日历事件
- **网页表单交互类**: 填写表单、提交数据
- **跨工具多步任务类**: 搜索 → 提取 → 创建 → 写入

## 当前局限

1. 搜索工具为 mock 实现，未接入真实搜索引擎
2. LLM 需要配置 OpenAI-compatible API
3. 训练数据导出已实现，但未接入真实微调流程
4. GUI grounding 使用简单 selector，未实现视觉定位

## 文档

- [系统架构](docs/architecture.md)
- [数据流水线](docs/pipeline.md)
- [失败类型定义](docs/failure_taxonomy.md)
- [评测指标](docs/evaluation.md)
- [训练数据导出](docs/training_data_export.md)
- [开发路线图](docs/roadmap.md)
