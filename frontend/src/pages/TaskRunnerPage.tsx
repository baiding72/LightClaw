import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import {
  type BrowserContextPayload,
  fetchBrowserContextFromExtension,
} from '../lib/browserExtension'

interface BuiltInTask {
  task_id: string
  instruction: string
  category: string
  difficulty: string
  allowed_tools: string[]
}

interface ToolCall {
  step: number
  tool: string
  args: Record<string, unknown>
  result: Record<string, unknown> | null
  error: string | null
  timestamp: string
}

interface GuiAction {
  step: number
  action: string
  target: string
  success: boolean
  details?: Record<string, unknown> | null
  timestamp: string
}

interface TaskError {
  step: number
  type: string
  message: string
  timestamp: string
}

interface TaskResult {
  success: boolean
  paused?: boolean
  task_id: string
  outcome: string
  lifecycle_status?: string
  current_goal?: string
  current_subgoal?: string
  active_checkpoint?: Record<string, unknown> | null
  total_steps: number
  total_tokens?: number
  total_latency_ms?: number
  error?: string
  state?: {
    current_step: number
    total_tokens: number
    total_latency_ms: number
    current_url?: string
    current_page_title?: string
    current_page_source?: Record<string, unknown> | null
    current_goal?: string
    current_subgoal?: string
    lifecycle_status?: string
    expected_result?: string
    plan_steps?: string[]
    memory_summary?: Record<string, unknown>
    candidate_tools?: Array<{ name: string; category: string; reason: string }>
    current_decision?: {
      chosen_tool?: string | null
      chosen_tool_reason?: string | null
      tool_args?: Record<string, unknown> | null
      response?: string | null
      candidate_tools?: Array<{ name: string; category: string; reason: string }>
    } | null
    recovery_trace?: Array<{
      step: number
      tool_name: string
      error_type: string
      error_message: string
      suggested_action?: string | null
      suggested_fix?: unknown
      recovery_plan?: Record<string, unknown> | null
      timestamp: string
    }>
    checkpoints?: Array<Record<string, unknown>>
    active_checkpoint?: Record<string, unknown> | null
    environment?: Record<string, unknown>
    thoughts: string[]
    observations: string[]
    tool_calls: ToolCall[]
    gui_actions?: GuiAction[]
    errors?: TaskError[]
    browser_context?: BrowserContextPayload
  }
}

interface NoteItem {
  id: number
  title: string
  content: string
  created_at: string
  updated_at: string
}

interface TodoItem {
  id: number
  title: string
  description?: string | null
  deadline?: string | null
  priority: string
  status: string
  created_at: string
  updated_at: string
}

