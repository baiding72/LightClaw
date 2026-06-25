import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Bot,
  Bug,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  FileText,
  FlaskConical,
  Folder,
  MessageSquare,
  Play,
  RefreshCw,
  Save,
  Search,
  Settings,
  TerminalSquare,
  Wrench,
  XCircle,
} from "lucide-react";
import "./styles.css";

type RunSummary = {
  id: string;
  path: string;
  modified_ms: number;
  event_count: number;
  title: string;
  run_type: string;
  session_id?: string | null;
  pass_count?: number | null;
  fail_count?: number | null;
  model?: string | null;
};

type TraceEvent = {
  ts?: string;
  run_id?: string;
  event: string;
  [key: string]: unknown;
};

type EventGroup = {
  id: string;
  title: string;
  subtitle: string;
  eventIndexes: number[];
  children?: EventGroup[];
};

type DisplayMessage = {
  key: string;
  role: "user" | "assistant";
  text: string;
  meta?: string;
};

type EvalCaseReport = {
  id: string;
  title: string;
  passed?: boolean;
  inputs: string[];
  replayAnswers: string[];
  failures: string[];
  tracePaths: string[];
  toolNames: string[];
};

type RunListGroup = {
  id: string;
  title: string;
  subtitle: string;
  runs: RunSummary[];
};

type ChatTurnResult = {
  session_id: string;
  run_id: string;
  run_path: string;
  answer: string;
};

type ToolSummary = {
  name: string;
  description: string;
  parameters: Record<string, { type?: string; description?: string }>;
  required: string[];
  permission: string;
  resource: string;
  action: string;
  risk: string;
  requires_consent: boolean;
};

type WorkspaceFileEntry = {
  path: string;
  is_dir: boolean;
  size: number;
  modified_ms: number;
  depth: number;
};

type WorkspaceFileContent = {
  path: string;
  content: string;
  truncated: boolean;
};

type PolicyConfig = {
  mode: "off" | "default" | "plan" | "auto";
  approval_timeout_seconds: number;
};

type PendingToolGate = {
  request_id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  permission: string;
  risk: string;
  reason: string;
  memory_scope?: string;
  source_route?: string;
};

type PendingMemoryCandidate = {
  candidate_key: string;
  candidate_label: string;
  candidate_evidence: string;
  candidate_evidence_count: number;
  candidate_threshold: number;
};

type MemoryCandidateDecision = {
  decision: "saved" | "dismissed";
  until_ms: number;
};

declare global {
  interface Window {
    __TAURI__?: unknown;
    __TAURI_INTERNALS__?: unknown;
  }
}

const isTauri =
  typeof window !== "undefined" && ("__TAURI_INTERNALS__" in window || "__TAURI__" in window);

const MEMORY_CANDIDATE_DECISIONS_KEY = "myclaw-memory-candidate-decisions";

function memoryCandidateDecision(candidateKey: string): MemoryCandidateDecision | null {
  try {
    const raw = window.localStorage.getItem(MEMORY_CANDIDATE_DECISIONS_KEY);
    if (!raw) return null;
    const decisions = JSON.parse(raw) as Record<string, MemoryCandidateDecision>;
    const decision = decisions[candidateKey];
    if (!decision || decision.until_ms <= Date.now()) return null;
    return decision;
  } catch {
    return null;
  }
}

function rememberMemoryCandidateDecision(candidateKey: string, decision: "saved" | "dismissed") {
  try {
    const raw = window.localStorage.getItem(MEMORY_CANDIDATE_DECISIONS_KEY);
    const decisions = raw ? (JSON.parse(raw) as Record<string, MemoryCandidateDecision>) : {};
    decisions[candidateKey] = {
      decision,
      until_ms: Date.now() + (decision === "saved" ? 365 * 24 * 60 * 60 * 1000 : 30 * 60 * 1000),
    };
    window.localStorage.setItem(MEMORY_CANDIDATE_DECISIONS_KEY, JSON.stringify(decisions));
  } catch {
    // Local suppression is best-effort; failed storage should not block confirmation.
  }
}

function memoryCandidateSaveText(candidate: PendingMemoryCandidate) {
  const profileLines: Record<string, string> = {
    "answer_style.concise": "回答风格：简洁直接",
    "language.zh": "回答语言：优先使用中文",
    "workflow.test_first": "工作流偏好：修改后先验证或跑测试，再总结结果",
    "answer_structure.conclusion_first": "回答结构：先给结论，再解释原因",
  };
  return `请记住：${profileLines[candidate.candidate_key] ?? candidate.candidate_label}`;
}

async function invokeCommand<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  if (!isTauri) {
    return mockInvoke(command, args) as T;
  }
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<T>(command, args);
}

const mockEvalEvents: TraceEvent[] = [
  {
    event: "eval_case_started",
    case_id: "badcase_0001_context_memory",
    iteration: 1,
    provider: "openai",
    model: "MiniMax-M2.7",
    seed: "我们正在学习 myClaw MVP 的 agent harness。",
    probe: "我刚刚在学习什么？",
  },
  {
    event: "agent_app_created",
    tool_names: ["get_time", "calculator", "echo", "list_office_files", "read_office_file", "write_office_file"],
    system_prompt_preview: "You are a helpful AI assistant running inside the myClaw ReAct harness...",
  },
  {
    event: "eval_user_input",
    content_preview: "我们正在学习 myClaw MVP 的 agent harness。",
    state_message_count: 0,
  },
  {
    event: "llm_input",
    message_count: 2,
    state_message_count: 1,
    has_summary: false,
    message_types: ["SystemMessage", "HumanMessage"],
    messages: [
      { type: "SystemMessage", content_preview: "Use the ReAct loop..." },
      { type: "HumanMessage", content_preview: "我们正在学习 myClaw MVP 的 agent harness。" },
    ],
  },
  {
    event: "ai_message",
    react_phase: "final",
    content_preview: "收到，我们正在学习 myClaw MVP 的 agent harness。",
  },
  {
    event: "eval_user_input",
    content_preview: "我刚刚在学习什么？",
    state_message_count: 2,
  },
  {
    event: "llm_input",
    message_count: 4,
    state_message_count: 3,
    has_summary: false,
    message_types: ["SystemMessage", "HumanMessage", "AIMessage", "HumanMessage"],
    messages: [
      { type: "SystemMessage", content_preview: "Use the ReAct loop..." },
      { type: "HumanMessage", content_preview: "我们正在学习 myClaw MVP 的 agent harness。" },
      { type: "AIMessage", content_preview: "收到，我们正在学习 myClaw MVP 的 agent harness。" },
      { type: "HumanMessage", content_preview: "我刚刚在学习什么？" },
    ],
  },
  {
    event: "ai_message",
    react_phase: "final",
    content_preview: "你刚刚在学习 myClaw MVP 的 agent harness。",
  },
  {
    event: "eval_case_completed",
    passed: true,
    failures: [],
    elapsed_seconds: 9.42,
    final_message_count: 4,
  },
  {
    event: "eval_summary",
    pass_count: 1,
    fail_count: 0,
  },
];

const mockInteractiveEvents: TraceEvent[] = [];

