# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**LightClaw** is a lightweight self-evolving agent system for personal productivity management. It features online trajectory collection, data pool management, training data export, and unified evaluation with frontend visualization.

## Common Commands

### Backend

```bash
# Install dependencies
cd backend
uv sync

# Copy environment file
cp .env.example .env
# Edit .env to configure LLM API

# Run development server
uv run python -m app.main

# Run tests
uv run pytest

# Run linting
uv run ruff check app/
```

### Frontend

```bash
# Install dependencies
cd frontend
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

### Scripts

```bash
# Seed demo data
cd scripts
uv run python seed_demo_data.py

# Run demo tasks
uv run python run_demo_tasks.py

# Run evaluation
uv run python run_eval.py

# Export training samples
uv run python export_samples.py
```

## Architecture

### Core Layers

1. **Runtime Layer** (`backend/app/runtime/`)
   - Agent loop with Plan → Act → Observe → Retry/Replan cycle
   - Components: Agent, Planner, Executor, Observer, RecoveryManager, State
   - Key file: `agent.py` - main execution loop

2. **Gateway Layer** (`backend/app/gateway/`)
   - Event collection and persistence
   - Logs: task events, step events, errors, GUI actions
   - Output: JSONL trajectory files in `data/trajectories/`

3. **DataPool Layer** (`backend/app/datapool/`)
   - Sample types: tool_use, self_correction, gui_grounding
   - Trajectory types: success, failure, repair
   - Export to training formats

4. **Evaluation Layer** (`backend/app/eval/`)
   - Metrics: task_success_rate, tool_execution_success_rate, recovery_rate, gui_action_accuracy
   - Benchmark runner for built-in tasks

5. **Tools System** (`backend/app/tools/`)
   - 12 tools: search, browser, file, notes, todos, calendar, calculator
   - Each tool has: schema, parameters, validation, execution

### Key Files

- `backend/app/main.py`: FastAPI app entry point
- `backend/app/core/config.py`: Settings and environment configuration
- `backend/app/core/enums.py`: All enum definitions (FailureType, TaskStatus, etc.)
- `backend/app/runtime/agent.py`: Main agent loop
- `backend/app/tools/registry.py`: Tool registration and retrieval
- `backend/app/tasks/definitions.py`: 20 built-in tasks

## Important Patterns

### Tool Implementation

```python
class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Tool description"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [ToolParameter(name="arg1", type="string", description="...", required=True)]

    async def execute(self, args: dict, context: ToolContext) -> ToolResult:
        # Implementation
        return self.create_success_result(result) or self.create_error_result(error, FailureType.XXX)
```

### Adding a New Task

Edit `backend/app/tasks/definitions.py`:

```python
TaskDefinition(
    task_id="new_task_001",
    instruction="Task instruction",
    category=TaskCategory.XXX,
    difficulty=TaskDifficulty.EASY,
    allowed_tools=["tool1", "tool2"],
    target_state={...},
    validation_rules={...},
)
```

### Failure Types

Defined in `backend/app/core/enums.py`:
- wrong_tool, wrong_args, tool_runtime_error
- gui_click_miss, gui_wrong_element, gui_state_stale
- planning_error, observation_error
- repair_success, repair_failed

## Data Flow

```
User Instruction → Agent.run() → Planner.decide_next_action()
    → Executor.execute() → Gateway.log_step()
    → Observer.observe() → (loop until done)
    → DataPoolBuilder.build_from_trajectory()
    → Export training samples
```

## Configuration

Environment variables (`.env`):
- `LLM_API_KEY`: Required - OpenAI-compatible API key
- `LLM_MODEL`: Model name (default: gpt-4o-mini)
- `LLM_BASE_URL`: API endpoint (default: OpenAI)
- `HEADLESS_BROWSER`: Playwright headless mode (default: true)

## Testing Strategy

- Tests located in `backend/tests/`
- Use pytest with async support
- Mock LLM calls for unit tests
- Integration tests require real LLM API

## Current Limitations

1. Search is mock implementation (no real search API)
2. Bounding box not implemented for GUI grounding
3. No real fine-tuning pipeline yet
4. Limited test coverage

## Extension Points

1. **New LLM Provider**: Implement `BaseLLMAdapter`
2. **New Tool**: Extend `BaseTool` and register in `tools/registry.py`
3. **New Metric**: Add to `eval/metrics.py`
4. **Memory Backend**: Extend memory managers for vector storage
