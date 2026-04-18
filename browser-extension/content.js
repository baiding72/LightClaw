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

    if (data.type !== 'LIGHTCLAW_EXTENSION_REQUEST') {
      return
    }

    chrome.runtime.sendMessage({ type: 'LIGHTCLAW_GET_BROWSER_CONTEXT' }, (response) => {
      if (chrome.runtime.lastError) {
        postError(data.requestId, chrome.runtime.lastError.message)
        return
      }

      if (!response || !response.ok) {
        postError(data.requestId, response?.error || 'Browser extension request failed.')
        return
      }

      postSuccess(data.requestId, response.payload)
    })
  })
})()