function mockInvoke(command: string, args?: Record<string, unknown>): unknown {
  if (command === "list_runs") {
    const interactiveSession = mockInteractiveEvents.find((event) => event.event === "interactive_session_started");
    const evalRun = {
      id: "mock-badcase-0001",
      path: "mock://badcase-0001",
      modified_ms: 1200,
      event_count: mockEvalEvents.length,
      title: "badcase 0001 context memory",
      run_type: "eval",
      pass_count: 1,
      fail_count: 0,
      model: "MiniMax-M2.7",
    };
    if (interactiveSession) {
      return [
        {
          id: "mock-interactive-session",
          path: "mock://interactive-session",
          modified_ms: 0,
          event_count: mockInteractiveEvents.length,
          title: `Interactive · ${String(interactiveSession.session_id ?? "browser-preview")}`,
          run_type: "interactive",
          session_id: String(interactiveSession.session_id ?? "browser-preview"),
          pass_count: null,
          fail_count: null,
          model: "Browser preview",
        },
        evalRun,
      ];
    }
    return [evalRun];
  }
  if (command === "read_run") {
    const path = String(args?.path ?? "");
    return path.includes("interactive") ? [...mockInteractiveEvents] : [...mockEvalEvents];
  }
  if (command === "create_eval_from_trace") {
    return `Mock eval spec generated from ${String(args?.path ?? "selected trace")}.`;
  }
  if (command === "start_eval_from_trace") {
    return `Mock eval started from ${String(args?.path ?? "selected trace")}.\nRun log: mock://badcase-0001`;
  }
  if (command === "start_agent_eval") {
    return `Mock agent eval started for ${String(args?.suite ?? "basic_tasks")}.\nRun log: mock://badcase-0001`;
  }
  if (command === "list_agent_tools") {
    return [
      {
        name: "calculator",
        description: "Evaluate a simple math expression.",
        parameters: { expression: { type: "string" } },
        required: ["expression"],
        permission: "tool:execute",
        resource: "tool",
        action: "execute",
        risk: "low",
        requires_consent: false,
      },
      {
        name: "save_note",
        description: "Create a new note in local storage.",
        parameters: { content: { type: "string" }, title: { type: "string" } },
        required: ["content"],
        permission: "memory.note:create",
        resource: "memory.note",
        action: "create",
        risk: "medium",
        requires_consent: true,
      },
    ];
  }
  if (command === "list_workspace_files") {
    return [
      { path: "memory/", is_dir: true, size: 0, modified_ms: 60000, depth: 0 },
      { path: "memory/profile.md", is_dir: false, size: 128, modified_ms: 70000, depth: 1 },
      { path: "memory/MEMORY.md", is_dir: false, size: 256, modified_ms: 80000, depth: 1 },
      { path: "office/", is_dir: true, size: 0, modified_ms: 240000, depth: 0 },
      { path: "office/notes/react.txt", is_dir: false, size: 64, modified_ms: 300000, depth: 2 },
    ];
  }
  if (command === "read_workspace_file") {
    return {
      path: String(args?.path ?? "memory/profile.md"),
      content: "myClaw memory design:\n\n- SessionState stores current thread state.\n- Summary stores compressed old turns.\n- Profile stores long-term user preferences.\n",
      truncated: false,
    };
  }
  if (command === "write_workspace_file") {
    return {
      path: String(args?.path ?? "memory/profile.md"),
      content: String(args?.content ?? ""),
      truncated: false,
    };
  }
  if (command === "get_policy_config") {
    return { mode: "off", approval_timeout_seconds: 300 };
  }
  if (command === "set_policy_config") {
    return args?.config ?? { mode: "off", approval_timeout_seconds: 300 };
  }
  if (command === "submit_tool_gate_decision") {
    return null;
  }
  if (command === "create_chat_session") {
    const sessionId = String(args?.sessionId ?? `browser-${Date.now()}`);
    mockInteractiveEvents.length = 0;
    mockInteractiveEvents.push({
      event: "interactive_session_started",
      session_id: sessionId,
      source: "browser_preview",
    });
    return {
      session_id: sessionId,
      run_id: "mock-badcase-0001",
      run_path: "mock://interactive-session",
      answer: "",
    };
  }
  if (command === "send_chat_message") {
    mockInteractiveEvents.push(
      {
        event: "user_input",
        content_preview: String(args?.message ?? ""),
        state_message_count: 0,
      },
      {
        event: "llm_input",
        message_count: 2,
        state_message_count: 1,
        has_summary: false,
        message_types: ["SystemMessage", "HumanMessage"],
      },
      {
        event: "ai_message",
        react_phase: "final",
        content_preview: `Mock answer for: ${String(args?.message ?? "")}`,
      },
      {
        event: "turn_completed",
        state_message_count: 2,
        has_summary: false,
      },
    );
    return {
      session_id: String(args?.sessionId ?? "browser-preview"),
      run_id: "mock-badcase-0001",
      run_path: "mock://interactive-session",
      answer: `Mock answer for: ${String(args?.message ?? "")}`,
    };
  }
  return null;
}

function eventTone(event: string) {
  if (event.includes("error") || event.includes("fail")) return "bad";
  if (event.includes("completed") || event.includes("summary")) return "good";
  if (event.includes("tool")) return "tool";
  if (event.includes("llm")) return "llm";
  return "neutral";
}

function eventDescription(event: string) {
  const descriptions: Record<string, string> = {
    agent_app_created: "创建 agent 图并绑定当前可用工具。",
    ai_message: "模型输出最终回复，没有继续调用工具。",
    eval_case_completed: "单个评测用例已结束，包含通过状态和失败原因。",
    eval_case_error: "评测运行异常，通常需要查看错误字段。",
    eval_case_started: "评测用例开始，记录模型、输入和判定规则。",
    eval_summary: "本次评测批次汇总，统计通过和失败次数。",
    eval_user_input: "评测脚本注入的一轮用户输入。",
    interactive_session_started: "交互会话开始，记录模型和 session id。",
    llm_input: "即将发送给模型的完整消息列表和上下文状态。",
    memory_candidate_signal: "隐含记忆候选信号，仅记录候选与确认状态，不直接写入长期 profile。",
    tool_gate_decision: "权限系统对工具调用的 allow/ask/deny 决策。",
    tool_call: "模型选择调用工具，这是 ReAct 的 Action。",
    tool_result: "工具执行结果回到模型，这是 ReAct 的 Observation。",
    turn_completed: "一轮交互结束，记录最终消息数量和摘要状态。",
    user_input: "真实交互里用户输入的一轮消息。",
  };
  return descriptions[event] ?? "暂未配置说明，可查看右侧 JSON 字段理解该事件。";
}