export default function TaskRunnerPage() {
  const [builtInTasks, setBuiltInTasks] = useState<BuiltInTask[]>([])
  const [selectedTask, setSelectedTask] = useState('')
  const [customInstruction, setCustomInstruction] = useState('')
  const [running, setRunning] = useState(false)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [result, setResult] = useState<TaskResult | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [recentNotes, setRecentNotes] = useState<NoteItem[]>([])
  const [recentTodos, setRecentTodos] = useState<TodoItem[]>([])
  const [browserContext, setBrowserContext] = useState<BrowserContextPayload | null>(null)
  const [selectedTabId, setSelectedTabId] = useState<number | null>(null)
  const [browserStatus, setBrowserStatus] = useState('Browser extension not connected yet.')
  const [loadingBrowserContext, setLoadingBrowserContext] = useState(false)
  const [jobContext, setJobContext] = useState({
    target_company: '',
    target_role: '',
    role_keywords: 'software engineer intern',
    candidate_name: '',
    candidate_email: '',
    resume_path: '',
  })

  useEffect(() => {
    void loadBuiltInTasks()
    void loadArtifacts()
  }, [])

  const loadBuiltInTasks = async () => {
    try {
      const response = await api.get<BuiltInTask[]>('/tasks/built-in/list')
      setBuiltInTasks(response.data)
    } catch (error) {
      console.error('Failed to load built-in tasks:', error)
    }
  }

  const loadArtifacts = async () => {
    try {
      const [notesResponse, todosResponse] = await Promise.all([
        api.get<{ notes: NoteItem[] }>('/notes', { params: { limit: 8 } }),
        api.get<{ todos: TodoItem[] }>('/todos', { params: { limit: 8 } }),
      ])
      setRecentNotes(notesResponse.data.notes)
      setRecentTodos(todosResponse.data.todos)
    } catch (error) {
      console.error('Failed to load artifacts:', error)
    }
  }

  const selectedTaskInfo = builtInTasks.find((task) => task.task_id === selectedTask)
  const toolCalls = result?.state?.tool_calls ?? []
  const guiActions = result?.state?.gui_actions ?? []
  const taskErrors = result?.state?.errors ?? []
  const currentDecision = result?.state?.current_decision
  const candidateTools = currentDecision?.candidate_tools ?? result?.state?.candidate_tools ?? []
  const recoveryTrace = result?.state?.recovery_trace ?? []
  const activeCheckpoint = result?.state?.active_checkpoint ?? result?.active_checkpoint ?? null
  const checkpointTitle = activeCheckpoint
    ? String(activeCheckpoint['title'] ?? activeCheckpoint['type'] ?? 'Pending checkpoint')
    : null
  const checkpointDescription = activeCheckpoint
    ? String(activeCheckpoint['description'] ?? '')
    : null
  const checkpointResumeHint = activeCheckpoint
    ? String(activeCheckpoint['resume_hint'] ?? 'Run the task again after handling this checkpoint.')
    : null
  const currentGoal = result?.current_goal
    ?? result?.state?.current_goal
    ?? customInstruction
    ?? selectedTaskInfo?.instruction
    ?? 'No goal captured yet.'
  const currentSubgoal = result?.current_subgoal
    ?? result?.state?.current_subgoal
    ?? 'Not set yet'
  const latestObservation = result?.state?.observations?.length
    ? result.state.observations[result.state.observations.length - 1]
    : 'No observation yet.'
  const memorySummary = result?.state?.memory_summary ?? null
  const availableTabs = browserContext?.tabs ?? []
  const canResume = Boolean(result?.paused && activeTaskId)
  const selectedBrowserTab = (
    availableTabs.find((tab) => tab.tab_id === selectedTabId)
    ?? browserContext?.selected_tab
    ?? null
  )
  const formatJson = (value: unknown) => JSON.stringify(value, null, 2)
  const formatValue = (value: unknown) => {
    if (typeof value === 'string') return value
    return JSON.stringify(value)
  }
  const toScreenshotUrl = (path: string) => {
    const normalizedPath = path.replace(/\\/g, '/')
    const fileName = normalizedPath.split('/').pop()
    return fileName ? `${api.defaults.baseURL?.replace(/\/api$/, '') || ''}/artifacts/screenshots/${fileName}` : null
  }
  const summarizeToolCall = (call: ToolCall) => {
    switch (call.tool) {
      case 'open_url':
        return call.result?.url ? `Opened ${String(call.result.url)}` : 'Opened page'
      case 'read_page':
        return call.result?.length ? `Read ${String(call.result.length)} chars from page` : 'Read page content'
      case 'click':
        return call.args?.selector ? `Clicked ${String(call.args.selector)}` : 'Clicked element'
      case 'type_text':
        return call.args?.selector
          ? `Typed into ${String(call.args.selector)}`
          : 'Typed text'
      case 'select_option':
        return call.args?.selector
          ? `Selected ${String(call.args.option)} in ${String(call.args.selector)}`
          : 'Selected option'
      case 'take_screenshot':
        return call.result?.path ? 'Captured screenshot' : 'Took screenshot'
      default:
        return call.tool
    }
  }
  const formatLifecycleLabel = (value?: string | null) =>
    (value || 'unknown').replace(/_/g, ' ')
  const lifecycleTone = (value?: string | null) => {
    if (value === 'completed') return 'bg-green-100 text-green-700'
    if (value === 'failed') return 'bg-red-100 text-red-700'
    if (value === 'waiting_for_user') return 'bg-amber-100 text-amber-700'
    if (value === 'recovering') return 'bg-orange-100 text-orange-700'
    return 'bg-slate-100 text-slate-700'
  }

  const browserTools = new Set(['open_url', 'read_page', 'click', 'type_text', 'select_option', 'take_screenshot', 'scroll'])

  const executionSteps = toolCalls.map((call) => {
    const screenshotPath =
      typeof call.result?.path === 'string' && call.tool === 'take_screenshot'
        ? call.result.path
        : null
    const screenshotUrl = screenshotPath ? toScreenshotUrl(screenshotPath) : null
    const sourceContext = call.result?.source_context

    return {
      ...call,
      isBrowserTool: browserTools.has(call.tool),
      screenshotPath,
      screenshotUrl,
      sourceContext,
    }
  })

  const refreshBrowserContext = async () => {
    setLoadingBrowserContext(true)
    try {
      const extensionContext = await fetchBrowserContextFromExtension()
      setBrowserContext(extensionContext)
      setSelectedTabId(extensionContext.selected_tab.tab_id)
      setBrowserStatus(`Connected to browser plugin at ${new Date(extensionContext.captured_at).toLocaleTimeString()}.`)
      setLogs((prev) => [...prev, `Browser context synced: ${extensionContext.selected_tab.title || extensionContext.selected_tab.url}`])
    } catch (error: any) {
      console.error('Failed to sync browser context:', error)
      setBrowserStatus(error.message || 'Failed to connect to browser extension.')
      setLogs((prev) => [...prev, `Browser context sync failed: ${error.message || 'unknown error'}`])
    } finally {
      setLoadingBrowserContext(false)
    }
  }

  const runTask = async () => {
    const instruction = customInstruction || selectedTaskInfo?.instruction
    if (!instruction) {
      alert('Please select a task or enter custom instruction')
      return
    }

    const isResumeRun = canResume
    setRunning(true)
    if (!isResumeRun) {
      setResult(null)
      setLogs(['Starting task...'])
    } else {
      setLogs((prev) => [...prev, `Resuming task: ${activeTaskId}`])
    }

    try {
      const scenarioContextPayload = jobContext.target_company || jobContext.target_role
        ? {
            target_company: jobContext.target_company || undefined,
            target_role: jobContext.target_role || undefined,
            search_preferences: {
              role_keywords: jobContext.role_keywords
                ? jobContext.role_keywords.split(',').map((item) => item.trim()).filter(Boolean)
                : [],
              target_companies: jobContext.target_company ? [jobContext.target_company] : [],
              internship_only: true,
            },
            candidate_profile: {
              full_name: jobContext.candidate_name || undefined,
              email: jobContext.candidate_email || undefined,
              resume_path: jobContext.resume_path || undefined,
            },
          }
        : undefined

      let taskId = activeTaskId
      if (!isResumeRun) {
        const createResponse = await api.post('/tasks', {
          instruction,
          category: selectedTaskInfo?.category || 'multi_step',
          difficulty: selectedTaskInfo?.difficulty || 'medium',
          allowed_tools: selectedTaskInfo?.allowed_tools,
          browser_context: selectedBrowserTab
            ? {
                source: 'browser_extension',
                captured_at: browserContext?.captured_at || new Date().toISOString(),
                selected_tab: selectedBrowserTab,
                tabs: availableTabs,
              }
            : undefined,
          scenario_type: scenarioContextPayload ? 'job_application' : undefined,
          scenario_context: scenarioContextPayload,
        })

        taskId = createResponse.data.task_id
        setActiveTaskId(taskId)
        setLogs((prev) => [...prev, `Task created: ${taskId}`, 'Running task...'])
      } else {
        setLogs((prev) => [...prev, 'Running resumed task...'])
      }

      const runPayload = {
        browser_context: selectedBrowserTab
          ? {
              source: 'browser_extension',
              captured_at: browserContext?.captured_at || new Date().toISOString(),
              selected_tab: selectedBrowserTab,
              tabs: availableTabs,
            }
          : undefined,
        scenario_context: scenarioContextPayload,
      }

      if (selectedBrowserTab) {
        setLogs((prev) => [
          ...prev,
          `Target tab: ${selectedBrowserTab.title || selectedBrowserTab.url}`,
          selectedBrowserTab.url,
        ])
      }

      const runResponse = await api.post<TaskResult>(`/tasks/${taskId}/run`, runPayload)

      setResult(runResponse.data)
      setActiveTaskId(runResponse.data.task_id)
      setLogs((prev) => [
        ...prev,
        `Task finished: ${runResponse.data.paused ? 'paused' : runResponse.data.success ? 'success' : 'failed'}`,
        `Steps executed: ${runResponse.data.total_steps}`,
      ])
      await loadArtifacts()
    } catch (error: any) {
      console.error('Failed to run task:', error)
      setLogs((prev) => [...prev, `Error: ${error.message}`])
      setResult({
        success: false,
        task_id: '',
        outcome: 'error',
        total_steps: 0,
        error: error.message,
      })
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold text-gray-900">Task Runner</h2>
        <p className="text-sm text-gray-600">
          Run a task, inspect each tool call, and see the notes or todos the agent created.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Launch</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Built-in Tasks
                </label>
                <select
                  value={selectedTask}
                  onChange={(e) => {
                    setSelectedTask(e.target.value)
                    setCustomInstruction('')
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select a task...</option>
                  {builtInTasks.map((task) => (
                    <option key={task.task_id} value={task.task_id}>
                      [{task.difficulty}] {task.instruction.substring(0, 50)}...
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Or Enter Custom Instruction
                </label>
                <textarea
                  value={customInstruction}
                  onChange={(e) => {
                    setCustomInstruction(e.target.value)
                    setSelectedTask('')
                  }}
                  placeholder="Enter your custom instruction..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={3}
                />
              </div>
            </div>

            <button
              onClick={runTask}
              disabled={running}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {running ? 'Running...' : canResume ? 'Resume Task' : 'Run Task'}
            </button>
          </div>

	          <div className="bg-white rounded-lg shadow p-6">
	            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-medium text-gray-900">Browser Context</h3>
                <p className="mt-1 text-sm text-gray-600">{browserStatus}</p>
              </div>
              <button
                onClick={() => void refreshBrowserContext()}
                disabled={loadingBrowserContext}
                className="px-3 py-2 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {loadingBrowserContext ? 'Syncing...' : 'Sync Tabs'}
              </button>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Target Tab
                </label>
                <select
                  value={selectedTabId ?? ''}
                  onChange={(e) => setSelectedTabId(e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={availableTabs.length === 0}
                >
                  <option value="">
                    {availableTabs.length === 0 ? 'Sync the browser plugin first...' : 'Select a tab...'}
                  </option>
                  {availableTabs.map((tab) => (
                    <option key={tab.tab_id} value={tab.tab_id}>
                      {tab.active ? '[Active] ' : ''}{tab.title || tab.url}
                    </option>
                  ))}
                </select>

                <div className="mt-3 space-y-2">
                  {availableTabs.length === 0 ? (
                    <div className="text-sm text-gray-500">
                      Load the unpacked extension, open LightClaw in the browser, then click "Sync Tabs".
                    </div>
                  ) : (
                    availableTabs.map((tab) => (
                      <div
                        key={tab.tab_id}
                        className={`rounded border px-3 py-2 text-sm ${
                          selectedBrowserTab?.tab_id === tab.tab_id
                            ? 'border-sky-300 bg-sky-50 text-sky-900'
                            : 'border-gray-200 bg-gray-50 text-gray-700'
                        }`}
                      >
                        <div className="font-medium">{tab.title || 'Untitled Tab'}</div>
                        <div className="mt-1 break-all text-xs text-gray-500">{tab.url}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded border bg-gray-50 p-4">
                <div className="text-sm font-medium text-gray-800">Selected Page</div>
                {selectedBrowserTab ? (
                  <div className="mt-3 space-y-3 text-sm text-gray-700">
                    <div>
                      <div className="text-xs uppercase tracking-wide text-gray-500">Title</div>
                      <div className="mt-1 font-medium text-gray-900">{selectedBrowserTab.title || 'Untitled Tab'}</div>
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-wide text-gray-500">URL</div>
                      <div className="mt-1 break-all">{selectedBrowserTab.url}</div>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className="px-2 py-1 rounded border bg-white text-gray-700">
                        tab #{selectedBrowserTab.tab_id}
                      </span>
                      <span className="px-2 py-1 rounded border bg-white text-gray-700">
                        window #{selectedBrowserTab.window_id}
                      </span>
                      {selectedBrowserTab.active ? (
                        <span className="px-2 py-1 rounded border bg-white text-gray-700">active</span>
                      ) : null}
                    </div>
                  </div>
                ) : (
                  <div className="mt-3 text-sm text-gray-500">
                    No target page selected yet.
                  </div>
                )}
              </div>
	            </div>
	          </div>

	          <div className="bg-white rounded-lg shadow p-6">
	            <h3 className="text-lg font-medium text-gray-900">Job Context</h3>
	            <p className="mt-1 text-sm text-gray-600">
	              Optional scenario context for internship search, application review, and form filling.
	            </p>
	            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
	              {[
	                ['target_company', 'Target Company'],
	                ['target_role', 'Target Role'],
	                ['role_keywords', 'Role Keywords'],
	                ['candidate_name', 'Candidate Name'],
	                ['candidate_email', 'Candidate Email'],
	                ['resume_path', 'Resume Path'],
	              ].map(([key, label]) => (
	                <div key={key}>
	                  <label className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
	                  <input
	                    value={jobContext[key as keyof typeof jobContext]}
	                    onChange={(e) => setJobContext((prev) => ({ ...prev, [key]: e.target.value }))}
	                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
	                  />
	                </div>
	              ))}
	            </div>
	          </div>

	          {selectedTaskInfo ? (
            <div className="bg-sky-50 rounded-lg p-4 border border-sky-100">
              <div className="text-sm text-sky-900 font-medium">Selected Task</div>
              <div className="mt-2 text-sm text-sky-800">{selectedTaskInfo.instruction}</div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-sky-700">
                <span className="px-2 py-1 rounded bg-white border border-sky-200">{selectedTaskInfo.category}</span>
                <span className="px-2 py-1 rounded bg-white border border-sky-200">{selectedTaskInfo.difficulty}</span>
                {selectedTaskInfo.allowed_tools.map((tool) => (
                  <span key={tool} className="px-2 py-1 rounded bg-white border border-sky-200">
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          <div className="bg-gray-900 rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-300 mb-2">Execution Log</h4>
            <div className="font-mono text-sm text-green-400 space-y-1 min-h-16">
              {logs.length === 0 ? (
                <div>&gt; Waiting for a task run...</div>
              ) : (
                logs.map((log, i) => <div key={i}>&gt; {log}</div>)
              )}
            </div>
          </div>

	          {result ? (
	            <div className={`rounded-lg p-6 border ${result.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
	              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
	                  <h3 className={`text-lg font-medium ${result.success ? 'text-green-800' : result.paused ? 'text-amber-800' : 'text-red-800'}`}>
	                    {result.success ? 'Task Completed' : result.paused ? 'Task Paused' : 'Task Failed'}
	                  </h3>
                  <div className="mt-2 text-sm text-gray-700">
                    Task ID: <span className="font-mono">{result.task_id}</span>
                  </div>
                </div>
	                <div className="grid grid-cols-4 gap-3 text-sm">
	                  <div className="rounded border bg-white px-3 py-2">
	                    <div className="text-gray-500">Outcome</div>
	                    <div className="font-medium text-gray-900">{result.outcome}</div>
	                  </div>
	                  <div className="rounded border bg-white px-3 py-2">
	                    <div className="text-gray-500">Lifecycle</div>
	                    <div className={`inline-flex rounded px-2 py-1 text-xs font-medium ${lifecycleTone(result.lifecycle_status || result.state?.lifecycle_status)}`}>
	                      {formatLifecycleLabel(result.lifecycle_status || result.state?.lifecycle_status)}
	                    </div>
	                  </div>
	                  <div className="rounded border bg-white px-3 py-2">
	                    <div className="text-gray-500">Steps</div>
	                    <div className="font-medium text-gray-900">{result.total_steps}</div>
	                  </div>
                  <div className="rounded border bg-white px-3 py-2">
                    <div className="text-gray-500">Latency</div>
                    <div className="font-medium text-gray-900">
                      {((result.total_latency_ms || 0) / 1000).toFixed(1)}s
                    </div>
                  </div>
                </div>
              </div>

	              {result.error ? (
                <div className="mt-4 text-sm text-red-700">
                  <strong>Error:</strong> {result.error}
                </div>
	              ) : null}

                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="rounded border bg-white p-4">
                        <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Current Goal</div>
                      <div className="mt-2 text-sm text-gray-900 whitespace-pre-wrap">
                        {currentGoal}
                      </div>
                    </div>
                    <div className="rounded border bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Current Subgoal</div>
                      <div className="mt-2 text-sm text-gray-900 whitespace-pre-wrap">
                        {currentSubgoal}
                      </div>
                    </div>
                  </div>

	              {result.state?.thoughts?.length ? (
	                <div className="mt-4">
                  <div className="text-sm font-medium text-gray-700 mb-2">Final Thought</div>
                  <div className="rounded border bg-white p-3 text-sm text-gray-700 whitespace-pre-wrap">
                    {result.state.thoughts[result.state.thoughts.length - 1]}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

	          {executionSteps.length > 0 ? (
	            <div className="bg-white rounded-lg shadow p-6">
	              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-medium text-gray-900">Execution Panel</h3>
                  <p className="mt-1 text-sm text-gray-600">
                    Every tool call, browser action, page target, and screenshot from the run.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-gray-600">
                  <span className="rounded border bg-gray-50 px-2 py-1">
                    {executionSteps.length} tool calls
                  </span>
                  <span className="rounded border bg-gray-50 px-2 py-1">
                    {guiActions.length} GUI actions
                  </span>
                  <span className="rounded border bg-gray-50 px-2 py-1">
                    {executionSteps.filter((call) => call.screenshotPath).length} screenshots
                  </span>
                </div>
	              </div>

	              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="rounded border bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Current Environment</div>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        <div>
                          <div className="text-xs uppercase tracking-wide text-gray-500">Page</div>
                          <div className="mt-1 text-sm text-gray-900 break-words">
                            {result?.state?.current_page_title || result?.state?.current_url || 'No page captured'}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs uppercase tracking-wide text-gray-500">Scenario</div>
                          <div className="mt-1 text-sm text-gray-900">
                            {String(result?.state?.environment?.scenario_type || 'generic')}
                          </div>
                        </div>
                      </div>
                      {result?.state?.current_url ? (
                        <a
                          href={result.state.current_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-3 block break-all text-sm text-sky-700 hover:text-sky-900"
                        >
                          {result.state.current_url}
                        </a>
                      ) : null}
                    </div>

                    <div className="rounded border bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Checkpoint / Resume</div>
                      {activeCheckpoint ? (
                          <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-3">
                          <div className="font-medium text-amber-900">
                            {checkpointTitle}
                          </div>
                          <div className="mt-1 text-sm text-amber-800">
                            {checkpointDescription}
                          </div>
                          <div className="mt-2 text-xs text-amber-700">
                            Resume: {checkpointResumeHint}
                          </div>
                        </div>
                      ) : (
                        <div className="mt-3 text-sm text-gray-500">
                          No active checkpoint. Runtime can continue automatically.
                        </div>
                      )}
                    </div>
                  </div>

	              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(280px,0.75fr)]">
	                <div className="rounded border bg-gray-50 p-4">
	                  <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Candidate Tools</div>
                      <div className="mt-3 space-y-2">
                        {candidateTools.length === 0 ? (
                          <div className="text-sm text-gray-500">No candidate tools recorded yet.</div>
                        ) : (
                          candidateTools.map((tool) => (
                            <div key={tool.name} className="rounded border bg-white px-3 py-2">
                              <div className="flex items-center justify-between gap-3">
                                <span className="font-medium text-gray-900">{tool.name}</span>
                                <span className="rounded bg-gray-100 px-2 py-1 text-xs text-gray-600">{tool.category}</span>
                              </div>
                              <div className="mt-1 text-xs text-gray-600">{tool.reason}</div>
                            </div>
                          ))
                        )}
                      </div>
	                </div>

	                <div className="rounded border bg-gray-50 p-4">
	                  <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Chosen Tool</div>
	                  <div className="mt-3 space-y-2">
	                    {currentDecision?.chosen_tool ? (
                          <div className="rounded border bg-white px-3 py-3">
                            <div className="font-medium text-gray-900">{currentDecision.chosen_tool}</div>
                            <div className="mt-2 text-sm text-gray-700 whitespace-pre-wrap">
                              {currentDecision.chosen_tool_reason || 'No rationale recorded.'}
                            </div>
                            {currentDecision.tool_args ? (
                              <pre className="mt-3 overflow-x-auto rounded border bg-gray-50 p-3 text-xs text-gray-700">
                                {formatJson(currentDecision.tool_args)}
                              </pre>
                            ) : null}
                          </div>
	                    ) : (
	                      <div className="text-sm text-gray-500">No chosen tool recorded yet.</div>
	                    )}
	                  </div>
	                </div>
	              </div>

                  <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                    <div className="rounded border bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Scene Memory</div>
                      <div className="mt-2 text-sm text-gray-800">
                        {memorySummary ? (
                          <pre className="overflow-x-auto rounded border bg-gray-50 p-3 text-xs text-gray-700">
                            {formatJson(memorySummary)}
                          </pre>
                        ) : (
                          'No memory snapshot yet.'
                        )}
                      </div>
                    </div>
                    <div className="rounded border bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Latest Observation</div>
                      <div className="mt-2 text-sm text-gray-800 whitespace-pre-wrap">
                        {latestObservation}
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                    <div className="rounded border bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Error / Recovery</div>
                      {recoveryTrace.length === 0 ? (
                        <div className="mt-2 text-sm text-gray-500">No recovery attempts recorded.</div>
                      ) : (
                        <div className="mt-2 space-y-2">
                          {recoveryTrace.slice(-3).reverse().map((item, index) => (
                            <div key={`${item.timestamp}-${index}`} className="rounded border bg-gray-50 px-3 py-2 text-sm">
                              <div className="font-medium text-gray-900">{item.error_type} · {item.tool_name}</div>
                              <div className="mt-1 text-gray-700">{item.error_message}</div>
                              {item.suggested_action ? (
                                <div className="mt-2 text-xs text-gray-600">Next: {item.suggested_action}</div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

	              <div className="space-y-4">
                {executionSteps.map((call) => (
                  <div key={`${call.step}-${call.tool}`} className="border rounded-lg p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span className="inline-flex h-7 min-w-7 items-center justify-center rounded bg-slate-900 px-2 text-xs font-medium text-white">
                          {call.step}
                        </span>
                        <div>
                          <div className="font-medium text-gray-900">{call.tool}</div>
                          <div className="text-xs text-gray-500">{new Date(call.timestamp).toLocaleString()}</div>
                          <div className="mt-1 text-sm text-gray-600">{summarizeToolCall(call)}</div>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        {call.isBrowserTool ? (
                          <span className="text-xs font-medium px-2 py-1 rounded bg-sky-100 text-sky-700">
                            browser
                          </span>
                        ) : null}
                        <span className={`text-xs font-medium px-2 py-1 rounded ${call.error ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                          {call.error ? 'failed' : 'success'}
                        </span>
                      </div>
                    </div>

                    {call.sourceContext && typeof call.sourceContext === 'object' ? (
                      <div className="mt-4 flex flex-wrap gap-2 text-xs">
                        {Object.entries(call.sourceContext).slice(0, 6).map(([key, value]) => (
                          <span key={key} className="rounded border bg-sky-50 px-2 py-1 text-sky-800">
                            {key}: {formatValue(value)}
                          </span>
                        ))}
                      </div>
                    ) : null}

                    {call.screenshotUrl ? (
                      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
                        <div className="grid gap-4 lg:grid-cols-2">
                          <div>
                            <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-2">Arguments</div>
                            <pre className="overflow-x-auto rounded border bg-gray-50 p-3 text-xs text-gray-700">{formatJson(call.args)}</pre>
                          </div>
                          <div>
                            <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-2">Result</div>
                            <pre className="overflow-x-auto rounded border bg-gray-50 p-3 text-xs text-gray-700">
                              {call.error || formatJson(call.result)}
                            </pre>
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-2">Screenshot</div>
                          <a href={call.screenshotUrl} target="_blank" rel="noreferrer" className="block">
                            <img
                              src={call.screenshotUrl}
                              alt={`Screenshot for step ${call.step}`}
                              className="h-40 w-full rounded border object-cover"
                            />
                          </a>
                          <div className="mt-2 break-all text-xs text-gray-500">{call.screenshotPath}</div>
                        </div>
                      </div>
                    ) : (
                    <div className="mt-4 grid gap-4 lg:grid-cols-2">
                      <div>
                        <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-2">Arguments</div>
                        <pre className="overflow-x-auto rounded border bg-gray-50 p-3 text-xs text-gray-700">{formatJson(call.args)}</pre>
                      </div>
                      <div>
                        <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-2">Result</div>
                        <pre className="overflow-x-auto rounded border bg-gray-50 p-3 text-xs text-gray-700">
                          {call.error || formatJson(call.result)}
                        </pre>
                      </div>
                    </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between gap-3 mb-4">
              <h3 className="text-lg font-medium text-gray-900">Artifacts</h3>
              <button
                onClick={() => void loadArtifacts()}
                className="px-3 py-2 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Refresh
              </button>
            </div>

            <div className="space-y-6">
              <div>
                <div className="text-sm font-medium text-gray-800 mb-3">Recent Notes</div>
                <div className="space-y-3">
                  {recentNotes.length === 0 ? (
                    <div className="text-sm text-gray-500">No notes yet.</div>
                  ) : (
                    recentNotes.map((note) => (
                      <div key={note.id} className="rounded border p-3">
                        <div className="font-medium text-gray-900">{note.title}</div>
                        <div className="mt-1 text-sm text-gray-600 whitespace-pre-wrap break-words">{note.content}</div>
                        <div className="mt-2 text-xs text-gray-500">{new Date(note.created_at).toLocaleString()}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div>
                <div className="text-sm font-medium text-gray-800 mb-3">Recent Todos</div>
                <div className="space-y-3">
                  {recentTodos.length === 0 ? (
                    <div className="text-sm text-gray-500">No todos yet.</div>
                  ) : (
                    recentTodos.map((todo) => (
                      <div key={todo.id} className="rounded border p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="font-medium text-gray-900">{todo.title}</div>
                          <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-700">{todo.priority}</span>
                        </div>
                        {todo.description ? (
                          <div className="mt-1 text-sm text-gray-600">{todo.description}</div>
                        ) : null}
                        <div className="mt-2 text-xs text-gray-500">
                          status: {todo.status}
                          {todo.deadline ? ` · deadline: ${new Date(todo.deadline).toLocaleString()}` : ''}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {result?.state?.observations?.length || taskErrors.length ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Observations</h3>
            <div className="space-y-2">
              {result?.state?.observations?.map((observation, index) => (
                <div key={`${index}-${observation}`} className="rounded border bg-gray-50 px-3 py-2 text-sm text-gray-700">
                  {observation}
                </div>
              ))}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Errors</h3>
            <div className="space-y-2">
              {taskErrors.length === 0 ? (
                <div className="rounded border bg-gray-50 px-3 py-2 text-sm text-gray-500">
                  No runtime errors recorded.
                </div>
              ) : (
                taskErrors.map((error, index) => (
                  <div key={`${error.timestamp}-${index}`} className="rounded border border-red-100 bg-red-50 px-3 py-2 text-sm">
                    <div className="font-medium text-red-800">{error.type}</div>
                    <div className="mt-1 text-red-700">{error.message}</div>
                    <div className="mt-2 text-xs text-red-500">
                      step {error.step} · {new Date(error.timestamp).toLocaleString()}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
