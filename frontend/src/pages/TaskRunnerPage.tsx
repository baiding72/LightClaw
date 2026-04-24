import { useEffect, useState } from 'react'
import axios from 'axios'
import { api } from '../lib/api'
import {
  checkBrowserExtensionHealth,
  focusBrowserTab,
  getAvailableTabs,
  type BrowserTabContext,
  type GuiActionDecision,
  type GuiObservationPayload,
  executeGuiAction,
  observeInteractiveTree,
} from '../lib/browserExtension'

interface BuiltInTask {
  task_id: string
  instruction: string
  category: string
  difficulty: string
  allowed_tools: string[]
}

interface TaskHistoryItem {
  task_id: string
  instruction: string
  category: string
  difficulty: string
  status: string
  created_at: string
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
  warnings?: Array<{ step: number; type: string; message: string; timestamp: string }>
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
      structured_output?: Record<string, unknown> | null
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
    warnings?: Array<{ step: number; type: string; message: string; timestamp: string }>
    browser_context?: {
      source: 'browser_extension'
      captured_at: string
      selected_tab: BrowserTabContext
      tabs: BrowserTabContext[]
    }
  }
}

interface GuiDecisionResponse {
  thought_process: string
  action_type: 'CLICK' | 'TYPE' | 'SCROLL' | 'WAIT' | 'FINISH'
  target_id?: string | null
  action_value?: string | null
  strategy?: 'read' | 'write' | null
  structured_output?: Record<string, unknown> | null
}