function formatRelative(ms: number) {
  if (!ms) return "just now";
  const minutes = Math.round(ms / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

function formatBytes(size: number) {
  if (!size) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function stringify(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function userEvents(events: TraceEvent[]) {
  return events.filter((event) => event.event === "eval_user_input" || event.event === "user_input");
}

function assistantEvents(events: TraceEvent[]) {
  return events.filter((event) => event.event === "ai_message");
}

function eventText(event: TraceEvent) {
  return String(event.content ?? event.answer ?? event.content_preview ?? event.answer_preview ?? "");
}

function eventPreview(event: TraceEvent) {
  const preview = event.content_preview ?? event.probe ?? event.seed ?? event.answer_preview ?? "";
  return String(preview).replace(/\s+/g, " ").slice(0, 36);
}

function formatFailures(value: unknown) {
  if (!Array.isArray(value) || value.length === 0) return "";
  return value.map((item) => `- ${String(item)}`).join("\n");
}

function evalMessages(events: TraceEvent[]): DisplayMessage[] {
  const messages: DisplayMessage[] = [];
  let replayCount = 0;

  events.forEach((event, index) => {
    if (event.event === "eval_user_input") {
      messages.push({
        key: `eval-user-${index}`,
        role: "user",
        text: String(event.content ?? event.content_preview ?? ""),
        meta: `case ${String(event.case_id ?? "-")} · turn ${String(event.turn ?? event.conversation_turn ?? "-")}`,
      });
      return;
    }

    if (event.event === "eval_turn_replayed") {
      replayCount += 1;
      messages.push({
        key: `eval-replay-${index}`,
        role: "assistant",
        text: String(event.answer ?? event.answer_preview ?? "(no answer captured)"),
        meta: `replay · ${event.passed === false ? "failed" : "passed"} · tools ${
          Array.isArray(event.tool_names) ? event.tool_names.filter(Boolean).join(", ") || "-" : "-"
        }`,
      });
      return;
    }

    if (event.event === "eval_case_completed") {
      const failures = formatFailures(event.failures);
      const passed = event.passed === true;
      const hasReplayAnswer = replayCount > 0 || event.answer_preview;
      messages.push({
        key: `eval-case-${index}`,
        role: "assistant",
        text:
          String(event.answer_preview ?? "") ||
          (failures ? `Failures:\n${failures}` : passed ? "Case passed." : "Case completed."),
        meta: `case ${String(event.case_id ?? "-")} · ${passed ? "PASS" : "FAIL"}`,
      });
      if (!hasReplayAnswer && !failures && !passed) {
        messages[messages.length - 1].text = "Case completed without replay transcript fields.";
      }
      return;
    }

    if (event.event === "eval_summary") {
      messages.push({
        key: `eval-summary-${index}`,
        role: "assistant",
        text: `Summary: ${String(event.pass_count ?? 0)} passed, ${String(event.fail_count ?? 0)} failed.`,
        meta: "eval summary",
      });
    }
  });

  return messages;
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function buildEvalCaseReports(events: TraceEvent[]): EvalCaseReport[] {
  const reports = new Map<string, EvalCaseReport>();
  const order: string[] = [];

  function ensure(caseId: string, title?: unknown) {
    if (!reports.has(caseId)) {
      reports.set(caseId, {
        id: caseId,
        title: String(title ?? caseId),
        inputs: [],
        replayAnswers: [],
        failures: [],
        tracePaths: [],
        toolNames: [],
      });
      order.push(caseId);
    }
    const report = reports.get(caseId)!;
    if (title && report.title === caseId) report.title = String(title);
    return report;
  }

  events.forEach((event) => {
    const rawCaseId = event.case_id ?? event.suite_id ?? event.run_id ?? "eval";
    const caseId = String(rawCaseId);
    if (!event.event.startsWith("eval_")) return;

    if (event.event === "eval_suite_started" || event.event === "eval_summary") return;

    const report = ensure(caseId, event.title);
    if (event.event === "eval_case_started") {
      report.tracePaths.push(...stringArray(event.trace_paths));
      return;
    }
    if (event.event === "eval_user_input") {
      const input = String(event.content ?? event.content_preview ?? "").trim();
      if (input) report.inputs.push(input);
      return;
    }
    if (event.event === "eval_turn_replayed") {
      const answer = String(event.answer ?? event.answer_preview ?? "").trim();
      if (answer) report.replayAnswers.push(answer);
      report.toolNames.push(...stringArray(event.tool_names));
      if (event.passed === false) report.passed = false;
      report.failures.push(...stringArray(event.failures));
      return;
    }
    if (event.event === "eval_case_completed") {
      if (typeof event.passed === "boolean") report.passed = event.passed;
      report.failures.push(...stringArray(event.failures));
      report.tracePaths.push(...stringArray(event.trace_paths));
      const answer = String(event.answer_preview ?? "").trim();
      if (answer) report.replayAnswers.push(answer);
    }
  });

  return order.map((caseId) => {
    const report = reports.get(caseId)!;
    return {
      ...report,
      failures: Array.from(new Set(report.failures)),
      tracePaths: Array.from(new Set(report.tracePaths)),
      toolNames: Array.from(new Set(report.toolNames.filter(Boolean))),
    };
  });
}

function evalRunGroup(run: RunSummary): Omit<RunListGroup, "runs"> {
  const id = `${run.id} ${run.title}`.toLowerCase();
  if (run.run_type === "interactive") {
    return {
      id: "source-traces",
      title: "Source Traces",
      subtitle: "历史对话，可一键 replay 成 eval",
    };
  }
  if (id.includes("basic_tasks") || id.includes("agent-eval-basic")) {
    return {
      id: "basic-agent",
      title: "Basic Agent Evals",
      subtitle: "基础工具与 ReAct 能力回归",
    };
  }
  if (
    id.includes("memory_policy_badcases") ||
    id.includes("trace-eval-memory_policy") ||
    id.includes("memory_module_cases") ||
    id.includes("agent-eval-memory_module")
  ) {
    return {
      id: "memory-evals",
      title: "Memory Evals",
      subtitle: "live_agent / trace_regression · 记忆模块与历史回归",
    };
  }
  if (id.includes("trace_eval") || id.includes("interactive-eval") || id.includes("generated_from_trace")) {
    return {
      id: "trace-replay",
      title: "Trace Replay Evals",
      subtitle: "从旧 trace 抽取用户输入后重放",
    };
  }
  if (id.includes("two-phase")) {
    return {
      id: "two-phase",
      title: "Two-Phase Skill Evals",
      subtitle: "help/run 技能选择回归",
    };
  }
  return {
    id: "other-evals",
    title: "Other Evals",
    subtitle: "其他评测运行",
  };
}

function groupEvalRuns(runs: RunSummary[]): RunListGroup[] {
  const groups = new Map<string, RunListGroup>();
  for (const run of runs) {
    const base = evalRunGroup(run);
    if (!groups.has(base.id)) {
      groups.set(base.id, { ...base, runs: [] });
    }
    groups.get(base.id)!.runs.push(run);
  }
  const order = ["basic-agent", "memory-evals", "trace-replay", "two-phase", "other-evals", "source-traces"];
  return Array.from(groups.values()).sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
}

function eventConversationTurn(event: TraceEvent, fallback: number) {
  const value = event.conversation_turn;
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function eventReactStep(event: TraceEvent, fallback: number) {
  const value = event.react_step;
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function stepSubtitle(events: TraceEvent[], indexes: number[]) {
  const names = indexes.map((index) => events[index]?.event).filter(Boolean);
  const hasFinal = names.includes("ai_message");
  const toolNames = indexes
    .map((index) => events[index]?.tool_name)
    .filter((name): name is string => typeof name === "string" && name.length > 0);
  if (toolNames.length > 0) return `tool: ${Array.from(new Set(toolNames)).join(", ")}`;
  if (hasFinal) return "final answer";
  return names.join(" -> ") || "agent step";
}

function groupEventsByTurn(events: TraceEvent[]): EventGroup[] {
  const groups: EventGroup[] = [];
  let currentTurn: EventGroup | null = null;
  let currentStep: EventGroup | null = null;
  let turnCount = 0;
  let inferredStep = 0;
  let setupIndexes: number[] = [];
  let closingIndexes: number[] = [];

  function flushSetup() {
    if (setupIndexes.length === 0) return;
    groups.push({
      id: "setup",
      title: "Run Setup",
      subtitle: "启动、工具绑定、评测配置",
      eventIndexes: setupIndexes,
    });
    setupIndexes = [];
  }

  events.forEach((event, index) => {
    if (event.event === "eval_user_input" || event.event === "user_input") {
      flushSetup();
      turnCount = eventConversationTurn(event, turnCount + 1);
      inferredStep = 0;
      currentTurn = {
        id: `turn-${turnCount}`,
        title: `Conversation Turn ${turnCount}`,
        subtitle: eventPreview(event) || eventDescription(event.event),
        eventIndexes: [index],
        children: [],
      };
      groups.push(currentTurn);
      currentStep = null;
      return;
    }

    if (event.event === "eval_case_completed" || event.event === "eval_summary" || event.event === "turn_completed") {
      if (currentTurn && event.event === "turn_completed") {
        currentTurn.eventIndexes.push(index);
        const step = eventReactStep(event, inferredStep || 1);
        if (!currentStep || currentStep.id !== `turn-${turnCount}-step-${step}`) {
          currentStep = {
            id: `turn-${turnCount}-step-${step}`,
            title: `ReAct Step ${step}`,
            subtitle: "completed",
            eventIndexes: [],
          };
          currentTurn.children?.push(currentStep);
        }
        currentStep.eventIndexes.push(index);
      } else {
        closingIndexes.push(index);
      }
      return;
    }

    if (currentTurn) {
      currentTurn.eventIndexes.push(index);
      if (event.event === "llm_input") {
        inferredStep += 1;
      }
      const step = eventReactStep(event, inferredStep || 1);
      if (!currentStep || currentStep.id !== `turn-${turnCount}-step-${step}`) {
        currentStep = {
          id: `turn-${turnCount}-step-${step}`,
          title: `ReAct Step ${step}`,
          subtitle: "",
          eventIndexes: [],
        };
        currentTurn.children?.push(currentStep);
      }
      currentStep.eventIndexes.push(index);
      currentStep.subtitle = stepSubtitle(events, currentStep.eventIndexes);
    } else {
      setupIndexes.push(index);
    }
  });

  flushSetup();
  if (closingIndexes.length > 0) {
    groups.push({
      id: "summary",
      title: "Run Summary",
      subtitle: "结束状态和统计结果",
      eventIndexes: closingIndexes,
    });
  }

  return groups;
}

function App() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<RunSummary | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [selectedEventIndex, setSelectedEventIndex] = useState<number>(0);
  const [query, setQuery] = useState("");
  const [activeView, setActiveView] = useState("sessions");
  const [evalOutput, setEvalOutput] = useState("");
  const [runningEvalPath, setRunningEvalPath] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [chatSessionId, setChatSessionId] = useState(() => `client-${Date.now()}`);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [collapsedRunGroups, setCollapsedRunGroups] = useState<Record<string, boolean>>({});
  const [errorMessage, setErrorMessage] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingToolCalls, setStreamingToolCalls] = useState<Array<{name: string, args: Record<string, unknown>, result?: string}>>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [agentTools, setAgentTools] = useState<ToolSummary[]>([]);
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFileEntry[]>([]);
  const [collapsedFileDirs, setCollapsedFileDirs] = useState<Record<string, boolean>>({});
  const [selectedWorkspaceFile, setSelectedWorkspaceFile] = useState<WorkspaceFileEntry | null>(null);
  const [workspaceFileContent, setWorkspaceFileContent] = useState<WorkspaceFileContent | null>(null);
  const [workspaceFileDraft, setWorkspaceFileDraft] = useState("");
  const [filePreviewLoading, setFilePreviewLoading] = useState(false);
  const [fileSaving, setFileSaving] = useState(false);
  const [resourceLoading, setResourceLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [policyConfig, setPolicyConfig] = useState<PolicyConfig>({ mode: "off", approval_timeout_seconds: 300 });
  const [pendingToolGate, setPendingToolGate] = useState<PendingToolGate | null>(null);
  const [pendingMemoryCandidate, setPendingMemoryCandidate] = useState<PendingMemoryCandidate | null>(null);
  const [queuedMemorySaveMessage, setQueuedMemorySaveMessage] = useState("");
  const [layoutWidths, setLayoutWidths] = useState(() => {
    const fallback = { runs: 292, inspector: 360 };
    try {
      const saved = window.localStorage.getItem("myclaw-layout-widths");
      if (!saved) return fallback;
      const parsed = JSON.parse(saved) as Partial<typeof fallback>;
      return {
        runs: clamp(Number(parsed.runs ?? fallback.runs), 230, 460),
        inspector: clamp(Number(parsed.inspector ?? fallback.inspector), 300, 620),
      };
    } catch {
      return fallback;
    }
  });

  useEffect(() => {
    window.localStorage.setItem("myclaw-layout-widths", JSON.stringify(layoutWidths));
  }, [layoutWidths]);

  useEffect(() => {
    invokeCommand<PolicyConfig>("get_policy_config")
      .then(setPolicyConfig)
      .catch((error) => setErrorMessage(String(error)));
  }, []);

  function startResizePane(pane: "runs" | "inspector", event: React.PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    const startX = event.clientX;
    const startRuns = layoutWidths.runs;
    const startInspector = layoutWidths.inspector;

    function onPointerMove(moveEvent: PointerEvent) {
      const delta = moveEvent.clientX - startX;
      setLayoutWidths({
        runs: pane === "runs" ? clamp(startRuns + delta, 230, 460) : startRuns,
        inspector: pane === "inspector" ? clamp(startInspector - delta, 300, 620) : startInspector,
      });
    }

    function onPointerUp() {
      document.body.classList.remove("is-resizing-layout");
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    }

    document.body.classList.add("is-resizing-layout");
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  }

  useEffect(() => {
    let unlistenContent: (() => void) | undefined;
    let unlistenToolCall: (() => void) | undefined;
    let unlistenToolResult: (() => void) | undefined;
    let unlistenToolGate: (() => void) | undefined;
    let unlistenMemoryCandidate: (() => void) | undefined;
    let unlistenFinal: (() => void) | undefined;
    let unlistenStreamComplete: (() => void) | undefined;
    let unlistenStreamError: (() => void) | undefined;

    async function setupListeners() {
      if (!isTauri) return;
      try {
        const { listen } = await import("@tauri-apps/api/event");

        unlistenContent = await listen("content_chunk", (event) => {
          const payload = event.payload as { content?: string };
          if (payload?.content) {
            setStreamingContent((prev) => prev + payload.content);
          }
        });

        unlistenToolCall = await listen("tool_call", (event) => {
          const payload = event.payload as { tool_name?: string; tool_args?: Record<string, unknown>; tool_call_id?: string };
          const toolName = payload?.tool_name;
          if (toolName) {
            setStreamingToolCalls((prev) => [
              ...prev,
              { name: toolName, args: payload?.tool_args || {}, result: undefined },
            ]);
          }
        });

        unlistenToolResult = await listen("tool_result", (event) => {
          const payload = event.payload as { tool_name?: string; result?: string; tool_call_id?: string };
          const toolName = payload?.tool_name;
          if (toolName) {
            setStreamingToolCalls((prev) => {
              const updated: Array<{name: string; args: Record<string, unknown>; result?: string}> = [...prev];
              const last = updated[updated.length - 1];
              if (last && last.name === toolName && payload?.result !== undefined) {
                last.result = payload.result;
              }
              return updated;
            });
          }
        });

        unlistenToolGate = await listen("tool_gate_decision", (event) => {
          const payload = event.payload as Partial<PendingToolGate> & {
            tool_gate_decision?: string;
            request_id?: string;
          };
          if (payload?.tool_gate_decision === "ask" && payload.request_id) {
            setPendingToolGate({
              request_id: payload.request_id,
              tool_name: String(payload.tool_name ?? "unknown_tool"),
              tool_args: (payload.tool_args as Record<string, unknown>) ?? {},
              permission: String(payload.permission ?? ""),
              risk: String(payload.risk ?? ""),
              reason: String(payload.reason ?? ""),
              memory_scope: payload.memory_scope ? String(payload.memory_scope) : undefined,
              source_route: payload.source_route ? String(payload.source_route) : undefined,
            });
          }
        });

        unlistenMemoryCandidate = await listen("memory_candidate_signal", (event) => {
          const payload = event.payload as Partial<PendingMemoryCandidate> & {
            would_prompt_for_confirmation?: boolean;
            suppressed?: boolean;
          };
          if (!payload?.would_prompt_for_confirmation || payload.suppressed) return;
          const candidateKey = String(payload.candidate_key ?? "");
          if (!candidateKey || memoryCandidateDecision(candidateKey)) return;
          setPendingMemoryCandidate({
            candidate_key: candidateKey,
            candidate_label: String(payload.candidate_label ?? candidateKey),
            candidate_evidence: String(payload.candidate_evidence ?? ""),
            candidate_evidence_count: Number(payload.candidate_evidence_count ?? 0),
            candidate_threshold: Number(payload.candidate_threshold ?? 3),
          });
        });

        unlistenFinal = await listen("ai_message", (event) => {
          const payload = event.payload as { content_preview?: string };
          if (payload?.content_preview) {
            setStreamingContent((prev) => prev || payload.content_preview || "");
          }
        });

        unlistenStreamComplete = await listen("stream_complete", async (event) => {
          const payload = event.payload as { run_path?: string };
          if (payload?.run_path) {
            await openRunByPath(payload.run_path);
          } else {
            await refreshRuns();
          }
          setIsStreaming(false);
          setIsSending(false);
          setStreamingContent("");
          setStreamingToolCalls([]);
        });

        unlistenStreamError = await listen("stream_error", (event) => {
          const payload = event.payload as { error?: string; error_type?: string };
          setIsStreaming(false);
          setIsSending(false);
          setErrorMessage(`${payload?.error_type ?? "StreamError"}: ${payload?.error ?? "Unknown error"}`);
        });
      } catch (e) {
        console.error("Failed to setup event listeners:", e);
      }
    }

    setupListeners();

    return () => {
      unlistenContent?.();
      unlistenToolCall?.();
      unlistenToolResult?.();
      unlistenToolGate?.();
      unlistenMemoryCandidate?.();
      unlistenFinal?.();
      unlistenStreamComplete?.();
      unlistenStreamError?.();
    };
  }, [isTauri]);

  async function refreshRuns() {
    try {
      const nextRuns = await invokeCommand<RunSummary[]>("list_runs");
      setRuns(nextRuns);
      if (!selectedRun && nextRuns.length > 0) {
        setSelectedRun(nextRuns[0]);
      }
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(String(error));
    }
  }

  useEffect(() => {
    refreshRuns().catch(console.error);
  }, []);

  useEffect(() => {
    if (!selectedRun) return;
    if (activeView === "tools" || activeView === "files") return;
    invokeCommand<TraceEvent[]>("read_run", { path: selectedRun.path })
      .then((nextEvents) => {
        setEvents(nextEvents);
        setSelectedEventIndex(0);
        setCollapsedGroups({});
        setErrorMessage("");
      })
      .catch((error) => setErrorMessage(String(error)));
  }, [activeView, selectedRun]);

  useEffect(() => {
    if (activeView !== "tools" && activeView !== "files") return;
    setResourceLoading(true);
    const command = activeView === "tools" ? "list_agent_tools" : "list_workspace_files";
    invokeCommand<ToolSummary[] | WorkspaceFileEntry[]>(command)
      .then((items) => {
        if (activeView === "tools") {
          setAgentTools(items as ToolSummary[]);
        } else {
          setWorkspaceFiles(items as WorkspaceFileEntry[]);
        }
        setErrorMessage("");
      })
      .catch((error) => setErrorMessage(String(error)))
      .finally(() => setResourceLoading(false));
  }, [activeView]);

  const visibleRuns = useMemo(() => {
    if (activeView === "sessions") {
      return runs.filter((run) => run.run_type === "interactive");
    }
    if (activeView === "evals") {
      return runs.filter((run) => run.run_type === "interactive" || run.run_type === "eval");
    }
    if (activeView === "tools" || activeView === "files") {
      return [];
    }
    return runs;
  }, [runs, activeView]);

  const filteredRuns = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!text) return visibleRuns;
    return visibleRuns.filter((run) => `${run.title} ${run.model ?? ""} ${run.id}`.toLowerCase().includes(text));
  }, [visibleRuns, query]);
  const evalRunGroups = useMemo(() => groupEvalRuns(filteredRuns), [filteredRuns]);
  const visibleWorkspaceFiles = useMemo(() => {
    const collapsedDirs = Object.entries(collapsedFileDirs)
      .filter(([, collapsed]) => collapsed)
      .map(([path]) => path);
    return workspaceFiles.filter((file) => {
      return !collapsedDirs.some((dir) => file.path !== dir && file.path.startsWith(dir));
    });
  }, [workspaceFiles, collapsedFileDirs]);

  const displayEvents = selectedRun ? events : [];
  const isEvalDisplay = selectedRun?.run_type === "eval" || displayEvents.some((event) => event.event.startsWith("eval_"));
  const selectedEvent = displayEvents[selectedEventIndex] ?? null;
  const users = userEvents(displayEvents);
  const assistants = assistantEvents(displayEvents);
  const evalDisplayMessages = useMemo(() => evalMessages(displayEvents), [displayEvents]);
  const toolCalls = displayEvents.filter((event) => event.event === "tool_call");
  const llmInputs = displayEvents.filter((event) => event.event === "llm_input");
  const evalSummary = displayEvents.find((event) => event.event === "eval_summary");
  const evalCaseReports = useMemo(() => buildEvalCaseReports(displayEvents), [displayEvents]);
  const eventGroups = useMemo(() => groupEventsByTurn(displayEvents), [displayEvents]);
  const currentSessionId = selectedRun?.run_type === "interactive" ? selectedRun.session_id ?? selectedRun.id.replace(/^interactive-/, "") : "";
  const hasBlankInteractiveSession = runs.some((run) => run.run_type === "interactive" && run.event_count <= 1);
  const canContinueSelectedRun = Boolean(currentSessionId);

  useEffect(() => {
    if (filteredRuns.length === 0) {
      setSelectedRun(null);
      setEvents([]);
      setSelectedEventIndex(0);
      return;
    }
    if (!selectedRun || !filteredRuns.some((run) => run.path === selectedRun.path)) {
      setSelectedRun(filteredRuns[0]);
    }
  }, [activeView, filteredRuns, selectedRun]);

  async function startEvalFromRun(run: RunSummary) {
    if (runningEvalPath) return;
    setRunningEvalPath(run.path);
    setEvalOutput("");
    try {
      const output = await invokeCommand<string>("start_eval_from_trace", { path: run.path });
      setEvalOutput(output);
      const runPath = output.match(/Run log:\s*(.+\.jsonl|mock:\/\/[^\s]+)/)?.[1]?.trim();
      if (runPath) {
        await openRunByPath(runPath);
      } else {
        await refreshRuns();
      }
      setActiveView("evals");
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(String(error));
    } finally {
      setRunningEvalPath("");
    }
  }

  async function openRunByPath(path: string) {
    try {
      const nextRuns = await invokeCommand<RunSummary[]>("list_runs");
      setRuns(nextRuns);
      const pathBasename = path.split("/").pop()?.replace(/\.jsonl$/, "") ?? path;
      const nextRun = nextRuns.find((run) => run.path === path || run.id === path || run.id === pathBasename) ?? {
        id: path.split("/").pop()?.replace(/\.jsonl$/, "") ?? path,
        path,
        modified_ms: 0,
        event_count: 0,
        title: "Interactive Session",
        run_type: "interactive",
        session_id: path.split("/").pop()?.replace(/^interactive-/, "").replace(/\.jsonl$/, "") ?? null,
        pass_count: null,
        fail_count: null,
        model: null,
      };
      setSelectedRun(nextRun);
      const nextEvents = await invokeCommand<TraceEvent[]>("read_run", { path: nextRun.path });
      setEvents(nextEvents);
      setSelectedEventIndex(Math.max(0, nextEvents.length - 1));
      setCollapsedGroups({});
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(String(error));
    }
  }

  useEffect(() => {
    if (!queuedMemorySaveMessage || isSending || !currentSessionId) return;
    const message = queuedMemorySaveMessage;
    setQueuedMemorySaveMessage("");
    sendChatMessage(message).catch((error) => setErrorMessage(String(error)));
  }, [queuedMemorySaveMessage, isSending, currentSessionId]);

  async function sendChatMessage(message: string) {
    if (!message || isSending || !currentSessionId) return;

    setIsSending(true);
    setEvalOutput("");
    setStreamingContent("");
    setStreamingToolCalls([]);
    setIsStreaming(true);
    setEvents((prev) => [
      ...prev,
      {
        event: "user_input",
        session_id: currentSessionId,
        content_preview: message,
        state_message_count: prev.length,
      },
    ]);
    setSelectedEventIndex(Math.max(0, events.length));
    try {
      if (isTauri) {
        await invokeCommand<void>("send_chat_message_stream", {
          sessionId: currentSessionId,
          message,
        });
        setIsSending(false);
      } else {
        const result = await invokeCommand<ChatTurnResult>("send_chat_message", {
          sessionId: currentSessionId,
          message,
        });
        setChatSessionId(result.session_id);
        await openRunByPath(result.run_path);
        setIsSending(false);
      }
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(String(error));
      setIsSending(false);
      setIsStreaming(false);
    }
  }

  async function sendChat() {
    const message = chatInput.trim();
    if (!message || isSending || !currentSessionId) return;
    setChatInput("");
    await sendChatMessage(message);
  }

  async function startNewSession() {
    if (hasBlankInteractiveSession || isCreatingSession) return;

    const nextSessionId = `client-${Date.now()}`;
    setIsCreatingSession(true);
    try {
      const result = await invokeCommand<ChatTurnResult>("create_chat_session", {
        sessionId: nextSessionId,
      });
      setChatSessionId(result.session_id);
      setChatInput("");
      setEvalOutput("");
      await openRunByPath(result.run_path);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(String(error));
    } finally {
      setIsCreatingSession(false);
    }
  }

  async function savePolicyConfig(nextConfig: PolicyConfig) {
    try {
      const saved = await invokeCommand<PolicyConfig>("set_policy_config", { config: nextConfig });
      setPolicyConfig(saved);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(String(error));
    }
  }

  async function answerToolGate(decision: "allow" | "deny") {
    if (!pendingToolGate) return;
    const requestId = pendingToolGate.request_id;
    setPendingToolGate(null);
    try {
      await invokeCommand<void>("submit_tool_gate_decision", {
        requestId,
        decision,
      });
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(String(error));
    }
  }

  function answerMemoryCandidate(decision: "save" | "dismiss") {
    if (!pendingMemoryCandidate) return;
    const candidate = pendingMemoryCandidate;
    setPendingMemoryCandidate(null);
    if (decision === "dismiss") {
      rememberMemoryCandidateDecision(candidate.candidate_key, "dismissed");
      return;
    }
    rememberMemoryCandidateDecision(candidate.candidate_key, "saved");
    setQueuedMemorySaveMessage(memoryCandidateSaveText(candidate));
  }

  async function openWorkspaceFile(file: WorkspaceFileEntry) {
    setSelectedWorkspaceFile(file);
    if (file.is_dir) {
      setWorkspaceFileContent(null);
      setWorkspaceFileDraft("");
      return;
    }
    setFilePreviewLoading(true);
    try {
      const content = await invokeCommand<WorkspaceFileContent>("read_workspace_file", { path: file.path });
      setWorkspaceFileContent(content);
      setWorkspaceFileDraft(content.content);
      setErrorMessage("");
    } catch (error) {
      const message = String(error);
      setWorkspaceFileContent({
        path: file.path,
        content: message,
        truncated: false,
      });
      setWorkspaceFileDraft(message);
    } finally {
      setFilePreviewLoading(false);
    }
  }

  async function saveWorkspaceFile() {
    if (!selectedWorkspaceFile || selectedWorkspaceFile.is_dir || !workspaceFileContent) return;
    setFileSaving(true);
    try {
      const saved = await invokeCommand<WorkspaceFileContent>("write_workspace_file", {
        path: selectedWorkspaceFile.path,
        content: workspaceFileDraft,
      });
      setWorkspaceFileContent(saved);
      setWorkspaceFileDraft(saved.content);
      const files = await invokeCommand<WorkspaceFileEntry[]>("list_workspace_files");
      setWorkspaceFiles(files);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(String(error));
    } finally {
      setFileSaving(false);
    }
  }

  function renderRunItem(run: RunSummary) {
    return (
      <div
        key={run.path}
        className={`run-item ${activeView === "evals" && run.run_type === "interactive" ? "has-action" : ""} ${selectedRun?.path === run.path ? "selected" : ""}`}
        onClick={() => setSelectedRun(run)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            setSelectedRun(run);
          }
        }}
        role="button"
        tabIndex={0}
      >
        <div className="run-icon">{run.run_type === "eval" ? <FlaskConical size={19} /> : <MessageSquare size={19} />}</div>
        <div className="run-meta">
          <div className="run-title">{run.title}</div>
          <div className="run-sub">
            {run.model ?? "unknown model"} · {run.event_count} events · {formatRelative(run.modified_ms)}
          </div>
        </div>
        {activeView === "evals" && run.run_type === "interactive" ? (
          <button
            className="inline-run-action"
            onClick={(event) => {
              event.stopPropagation();
              startEvalFromRun(run);
            }}
            disabled={Boolean(runningEvalPath)}
            title="抽取这个 trace 的用户输入，生成 eval spec，并用新会话 replay"
          >
            {runningEvalPath === run.path ? <RefreshCw size={14} className="spin" /> : <Play size={14} />}
            Replay
          </button>
        ) : null}
        {run.fail_count ? <XCircle size={18} className="bad-text" /> : <CheckCircle2 size={18} className="good-text" />}
      </div>
    );
  }

  return (
    <div
      className="app-shell"
      style={{
        gridTemplateColumns: `78px ${layoutWidths.runs}px 8px minmax(360px, 1fr) 8px ${layoutWidths.inspector}px`,
      }}
    >
      <aside className="rail">
        <div className="avatar">mC</div>
        <RailButton icon={<MessageSquare size={21} />} label="会话" active={activeView === "sessions"} onClick={() => setActiveView("sessions")} />
        <RailButton icon={<Activity size={21} />} label="Trace" active={activeView === "trace"} onClick={() => setActiveView("trace")} />
        <RailButton icon={<Bug size={21} />} label="评测" active={activeView === "evals"} onClick={() => setActiveView("evals")} />
        <RailButton icon={<Wrench size={21} />} label="工具" active={activeView === "tools"} onClick={() => setActiveView("tools")} />
        <RailButton icon={<Folder size={21} />} label="文件" active={activeView === "files"} onClick={() => setActiveView("files")} />
        <div className="rail-spacer" />
        <RailButton icon={<Settings size={21} />} label="设置" active={settingsOpen} onClick={() => setSettingsOpen(true)} />
      </aside>

      <aside className="run-list">
        <div className="search-box">
          <Search size={20} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索 run、模型、badcase" />
        </div>
        {activeView === "sessions" ? (
          <button
            className="primary-outline"
            onClick={startNewSession}
            disabled={isCreatingSession || hasBlankInteractiveSession}
            title={hasBlankInteractiveSession ? "当前已有空白会话，先使用它再新建。" : "创建新的空白 myClaw 交互会话"}
          >
            {isCreatingSession ? <RefreshCw size={18} className="spin" /> : <MessageSquare size={18} />}
            {hasBlankInteractiveSession ? "空白会话已就绪" : isCreatingSession ? "创建中" : "新建空白会话"}
          </button>
        ) : null}
        {(activeView === "tools" || activeView === "files") ? (
          <button
            className="primary-outline"
            onClick={() => {
              setResourceLoading(true);
              invokeCommand<ToolSummary[] | WorkspaceFileEntry[]>(
                activeView === "tools" ? "list_agent_tools" : "list_workspace_files",
              )
                .then((items) => {
                  if (activeView === "tools") {
                    setAgentTools(items as ToolSummary[]);
                  } else {
                    setWorkspaceFiles(items as WorkspaceFileEntry[]);
                  }
                  setErrorMessage("");
                })
                .catch((error) => setErrorMessage(String(error)))
                .finally(() => setResourceLoading(false));
            }}
            disabled={resourceLoading}
          >
            {resourceLoading ? <RefreshCw size={18} className="spin" /> : <RefreshCw size={18} />}
            刷新
          </button>
        ) : null}
        <div className="section-title">
          {activeView === "sessions"
            ? "Sessions"
            : activeView === "evals"
              ? "Eval Runs & Sessions"
              : activeView === "tools"
                ? "Tool Registry"
                : activeView === "files"
                  ? "Workspace"
                  : "Traces"}
        </div>
        {activeView === "tools" ? (
          <div className="side-summary">
            <strong>{agentTools.length}</strong>
            <span>当前 agent 可用工具</span>
          </div>
        ) : activeView === "files" ? (
          <div className="side-summary">
            <strong>{workspaceFiles.length}</strong>
            <span>workspace 条目</span>
          </div>
        ) : null}
        <div className="runs">
          {activeView === "evals"
            ? evalRunGroups.map((group) => {
                const collapsed = collapsedRunGroups[group.id] ?? false;
                return (
                  <div className="run-group" key={group.id}>
                    <button
                      className="run-group-header"
                      onClick={() =>
                        setCollapsedRunGroups((prev) => ({
                          ...prev,
                          [group.id]: !(prev[group.id] ?? false),
                        }))
                      }
                    >
                      <ChevronDown size={15} className={collapsed ? "collapsed" : ""} />
                      <span className="run-group-title">{group.title}</span>
                      <span className="run-group-subtitle">{group.subtitle}</span>
                      <span className="event-count">{group.runs.length}</span>
                    </button>
                    {!collapsed ? group.runs.map((run) => renderRunItem(run)) : null}
                  </div>
                );
              })
            : filteredRuns.map((run) => renderRunItem(run))}
        </div>
      </aside>

      <div
        className="resize-handle"
        onPointerDown={(event) => startResizePane("runs", event)}
        title="拖动调整会话列表宽度"
      />

      <main className="workspace">
        <header className="topbar">
          <div className="run-status">
            <CircleDot size={14} />
            {selectedRun?.run_type ?? "no run"} · {selectedRun?.model ?? "model unknown"}
          </div>
        </header>

        {activeView === "tools" ? (
          <ResourceView
            title="当前 Agent 工具"
            subtitle="来自 myClaw.core.tools.ALL_TOOLS，并附带权限系统映射。"
            metrics={[
              ["Tools", agentTools.length],
              ["Consent", agentTools.filter((tool) => tool.requires_consent).length],
              ["Resources", new Set(agentTools.map((tool) => tool.resource)).size],
            ]}
          >
            <div className="tool-grid">
              {agentTools.map((tool) => {
                const parameters = Object.entries(tool.parameters ?? {});
                return (
                  <div className="tool-card" key={tool.name}>
                    <div className="tool-card-head">
                      <div>
                        <h3>{tool.name}</h3>
                        <p>{tool.description || "No description"}</p>
                      </div>
                      <span className={`risk-pill ${tool.risk}`}>{tool.risk}</span>
                    </div>
                    <div className="tool-meta-row">
                      <span>{tool.permission}</span>
                      <span>{tool.requires_consent ? "requires consent" : "auto allowed"}</span>
                    </div>
                    <div className="param-list">
                      {parameters.length > 0 ? (
                        parameters.map(([name, schema]) => (
                          <span className={tool.required?.includes(name) ? "required" : ""} key={name}>
                            {name}: {schema?.type ?? "any"}
                          </span>
                        ))
                      ) : (
                        <span>no parameters</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </ResourceView>
        ) : activeView === "files" ? (
          <ResourceView
            title="Workspace 文件目录"
            subtitle="workspace 目录，包含 office 沙箱文件和 memory 记忆文件。"
            metrics={[
              ["Entries", workspaceFiles.length],
              ["Files", workspaceFiles.filter((file) => !file.is_dir).length],
              ["Dirs", workspaceFiles.filter((file) => file.is_dir).length],
            ]}
          >
            <div className="file-tree">
              {visibleWorkspaceFiles.map((file) => (
                <button
                  className={`file-row ${file.is_dir ? "directory" : "file"} ${selectedWorkspaceFile?.path === file.path ? "selected" : ""}`}
                  key={file.path}
                  style={{ paddingLeft: `${12 + file.depth * 18}px` }}
                  onClick={() => {
                    if (file.is_dir) {
                      setCollapsedFileDirs((prev) => ({
                        ...prev,
                        [file.path]: !(prev[file.path] ?? false),
                      }));
                    }
                    openWorkspaceFile(file);
                  }}
                  title={file.path}
                >
                  <span className="file-icon">
                    {file.is_dir ? (
                      <>
                        <ChevronDown size={14} className={collapsedFileDirs[file.path] ? "collapsed" : ""} />
                        <Folder size={16} />
                      </>
                    ) : (
                      <FileText size={16} />
                    )}
                  </span>
                  <span className="file-path">{file.path}</span>
                  <span className="file-meta">{file.is_dir ? "folder" : formatBytes(file.size)}</span>
                  <span className="file-meta">{formatRelative(file.modified_ms)}</span>
                </button>
              ))}
              {workspaceFiles.length === 0 ? <div className="empty-state">workspace 目录为空。</div> : null}
            </div>
          </ResourceView>
        ) : (
        <section className="conversation">
          <div className="run-heading">
            <div>
              <h1>{selectedRun?.title ?? "No trace selected"}</h1>
              <p>{selectedRun?.path ?? "Run an eval or open a trace from the left."}</p>
            </div>
            <div className="metrics">
              <Metric label="Events" value={displayEvents.length} />
              <Metric label="LLM Inputs" value={llmInputs.length} />
              <Metric label="Tools" value={toolCalls.length} />
            </div>
          </div>

          {isEvalDisplay ? (
            <EvalReportView summary={evalSummary} reports={evalCaseReports} onOpenTrace={openRunByPath} />
          ) : (
          <div className="messages">
            {isEvalDisplay
              ? evalDisplayMessages.map((message) => (
                  <MessageBubble key={message.key} role={message.role} text={message.text} meta={message.meta} />
                ))
              : users.map((event, index) => {
                  const answer = assistants[index];
                  return (
                    <React.Fragment key={`${event.event}-${index}`}>
                      <MessageBubble role="user" text={String(event.content_preview ?? "")} />
                      {answer ? (
                        <MessageBubble
                          role="assistant"
                          text={eventText(answer)}
                          meta={`ReAct ${answer.react_phase ?? "final"} · messages ${
                            llmInputs[index + 1]?.message_count ?? llmInputs[index]?.message_count ?? "-"
                          } · summary ${String(llmInputs[index]?.has_summary ?? false)}`}
                        />
                      ) : null}
                    </React.Fragment>
                  );
                })}
            {isStreaming ? (
              <MessageBubble role="assistant" text={streamingContent || "正在连接模型..."} meta="流式生成中..." />
            ) : null}
            {isStreaming && streamingToolCalls.length > 0 ? (
              <div className="streaming-tool-calls">
                {streamingToolCalls.map((tc, i) => (
                  <div key={i} className="tool-call-item">
                    <span className="tool-call-name">⟳ {tc.name}</span>
                    <span className="tool-call-args">{JSON.stringify(tc.args)}</span>
                    {tc.result !== undefined ? (
                      <span className="tool-call-result">{tc.result}</span>
                    ) : (
                      <span className="tool-call-loading">...</span>
                    )}
                  </div>
                ))}
              </div>
            ) : null}
            {displayEvents.length === 0 && !isStreaming ? (
              <div className="empty-state">
                {activeView === "sessions"
                  ? "还没有交互会话。点击左侧“新建交互会话”开始。"
                  : activeView === "evals"
                    ? "还没有 badcase trace。运行一次 eval 后会出现在这里。"
                    : "还没有 trace。交互会话和 badcase 运行都会出现在这里。"}
              </div>
            ) : null}
          </div>
          )}

          {evalOutput ? <pre className="eval-output">{evalOutput}</pre> : null}
          {!isEvalDisplay ? (
          <div className="composer">
            <textarea
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                  event.preventDefault();
                  sendChat();
                }
              }}
              placeholder={
                canContinueSelectedRun
                  ? "输入一轮 myClaw 交互，⌘+Enter 续写当前会话。Trace 会实时写入 runs。"
                  : "请选择一个历史会话继续对话，或在会话页新建空白会话。"
              }
            />
            <div className="composer-actions">
              <span>{currentSessionId || "no interactive session selected"}</span>
              {(isSending || isStreaming) ? (
                <div className="composer-loading">
                  <div className="spinner" />
                  <span>流式发送中...</span>
                </div>
              ) : (
                <button onClick={sendChat} disabled={isSending || !chatInput.trim() || !canContinueSelectedRun}>
                  {isSending ? <RefreshCw size={18} className="spin" /> : <TerminalSquare size={18} />}
                  {isSending ? "运行中" : "继续对话"}
                </button>
              )}
            </div>
          </div>
          ) : null}
        </section>
        )}
      </main>

      <div
        className="resize-handle"
        onPointerDown={(event) => startResizePane("inspector", event)}
        title="拖动调整 Trace Inspector 宽度"
      />

      <aside className="inspector">
        <div className="inspector-header">
          <div>
            <div className="eyebrow">{activeView === "files" ? "File Preview" : "Trace Inspector"}</div>
            <h2>{activeView === "files" ? selectedWorkspaceFile?.path ?? "No file selected" : selectedEvent?.event ?? "No event"}</h2>
          </div>
          {activeView === "files" ? (
            <button
              className="icon-button"
              onClick={saveWorkspaceFile}
              disabled={!workspaceFileContent || selectedWorkspaceFile?.is_dir || workspaceFileDraft === workspaceFileContent.content || fileSaving}
              title="保存文件"
            >
              {fileSaving ? <RefreshCw size={18} className="spin" /> : <Save size={18} />}
            </button>
          ) : (
            <button className="icon-button" onClick={refreshRuns} title="Refresh runs">
              <RefreshCw size={18} />
            </button>
          )}
        </div>

        <div className="summary-strip">
          {activeView === "files" ? (
            <>
              <span className="status good">{selectedWorkspaceFile?.is_dir ? "Folder" : "Text Preview"}</span>
              <span>
                {selectedWorkspaceFile
                  ? selectedWorkspaceFile.is_dir
                    ? "directory"
                    : formatBytes(selectedWorkspaceFile.size)
                  : "workspace"}
              </span>
            </>
          ) : (
            <>
              <span className={evalSummary?.fail_count ? "status bad" : "status good"}>
                {evalSummary?.fail_count ? "Failing" : "Passing"}
              </span>
              <span>{selectedRun?.run_type ?? "trace"}</span>
            </>
          )}
        </div>
        {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}

        {activeView === "files" ? (
          <div className="inspector-file-preview">
            {filePreviewLoading ? (
              <div className="empty-state">正在读取文件...</div>
            ) : selectedWorkspaceFile?.is_dir ? (
              <div className="empty-state">已选择文件夹。展开左侧目录后选择文本文件查看内容。</div>
            ) : workspaceFileContent ? (
              <>
                {workspaceFileContent.truncated ? <div className="file-preview-note">文件较大，已截断预览。</div> : null}
                <textarea
                  className="file-editor"
                  value={workspaceFileDraft}
                  onChange={(event) => setWorkspaceFileDraft(event.target.value)}
                  spellCheck={false}
                  disabled={workspaceFileContent.truncated || fileSaving}
                />
              </>
            ) : (
              <div className="empty-state">选择左侧文本文件查看内容。</div>
            )}
          </div>
        ) : (
          <>
            <div className="event-timeline">
              {eventGroups.map((group) => {
                const isCollapsed = collapsedGroups[group.id] ?? false;
                const containsSelected = group.eventIndexes.includes(selectedEventIndex);
                const collapsed = isCollapsed && !containsSelected;
                const childIndexes = new Set(group.children?.flatMap((child) => child.eventIndexes) ?? []);
                const directIndexes = group.eventIndexes.filter((eventIndex) => !childIndexes.has(eventIndex));
                return (
                  <div className="event-group" key={group.id}>
                    <button
                      className={`event-group-header ${containsSelected ? "active" : ""}`}
                      onClick={() =>
                        setCollapsedGroups((prev) => ({
                          ...prev,
                          [group.id]: !(prev[group.id] ?? false),
                        }))
                      }
                    >
                      <ChevronDown size={15} className={collapsed ? "collapsed" : ""} />
                      <span className="event-group-title">{group.title}</span>
                      <span className="event-group-subtitle">{group.subtitle}</span>
                      <span className="event-count">{group.eventIndexes.length}</span>
                    </button>
                    {!collapsed
                      ? directIndexes.map((eventIndex) => {
                          const event = displayEvents[eventIndex];
                          if (!event) return null;
                          return (
                            <button
                              key={`${event.event}-${eventIndex}`}
                              className={`event-row ${eventTone(event.event)} ${selectedEventIndex === eventIndex ? "active" : ""}`}
                              onClick={() => setSelectedEventIndex(eventIndex)}
                              aria-label={event.event}
                            >
                              <span className="event-dot" />
                              <span className="event-name">{event.event}</span>
                            </button>
                          );
                        })
                      : null}
                    {!collapsed
                      ? group.children?.map((child) => {
                          const childCollapsed = collapsedGroups[child.id] ?? false;
                          const childContainsSelected = child.eventIndexes.includes(selectedEventIndex);
                          const hideChild = childCollapsed && !childContainsSelected;
                          return (
                            <div className="event-subgroup" key={child.id}>
                              <button
                                className={`event-group-header step ${childContainsSelected ? "active" : ""}`}
                                onClick={() =>
                                  setCollapsedGroups((prev) => ({
                                    ...prev,
                                    [child.id]: !(prev[child.id] ?? false),
                                  }))
                                }
                              >
                                <ChevronDown size={14} className={hideChild ? "collapsed" : ""} />
                                <span className="event-group-title">{child.title}</span>
                                <span className="event-group-subtitle">{child.subtitle}</span>
                                <span className="event-count">{child.eventIndexes.length}</span>
                              </button>
                              {!hideChild
                                ? child.eventIndexes.map((eventIndex) => {
                                    const event = displayEvents[eventIndex];
                                    if (!event) return null;
                                    return (
                                      <button
                                        key={`${event.event}-${eventIndex}`}
                                        className={`event-row nested ${eventTone(event.event)} ${selectedEventIndex === eventIndex ? "active" : ""}`}
                                        onClick={() => setSelectedEventIndex(eventIndex)}
                                        aria-label={event.event}
                                      >
                                        <span className="event-dot" />
                                        <span className="event-name">{event.event}</span>
                                      </button>
                                    );
                                  })
                                : null}
                            </div>
                          );
                        })
                      : null}
                  </div>
                );
              })}
            </div>

            <div className="detail-panel">
              <div className="detail-tabs">
                <span>JSON</span>
                <span>Messages</span>
                <span>Tools</span>
              </div>
              <pre>{selectedEvent ? stringify(selectedEvent) : "Select an event to inspect raw trace data."}</pre>
            </div>
          </>
        )}
      </aside>
      {settingsOpen ? (
        <div className="modal-backdrop" onMouseDown={() => setSettingsOpen(false)}>
          <div className="settings-modal" onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="eyebrow">Settings</div>
                <h2>权限与观察</h2>
              </div>
              <button className="icon-button" onClick={() => setSettingsOpen(false)} title="关闭设置">
                <XCircle size={18} />
              </button>
            </div>
            <div className="setting-block">
              <label>工具权限模式</label>
              <div className="mode-options">
                {(["off", "default", "plan", "auto"] as const).map((mode) => (
                  <button
                    key={mode}
                    className={policyConfig.mode === mode ? "active" : ""}
                    onClick={() => savePolicyConfig({ ...policyConfig, mode })}
                  >
                    {mode === "off" ? "关闭" : mode === "default" ? "默认" : mode === "plan" ? "计划" : "自动"}
                  </button>
                ))}
              </div>
              <p>
                默认：未命中规则时询问。计划：只允许读。自动：只读和低风险工具自动放行，中高风险工具仍需确认。
              </p>
            </div>
            <div className="setting-block">
              <label>确认等待时间</label>
              <input
                type="number"
                min={10}
                max={3600}
                value={policyConfig.approval_timeout_seconds}
                onChange={(event) =>
                  savePolicyConfig({
                    ...policyConfig,
                    approval_timeout_seconds: Number(event.target.value),
                  })
                }
              />
            </div>
          </div>
        </div>
      ) : null}
      {pendingToolGate ? (
        <div className="modal-backdrop">
          <div className="approval-modal">
            <div className="modal-header">
              <div>
                <div className="eyebrow">Tool Gate</div>
                <h2>允许执行这个工具吗？</h2>
              </div>
            </div>
            <div className="approval-summary">
              <strong>{pendingToolGate.tool_name}</strong>
              <span>{pendingToolGate.permission}</span>
              <span>风险：{pendingToolGate.risk || "low"}</span>
              {pendingToolGate.memory_scope ? <span>记忆范围：{pendingToolGate.memory_scope}</span> : null}
              {pendingToolGate.source_route ? <span>来源判断：{pendingToolGate.source_route}</span> : null}
            </div>
            <p>{pendingToolGate.reason || "该工具需要你确认后才能继续。"}</p>
            <pre>{stringify(pendingToolGate.tool_args)}</pre>
            <div className="modal-actions">
              <button className="secondary-action" onClick={() => answerToolGate("deny")}>拒绝并暂停</button>
              <button className="primary-action" onClick={() => answerToolGate("allow")}>允许执行</button>
            </div>
          </div>
        </div>
      ) : null}
      {pendingMemoryCandidate ? (
        <div className="modal-backdrop">
          <div className="approval-modal">
            <div className="modal-header">
              <div>
                <div className="eyebrow">Memory Candidate</div>
                <h2>保存为长期偏好吗？</h2>
              </div>
            </div>
            <div className="approval-summary">
              <strong>{pendingMemoryCandidate.candidate_label}</strong>
              <span>{pendingMemoryCandidate.candidate_key}</span>
              <span>
                证据：{pendingMemoryCandidate.candidate_evidence_count}/{pendingMemoryCandidate.candidate_threshold}
              </span>
            </div>
            <p>系统多次观察到这个偏好。确认后会发送一条显式记忆请求，再由后端写入 profile。</p>
            <pre>{pendingMemoryCandidate.candidate_evidence || "暂无证据摘要"}</pre>
            <div className="modal-actions">
              <button className="secondary-action" onClick={() => answerMemoryCandidate("dismiss")}>暂不保存</button>
              <button className="primary-action" onClick={() => answerMemoryCandidate("save")}>保存为长期偏好</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function RailButton({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={`rail-button ${active ? "active" : ""}`} onClick={onClick} title={label}>
      {icon}
      <span>{label}</span>
    </button>
  );
}

function ResourceView({
  title,
  subtitle,
  metrics,
  children,
}: {
  title: string;
  subtitle: string;
  metrics: Array<[string, React.ReactNode]>;
  children: React.ReactNode;
}) {
  return (
    <section className="resource-view">
      <div className="run-heading">
        <div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        <div className="metrics">
          {metrics.map(([label, value]) => (
            <Metric key={label} label={label} value={value} />
          ))}
        </div>
      </div>
      <div className="resource-body">{children}</div>
    </section>
  );
}

function EvalReportView({
  summary,
  reports,
  onOpenTrace,
}: {
  summary: TraceEvent | undefined;
  reports: EvalCaseReport[];
  onOpenTrace: (path: string) => void;
}) {
  const passCount = Number(summary?.pass_count ?? reports.filter((report) => report.passed === true).length);
  const failCount = Number(summary?.fail_count ?? reports.filter((report) => report.passed === false).length);

  return (
    <div className="eval-report">
      <div className="eval-report-head">
        <div>
          <div className="eyebrow">Eval Report</div>
          <h2>{String(summary?.suite_id ?? summary?.case_id ?? "Selected eval")}</h2>
        </div>
        <div className="metrics">
          <Metric label="Pass" value={passCount} />
          <Metric label="Fail" value={failCount} />
          <Metric label="Cases" value={reports.length} />
        </div>
      </div>

      <div className="eval-case-list">
        {reports.map((report) => (
          <section className={`eval-case ${report.passed === false ? "failed" : "passed"}`} key={report.id}>
            <div className="eval-case-head">
              <div>
                <h3>{report.id}</h3>
                <p>{report.title}</p>
              </div>
              <span className={`eval-status ${report.passed === false ? "failed" : "passed"}`}>
                {report.passed === false ? "FAIL" : "PASS"}
              </span>
            </div>

            {report.inputs.length > 0 ? (
              <div className="eval-field">
                <span>Inputs</span>
                {report.inputs.map((input, index) => (
                  <p key={`${report.id}-input-${index}`}>{input}</p>
                ))}
              </div>
            ) : null}

            {report.replayAnswers.length > 0 ? (
              <div className="eval-field">
                <span>Replay</span>
                {report.replayAnswers.map((answer, index) => (
                  <p key={`${report.id}-answer-${index}`}>{answer}</p>
                ))}
              </div>
            ) : null}

            {report.failures.length > 0 ? (
              <div className="eval-field failures">
                <span>Failures</span>
                {report.failures.map((failure) => (
                  <p key={failure}>{failure}</p>
                ))}
              </div>
            ) : null}

            {report.toolNames.length > 0 ? (
              <div className="eval-tags">
                {report.toolNames.map((tool) => (
                  <span key={tool}>{tool}</span>
                ))}
              </div>
            ) : null}

            {report.tracePaths.length > 0 ? (
              <div className="eval-traces">
                <span>Source traces</span>
                {report.tracePaths.map((path) => (
                  <button key={path} onClick={() => onOpenTrace(path)} title={path}>
                    <FileText size={14} />
                    {path.split("/").pop()}
                  </button>
                ))}
              </div>
            ) : null}
          </section>
        ))}
        {reports.length === 0 ? <div className="empty-state">这个 eval log 没有可汇总的 case 事件。</div> : null}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function extractThinking(text: string): { display: string; thinking: string | null } {
  // Match thinking block - handles content between <thinking> tags
  // The thinking block may contain newlines and special characters like markdown images
  const thinkMatch = text.match(/<think>([\s\S]*?)<\/think>/);
  if (thinkMatch) {
    const thinkingContent = thinkMatch[1];
    // Remove any markdown images from thinking display
    const cleanThinking = thinkingContent.replace(/!\[.*?\]\(.*?\)/g, '').trim();
    // Extract display text after thinking block
    const display = text.replace(/<think>[\s\S]*?<\/think>\s*/g, '').trim();
    return {
      display: display || "(empty response)",
      thinking: cleanThinking || null,
    };
  }
  return { display: text, thinking: null };
}

function MessageBubble({ role, text, meta }: { role: "user" | "assistant"; text: string; meta?: string }) {
  const { display: cleanText, thinking } = extractThinking(text);

  return (
    <div className={`message ${role}`}>
      <div className="message-avatar">{role === "user" ? <FileText size={16} /> : <Bot size={16} />}</div>
      <div className="message-body">
        <div className="message-label">
          {role === "user" ? "User" : "Assistant"}
          {meta ? (
            <>
              <ChevronDown size={14} />
              <span>{meta}</span>
            </>
          ) : null}
        </div>
        <div className="message-text">{cleanText}</div>
        {thinking ? (
          <div className="message-thinking">
            <span className="thinking-label">{"<think>"}</span>
            <span className="thinking-text">{thinking}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { error: string }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { error: "" };
  }

  static getDerivedStateFromError(error: unknown) {
    return { error: String(error) };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="fatal-error">
          <strong>客户端渲染异常</strong>
          <pre>{this.state.error}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("root")!).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
);
