export interface BrowserTabContext {
  tab_id: number
  window_id: number
  title: string
  url: string
  active: boolean
  fav_icon_url?: string | null
}

export interface BrowserExtensionHealth {
  bridge_injected: boolean
  runtime_available: boolean
  extension_version?: string
  browser_family?: string
  permissions?: string[]
  page_origin?: string
  user_agent?: string
}

export interface GuiObservationPayload {
  tab: BrowserTabContext
  observation: {
    metadata: {
      url: string
      title: string
      viewport_width: number
      viewport_height: number
      scroll_x: number
      scroll_y: number
      timestamp: string
    }
    nodes: Array<{
      agent_id: string
      tag: string
      role: string
      text: string
      aria_label?: string
      placeholder?: string
      href?: string
      value?: string
      disabled: boolean
      checked?: boolean
      rect: { x: number; y: number; width: number; height: number }
      context_text?: string
    }>
    som_text: string
    screenshot_base64?: string
  }
}

export interface GuiActionDecision {
  thought_process?: string
  action_type: 'CLICK' | 'TYPE' | 'SCROLL' | 'WAIT' | 'FINISH'
  target_id?: string | null
  action_value?: string | null
}

export interface GuiActionResultPayload {
  tab: BrowserTabContext
  result: {
    success: boolean
    status: 'Success' | 'ElementNotFound' | 'Error'
    action_type: string
    target_id?: string | null
    detail?: string
    error?: string
  }
}

interface ExtensionTabsResponse {
  type: 'LIGHTCLAW_TABS_RESPONSE'
  requestId: string
  payload: BrowserTabContext[]
}

interface ExtensionHealthResponse {
  type: 'LIGHTCLAW_EXTENSION_HEALTH_RESPONSE'
  requestId: string
  payload: BrowserExtensionHealth
}

interface GuiObserveResponse {
  type: 'LIGHTCLAW_GUI_OBSERVE_RESPONSE'
  requestId: string
  payload: GuiObservationPayload
}

interface GuiActionResponse {
  type: 'LIGHTCLAW_GUI_ACTION_RESPONSE'
  requestId: string
  payload: GuiActionResultPayload
}

interface FocusTabResponse {
  type: 'LIGHTCLAW_FOCUS_TAB_RESPONSE'
  requestId: string
  payload: BrowserTabContext | null
}

interface ExtensionErrorResponse {
  type: 'LIGHTCLAW_EXTENSION_ERROR'
  requestId: string
  error: string
}

type ExtensionResponse =
  | ExtensionTabsResponse
  | ExtensionHealthResponse
  | GuiObserveResponse
  | GuiActionResponse
  | FocusTabResponse
  | ExtensionErrorResponse
const HEALTH_CHECK_TYPE = 'LIGHTCLAW_EXTENSION_HEALTH_CHECK'
const REQUEST_TIMEOUT_MS = 4000

type ExtensionResponseType = ExtensionResponse['type']

function normalizeExtensionRuntimeError(error: unknown): Error {
  const message = error instanceof Error ? error.message : String(error || '')
  console.error('[LightClaw Extension Error]', message)

  if (
    (message.includes('permission') || message.includes('Cannot access contents')) &&
    !message.includes('origin_permission=true')
  ) {
    return new Error(
      `扩展疑似缺少当前网页的访问权限。原始错误：${message}。请打开 chrome://extensions -> LightClaw Browser Bridge -> 站点访问，确认已允许访问当前网站，然后刷新目标网页重试。`,
    )
  }

  if (
    message.includes('Receiving end does not exist') ||
    message.includes('Service worker') ||
    message.includes('Extension context invalidated') ||
    message.includes('The message port closed before a response was received')
  ) {
    return new Error(
      `扩展后台可能已休眠或崩溃。原始错误：${message}。请在 chrome://extensions 中点击 LightClaw Browser Bridge 的刷新图标重载扩展，并刷新目标网页后重试。`,
    )
  }

  return new Error(message || '扩展执行失败。请重载扩展后重试。')
}

async function requestFromExtension<TPayload>(
  requestType: string,
  expectedResponseType: ExtensionResponseType,
): Promise<TPayload> {
  if (typeof window === 'undefined') {
    throw new Error('浏览器扩展桥接仅能在浏览器环境中使用。')
  }

  const requestId = crypto.randomUUID()

  return await new Promise<TPayload>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      cleanup()
      reject(new Error('浏览器扩展没有响应。请确认当前使用的是 Chromium 浏览器、扩展已加载，并且 LightClaw 打开在 http://127.0.0.1 或 http://localhost。'))
    }, REQUEST_TIMEOUT_MS)

    const handleMessage = (event: MessageEvent<ExtensionResponse>) => {
      if (event.source !== window) {
        return
      }
      if (!event.data || event.data.requestId !== requestId) {
        return
      }
      if (event.data.type !== expectedResponseType && event.data.type !== 'LIGHTCLAW_EXTENSION_ERROR') {
        return
      }

      cleanup()

      if (event.data.type === 'LIGHTCLAW_EXTENSION_ERROR') {
        reject(normalizeExtensionRuntimeError(event.data.error))
        return
      }

      resolve(event.data.payload as TPayload)
    }

    const cleanup = () => {
      window.clearTimeout(timeoutId)
      window.removeEventListener('message', handleMessage)
    }

    window.addEventListener('message', handleMessage)
    window.postMessage(
      {
        source: 'lightclaw-app',
        type: requestType,
        requestId,
      },
      window.location.origin
    )
  })
}

