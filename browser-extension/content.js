(function () {
  const APP_SOURCE = 'lightclaw-app'
  const RESPONSE_ORIGIN = window.location.origin

  function postSuccess(requestId, payload, type = 'LIGHTCLAW_EXTENSION_RESPONSE') {
    window.postMessage(
      {
        type,
        requestId,
        payload,
      },
      RESPONSE_ORIGIN
    )
  }

  function postError(requestId, error) {
    window.postMessage(
      {
        type: 'LIGHTCLAW_EXTENSION_ERROR',
        requestId,
        error,
      },
      RESPONSE_ORIGIN
    )
  }

  window.__LIGHTCLAW_BROWSER_BRIDGE__ = {
    injected: true,
    origin: RESPONSE_ORIGIN,
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window) {
      return
    }

    const data = event.data
    if (!data || data.source !== APP_SOURCE) {
      return
    }

    if (data.type === 'LIGHTCLAW_EXTENSION_HEALTH_CHECK') {
      const runtimeAvailable = typeof chrome !== 'undefined' && Boolean(chrome.runtime?.id)
      if (!runtimeAvailable) {
        postError(data.requestId, 'Extension bridge injected, but chrome.runtime is unavailable in this browser tab.')
        return
      }

      chrome.runtime.sendMessage({ type: 'LIGHTCLAW_EXTENSION_HEALTH' }, (response) => {
        if (chrome.runtime.lastError) {
          postError(data.requestId, chrome.runtime.lastError.message)
          return
        }

        if (!response || !response.ok) {
          postError(data.requestId, response?.error || 'Browser extension health check failed.')
          return
        }

        postSuccess(data.requestId, {
          bridge_injected: true,
          page_origin: RESPONSE_ORIGIN,
          user_agent: navigator.userAgent,
          ...response.payload,
        }, 'LIGHTCLAW_EXTENSION_HEALTH_RESPONSE')
      })
      return
    }

    const handlers = {
      LIGHTCLAW_TABS_REQUEST: {
        message: { type: 'LIGHTCLAW_GET_TABS' },
        responseType: 'LIGHTCLAW_TABS_RESPONSE',
      },
      LIGHTCLAW_FOCUS_TAB_REQUEST: {
        message: { type: 'LIGHTCLAW_FOCUS_TAB', tabId: data.tabId, windowId: data.windowId },
        responseType: 'LIGHTCLAW_FOCUS_TAB_RESPONSE',
      },
      LIGHTCLAW_GUI_OBSERVE_REQUEST: {
        message: { type: 'LIGHTCLAW_GUI_OBSERVE', tabId: data.tabId },
        responseType: 'LIGHTCLAW_GUI_OBSERVE_RESPONSE',
      },
      LIGHTCLAW_GUI_ACTION_REQUEST: {
        message: { type: 'LIGHTCLAW_GUI_ACTION', tabId: data.tabId, action: data.action },
        responseType: 'LIGHTCLAW_GUI_ACTION_RESPONSE',
      },
    }

    const handler = handlers[data.type]
    if (!handler) {
      return
    }

    chrome.runtime.sendMessage(handler.message, (response) => {
      if (chrome.runtime.lastError) {
        postError(data.requestId, chrome.runtime.lastError.message)
        return
      }

      if (!response || !response.ok) {
        postError(data.requestId, response?.error || 'Browser extension request failed.')
        return
      }

      postSuccess(data.requestId, response.payload, handler.responseType)
    })
  })
})()