interface GuiExecutionSnapshot {
  success: boolean
  status: 'Success' | 'ElementNotFound' | 'Error'
  action_type: string
  target_id?: string | null
  detail?: string
  error?: string
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

interface LLMHealth {
  status: 'healthy' | 'unhealthy' | 'degraded'
  model?: string
  response?: string
  latency_ms?: number
  error?: string
}

interface LLMProfileItem {
  profile_id: string
  name: string
  provider: string
  model: string
  base_url: string
  has_api_key: boolean
  api_key_masked: string
}

interface LLMSettingsPayload {
  active_profile_id?: string | null
  profiles: LLMProfileItem[]
}

interface ModelOption {
  id: string
  provider: string
  model: string
  label: string
  base_url: string
  capabilities: Array<'text' | 'reasoning' | 'vision' | 'gui'>
  hint: string
}

const MODEL_OPTIONS: ModelOption[] = [
  {
    id: 'deepseek-chat',
    provider: 'deepseek',
    model: 'deepseek-chat',
    label: 'deepseek-chat',
    base_url: 'https://api.deepseek.com/v1',
    capabilities: ['text'],
    hint: 'DeepSeek 官方 API 当前主文本模型，适合普通对话与工具调用。',
  },
  {
    id: 'deepseek-reasoner',
    provider: 'deepseek',
    model: 'deepseek-reasoner',
    label: 'deepseek-reasoner',
    base_url: 'https://api.deepseek.com/v1',
    capabilities: ['text', 'reasoning'],
    hint: 'DeepSeek 官方推理模型，适合复杂规划。官方文档当前未给出同级视觉 API 列表。',
  },
  {
    id: 'qwen-plus',
    provider: 'qwen',
    model: 'qwen-plus',
    label: 'qwen-plus',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    capabilities: ['text', 'reasoning'],
    hint: 'Qwen 官方通用文本模型，适合非视觉任务。',
  },
  {
    id: 'qwen-max',
    provider: 'qwen',
    model: 'qwen-max',
    label: 'qwen-max',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    capabilities: ['text', 'reasoning'],
    hint: 'Qwen 高能力文本模型，适合复杂规划与总结。',
  },
  {
    id: 'qwen-vl-plus',
    provider: 'qwen',
    model: 'qwen-vl-plus',
    label: 'qwen-vl-plus',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    capabilities: ['vision'],
    hint: 'Qwen 官方 OpenAI 兼容视觉模型。视觉任务至少应使用 Qwen VL 系列。',
  },
  {
    id: 'qwen-vl-max',
    provider: 'qwen',
    model: 'qwen-vl-max',
    label: 'qwen-vl-max',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    capabilities: ['vision', 'reasoning'],
    hint: 'Qwen 官方高阶视觉模型。适合复杂截图理解与页面布局判断。',
  },
  {
    id: 'qwen3-vl-plus',
    provider: 'qwen',
    model: 'qwen3-vl-plus',
    label: 'qwen3-vl-plus',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    capabilities: ['vision', 'reasoning'],
    hint: 'Qwen 新一代视觉模型，官方模型列表包含该名称，可用于视觉理解。',
  },
  {
    id: 'gui-plus',
    provider: 'qwen',
    model: 'gui-plus',
    label: 'gui-plus',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    capabilities: ['vision', 'gui'],
    hint: '阿里云 GUI 专用模型，针对截图+界面交互优化。仅支持中国内地部署。',
  },
  {
    id: 'gpt-4o-mini',
    provider: 'openai',
    model: 'gpt-4o-mini',
    label: 'gpt-4o-mini',
    base_url: 'https://api.openai.com/v1',
    capabilities: ['text', 'vision'],
    hint: 'OpenAI 通用模型，可做文本与图像理解。',
  },
]

const DEFAULT_MODEL_OPTION = MODEL_OPTIONS.find((item) => item.id === 'qwen-vl-max') || MODEL_OPTIONS[0]

const QA_TEST_CASES = {
  readAndSummarize:
    "请在当前页面中检索‘大语言模型算法实习生’的相关记录，提取出该岗位的投递时间、当前的应聘状态（如初筛、一面、笔试等），并生成一段简短的总结确认。",
  guiFormFill:
    "请帮我点击编辑教育经历，依次将本科学校输入为‘华中科技大学’，专业输入为‘自动化’；将硕士学校输入为‘厦门大学’，专业输入为‘航空航天工程’，确认无误后点击保存按钮。",
}

const formatProviderName = (provider: string) => {
  if (provider === 'deepseek') return 'DeepSeek'
  if (provider === 'qwen') return 'Qwen'
  if (provider === 'openai') return 'OpenAI'
  return provider
}

export default function TaskRunnerPage() {
  const [builtInTasks, setBuiltInTasks] = useState<BuiltInTask[]>([])
  const [taskHistory, setTaskHistory] = useState<TaskHistoryItem[]>([])
  const [showAllHistory, setShowAllHistory] = useState(false)
  const [selectedTask, setSelectedTask] = useState('')
  const [selectedHistoryTaskId, setSelectedHistoryTaskId] = useState<string | null>(null)
  const [customInstruction, setCustomInstruction] = useState(QA_TEST_CASES.readAndSummarize)
  const [running, setRunning] = useState(false)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [result, setResult] = useState<TaskResult | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [recentNotes, setRecentNotes] = useState<NoteItem[]>([])
  const [recentTodos, setRecentTodos] = useState<TodoItem[]>([])
  const [availableTabs, setAvailableTabs] = useState<BrowserTabContext[]>([])
  const [selectedTabId, setSelectedTabId] = useState<number | null>(null)
  const [browserStatus, setBrowserStatus] = useState('浏览器扩展尚未连接')
  const [llmStatus, setLlmStatus] = useState('正在检查 LLM 状态...')
  const [loadingBrowserContext, setLoadingBrowserContext] = useState(false)
  const [llmProfiles, setLlmProfiles] = useState<LLMProfileItem[]>([])
  const [activeProfileId, setActiveProfileId] = useState<string>('')
  const [selectedProfileId, setSelectedProfileId] = useState<string>('')
  const [savingLlmProfile, setSavingLlmProfile] = useState(false)
  const [guiSuccessBurst, setGuiSuccessBurst] = useState(false)
  const [latestGuiObservation, setLatestGuiObservation] = useState<GuiObservationPayload | null>(null)
  const [latestGuiDecision, setLatestGuiDecision] = useState<GuiDecisionResponse | null>(null)
  const [latestGuiExecution, setLatestGuiExecution] = useState<GuiExecutionSnapshot | null>(null)
  const [latestErrorTrace, setLatestErrorTrace] = useState<string | null>(null)
  const [latestConsecutiveErrors, setLatestConsecutiveErrors] = useState(0)
  const [showVisionPanel, setShowVisionPanel] = useState(true)
  const [llmForm, setLlmForm] = useState({
    profile_id: '',
    name: DEFAULT_MODEL_OPTION.provider,
    provider: DEFAULT_MODEL_OPTION.provider,
    model: DEFAULT_MODEL_OPTION.model,
    base_url: DEFAULT_MODEL_OPTION.base_url,
    api_key: '',
  })

  useEffect(() => {
    void loadBuiltInTasks()
    void loadTaskHistory()
    void loadArtifacts()
    void loadLlmSettings()
    void probeLlmHealth()
    void refreshAvailableTabs()
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

  const loadTaskHistory = async () => {
    try {
      const response = await api.get<{ tasks: TaskHistoryItem[] }>('/tasks', {
        params: { page: 1, page_size: 12 },
      })
      setTaskHistory(response.data.tasks)
    } catch (error) {
      console.error('Failed to load task history:', error)
    }
  }

  const loadLlmSettings = async () => {
    try {
      const response = await api.get<LLMSettingsPayload>('/settings/llm')
      const payload = response.data
      setLlmProfiles(payload.profiles)
      const currentProfileId = payload.active_profile_id || payload.profiles[0]?.profile_id || ''
      setActiveProfileId(currentProfileId)
      const preferredProfile =
        payload.profiles.find((item) => item.provider === DEFAULT_MODEL_OPTION.provider && item.model === DEFAULT_MODEL_OPTION.model)
        || payload.profiles.find((item) => item.provider === DEFAULT_MODEL_OPTION.provider)
        || payload.profiles.find((item) => item.profile_id === currentProfileId)
        || null
      setSelectedProfileId(preferredProfile?.profile_id || currentProfileId)
      if (preferredProfile) {
        setLlmForm({
          profile_id: preferredProfile.profile_id,
          name: preferredProfile.name,
          provider: preferredProfile.provider,
          model: preferredProfile.model,
          base_url: preferredProfile.base_url,
          api_key: '',
        })
      }
    } catch (error) {
      console.error('加载 LLM 配置失败:', error)
    }
  }

  const selectedTaskInfo = builtInTasks.find((task) => task.task_id === selectedTask)
  const toolCalls = result?.state?.tool_calls ?? []
  const guiActions = result?.state?.gui_actions ?? []
  const taskErrors = result?.state?.errors ?? []
  const taskWarnings = result?.state?.warnings ?? result?.warnings ?? []
  const currentDecision = result?.state?.current_decision
  const candidateTools = currentDecision?.candidate_tools ?? result?.state?.candidate_tools ?? []
  const latestStructuredOutput = latestGuiDecision?.structured_output ?? currentDecision?.structured_output ?? null
  const recoveryTrace = result?.state?.recovery_trace ?? []
  const activeCheckpoint = result?.state?.active_checkpoint ?? result?.active_checkpoint ?? null
  const checkpointTitle = activeCheckpoint
    ? String(activeCheckpoint['title'] ?? activeCheckpoint['type'] ?? '待处理检查点')
    : null
  const checkpointDescription = activeCheckpoint
    ? String(activeCheckpoint['description'] ?? '')
    : null
  const checkpointResumeHint = activeCheckpoint
    ? String(activeCheckpoint['resume_hint'] ?? '处理完成后重新运行任务即可继续。')
    : null
  const currentGoal = result?.current_goal
    ?? result?.state?.current_goal
    ?? customInstruction
    ?? selectedTaskInfo?.instruction
    ?? '当前还没有记录目标。'
  const currentSubgoal = result?.current_subgoal
    ?? result?.state?.current_subgoal
    ?? '尚未设置'
  const latestObservation = result?.state?.observations?.length
    ? result.state.observations[result.state.observations.length - 1]
    : '当前还没有观察结果。'
  const currentGuiObservation = latestGuiObservation?.observation ?? null
  const currentScreenshotDataUrl = currentGuiObservation?.screenshot_base64
    ? currentGuiObservation.screenshot_base64.startsWith('data:image')
      ? currentGuiObservation.screenshot_base64
      : `data:image/jpeg;base64,${currentGuiObservation.screenshot_base64}`
    : null
  const actionSpaceCounts = currentGuiObservation
    ? currentGuiObservation.nodes.reduce<Record<string, number>>((acc, node) => {
        const key = node.role || 'generic'
        acc[key] = (acc[key] || 0) + 1
        return acc
      }, {})
    : {}
  const roleColorMap: Record<string, string> = {
    button: '#569CD6',
    link: '#4EC9B0',
    input: '#DCDCAA',
    textarea: '#C586C0',
    select: '#CE9178',
    checkbox: '#B5CEA8',
    radio: '#9CDCFE',
    tab: '#F44747',
    menuitem: '#D7BA7D',
    generic: '#808080',
  }
  const totalObservedNodes = currentGuiObservation?.nodes.length ?? 0
  const stackedRoleSegments = Object.entries(actionSpaceCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([role, count]) => ({
      role,
      count,
      percentage: totalObservedNodes > 0 ? (count / totalObservedNodes) * 100 : 0,
      color: roleColorMap[role] || roleColorMap.generic,
    }))
  const groupedObservationNodes = currentGuiObservation
    ? currentGuiObservation.nodes.reduce<Record<string, typeof currentGuiObservation.nodes>>((acc, node) => {
        const key = node.role || 'generic'
        acc[key] = acc[key] || []
        acc[key].push(node)
        return acc
      }, {})
    : {}
  const latestTargetId = latestGuiDecision?.target_id || null
  const latestTargetSucceeded = latestGuiExecution?.success ?? null
  const memorySummary = result?.state?.memory_summary ?? null
  const visibleHistoryTasks = showAllHistory ? taskHistory : taskHistory.slice(0, 3)
  const selectedBrowserTab = availableTabs.find((tab) => tab.tab_id === selectedTabId) ?? null
  const taskRunnerTab =
    availableTabs.find((tab) => tab.active && tab.url.startsWith(window.location.origin)) ??
    availableTabs.find((tab) => tab.url.startsWith(window.location.origin)) ??
    null
  const formatJson = (value: unknown) => JSON.stringify(value, null, 2)
  const formatValue = (value: unknown) => {
    if (typeof value === 'string') return value
    return JSON.stringify(value)
  }
  const normalizeSomText = (value: string) =>
    value
      .split('\n')
      .map((line) => line.replace(/\s+/g, ' ').trim())
      .filter(Boolean)

  const computeSomOverlapRatio = (previousText: string, nextText: string) => {
    const previousLines = new Set(normalizeSomText(previousText))
    const nextLines = new Set(normalizeSomText(nextText))
    if (previousLines.size === 0 || nextLines.size === 0) {
      return 0
    }

    let intersection = 0
    for (const line of previousLines) {
      if (nextLines.has(line)) {
        intersection += 1
      }
    }

    return intersection / Math.max(previousLines.size, nextLines.size)
  }
  const toScreenshotUrl = (path: string) => {
    const normalizedPath = path.replace(/\\/g, '/')
    const fileName = normalizedPath.split('/').pop()
    return fileName ? `${api.defaults.baseURL?.replace(/\/api$/, '') || ''}/artifacts/screenshots/${fileName}` : null
  }
  const summarizeToolCall = (call: ToolCall) => {
    switch (call.tool) {
      case 'click':
        return call.args?.selector ? `点击 ${String(call.args.selector)}` : '已点击元素'
      case 'type_text':
        return call.args?.selector
          ? `向 ${String(call.args.selector)} 输入文本`
          : '已输入文本'
      case 'select_option':
        return call.args?.selector
          ? `在 ${String(call.args.selector)} 选择 ${String(call.args.option)}`
          : '已选择选项'
      case 'take_screenshot':
        return call.result?.path ? '已截取页面截图' : '已执行截图'
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

  const browserTools = new Set(['click', 'type_text', 'select_option', 'take_screenshot', 'scroll'])

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

  const formatApiError = (error: unknown) => {
    if (axios.isAxiosError(error)) {
      const payload = error.response?.data
      if (typeof payload === 'string' && payload.trim()) {
        return payload
      }
      if (payload && typeof payload === 'object') {
        const record = payload as Record<string, unknown>
        const detail = record.detail
        const message = record.error
        if (typeof detail === 'string' && detail.trim()) return detail
        if (typeof message === 'string' && message.trim()) return message
      }
      return error.message
    }
    if (error instanceof Error) return error.message
    return String(error)
  }

  const probeBrowserExtension = async () => {
    try {
      await checkBrowserExtensionHealth()
      setBrowserStatus('☑️ 浏览器扩展已连接')
    } catch (error) {
      const message = formatApiError(error)
      setBrowserStatus(`浏览器扩展异常：${message}`)
    }
  }

  const probeLlmHealth = async () => {
    try {
      const response = await api.get<LLMHealth>('/health/llm')
      if (response.data.status === 'healthy') {
        setLlmStatus('☑️ LLM 已连接')
      } else if (response.data.status === 'degraded') {
        setLlmStatus(`LLM 异常：${response.data.error || '网关暂时不可用'}`)
      } else {
        setLlmStatus(`LLM 异常：${response.data.error || '未知错误'}`)
      }
    } catch (error) {
      setLlmStatus('LLM 异常：健康检查不可用')
    }
  }

  const loadProfileIntoForm = (profileId: string) => {
    setSelectedProfileId(profileId)
    const profile = llmProfiles.find((item) => item.profile_id === profileId)
    if (!profile) return
    setLlmForm({
      profile_id: profile.profile_id,
      name: profile.name,
      provider: profile.provider,
      model: profile.model,
      base_url: profile.base_url,
      api_key: '',
    })
  }

  const selectedModelOption = MODEL_OPTIONS.find((item) => item.model === llmForm.model) || null
  const isCustomModel = !selectedModelOption
  const matchedSavedProfile = selectedProfileId
    ? llmProfiles.find((item) => item.profile_id === selectedProfileId) || null
    : llmProfiles.find((item) => item.provider === llmForm.provider && item.model === llmForm.model) || null

  const applyModelOption = (optionId: string) => {
    if (optionId === 'custom') {
      setLlmForm((prev) => ({
        ...prev,
        provider: prev.provider || 'custom',
      }))
      return
    }
    const option = MODEL_OPTIONS.find((item) => item.id === optionId)
    if (!option) return
    const matchedProfile = llmProfiles.find((item) => item.provider === option.provider && item.model === option.model) || null
    setSelectedProfileId(matchedProfile?.profile_id || '')
    setLlmForm((prev) => ({
      ...prev,
      name: !prev.name || prev.name === prev.model || prev.name === prev.provider ? option.provider : prev.name,
      provider: option.provider,
      model: option.model,
      base_url: option.base_url,
      profile_id: matchedProfile?.profile_id || '',
    }))
  }

  const saveLlmProfile = async () => {
    const normalizedName = llmForm.name.trim() || llmForm.provider.trim() || llmForm.model.trim()
    if (!normalizedName || !llmForm.provider || !llmForm.model || !llmForm.base_url) {
      alert('请完整填写模型、Base URL 和 API Key 配置。')
      return
    }
    setSavingLlmProfile(true)
    try {
      const payload = { ...llmForm, name: normalizedName }
      const response = await api.post<LLMSettingsPayload>('/settings/llm/profiles', payload)
      setLlmProfiles(response.data.profiles)
      const currentProfileId = llmForm.profile_id || response.data.active_profile_id || ''
      setActiveProfileId(response.data.active_profile_id || '')
      setSelectedProfileId(currentProfileId)
      setLlmForm((prev) => ({ ...prev, profile_id: currentProfileId, name: normalizedName, api_key: '' }))
      await probeLlmHealth()
      setLogs((prev) => [...prev, `LLM 配置已保存：${normalizedName}`])
    } catch (error) {
      const message = formatApiError(error)
      alert(`保存 LLM 配置失败：${message}`)
    } finally {
      setSavingLlmProfile(false)
    }
  }

  const activateLlmProfile = async () => {
    if (!selectedProfileId) {
      alert('请先选择一个已保存的配置。')
      return
    }
    setSavingLlmProfile(true)
    try {
      const response = await api.post<LLMSettingsPayload>('/settings/llm/activate', {
        profile_id: selectedProfileId,
      })
      setLlmProfiles(response.data.profiles)
      setActiveProfileId(response.data.active_profile_id || '')
      await probeLlmHealth()
      setLogs((prev) => [...prev, `已切换 LLM 配置：${selectedProfileId}`])
    } catch (error) {
      const message = formatApiError(error)
      alert(`切换 LLM 配置失败：${message}`)
    } finally {
      setSavingLlmProfile(false)
    }
  }

  const loadHistoryTaskIntoEditor = (task: TaskHistoryItem) => {
    setSelectedHistoryTaskId(task.task_id)
    setSelectedTask('')
    setCustomInstruction(task.instruction)
    setLogs((prev) => [...prev, `已载入历史任务：${task.task_id}`])
  }

  const refreshAvailableTabs = async () => {
    setLoadingBrowserContext(true)
    try {
      await probeBrowserExtension()
      await checkBrowserExtensionHealth()
      const tabs = await getAvailableTabs()
      setAvailableTabs(tabs)
      setSelectedTabId((previousTabId) => (
        previousTabId && tabs.some((tab) => tab.tab_id === previousTabId) ? previousTabId : null
      ))
      setBrowserStatus('☑️ 浏览器扩展已连接')
      setLogs((prev) => [...prev, `已刷新目标标签页列表：${tabs.length} 个网页标签页`])
    } catch (error) {
      const message = formatApiError(error)
      console.error('Failed to refresh browser tabs:', error)
      setAvailableTabs([])
      setSelectedTabId(null)
      setBrowserStatus(`浏览器扩展异常：${message}`)
      setLogs((prev) => [...prev, `标签页列表刷新失败：${message}`])
    } finally {
      setLoadingBrowserContext(false)
    }
  }

  const clearTaskInput = () => {
    if (!customInstruction && !selectedTask && !selectedHistoryTaskId) return
    const confirmed = window.confirm('确认清空当前任务输入和已加载的历史任务吗？')
    if (!confirmed) return
    setSelectedTask('')
    setSelectedHistoryTaskId(null)
    setCustomInstruction('')
    setLogs((prev) => [...prev, '已清空当前任务输入'])
  }

  const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))
  const postGuiTrace = async (payload: Record<string, unknown>) => {
    try {
      await api.post('/v1/gui/trace', payload)
    } catch (error) {
      console.error('Failed to persist GUI trace:', error)
    }
  }

  const buildGuiTaskResult = (params: {
    success: boolean
    taskId: string
    outcome: string
    totalSteps: number
    instruction: string
    currentUrl?: string
    currentTitle?: string
    thoughts: string[]
    observations: string[]
    guiActions: GuiAction[]
    errors: TaskError[]
    finalDecision?: GuiDecisionResponse | null
  }): TaskResult => ({
    success: params.success,
    paused: false,
    task_id: params.taskId,
    outcome: params.outcome,
    lifecycle_status: params.success ? 'completed' : 'failed',
    total_steps: params.totalSteps,
    current_goal: params.instruction,
    current_subgoal: params.success ? '任务已完成' : '任务中断',
    error: params.errors.length ? params.errors[params.errors.length - 1].message : undefined,
    state: {
      current_step: params.totalSteps,
      total_tokens: 0,
      total_latency_ms: 0,
      current_url: params.currentUrl,
      current_page_title: params.currentTitle,
      current_goal: params.instruction,
      current_subgoal: params.success ? '任务已完成' : '任务中断',
      lifecycle_status: params.success ? 'completed' : 'failed',
      plan_steps: [],
      memory_summary: {
        mode: 'gui_loop',
      },
      candidate_tools: [],
      current_decision: params.finalDecision
        ? {
            response: params.finalDecision.thought_process,
            structured_output: params.finalDecision.structured_output ?? null,
            chosen_tool: params.finalDecision.action_type,
            tool_args: {
              target_id: params.finalDecision.target_id ?? null,
              action_value: params.finalDecision.action_value ?? null,
              strategy: params.finalDecision.strategy ?? null,
            },
            candidate_tools: [],
          }
        : null,
      recovery_trace: [],
      checkpoints: [],
      active_checkpoint: null,
      environment: {
        scenario_type: 'gui_loop',
      },
      thoughts: params.thoughts,
      observations: params.observations,
      tool_calls: [],
      gui_actions: params.guiActions,
      errors: params.errors,
      warnings: [],
      browser_context: selectedBrowserTab
        ? {
            source: 'browser_extension',
            captured_at: new Date().toISOString(),
            selected_tab: selectedBrowserTab,
            tabs: availableTabs,
          }
        : undefined,
    },
  })

  const startGuiTask = async (instruction: string) => {
    if (!selectedBrowserTab?.tab_id) {
      throw new Error('请选择要操作的目标网页')
    }

    let taskId: string = activeTaskId || ''
    if (!taskId) {
      const createResponse = await api.post('/tasks', {
        instruction,
        category: selectedTaskInfo?.category || 'web_form',
        difficulty: selectedTaskInfo?.difficulty || 'medium',
        allowed_tools: ['click', 'type_text', 'select_option', 'scroll', 'take_screenshot'],
      })
      taskId = createResponse.data.task_id
      setActiveTaskId(taskId)
    }

    const thoughts: string[] = []
    const observations: string[] = []
    const guiActions: GuiAction[] = []
    const guiErrors: TaskError[] = []

    let previousErrorTrace: string | null = null
    let consecutiveErrors = 0
    let latestObservation: GuiObservationPayload | null = null
    let lastFailedDecision: GuiDecisionResponse | null = null
    let previousObservationSnapshot: { scrollY: number; somText: string } | null = null
    let previousSuccessfulDecision: GuiDecisionResponse | null = null
    const runnerTabToRestore = taskRunnerTab

    setLogs([`GUI 任务开始：${instruction}`, `任务 ID：${taskId}`])
    setLatestGuiObservation(null)
    setLatestGuiDecision(null)
    setLatestGuiExecution(null)
    setLatestErrorTrace(null)
    setLatestConsecutiveErrors(0)

    try {
      for (let stepIndex = 1; stepIndex <= 15; stepIndex += 1) {
        setLogs((prev) => [...prev, `[Loop ${stepIndex}] 观察当前页面...`])
        latestObservation = await observeInteractiveTree(selectedBrowserTab.tab_id)
        setLatestGuiObservation(latestObservation)
        if (!latestObservation.observation) {
          throw new Error('扩展没有返回有效的页面观察结果。请确认目标网页允许脚本注入，并重试。')
        }
        if (
          previousSuccessfulDecision?.action_type === 'SCROLL' &&
          previousObservationSnapshot &&
          computeSomOverlapRatio(previousObservationSnapshot.somText, latestObservation.observation.som_text) >= 0.95
        ) {
          previousErrorTrace = '系统拦截：页面已到底部或无新内容加载，严禁继续滚动，请立刻从现有内容中提取信息或返回 FINISH。'
          setLatestErrorTrace(previousErrorTrace)
          setLatestConsecutiveErrors((value) => value)
          setLogs((prev) => [...prev, `[Self-Correction] ${previousErrorTrace}`])
        }
        observations.push(`第 ${stepIndex} 步：观察到 ${latestObservation.observation.nodes.length} 个可交互元素`)
        await postGuiTrace({
          task_id: taskId,
          step_index: stepIndex,
          task_description: instruction,
          observation: latestObservation.observation,
        })

        const decisionResponse = await api.post<GuiDecisionResponse>('/v1/gui/decision', {
          task_description: instruction,
          observation: latestObservation.observation,
          previous_error_trace: previousErrorTrace,
          task_id: taskId,
          step_index: stepIndex,
        })

        const decision = decisionResponse.data
        setLatestGuiDecision(decision)
        thoughts.push(decision.thought_process)
        setLogs((prev) => [
          ...prev,
          `[Agent Thought] ${decision.thought_process}`,
          `[Action] ${decision.action_type}${decision.target_id ? ` -> ${decision.target_id}` : ''}${decision.action_value ? ` (${decision.action_value})` : ''}`,
        ])
        await postGuiTrace({
          task_id: taskId,
          step_index: stepIndex,
          task_description: instruction,
          decision,
          previous_error_trace: previousErrorTrace,
        })

        if (decision.action_type === 'FINISH') {
          const guiResult = buildGuiTaskResult({
            success: true,
            taskId,
            outcome: decision.action_value || 'gui_finished',
            totalSteps: stepIndex,
            instruction,
            currentUrl: latestObservation.observation.metadata.url,
            currentTitle: latestObservation.observation.metadata.title,
            thoughts,
            observations,
            guiActions,
            errors: guiErrors,
            finalDecision: decision,
          })
          setResult(guiResult)
          setGuiSuccessBurst(true)
          window.setTimeout(() => setGuiSuccessBurst(false), 2000)
          setLogs((prev) => [...prev, `✦ 任务完成：${decision.action_value || decision.thought_process}`])
          await api.patch(`/tasks/${taskId}`, {
            status: 'completed',
            result: guiResult,
          })
          await loadTaskHistory()
          return
        }

        const executionPayload = await executeGuiAction(
          decision as GuiActionDecision,
          selectedBrowserTab.tab_id,
        )

        const executionResult = executionPayload.result
        setLatestGuiExecution(executionResult)
        guiActions.push({
          step: stepIndex,
          action: decision.action_type,
          target: decision.target_id || '',
          success: executionResult.success,
          details: {
            action_value: decision.action_value ?? null,
            status: executionResult.status,
            detail: executionResult.detail ?? null,
            error: executionResult.error ?? null,
          },
          timestamp: new Date().toISOString(),
        })

        setLogs((prev) => [
          ...prev,
          `[Execution Result] ${executionResult.status}${executionResult.error ? `: ${executionResult.error}` : ''}`,
        ])
        await postGuiTrace({
          task_id: taskId,
          step_index: stepIndex,
          task_description: instruction,
          decision,
          execution_result: executionResult,
          previous_error_trace: previousErrorTrace,
        })

        if (executionResult.success) {
          previousObservationSnapshot = {
            scrollY: latestObservation.observation.metadata.scroll_y,
            somText: latestObservation.observation.som_text,
          }
          previousSuccessfulDecision = decision
          if (previousErrorTrace) {
            await postGuiTrace({
              task_id: taskId,
              step_index: stepIndex,
              task_description: instruction,
              observation: latestObservation?.observation,
              decision,
              execution_result: executionResult,
              previous_error_trace: previousErrorTrace,
              rejected_decision: lastFailedDecision,
            })
          }
          previousErrorTrace = null
          lastFailedDecision = null
          consecutiveErrors = 0
          setLatestErrorTrace(null)
          setLatestConsecutiveErrors(0)
          await sleep(1200)
          continue
        }

        previousErrorTrace = `${executionResult.status}: ${executionResult.error || executionResult.detail || 'unknown'}`
        lastFailedDecision = decision
        previousSuccessfulDecision = null
        consecutiveErrors += 1
        setLatestErrorTrace(previousErrorTrace)
        setLatestConsecutiveErrors(consecutiveErrors)
        guiErrors.push({
          step: stepIndex,
          type: executionResult.status,
          message: previousErrorTrace,
          timestamp: new Date().toISOString(),
        })

        if (consecutiveErrors > 3) {
          throw new Error(`连续执行失败超过 3 次，需要用户接管。最后错误：${previousErrorTrace}`)
        }

        await sleep(900)
      }

      throw new Error('达到最大循环次数，任务未完成。')
    } finally {
      if (runnerTabToRestore?.tab_id && runnerTabToRestore?.window_id) {
        try {
          await focusBrowserTab(runnerTabToRestore.tab_id, runnerTabToRestore.window_id)
        } catch {
        }
      }
    }
  }

  const runTask = async () => {
    const instruction = customInstruction || selectedTaskInfo?.instruction
    if (!instruction) {
      alert('请先选择模板任务，或输入自定义任务。')
      return
    }

    setRunning(true)
    setResult(null)

    try {
      await startGuiTask(instruction)
      await loadArtifacts()
      await loadTaskHistory()
    } catch (error) {
      const message = formatApiError(error)
      console.error('Failed to run task:', error)
      setLogs((prev) => [...prev, `错误：${message}`])
      const failedTaskId = activeTaskId || `gui_failed_${Date.now()}`
      const failedResult = buildGuiTaskResult({
        success: false,
        taskId: failedTaskId,
        outcome: 'gui_failed',
        totalSteps: 0,
        instruction,
        currentUrl: selectedBrowserTab?.url,
        currentTitle: selectedBrowserTab?.title,
        thoughts: [],
        observations: [],
        guiActions: [],
        errors: [{
          step: 0,
          type: 'gui_loop_error',
          message,
          timestamp: new Date().toISOString(),
        }],
        finalDecision: latestGuiDecision,
      })
      setResult(failedResult)
      if (activeTaskId) {
        try {
          await api.patch(`/tasks/${activeTaskId}`, {
            status: 'failed',
            result: failedResult,
          })
        } catch (patchError) {
          console.error('Failed to persist failed GUI task result:', patchError)
        }
      }
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold text-gray-900">任务执行器</h2>
        <p className="text-sm text-gray-600">
          运行任务，查看每一步工具调用，并检查执行过程留下的结果。
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">任务启动</h3>
            <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
              <div className="rounded border bg-gray-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium text-gray-900">最近任务</div>
                  {taskHistory.length > 3 ? (
                    <button
                      type="button"
                      onClick={() => setShowAllHistory((prev) => !prev)}
                      className="text-xs text-sky-700 hover:text-sky-900"
                    >
                      {showAllHistory ? '收起' : '显示全部'}
                    </button>
                  ) : null}
                </div>
                <div className="mt-3 space-y-2">
                  {taskHistory.length === 0 ? (
                    <div className="text-sm text-gray-500">还没有历史任务。</div>
                  ) : (
                    visibleHistoryTasks.map((task) => (
                      <button
                        key={task.task_id}
                        type="button"
                        onClick={() => loadHistoryTaskIntoEditor(task)}
                        className={`w-full rounded border px-3 py-3 text-left text-sm ${
                          selectedHistoryTaskId === task.task_id
                            ? 'border-sky-300 bg-sky-50 text-sky-900'
                            : 'border-gray-200 bg-white text-gray-800 hover:bg-gray-50'
                        }`}
                      >
                        <div className="font-medium line-clamp-2">{task.instruction}</div>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
                          <span>{task.status}</span>
                          <span>{task.category}</span>
                        </div>
                      </button>
                    ))
                  )}
                </div>
              </div>

              <div>
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    内置模板
                  </label>
                  <select
                    value={selectedTask}
                    onChange={(e) => {
                      const taskId = e.target.value
                      setSelectedTask(taskId)
                      setSelectedHistoryTaskId(null)
                      const task = builtInTasks.find((item) => item.task_id === taskId)
                      setCustomInstruction(task?.instruction || '')
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">请选择模板...</option>
                    {builtInTasks.map((task) => (
                      <option key={task.task_id} value={task.task_id}>
                        [{task.difficulty}] {task.instruction.substring(0, 50)}...
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    任务输入
                  </label>
                  <div className="mb-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedTask('')
                        setSelectedHistoryTaskId(null)
                        setCustomInstruction(QA_TEST_CASES.readAndSummarize)
                      }}
                      className="rounded border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-800 hover:bg-sky-100"
                    >
                      QA Case 1：信息检索总结
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedTask('')
                        setSelectedHistoryTaskId(null)
                        setCustomInstruction(QA_TEST_CASES.guiFormFill)
                      }}
                      className="rounded border border-violet-200 bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-800 hover:bg-violet-100"
                    >
                      QA Case 2：多步骤表单填写
                    </button>
                  </div>
                  <textarea
                    value={customInstruction}
                    onChange={(e) => {
                      setCustomInstruction(e.target.value)
                      setSelectedTask('')
                    }}
                    placeholder="直接输入新任务，或从左侧载入历史任务..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows={5}
                  />
                  <div className="mt-2 text-xs text-gray-500">
                    {selectedHistoryTaskId
                      ? `已载入历史任务：${selectedHistoryTaskId}。可编辑后提交，也可直接运行。`
                      : '你可以直接输入新任务，也可以从左侧选择历史任务。'}
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h4 className="text-sm font-semibold text-slate-900">目标网页</h4>
                  <div className="mt-1 text-sm text-slate-600">{browserStatus}</div>
                </div>
                <button
                  type="button"
                  onClick={() => void refreshAvailableTabs()}
                  disabled={loadingBrowserContext}
                  className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                >
                  {loadingBrowserContext ? '刷新中...' : '刷新标签页'}
                </button>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">
                    目标标签页选择器
                  </label>
                  <select
                    value={selectedTabId ?? ''}
                    onChange={(e) => setSelectedTabId(e.target.value ? Number(e.target.value) : null)}
                    className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    disabled={availableTabs.length === 0}
                  >
                    <option value="">
                      {availableTabs.length === 0 ? '未发现可操作网页标签页' : '请选择目标网页'}
                    </option>
                    {availableTabs.map((tab) => {
                      const domain = (() => {
                        try {
                          return new URL(tab.url).hostname
                        } catch {
                          return tab.url
                        }
                      })()
                      return (
                        <option key={tab.tab_id} value={tab.tab_id}>
                          {(tab.title || '未命名页面').slice(0, 48)} | {domain}
                        </option>
                      )
                    })}
                  </select>
                  <div className="mt-2 text-xs text-slate-500">
                    系统只会向这里选中的标签页注入观察和执行脚本。
                  </div>
                </div>

                <div className="rounded-lg border border-slate-200 bg-white p-4">
                  <div className="text-sm font-medium text-slate-800">当前瞄准目标</div>
                  {selectedBrowserTab ? (
                    <div className="mt-3 space-y-3 text-sm text-slate-700">
                      <div className="flex items-start gap-3">
                        {selectedBrowserTab.fav_icon_url ? (
                          <img
                            src={selectedBrowserTab.fav_icon_url}
                            alt=""
                            className="mt-0.5 h-4 w-4 rounded-sm"
                          />
                        ) : null}
                        <div className="min-w-0">
                          <div className="font-medium text-slate-900">{selectedBrowserTab.title || '未命名标签页'}</div>
                          <div className="mt-1 break-all text-xs text-slate-500">{selectedBrowserTab.url}</div>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs text-slate-600">
                        <span className="rounded border border-slate-200 bg-slate-50 px-2 py-1">tab #{selectedBrowserTab.tab_id}</span>
                        <span className="rounded border border-slate-200 bg-slate-50 px-2 py-1">window #{selectedBrowserTab.window_id}</span>
                        {selectedBrowserTab.active ? (
                          <span className="rounded border border-emerald-200 bg-emerald-50 px-2 py-1 text-emerald-700">当前激活</span>
                        ) : null}
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-800">
                      请选择要操作的目标网页
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-3">
              {!selectedBrowserTab ? (
                <div className="w-full rounded-md border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-800">
                  请选择要操作的目标网页
                </div>
              ) : null}
              <button
                onClick={runTask}
                disabled={running || !selectedBrowserTab}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {running ? '执行中...' : '运行任务'}
              </button>
              <button
                type="button"
                onClick={clearTaskInput}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
              >
                清空
              </button>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-medium text-gray-900">模型配置</h3>
                <div className="mt-1 text-sm text-gray-600">{llmStatus}</div>
              </div>
              <button
                type="button"
                onClick={() => void loadLlmSettings()}
                className="px-3 py-2 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                重新加载
              </button>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">已保存配置</label>
                <select
                  value={selectedProfileId}
                  onChange={(e) => loadProfileIntoForm(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">请选择配置...</option>
                  {llmProfiles.map((profile) => (
                    <option key={profile.profile_id} value={profile.profile_id}>
                      {formatProviderName(profile.provider)}{profile.profile_id === activeProfileId ? '（当前）' : ''}
                    </option>
                  ))}
                </select>
                {selectedProfileId ? (
                  <div className="mt-2 text-xs text-gray-500">
                    {llmProfiles.find((item) => item.profile_id === selectedProfileId)?.api_key_masked || '未保存密钥'}
                  </div>
                ) : null}
                <button
                  type="button"
                  onClick={activateLlmProfile}
                  disabled={savingLlmProfile || !selectedProfileId || selectedProfileId === activeProfileId}
                  className="mt-3 w-full px-3 py-2 text-sm bg-slate-900 text-white rounded-md hover:bg-slate-800 disabled:opacity-50"
                >
                  设为当前配置
                </button>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">配置名称</label>
                  <input
                    value={llmForm.name}
                    onChange={(e) => setLlmForm((prev) => ({ ...prev, name: e.target.value }))}
                    placeholder="默认会使用 provider 名称，例如 qwen"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">模型</label>
                  <select
                    value={selectedModelOption?.id || 'custom'}
                    onChange={(e) => applyModelOption(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {MODEL_OPTIONS.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                    <option value="custom">自定义模型</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Provider</label>
                  <input
                    value={llmForm.provider}
                    readOnly
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div className="md:col-span-2">
                  <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                    <div className="font-medium text-slate-900">
                      {selectedModelOption ? `当前模型：${selectedModelOption.label}` : '当前模型：自定义'}
                    </div>
                    <div className="mt-1">{selectedModelOption?.hint || '自定义模型时，请确认该模型支持你需要的输入类型。'}</div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      {(selectedModelOption?.capabilities || []).map((capability) => (
                        <span key={capability} className="rounded border bg-white px-2 py-1 text-slate-700">
                          {capability}
                        </span>
                      ))}
                    </div>
                    <div className="mt-2 text-xs text-slate-600">
                      视觉任务建议使用 Qwen VL / GUI-Plus。根据当前查到的官方文档，DeepSeek 官方 API 明确列出的仍是 `deepseek-chat` 与 `deepseek-reasoner`，没有同级视觉模型列表。
                    </div>
                    <div className="mt-2 text-xs text-slate-600">
                      已保存密钥：{matchedSavedProfile?.api_key_masked || '未保存'}
                    </div>
                  </div>
                </div>
                {isCustomModel ? (
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-2">模型 ID</label>
                    <input
                      value={llmForm.model}
                      onChange={(e) => setLlmForm((prev) => ({ ...prev, model: e.target.value }))}
                      placeholder="例如 qwen-vl-max / deepseek-chat"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                ) : null}
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">Base URL</label>
                  <input
                    value={llmForm.base_url}
                    onChange={(e) => setLlmForm((prev) => ({ ...prev, base_url: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">API Key</label>
                  <input
                    type="password"
                    value={llmForm.api_key}
                    onChange={(e) => setLlmForm((prev) => ({ ...prev, api_key: e.target.value }))}
                    placeholder={llmForm.profile_id ? '留空则保留当前已保存的 API Key' : '输入新的 API Key'}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div className="md:col-span-2 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={saveLlmProfile}
                    disabled={savingLlmProfile}
                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                  >
                    {savingLlmProfile ? '保存中...' : '保存配置'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const preset = DEFAULT_MODEL_OPTION
                      setSelectedProfileId('')
                      setLlmForm({
                        profile_id: '',
                        name: preset.provider,
                        provider: preset.provider,
                        model: preset.model,
                        base_url: preset.base_url,
                        api_key: '',
                      })
                    }}
                    className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
                  >
                    新建配置
                  </button>
                </div>
              </div>
            </div>
          </div>

          {selectedTaskInfo ? (
            <div className="bg-sky-50 rounded-lg p-4 border border-sky-100">
              <div className="text-sm text-sky-900 font-medium">当前模板</div>
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
            <h4 className="text-sm font-medium text-gray-300 mb-2">执行日志</h4>
            <div className="font-mono text-sm text-green-400 space-y-1 min-h-16">
              {logs.length === 0 ? (
                <div>&gt; 等待任务开始...</div>
              ) : (
                logs.map((log, i) => <div key={i}>&gt; {log}</div>)
              )}
            </div>
            {guiSuccessBurst ? (
              <div className="mt-3 text-center text-sm font-medium text-amber-300">
                ✦ 任务完成 ✦
              </div>
            ) : null}
          </div>

	          {result ? (
	            <div className={`rounded-lg p-6 border ${result.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
	              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
	                  <h3 className={`text-lg font-medium ${result.success ? 'text-green-800' : result.paused ? 'text-amber-800' : 'text-red-800'}`}>
	                    {result.success ? '任务完成' : result.paused ? '任务暂停' : '任务失败'}
	                  </h3>
                  <div className="mt-2 text-sm text-gray-700">
                    任务 ID：<span className="font-mono">{result.task_id}</span>
                  </div>
                </div>
	                <div className="grid grid-cols-4 gap-3 text-sm">
	                  <div className="rounded border bg-white px-3 py-2">
	                    <div className="text-gray-500">结果</div>
	                    <div className="font-medium text-gray-900">{result.outcome}</div>
	                  </div>
	                  <div className="rounded border bg-white px-3 py-2">
	                    <div className="text-gray-500">生命周期</div>
	                    <div className={`inline-flex rounded px-2 py-1 text-xs font-medium ${lifecycleTone(result.lifecycle_status || result.state?.lifecycle_status)}`}>
	                      {formatLifecycleLabel(result.lifecycle_status || result.state?.lifecycle_status)}
	                    </div>
	                  </div>
	                  <div className="rounded border bg-white px-3 py-2">
	                    <div className="text-gray-500">步数</div>
	                    <div className="font-medium text-gray-900">{result.total_steps}</div>
	                  </div>
                  <div className="rounded border bg-white px-3 py-2">
                    <div className="text-gray-500">耗时</div>
                    <div className="font-medium text-gray-900">
                      {((result.total_latency_ms || 0) / 1000).toFixed(1)}s
                    </div>
                  </div>
                </div>
              </div>

	              {result.error ? (
                <div className="mt-4 text-sm text-red-700">
                  <strong>错误：</strong> {result.error}
                </div>
	              ) : null}

                {taskWarnings.length > 0 ? (
                  <div className="mt-4 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                    <div className="font-medium">警告</div>
                    <div className="mt-2 space-y-2">
                      {taskWarnings.slice(-2).map((warning, index) => (
                        <div key={`${warning.timestamp}-${index}`}>{warning.message}</div>
                      ))}
                    </div>
                  </div>
                ) : null}

                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="rounded border bg-white p-4">
                        <div className="text-xs font-medium uppercase tracking-wide text-gray-500">当前目标</div>
                      <div className="mt-2 text-sm text-gray-900 whitespace-pre-wrap">
                        {currentGoal}
                      </div>
                    </div>
                    <div className="rounded border bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">当前子目标</div>
                      <div className="mt-2 text-sm text-gray-900 whitespace-pre-wrap">
                        {currentSubgoal}
                      </div>
                    </div>
                  </div>

	              {result.state?.thoughts?.length ? (
	                <div className="mt-4">
                  <div className="text-sm font-medium text-gray-700 mb-2">最终思考</div>
                  <div className="rounded border bg-white p-3 text-sm text-gray-700 whitespace-pre-wrap">
                    {result.state.thoughts[result.state.thoughts.length - 1]}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

	          {executionSteps.length > 0 || latestGuiObservation ? (
	            <div className="bg-white rounded-lg shadow p-6">
	              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-medium text-gray-900">执行面板</h3>
                  <p className="mt-1 text-sm text-gray-600">
                    展示本次运行的工具调用、浏览器动作、目标页面和截图。
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-gray-600">
                  <span className="rounded border bg-gray-50 px-2 py-1">
                    {executionSteps.length} 次工具调用
                  </span>
                  <span className="rounded border bg-gray-50 px-2 py-1">
                    {guiActions.length} 次 GUI 动作
                  </span>
                  <span className="rounded border bg-gray-50 px-2 py-1">
                    {executionSteps.filter((call) => call.screenshotPath).length} 张截图
                  </span>
                </div>
	              </div>

	              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="rounded border bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">当前环境</div>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        <div>
                          <div className="text-xs uppercase tracking-wide text-gray-500">页面</div>
                          <div className="mt-1 text-sm text-gray-900 break-words">
                            {result?.state?.current_page_title || result?.state?.current_url || '尚未捕获页面'}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs uppercase tracking-wide text-gray-500">场景</div>
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
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">检查点 / 恢复</div>
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
                          当前没有活动检查点，运行时可以继续自动执行。
                        </div>
                      )}
                    </div>
                  </div>

	              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(280px,0.75fr)]">
	                <div className="rounded border bg-gray-50 p-4 lg:col-span-2">
	                  <div className="flex flex-wrap items-center justify-between gap-3">
	                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">GUI Board</div>
		                    {currentGuiObservation ? (
		                      <div className="flex flex-wrap gap-2 text-xs">
		                        <span className="rounded border bg-white px-2 py-1 text-gray-700">
		                          可交互元素 {currentGuiObservation.nodes.length}
		                        </span>
		                        <span className="rounded border bg-white px-2 py-1 text-gray-700">
		                          页面 {currentGuiObservation.metadata.title || 'Untitled'}
		                        </span>
		                      </div>
		                    ) : null}
	                  </div>
	                  <div className="mt-3 flex flex-wrap gap-2">
	                    {Object.entries(actionSpaceCounts).length === 0 ? (
	                      <span className="text-sm text-gray-500">当前还没有 GUI 观察数据。</span>
	                    ) : (
	                      Object.entries(actionSpaceCounts).map(([role, count]) => (
	                        <span
	                          key={role}
	                          className="rounded border border-sky-200 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-800"
	                        >
	                          {role} × {count}
	                        </span>
	                      ))
	                    )}
	                  </div>
	                  {stackedRoleSegments.length > 0 ? (
	                    <div className="mt-4">
	                      <div className="mb-2 text-xs uppercase tracking-wide text-gray-500">元素分布</div>
	                      <div className="flex h-4 w-full overflow-hidden rounded border border-gray-200 bg-gray-950">
	                        {stackedRoleSegments.map((segment) => (
	                          <div
	                            key={segment.role}
	                            title={`${segment.role}: ${segment.count}`}
	                            className="h-full transition-all"
	                            style={{
	                              width: `${Math.max(segment.percentage, 4)}%`,
	                              backgroundColor: segment.color,
	                            }}
	                          />
	                        ))}
	                      </div>
	                      <div className="mt-2 flex flex-wrap gap-2 text-xs">
	                        {stackedRoleSegments.map((segment) => (
	                          <span
	                            key={segment.role}
	                            className="inline-flex items-center gap-2 rounded border bg-white px-2 py-1 text-gray-700"
	                            title={`${segment.role}: ${segment.count}`}
	                          >
	                            <span
	                              className="inline-block h-2.5 w-2.5 rounded-sm"
	                              style={{ backgroundColor: segment.color }}
	                            />
	                            <span>{segment.role}</span>
	                            <span className="text-gray-500">{segment.count}</span>
	                          </span>
	                        ))}
	                      </div>
	                    </div>
	                  ) : null}
	                  <div className="mt-4 grid gap-4 lg:grid-cols-3">
	                    <div className="rounded border bg-white p-3">
	                      <div className="text-xs uppercase tracking-wide text-gray-500">最近思考</div>
	                      <div className="mt-2 text-sm text-gray-900 whitespace-pre-wrap">
	                        {latestGuiDecision?.thought_process || '还没有决策。'}
	                      </div>
	                    </div>
	                    <div className="rounded border bg-white p-3">
	                      <div className="text-xs uppercase tracking-wide text-gray-500">最近动作</div>
	                      <div className="mt-2 text-sm text-gray-900">
	                        {latestGuiDecision
	                          ? `${latestGuiDecision.action_type}${latestGuiDecision.target_id ? ` -> ${latestGuiDecision.target_id}` : ''}${latestGuiDecision.action_value ? ` (${latestGuiDecision.action_value})` : ''}`
	                          : '还没有动作。'}
	                      </div>
	                    </div>
	                    <div className="rounded border bg-white p-3">
	                      <div className="text-xs uppercase tracking-wide text-gray-500">最近结果</div>
	                      <div className="mt-2 text-sm text-gray-900">
	                        {latestGuiExecution
	                          ? `${latestGuiExecution.status}${latestGuiExecution.error ? `: ${latestGuiExecution.error}` : ''}`
	                          : '还没有执行结果。'}
	                      </div>
	                    </div>
	                  </div>
	                  <div className="mt-4">
	                    {latestErrorTrace ? (
	                      <div className="rounded border border-amber-500/40 bg-amber-900/10 p-3">
	                        <div className="flex items-center justify-between gap-3">
	                          <div className="text-xs font-medium uppercase tracking-wide text-amber-700">最近失败链</div>
	                          <div className="text-xs text-amber-700">连续失败：{latestConsecutiveErrors}/3 次</div>
	                        </div>
	                        <pre className="mt-2 overflow-auto whitespace-pre-wrap font-mono text-xs text-amber-900">
	                          {latestErrorTrace}
	                        </pre>
	                      </div>
	                    ) : (
	                      <div className="rounded border border-emerald-500/30 bg-emerald-900/5 p-3">
	                        <div className="text-xs font-medium uppercase tracking-wide text-emerald-700">最近失败链</div>
	                        <div className="mt-2 text-sm text-emerald-800">状态健康，上一轮执行成功。</div>
	                      </div>
	                    )}
	                  </div>
	                  <div className="mt-4 rounded border bg-slate-950 p-3 text-slate-100">
	                    <div className="flex items-center justify-between gap-3">
	                      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">Agent 视觉监控 (SoM Vision)</div>
	                      <button
	                        type="button"
	                        onClick={() => setShowVisionPanel((prev) => !prev)}
	                        className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
	                      >
	                        {showVisionPanel ? '收起' : '展开'}
	                      </button>
	                    </div>
	                    {showVisionPanel ? (
	                      currentScreenshotDataUrl ? (
	                        <div className="mt-3">
	                          <div className="overflow-hidden rounded border border-cyan-500/30 bg-black shadow-[inset_0_0_0_1px_rgba(34,211,238,0.08)]">
	                            <img
	                              src={currentScreenshotDataUrl}
	                              alt="Agent SoM vision"
	                              className="max-h-96 w-full object-contain bg-[linear-gradient(to_bottom,rgba(255,255,255,0.02)_0,rgba(255,255,255,0.02)_1px,transparent_1px,transparent_3px)]"
	                            />
	                          </div>
	                          <div className="mt-2 flex items-center justify-between gap-3 text-xs text-slate-400">
	                            <span>当前视口 SoM 标注截图</span>
	                            <a
	                              href={currentScreenshotDataUrl}
	                              target="_blank"
	                              rel="noreferrer"
	                              className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-cyan-300 hover:bg-slate-800"
	                            >
	                              新标签页打开
	                            </a>
	                          </div>
	                        </div>
	                      ) : (
	                        <div className="mt-3 rounded border border-slate-800 bg-slate-900/80 p-3 text-sm text-slate-400">
	                          当前 observation 还没有携带截图数据。
	                        </div>
	                      )
	                    ) : null}
	                  </div>
	                  {currentGuiObservation?.som_text ? (
	                    <div className="mt-4 rounded border bg-white p-3">
	                      <div className="text-xs uppercase tracking-wide text-gray-500">元素树状预览</div>
	                      <div className="mt-3 space-y-2">
	                        {Object.entries(groupedObservationNodes)
	                          .sort((a, b) => b[1].length - a[1].length)
	                          .map(([role, nodes]) => (
	                            <details key={role} className="rounded border bg-gray-50 p-2" open={nodes.length <= 4}>
	                              <summary className="cursor-pointer list-none text-sm font-medium text-gray-800">
	                                <span
	                                  className="mr-2 inline-block h-2.5 w-2.5 rounded-sm"
	                                  style={{ backgroundColor: roleColorMap[role] || roleColorMap.generic }}
	                                />
	                                {role} ({nodes.length})
	                              </summary>
	                              <div className="mt-2 space-y-2">
	                                {nodes.map((node) => (
	                                  <div
	                                    key={node.agent_id}
	                                    className={`rounded border p-2 text-xs text-gray-700 ${
	                                      latestTargetId === node.agent_id
	                                        ? latestTargetSucceeded
	                                          ? 'border-green-700/50 bg-green-950/10'
	                                          : 'border-red-700/50 bg-red-950/10'
	                                        : 'bg-white'
	                                    }`}
	                                  >
	                                    <div className="font-mono text-[11px] text-gray-500">
	                                      {node.agent_id} · &lt;{node.tag}&gt;
	                                      {latestTargetId === node.agent_id ? (
	                                        <span
	                                          className={`ml-2 rounded px-1.5 py-0.5 text-[10px] font-medium ${
	                                            latestTargetSucceeded
	                                              ? 'bg-green-900/20 text-green-700'
	                                              : 'bg-red-900/20 text-red-700'
	                                          }`}
	                                        >
	                                          {latestTargetSucceeded ? '[✓ Last Action]' : '[✗ Failed Target]'}
	                                        </span>
	                                      ) : null}
	                                    </div>
	                                    <div className="mt-1 text-sm text-gray-900">
	                                      {node.text || node.aria_label || node.placeholder || '(empty)'}
	                                    </div>
	                                    {node.context_text ? (
	                                      <div className="mt-1 text-gray-500">{node.context_text}</div>
	                                    ) : null}
	                                  </div>
	                                ))}
	                              </div>
	                            </details>
	                          ))}
	                      </div>
	                    </div>
	                  ) : null}
	                </div>

	                <div className="rounded border bg-gray-50 p-4">
	                  <div className="text-xs font-medium uppercase tracking-wide text-gray-500">候选工具</div>
                      <div className="mt-3 space-y-2">
                        {candidateTools.length === 0 ? (
                          <div className="text-sm text-gray-500">还没有候选工具记录。</div>
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
	                  <div className="text-xs font-medium uppercase tracking-wide text-gray-500">实际选择的工具</div>
	                  <div className="mt-3 space-y-2">
	                    {currentDecision?.chosen_tool ? (
                          <div className="rounded border bg-white px-3 py-3">
                            <div className="font-medium text-gray-900">{currentDecision.chosen_tool}</div>
                            <div className="mt-2 text-sm text-gray-700 whitespace-pre-wrap">
                              {currentDecision.chosen_tool_reason || '没有记录选择理由。'}
                            </div>
                            {currentDecision.tool_args ? (
                              <pre className="mt-3 overflow-x-auto rounded border bg-gray-50 p-3 text-xs text-gray-700">
                                {formatJson(currentDecision.tool_args)}
                              </pre>
                            ) : null}
                          </div>
	                    ) : (
	                      <div className="text-sm text-gray-500">还没有记录已选工具。</div>
	                    )}
	                  </div>
	                </div>
	              </div>

                  <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                    <div className="rounded border bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">场景记忆</div>
                      <div className="mt-2 text-sm text-gray-800">
                        {memorySummary ? (
                          <pre className="overflow-x-auto rounded border bg-gray-50 p-3 text-xs text-gray-700">
                            {formatJson(memorySummary)}
                          </pre>
                        ) : (
                          '当前还没有记忆快照。'
                        )}
                      </div>
                    </div>
                    <div className="rounded border bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">最新观察</div>
                      <div className="mt-2 text-sm text-gray-800 whitespace-pre-wrap">
                        {latestObservation}
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                    <div className="rounded border bg-white p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">错误 / 恢复</div>
                      {recoveryTrace.length === 0 ? (
                        <div className="mt-2 text-sm text-gray-500">还没有恢复尝试记录。</div>
                      ) : (
                        <div className="mt-2 space-y-2">
                          {recoveryTrace.slice(-3).reverse().map((item, index) => (
                            <div key={`${item.timestamp}-${index}`} className="rounded border bg-gray-50 px-3 py-2 text-sm">
                              <div className="font-medium text-gray-900">{item.error_type} · {item.tool_name}</div>
                              <div className="mt-1 text-gray-700">{item.error_message}</div>
                              {item.suggested_action ? (
                                <div className="mt-2 text-xs text-gray-600">下一步：{item.suggested_action}</div>
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
                            浏览器
                          </span>
                        ) : null}
                        <span className={`text-xs font-medium px-2 py-1 rounded ${call.error ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                          {call.error ? '失败' : '成功'}
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
                            <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-2">参数</div>
                            <pre className="overflow-x-auto rounded border bg-gray-50 p-3 text-xs text-gray-700">{formatJson(call.args)}</pre>
                          </div>
                          <div>
                            <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-2">结果</div>
                            <pre className="overflow-x-auto rounded border bg-gray-50 p-3 text-xs text-gray-700">
                              {call.error || formatJson(call.result)}
                            </pre>
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-2">截图</div>
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
                        <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-2">参数</div>
                        <pre className="overflow-x-auto rounded border bg-gray-50 p-3 text-xs text-gray-700">{formatJson(call.args)}</pre>
                      </div>
                      <div>
                        <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-2">结果</div>
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
              <h3 className="text-lg font-medium text-gray-900">产物</h3>
              <button
                onClick={() => void loadArtifacts()}
                className="px-3 py-2 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                刷新
              </button>
            </div>

            <div className="space-y-6">
              <div>
                <div className="text-sm font-medium text-gray-800 mb-3">本轮结构化结果</div>
                {latestStructuredOutput ? (
                  <pre className="overflow-x-auto rounded border bg-gray-50 p-3 text-xs text-gray-700">
                    {formatJson(latestStructuredOutput)}
                  </pre>
                ) : (
                  <div className="text-sm text-gray-500">当前任务还没有生成结构化结果。</div>
                )}
              </div>

              <div>
                <div className="text-sm font-medium text-gray-800 mb-3">最近笔记</div>
                <div className="space-y-3">
                  {recentNotes.length === 0 ? (
                    <div className="text-sm text-gray-500">还没有笔记。</div>
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
                <div className="text-sm font-medium text-gray-800 mb-3">最近待办</div>
                <div className="space-y-3">
                  {recentTodos.length === 0 ? (
                    <div className="text-sm text-gray-500">还没有待办。</div>
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
                          状态：{todo.status}
                          {todo.deadline ? ` · 截止时间：${new Date(todo.deadline).toLocaleString()}` : ''}
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
            <h3 className="text-lg font-medium text-gray-900 mb-4">观察</h3>
            <div className="space-y-2">
              {result?.state?.observations?.map((observation, index) => (
                <div key={`${index}-${observation}`} className="rounded border bg-gray-50 px-3 py-2 text-sm text-gray-700">
                  {observation}
                </div>
              ))}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">错误</h3>
            <div className="space-y-2">
              {taskErrors.length === 0 ? (
                <div className="rounded border bg-gray-50 px-3 py-2 text-sm text-gray-500">
                  没有记录到运行时错误。
                </div>
              ) : (
                taskErrors.map((error, index) => (
                  <div key={`${error.timestamp}-${index}`} className="rounded border border-red-100 bg-red-50 px-3 py-2 text-sm">
                    <div className="font-medium text-red-800">{error.type}</div>
                    <div className="mt-1 text-red-700">{error.message}</div>
                    <div className="mt-2 text-xs text-red-500">
                      第 {error.step} 步 · {new Date(error.timestamp).toLocaleString()}
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
