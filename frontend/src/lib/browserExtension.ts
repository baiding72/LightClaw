export interface BrowserTabContext {
  tab_id: number
  window_id: number
  title: string
  url: string
  active: boolean
  fav_icon_url?: string | null
}

export interface BrowserContextPayload {
  source: 'browser_extension'
  captured_at: string
  selected_tab: BrowserTabContext
  tabs: BrowserTabContext[]
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

interface ExtensionSuccessResponse {
  type: 'LIGHTCLAW_EXTENSION_RESPONSE'
  requestId: string
  payload: BrowserContextPayload
}

interface ExtensionHealthResponse {
  type: 'LIGHTCLAW_EXTENSION_HEALTH_RESPONSE'
  requestId: string
  payload: BrowserExtensionHealth
}

interface ExtensionErrorResponse {
  type: 'LIGHTCLAW_EXTENSION_ERROR'
  requestId: string
  error: string
}

type ExtensionResponse =
  | ExtensionSuccessResponse
  | ExtensionHealthResponse
  | ExtensionErrorResponse

const REQUEST_TYPE = 'LIGHTCLAW_EXTENSION_REQUEST'
const HEALTH_CHECK_TYPE = 'LIGHTCLAW_EXTENSION_HEALTH_CHECK'
const REQUEST_TIMEOUT_MS = 4000

type ExtensionResponseType = ExtensionResponse['type']

async function requestFromExtension<TPayload>(
  requestType: string,
  expectedResponseType: ExtensionResponseType,
): Promise<TPayload> {
  if (typeof window === 'undefined') {
    throw new Error('Browser extension bridge is only available in the browser.')
  }

  const requestId = crypto.randomUUID()

  return await new Promise<TPayload>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      cleanup()
      reject(new Error('Browser extension did not respond. Check that the unpacked extension is loaded in this Chromium browser and that LightClaw is opened on http://127.0.0.1 or http://localhost.'))
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
        reject(new Error(event.data.error))
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

export async function fetchBrowserContextFromExtension(): Promise<BrowserContextPayload> {
  return requestFromExtension<BrowserContextPayload>(
    REQUEST_TYPE,
    'LIGHTCLAW_EXTENSION_RESPONSE',
  )
}
