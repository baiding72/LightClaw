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

interface TaskResult {
  success: boolean
  task_id: string
  outcome: string
  total_steps: number
  total_tokens?: number
  total_latency_ms?: number
  error?: string
  state?: {
    current_step: number
    total_tokens: number
    total_latency_ms: number
    thoughts: string[]
    observations: string[]
    tool_calls: ToolCall[]
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
  const [result, setResult] = useState<TaskResult | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [recentNotes, setRecentNotes] = useState<NoteItem[]>([])
  const [recentTodos, setRecentTodos] = useState<TodoItem[]>([])
  const [browserContext, setBrowserContext] = useState<BrowserContextPayload | null>(null)
  const [selectedTabId, setSelectedTabId] = useState<number | null>(null)
  const [browserStatus, setBrowserStatus] = useState('Browser extension not connected yet.')
  const [loadingBrowserContext, setLoadingBrowserContext] = useState(false)

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
  const availableTabs = browserContext?.tabs ?? []
  const selectedBrowserTab = (
    availableTabs.find((tab) => tab.tab_id === selectedTabId)
    ?? browserContext?.selected_tab
    ?? null
  )

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

    setRunning(true)
    setResult(null)
    setLogs(['Starting task...'])

    try {
      const createResponse = await api.post('/tasks', {
        instruction,
        category: selectedTaskInfo?.category || 'multi_step',
        difficulty: selectedTaskInfo?.difficulty || 'medium',
        allowed_tools: selectedTaskInfo?.allowed_tools,
      })

      const taskId = createResponse.data.task_id
      setLogs((prev) => [...prev, `Task created: ${taskId}`, 'Running task...'])

      const runPayload = selectedBrowserTab
        ? {
            browser_context: {
              source: 'browser_extension',
              captured_at: browserContext?.captured_at || new Date().toISOString(),
              selected_tab: selectedBrowserTab,
              tabs: availableTabs,
            },
          }
        : {}

      if (selectedBrowserTab) {
        setLogs((prev) => [
          ...prev,
          `Target tab: ${selectedBrowserTab.title || selectedBrowserTab.url}`,
          selectedBrowserTab.url,
        ])
      }

      const runResponse = await api.post<TaskResult>(`/tasks/${taskId}/run`, runPayload)

      setResult(runResponse.data)
      setLogs((prev) => [
        ...prev,
        `Task finished: ${runResponse.data.success ? 'success' : 'failed'}`,
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

  const formatJson = (value: unknown) => JSON.stringify(value, null, 2)

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
              {running ? 'Running...' : 'Run Task'}
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
                  <h3 className={`text-lg font-medium ${result.success ? 'text-green-800' : 'text-red-800'}`}>
                    {result.success ? 'Task Completed' : 'Task Failed'}
                  </h3>
                  <div className="mt-2 text-sm text-gray-700">
                    Task ID: <span className="font-mono">{result.task_id}</span>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div className="rounded border bg-white px-3 py-2">
                    <div className="text-gray-500">Outcome</div>
                    <div className="font-medium text-gray-900">{result.outcome}</div>
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

          {toolCalls.length > 0 ? (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Tool Timeline</h3>
              <div className="space-y-4">
                {toolCalls.map((call) => (
                  <div key={`${call.step}-${call.tool}`} className="border rounded-lg p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span className="inline-flex h-7 min-w-7 items-center justify-center rounded bg-slate-900 px-2 text-xs font-medium text-white">
                          {call.step}
                        </span>
                        <div>
                          <div className="font-medium text-gray-900">{call.tool}</div>
                          <div className="text-xs text-gray-500">{new Date(call.timestamp).toLocaleString()}</div>
                        </div>
                      </div>
                      <span className={`text-xs font-medium px-2 py-1 rounded ${call.error ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                        {call.error ? 'failed' : 'success'}
                      </span>
                    </div>

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

      {result?.state?.observations?.length ? (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Observations</h3>
          <div className="space-y-2">
            {result.state.observations.map((observation, index) => (
              <div key={`${index}-${observation}`} className="rounded border bg-gray-50 px-3 py-2 text-sm text-gray-700">
                {observation}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
