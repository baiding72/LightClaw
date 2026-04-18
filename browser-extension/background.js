chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.type) {
    return false
  }

  if (message.type === 'LIGHTCLAW_EXTENSION_HEALTH') {
    sendResponse({
      ok: true,
      payload: {
        extension_version: chrome.runtime.getManifest().version,
        runtime_available: true,
        browser_family: 'chromium',
        permissions: ['tabs'],
      },
    })
    return false
  }

  if (message.type !== 'LIGHTCLAW_GET_BROWSER_CONTEXT') {
    return false
  }

  chrome.tabs.query({ currentWindow: true }, (tabs) => {
    if (chrome.runtime.lastError) {
      sendResponse({
        ok: false,
        error: chrome.runtime.lastError.message,
      })
      return
    }

    const normalizedTabs = tabs
      .filter((tab) => typeof tab.id === 'number' && typeof tab.windowId === 'number' && tab.url)
      .map((tab) => ({
        tab_id: tab.id,
        window_id: tab.windowId,
        title: tab.title || '',
        url: tab.url || '',
        active: Boolean(tab.active),
        fav_icon_url: tab.favIconUrl || null,
      }))

    const selectedTab = normalizedTabs.find((tab) => tab.active) || normalizedTabs[0]
    if (!selectedTab) {
      sendResponse({
        ok: false,
        error: 'No tabs found in the current browser window.',
      })
      return
    }

    sendResponse({
      ok: true,
      payload: {
        source: 'browser_extension',
        captured_at: new Date().toISOString(),
        selected_tab: selectedTab,
        tabs: normalizedTabs,
      },
    })
  })

  return true
})
