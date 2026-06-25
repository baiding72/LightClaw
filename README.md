# LightClaw

LightClaw is a local agent harness for experimenting with custom ReAct loops, tool execution, memory routing, policy gates, and badcase-driven evaluation. It includes a Python runtime for the agent and a Tauri/Vite client for inspecting runs and traces.

## What It Includes

- A custom ReAct agent loop without LangGraph.
- OpenAI and Anthropic chat model adapters through LangChain packages.
- Built-in tools for time, calculation, web lookup, notes, profile memory, office files, shell, and tasks.
- Memory routing rules for session memory, user profile memory, project notes, and workspace files.
- Tool policy and guardrail tests for risky or ambiguous tool calls.
- JSONL run traces and deterministic eval cases for regression testing.
- A local Mac client for replaying traces and running interactive turns.

## Repository Layout

```text
.
├── main.py                 # Interactive CLI entry point
├── interactive_turn.py     # One-turn runner used by the client and eval flows
├── core/                   # Agent loop, providers, tools, memory, policy, state
├── evals/                  # Evaluation runners, cases, and badcase scripts
├── tests/                  # Pytest regression suite
├── docs/                   # Design notes and migration documentation
├── badcases/               # Known failure cases and analysis
├── config/                 # Runtime policy configuration
└── client/                 # React + Vite + Tauri desktop inspector
```

Generated runtime data such as `.env`, `runs/`, `sessions/`, `workspace/`, `runtime/`, `node_modules/`, and Tauri `target/` builds is intentionally ignored by Git.

## Requirements

- Python 3.11 or newer
- Node.js 18 or newer
- npm
- Rust toolchain, only required for the Tauri desktop app

Python packages used by the current runtime:

```bash
python3 -m pip install langchain-core langchain-openai langchain-anthropic pytest
```

The frontend dependencies are declared in `client/package.json`.

## Configuration

Create a local `.env` file in the repository root:

```bash
OPENAI_API_KEY=your-openai-key
MYCLAW_PROVIDER=openai
MYCLAW_MODEL=gpt-4o
```

For Anthropic:

```bash
ANTHROPIC_API_KEY=your-anthropic-key
MYCLAW_PROVIDER=anthropic
MYCLAW_MODEL=claude-sonnet-4-7-20250514
```

For OpenAI-compatible providers, set:

```bash
OPENAI_API_BASE=https://your-compatible-endpoint.example/v1
```

## Run The CLI

```bash
python3 main.py
```

The CLI starts an interactive agent session. Type `exit`, `quit`, or `q` to stop.

## Run The Client

Browser preview:

```bash
cd client
npm install
npm run dev
```

Tauri desktop app:

```bash
cd client
npm run tauri -- dev
```

Build the Mac app:

```bash
cd client
npm run tauri -- build
```

## Run Tests

```bash
python3 -m pytest tests -q
```

Some integration tests require a configured LLM API key. Unit-style tests use fake models and should run without external services.

## Run Evaluations

Basic evaluation runner:

```bash
python3 -m evals.agent_eval_runner --case-file evals/cases/basic_tasks.json
```

Known badcase probe:

```bash
python3 -m evals.badcase_0001_context_memory
```

Evaluation traces and generated reports are local artifacts and are not committed by default.

## Development Notes

- Keep secrets in `.env`; do not commit API keys or credentials.
- Keep generated traces under `runs/` and session data under `sessions/`.
- Add new tools under `core/tools/` and cover behavior with focused tests in `tests/`.
- Use `docs/` and `badcases/` to preserve design decisions and failure analyses.

## Current Status

LightClaw is an experimental local harness. The codebase is structured for rapid iteration on agent behavior, memory policy, tool safety, and trace-based debugging rather than production deployment.
