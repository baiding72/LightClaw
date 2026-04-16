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

interface ExtensionSuccessResponse {
  type: 'LIGHTCLAW_EXTENSION_RESPONSE'
  requestId: string
  payload: BrowserContextPayload
}

interface ExtensionErrorResponse {
  type: 'LIGHTCLAW_EXTENSION_ERROR'
  requestId: string
  error: string
}

type ExtensionResponse = ExtensionSuccessResponse | ExtensionErrorResponse

const REQUEST_TYPE = 'LIGHTCLAW_EXTENSION_REQUEST'
const REQUEST_TIMEOUT_MS = 4000

export async function fetchBrowserContextFromExtension(): Promise<BrowserContextPayload> {
  if (typeof window === 'undefined') {
    throw new Error('Browser extension bridge is only available in the browser.')
  }

  const requestId = crypto.randomUUID()

  return await new Promise<BrowserContextPayload>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      cleanup()
      reject(new Error('Browser extension did not respond.'))
    }, REQUEST_TIMEOUT_MS)

    const handleMessage = (event: MessageEvent<ExtensionResponse>) => {
      if (event.source !== window) {
        return
      }
      if (!event.data || event.data.requestId !== requestId) {
        return
      }
      if (event.data.type !== 'LIGHTCLAW_EXTENSION_RESPONSE' && event.data.type !== 'LIGHTCLAW_EXTENSION_ERROR') {
        return
      }

      cleanup()

      if (event.data.type === 'LIGHTCLAW_EXTENSION_ERROR') {
        reject(new Error(event.data.error))
        return
      }

      resolve(event.data.payload)
    }

    const cleanup = () => {
      window.clearTimeout(timeoutId)
      window.removeEventListener('message', handleMessage)
    }

    window.addEventListener('message', handleMessage)
    window.postMessage(
      {
        source: 'lightclaw-app',
        type: REQUEST_TYPE,
        requestId,
      },
      window.location.origin
    )
  })
}