export async function checkBrowserExtensionHealth(): Promise<BrowserExtensionHealth> {
  return requestFromExtension<BrowserExtensionHealth>(
    HEALTH_CHECK_TYPE,
    'LIGHTCLAW_EXTENSION_HEALTH_RESPONSE',
  )
}

export async function getAvailableTabs(): Promise<BrowserTabContext[]> {
  return requestFromExtension<BrowserTabContext[]>(
    'LIGHTCLAW_TABS_REQUEST',
    'LIGHTCLAW_TABS_RESPONSE',
  )
}

export async function focusBrowserTab(tabId: number, windowId: number): Promise<BrowserTabContext | null> {
  if (typeof window === 'undefined') {
    throw new Error('浏览器扩展桥接仅能在浏览器环境中使用。')
  }

  const requestId = crypto.randomUUID()
  return await new Promise<BrowserTabContext | null>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      cleanup()
      reject(new Error('切换标签页超时。'))
    }, REQUEST_TIMEOUT_MS)

    const handleMessage = (event: MessageEvent<ExtensionResponse>) => {
      if (event.source !== window) return
      if (!event.data || event.data.requestId !== requestId) return
      if (event.data.type !== 'LIGHTCLAW_FOCUS_TAB_RESPONSE' && event.data.type !== 'LIGHTCLAW_EXTENSION_ERROR') return

      cleanup()
      if (event.data.type === 'LIGHTCLAW_EXTENSION_ERROR') {
        reject(normalizeExtensionRuntimeError(event.data.error))
        return
      }
      resolve(event.data.payload as BrowserTabContext | null)
    }

    const cleanup = () => {
      window.clearTimeout(timeoutId)
      window.removeEventListener('message', handleMessage)
    }

    window.addEventListener('message', handleMessage)
    window.postMessage(
      {
        source: 'lightclaw-app',
        type: 'LIGHTCLAW_FOCUS_TAB_REQUEST',
        requestId,
        tabId,
        windowId,
      },
      window.location.origin,
    )
  })
}

export async function observeInteractiveTree(tabId?: number): Promise<GuiObservationPayload> {
  if (typeof window === 'undefined') {
    throw new Error('浏览器扩展桥接仅能在浏览器环境中使用。')
  }

  const requestId = crypto.randomUUID()
  return await new Promise<GuiObservationPayload>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      cleanup()
      reject(new Error('观察当前页面超时。请确认目标标签页仍然打开，且扩展已启用。'))
    }, REQUEST_TIMEOUT_MS)

    const handleMessage = (event: MessageEvent<ExtensionResponse>) => {
      if (event.source !== window) return
      if (!event.data || event.data.requestId !== requestId) return
      if (event.data.type !== 'LIGHTCLAW_GUI_OBSERVE_RESPONSE' && event.data.type !== 'LIGHTCLAW_EXTENSION_ERROR') return

      cleanup()
      if (event.data.type === 'LIGHTCLAW_EXTENSION_ERROR') {
        reject(normalizeExtensionRuntimeError(event.data.error))
        return
      }
      resolve(event.data.payload as GuiObservationPayload)
    }

    const cleanup = () => {
      window.clearTimeout(timeoutId)
      window.removeEventListener('message', handleMessage)
    }

    window.addEventListener('message', handleMessage)
    window.postMessage(
      {
        source: 'lightclaw-app',
        type: 'LIGHTCLAW_GUI_OBSERVE_REQUEST',
        requestId,
        tabId,
      },
      window.location.origin,
    )
  })
}

export async function executeGuiAction(
  action: GuiActionDecision,
  tabId?: number,
): Promise<GuiActionResultPayload> {
  if (typeof window === 'undefined') {
    throw new Error('浏览器扩展桥接仅能在浏览器环境中使用。')
  }

  const requestId = crypto.randomUUID()
  return await new Promise<GuiActionResultPayload>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      cleanup()
      reject(new Error('执行页面动作超时。请确认目标标签页仍然可用。'))
    }, REQUEST_TIMEOUT_MS)

    const handleMessage = (event: MessageEvent<ExtensionResponse>) => {
      if (event.source !== window) return
      if (!event.data || event.data.requestId !== requestId) return
      if (event.data.type !== 'LIGHTCLAW_GUI_ACTION_RESPONSE' && event.data.type !== 'LIGHTCLAW_EXTENSION_ERROR') return

      cleanup()
      if (event.data.type === 'LIGHTCLAW_EXTENSION_ERROR') {
        reject(normalizeExtensionRuntimeError(event.data.error))
        return
      }
      resolve(event.data.payload as GuiActionResultPayload)
    }

    const cleanup = () => {
      window.clearTimeout(timeoutId)
      window.removeEventListener('message', handleMessage)
    }

    window.addEventListener('message', handleMessage)
    window.postMessage(
      {
        source: 'lightclaw-app',
        type: 'LIGHTCLAW_GUI_ACTION_REQUEST',
        requestId,
        tabId,
        action,
      },
      window.location.origin,
    )
  })
}
