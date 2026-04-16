(function () {
  const APP_SOURCE = 'lightclaw-app'

  window.addEventListener('message', (event) => {
    if (event.source !== window) {
      return
    }

    const data = event.data
    if (!data || data.source !== APP_SOURCE || data.type !== 'LIGHTCLAW_EXTENSION_REQUEST') {
      return
    }

    chrome.runtime.sendMessage({ type: 'LIGHTCLAW_GET_BROWSER_CONTEXT' }, (response) => {
      if (chrome.runtime.lastError) {
        window.postMessage(
          {
            type: 'LIGHTCLAW_EXTENSION_ERROR',
            requestId: data.requestId,
            error: chrome.runtime.lastError.message,
          },
          window.location.origin
        )
        return
      }

      if (!response || !response.ok) {
        window.postMessage(
          {
            type: 'LIGHTCLAW_EXTENSION_ERROR',
            requestId: data.requestId,
            error: response?.error || 'Browser extension request failed.',
          },
          window.location.origin
        )
        return
      }

      window.postMessage(
        {
          type: 'LIGHTCLAW_EXTENSION_RESPONSE',
          requestId: data.requestId,
          payload: response.payload,
        },
        window.location.origin
      )
    })
  })
})()
