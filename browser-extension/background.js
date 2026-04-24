function buildInteractiveTreeInPage() {
  const agentIdAttr = 'data-agent-id'
  const normalizeText = (value) => String(value || '').replace(/\s+/g, ' ').trim()
  const interactiveSelector = [
    'a[href]',
    'button',
    'input',
    'textarea',
    'select',
    '[role="button"]',
    '[role="link"]',
    '[role="tab"]',
    '[role="menuitem"]',
    '[onclick]',
    '[contenteditable="true"]',
    '[tabindex]:not([tabindex="-1"])',
  ].join(',')

  function isProbablyInteractive(element) {
    if (element.matches(interactiveSelector)) {
      return true
    }

    const style = window.getComputedStyle(element)
    if (style.cursor === 'pointer') {
      return true
    }

    const role = (element.getAttribute('role') || '').toLowerCase()
    return ['button', 'link', 'tab', 'menuitem'].includes(role)
  }

  function isVisible(element) {
    const style = window.getComputedStyle(element)
    if (
      style.display === 'none' ||
      style.visibility === 'hidden' ||
      style.opacity === '0' ||
      style.pointerEvents === 'none'
    ) {
      return false
    }

    const rect = element.getBoundingClientRect()
    if (rect.width < 4 || rect.height < 4) {
      return false
    }

    if (
      rect.bottom < 0 ||
      rect.right < 0 ||
      rect.top > window.innerHeight ||
      rect.left > window.innerWidth
    ) {
      return false
    }

    const cx = Math.min(Math.max(rect.left + rect.width / 2, 0), window.innerWidth - 1)
    const cy = Math.min(Math.max(rect.top + rect.height / 2, 0), window.innerHeight - 1)
    const topElement = document.elementFromPoint(cx, cy)
    if (!topElement) {
      return false
    }

    return topElement === element || element.contains(topElement) || topElement.contains(element)
  }

  function deriveRole(element) {
    const explicitRole = (element.getAttribute('role') || '').toLowerCase()
    if (['button', 'link', 'tab', 'menuitem'].includes(explicitRole)) {
      return explicitRole
    }

    const tag = element.tagName.toLowerCase()
    if (tag === 'a') return 'link'
    if (tag === 'button') return 'button'
    if (tag === 'textarea') return 'textarea'
    if (tag === 'select') return 'select'
    if (tag === 'input') {
      const type = (element.getAttribute('type') || 'text').toLowerCase()
      if (type === 'checkbox') return 'checkbox'
      if (type === 'radio') return 'radio'
      return 'input'
    }
    return 'generic'
  }

  function extractOwnText(element) {
    const aria = normalizeText(element.getAttribute('aria-label'))
    const placeholder = normalizeText(element.getAttribute('placeholder'))
    const innerText = normalizeText(element.innerText)
    const value =
      element instanceof HTMLInputElement ||
      element instanceof HTMLTextAreaElement ||
      element instanceof HTMLSelectElement
        ? normalizeText(element.value)
        : ''

    return aria || innerText || placeholder || value
  }

  function extractContextText(element) {
    const candidates = [
      element.closest('label'),
      element.parentElement,
      element.previousElementSibling,
    ].filter(Boolean)

    for (const candidate of candidates) {
      const text = normalizeText(candidate.innerText)
      if (text && text !== extractOwnText(element)) {
        return text.slice(0, 200)
      }
    }

    return ''
  }

  function ensureAgentId(element, index) {
    const existing = element.getAttribute(agentIdAttr)
    if (existing) {
      return existing
    }

    const id = `agent-${index + 1}`
    element.setAttribute(agentIdAttr, id)
    return id
  }

  function extractStaticTextSnippets(elements) {
    const textTags = new Set(['div', 'span', 'p', 'td', 'th', 'li', 'h1', 'h2', 'h3', 'h4', 'strong'])
    const snippets = []
    const seen = new Set()

    for (const element of elements) {
      const tag = element.tagName.toLowerCase()
      if (!textTags.has(tag)) {
        continue
      }

      if (element.matches(interactiveSelector) || element.closest(`[${agentIdAttr}]`)) {
        continue
      }

      if (!isVisible(element)) {
        continue
      }

      const text = normalizeText(element.innerText)
      if (!text || text.length < 2 || text.length > 120) {
        continue
      }

      if (seen.has(text)) {
        continue
      }

      seen.add(text)
      snippets.push(text)
      if (snippets.length >= 80) {
        break
      }
    }

    return snippets
  }

  const rawElements = Array.from(document.querySelectorAll('body *'))
  const nodes = rawElements
    .filter((element) => isProbablyInteractive(element) && isVisible(element))
    .map((element, index) => {
      const rect = element.getBoundingClientRect()
      return {
        agent_id: ensureAgentId(element, index),
        tag: element.tagName.toLowerCase(),
        role: deriveRole(element),
        text: extractOwnText(element),
        aria_label: normalizeText(element.getAttribute('aria-label')) || undefined,
        placeholder: normalizeText(element.getAttribute('placeholder')) || undefined,
        href: element instanceof HTMLAnchorElement ? element.href : undefined,
        value:
          element instanceof HTMLInputElement ||
          element instanceof HTMLTextAreaElement ||
          element instanceof HTMLSelectElement
            ? normalizeText(element.value) || undefined
            : undefined,
        disabled:
          element instanceof HTMLButtonElement ||
          element instanceof HTMLInputElement ||
          element instanceof HTMLSelectElement ||
          element instanceof HTMLTextAreaElement
            ? Boolean(element.disabled)
            : element.getAttribute('aria-disabled') === 'true',
        checked:
          element instanceof HTMLInputElement &&
          ['checkbox', 'radio'].includes((element.type || '').toLowerCase())
            ? element.checked
            : undefined,
        context_text: extractContextText(element) || undefined,
        rect: {
          x: Math.round(rect.left),
          y: Math.round(rect.top),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        },
      }
    })
    .filter((node) => !node.disabled && (node.text || node.aria_label || node.placeholder || node.role === 'input'))

  const staticTextSnippets = extractStaticTextSnippets(rawElements)

  const somText = nodes
    .map((node) => {
      const label = node.text || node.aria_label || node.placeholder || '(empty)'
      const context = node.context_text ? ` | context: ${node.context_text}` : ''
      return `[ID: ${node.agent_id}] <${node.tag} role="${node.role}"> ${label} </${node.tag}>${context}`
    })
    .concat(staticTextSnippets.map((text) => `[TEXT] ${text}`))
    .join('\n')

  return {
    metadata: {
      url: window.location.href,
      title: document.title,
      viewport_width: window.innerWidth,
      viewport_height: window.innerHeight,
      scroll_x: window.scrollX,
      scroll_y: window.scrollY,
      timestamp: new Date().toISOString(),
    },
    nodes,
    som_text: somText,
  }
}

function drawSomOverlayInPage(nodes) {
  const overlayId = `lightclaw-som-overlay-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const overlay = document.createElement('div')
  overlay.id = overlayId
  overlay.style.position = 'fixed'
  overlay.style.inset = '0'
  overlay.style.zIndex = '2147483647'
  overlay.style.pointerEvents = 'none'
  overlay.style.background = 'transparent'

  for (const node of nodes || []) {
    if (!node?.rect) {
      continue
    }

    const frame = document.createElement('div')
    frame.style.position = 'fixed'
    frame.style.left = `${node.rect.x}px`
    frame.style.top = `${node.rect.y}px`
    frame.style.width = `${Math.max(node.rect.width, 8)}px`
    frame.style.height = `${Math.max(node.rect.height, 8)}px`
    frame.style.border = '2px solid rgba(255, 59, 48, 0.95)'
    frame.style.borderRadius = '4px'
    frame.style.boxSizing = 'border-box'
    frame.style.background = 'transparent'

    const label = document.createElement('div')
    label.textContent = `[${String(node.agent_id || '').replace(/^agent-/, '')}]`
    label.style.position = 'absolute'
    label.style.left = '0'
    label.style.top = '0'
    label.style.transform = 'translateY(-100%)'
    label.style.background = 'rgba(255, 59, 48, 0.95)'
    label.style.color = '#fff'
    label.style.fontSize = '11px'
    label.style.lineHeight = '1'
    label.style.fontWeight = '700'
    label.style.padding = '2px 4px'
    label.style.borderRadius = '4px'
    label.style.fontFamily = 'ui-monospace, SFMono-Regular, Menlo, monospace'
    label.style.whiteSpace = 'nowrap'

    frame.appendChild(label)
    overlay.appendChild(frame)
  }

  document.documentElement.appendChild(overlay)
  return overlayId
}

function removeSomOverlayInPage(overlayId) {
  if (!overlayId) {
    return false
  }

  const overlay = document.getElementById(overlayId)
  if (!overlay) {
    return false
  }

  overlay.remove()
  return true
}

async function normalizeCapturedScreenshot(dataUrl) {
  if (!dataUrl || typeof dataUrl !== 'string') {
    return null
  }

  try {
    const response = await fetch(dataUrl)
    const blob = await response.blob()
    const imageBitmap = await createImageBitmap(blob)

    const maxWidth = 1600
    const maxHeight = 1600
    const scale = Math.min(
      1,
      maxWidth / Math.max(imageBitmap.width, 1),
      maxHeight / Math.max(imageBitmap.height, 1),
    )
    const width = Math.max(32, Math.round(imageBitmap.width * scale))
    const height = Math.max(32, Math.round(imageBitmap.height * scale))

    const canvas = new OffscreenCanvas(width, height)
    const ctx = canvas.getContext('2d', { alpha: false })
    if (!ctx) {
      return dataUrl
    }

    ctx.drawImage(imageBitmap, 0, 0, width, height)
    const outputBlob = await canvas.convertToBlob({ type: 'image/jpeg', quality: 0.6 })

    return await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onloadend = () => resolve(reader.result || dataUrl)
      reader.onerror = () => reject(reader.error || new Error('Failed to read screenshot blob'))
      reader.readAsDataURL(outputBlob)
    })
  } catch (error) {
    return dataUrl
  }
}

async function performAgentAction(action) {
  const agentIdAttr = 'data-agent-id'
  const findScrollableContainer = () => {
    const candidates = Array.from(document.querySelectorAll('*')).filter((element) => {
      if (!(element instanceof HTMLElement)) {
        return false
      }

      const style = window.getComputedStyle(element)
      const overflowY = style.overflowY || ''
      if (!['auto', 'scroll', 'overlay'].some((value) => overflowY.includes(value))) {
        return false
      }

      const rect = element.getBoundingClientRect()
      if (rect.width < 40 || rect.height < 40) {
        return false
      }

      const inViewport =
        rect.bottom > 0 &&
        rect.right > 0 &&
        rect.top < window.innerHeight &&
        rect.left < window.innerWidth
      if (!inViewport) {
        return false
      }

      return element.scrollHeight > element.clientHeight + 8
    })

    const best = candidates
      .map((element) => ({
        element,
        area: element.clientWidth * element.clientHeight,
      }))
      .sort((a, b) => b.area - a.area)[0]

    return best?.element || document.scrollingElement || document.documentElement
  }

  const dispatchMouseSequence = (element) => {
    const rect = element.getBoundingClientRect()
    const clientX = Math.round(rect.left + Math.min(rect.width / 2, Math.max(rect.width - 1, 1)))
    const clientY = Math.round(rect.top + Math.min(rect.height / 2, Math.max(rect.height - 1, 1)))
    const eventInit = {
      bubbles: true,
      cancelable: true,
      composed: true,
      clientX,
      clientY,
      view: window,
    }

    element.dispatchEvent(new MouseEvent('mouseover', eventInit))
    element.dispatchEvent(new MouseEvent('mouseenter', eventInit))
    element.dispatchEvent(new MouseEvent('mousedown', eventInit))
    element.dispatchEvent(new MouseEvent('mouseup', eventInit))
    element.dispatchEvent(new MouseEvent('click', eventInit))
  }

  const actionType = String(action?.action_type || '').toUpperCase()
  const targetId = action?.target_id ? String(action.target_id) : null
  const actionValue = action?.action_value != null ? String(action.action_value) : null

  if (actionType === 'WAIT') {
    const waitMs = Number.parseInt(actionValue || '0', 10)
    await new Promise((resolve) => window.setTimeout(resolve, waitMs))
    return {
      success: true,
      status: 'Success',
      action_type: actionType,
      target_id: null,
    }
  }

  if (actionType === 'SCROLL') {
    const container = findScrollableContainer()
    const beforeTop = container.scrollTop
    const deltaBase = Math.max(container.clientHeight * 0.8, 240)
    const delta = actionValue === 'up' ? -deltaBase : deltaBase

    if (container === document.scrollingElement || container === document.documentElement || container === document.body) {
      window.scrollBy({ top: delta, left: 0, behavior: 'smooth' })
    } else {
      container.scrollBy({ top: delta, left: 0, behavior: 'smooth' })
    }

    await new Promise((resolve) => window.setTimeout(resolve, 350))
    const afterTop = container.scrollTop
    const detailBase = `Scrolled ${actionValue || 'down'} in ${container === document.scrollingElement || container === document.documentElement || container === document.body ? 'document' : 'container'}`
    const reachedBottom = Math.abs(afterTop - beforeTop) < 5

    return {
      success: true,
      status: 'Success',
      action_type: actionType,
      target_id: null,
      detail: reachedBottom
        ? `${detailBase} [System Warning: Reached the bottom of the scroll container. DO NOT SCROLL ANYMORE.]`
        : detailBase,
    }
  }

  if (actionType === 'FINISH') {
    return {
      success: true,
      status: 'Success',
      action_type: actionType,
      target_id: null,
    }
  }

  if (!targetId) {
    return {
      success: false,
      status: 'Error',
      action_type: actionType,
      target_id: null,
      error: 'Missing target_id',
    }
  }

  const element = document.querySelector(`[${agentIdAttr}="${CSS.escape(targetId)}"]`)
  if (!element) {
    return {
      success: false,
      status: 'ElementNotFound',
      action_type: actionType,
      target_id: targetId,
      error: `Element ${targetId} not found`,
    }
  }

  try {
    if (actionType === 'CLICK') {
      element.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' })
      dispatchMouseSequence(element)
      return {
        success: true,
        status: 'Success',
        action_type: actionType,
        target_id: targetId,
      }
    }

    if (actionType === 'TYPE') {
      if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)) {
        return {
          success: false,
          status: 'Error',
          action_type: actionType,
          target_id: targetId,
          error: `Element ${targetId} is not a text input`,
        }
      }

      element.focus()
      element.value = ''
      element.dispatchEvent(new InputEvent('input', { bubbles: true, data: null, inputType: 'deleteContentBackward' }))

      for (const char of actionValue || '') {
        element.value += char
        element.dispatchEvent(new InputEvent('input', { bubbles: true, data: char, inputType: 'insertText' }))
      }

      element.dispatchEvent(new Event('change', { bubbles: true }))
      return {
        success: true,
        status: 'Success',
        action_type: actionType,
        target_id: targetId,
      }
    }

    return {
      success: false,
      status: 'Error',
      action_type: actionType,
      target_id: targetId,
      error: `Unsupported action type: ${actionType}`,
    }
  } catch (error) {
    return {
      success: false,
      status: 'Error',
      action_type: actionType,
      target_id: targetId,
      error: error instanceof Error ? error.message : String(error),
    }
  }
}

function normalizeTabs(tabs) {
  return tabs
    .filter((tab) => typeof tab.id === 'number' && typeof tab.windowId === 'number' && tab.url)
    .map((tab) => ({
      tab_id: tab.id,
      window_id: tab.windowId,
      title: tab.title || '',
      url: tab.url || '',
      active: Boolean(tab.active),
      fav_icon_url: tab.favIconUrl || null,
    }))
}

function safeRespond(sendResponse, payload) {
  try {
    sendResponse(payload)
  } catch (error) {
    console.error('[LightClaw Bridge] Failed to send response:', error)
  }
}

function queryAvailableTabs(sendResponse) {
  try {
    chrome.tabs.query({ url: ['http://*/*', 'https://*/*'] }, (tabs) => {
      if (chrome.runtime.lastError) {
        safeRespond(sendResponse, {
          ok: false,
          error: chrome.runtime.lastError.message,
        })
        return
      }

      safeRespond(sendResponse, {
        ok: true,
        payload: normalizeTabs(tabs),
      })
    })
  } catch (error) {
    safeRespond(sendResponse, {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    })
  }
}

function focusTab(message, sendResponse) {
  const tabId = typeof message.tabId === 'number' ? message.tabId : null
  const windowId = typeof message.windowId === 'number' ? message.windowId : null

  if (tabId === null || windowId === null) {
    safeRespond(sendResponse, {
      ok: false,
      error: 'Missing tabId or windowId.',
    })
    return
  }

  Promise.resolve()
    .then(async () => {
      await chrome.windows.update(windowId, { focused: true })
      const tab = await chrome.tabs.update(tabId, { active: true })
      return normalizeSingleTab(tab)
    })
    .then((focusedTab) => {
      safeRespond(sendResponse, {
        ok: true,
        payload: focusedTab,
      })
    })
    .catch((error) => {
      safeRespond(sendResponse, {
        ok: false,
        error: error instanceof Error ? error.message : String(error),
      })
    })
}

function normalizeSingleTab(tab) {
  if (!tab || typeof tab.id !== 'number' || typeof tab.windowId !== 'number' || !tab.url) {
    return null
  }

  return {
    tab_id: tab.id,
    window_id: tab.windowId,
    title: tab.title || '',
    url: tab.url || '',
    active: Boolean(tab.active),
    fav_icon_url: tab.favIconUrl || null,
    status: tab.status || null,
    discarded: Boolean(tab.discarded),
    frozen: typeof tab.frozen === 'boolean' ? tab.frozen : null,
    incognito: Boolean(tab.incognito),
  }
}

function buildOriginPattern(urlString) {
  try {
    const url = new URL(urlString)
    if (!['http:', 'https:'].includes(url.protocol)) {
      return null
    }
    return `${url.protocol}//${url.host}/*`
  } catch {
    return null
  }
}

function checkOriginPermission(originPattern) {
  return new Promise((resolve) => {
    if (!originPattern) {
      resolve(null)
      return
    }

    try {
      chrome.permissions.contains({ origins: [originPattern] }, (granted) => {
        if (chrome.runtime.lastError) {
          resolve(`permissions.contains error: ${chrome.runtime.lastError.message}`)
          return
        }
        resolve(Boolean(granted))
      })
    } catch (error) {
      resolve(`permissions.contains threw: ${error instanceof Error ? error.message : String(error)}`)
    }
  })
}

async function buildScriptingFailureDetails(tab, rawError) {
  const message = String(rawError || '')
  const originPattern = buildOriginPattern(tab?.url)
  const permissionState = await checkOriginPermission(originPattern)

  return [
    `executeScript failed: ${message}`,
    `tab_id=${tab?.tab_id ?? 'unknown'}`,
    `url=${tab?.url || 'unknown'}`,
    `title=${tab?.title || 'unknown'}`,
    `status=${tab?.status ?? 'unknown'}`,
    `discarded=${String(tab?.discarded ?? 'unknown')}`,
    `frozen=${String(tab?.frozen ?? 'unknown')}`,
    `incognito=${String(tab?.incognito ?? 'unknown')}`,
    `origin_permission=${String(permissionState)}`,
    originPattern ? `origin_pattern=${originPattern}` : null,
  ]
    .filter(Boolean)
    .join(' | ')
}

function waitForTabComplete(tabId, timeoutMs = 2000) {
  return new Promise((resolve) => {
    let settled = false
    let timeoutId = null

    const cleanup = () => {
      if (settled) return
      settled = true
      if (timeoutId) {
        clearTimeout(timeoutId)
      }
      chrome.tabs.onUpdated.removeListener(handleUpdated)
      resolve()
    }

    const handleUpdated = (updatedTabId, changeInfo) => {
      if (updatedTabId !== tabId) return
      if (changeInfo.status === 'complete') {
        cleanup()
      }
    }

    chrome.tabs.onUpdated.addListener(handleUpdated)
    timeoutId = setTimeout(cleanup, timeoutMs)
  })
}

function getTabById(tabId) {
  return new Promise((resolve, reject) => {
    try {
      chrome.tabs.get(tabId, (tab) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message))
          return
        }
        resolve(tab)
      })
    } catch (error) {
      reject(error)
    }
  })
}

async function focusAndWakeTab(tab) {
  if (!tab?.tab_id || !tab?.window_id) {
    return tab
  }

  try {
    await chrome.windows.update(tab.window_id, { focused: true })
  } catch {
  }

  try {
    await chrome.tabs.update(tab.tab_id, { active: true })
  } catch {
  }

  let latestTab = null
  try {
    latestTab = await getTabById(tab.tab_id)
  } catch {
    return tab
  }

  const isDiscarded = Boolean(latestTab?.discarded)
  const isUnloaded = latestTab?.status === 'unloaded'

  if (isDiscarded || isUnloaded) {
    try {
      await chrome.tabs.reload(tab.tab_id)
    } catch {
    }
  }

  await waitForTabComplete(tab.tab_id, 4000)

  try {
    latestTab = await getTabById(tab.tab_id)
  } catch {
    return tab
  }

  return normalizeSingleTab(latestTab) || tab
}

function withActiveTab(message, sendResponse, handler) {
  const requestedTabId = typeof message.tabId === 'number' ? message.tabId : null

  if (requestedTabId !== null) {
    try {
      chrome.tabs.get(requestedTabId, (tab) => {
        if (chrome.runtime.lastError) {
          safeRespond(sendResponse, {
            ok: false,
            error: chrome.runtime.lastError.message,
          })
          return
        }

        const selectedTab = normalizeSingleTab(tab)
        if (!selectedTab) {
          safeRespond(sendResponse, {
            ok: false,
            error: `Tab ${requestedTabId} is unavailable or not a regular web page.`,
          })
          return
        }

        Promise.resolve()
          .then(() => handler(selectedTab))
          .catch((error) => {
            safeRespond(sendResponse, {
              ok: false,
              error: error instanceof Error ? error.message : String(error),
            })
          })
      })
    } catch (error) {
      safeRespond(sendResponse, {
        ok: false,
        error: error instanceof Error ? error.message : String(error),
      })
    }
    return
  }

  try {
    chrome.tabs.query({ currentWindow: true }, (tabs) => {
      if (chrome.runtime.lastError) {
        safeRespond(sendResponse, {
          ok: false,
          error: chrome.runtime.lastError.message,
        })
        return
      }

      const normalizedTabs = normalizeTabs(tabs)
      const selectedTab =
        normalizedTabs.find((tab) => tab.tab_id === requestedTabId) ||
        normalizedTabs.find((tab) => tab.active) ||
        normalizedTabs[0]

      if (!selectedTab) {
        safeRespond(sendResponse, {
          ok: false,
          error: 'No active tab is available.',
        })
        return
      }

      Promise.resolve()
        .then(() => handler(selectedTab))
        .catch((error) => {
          safeRespond(sendResponse, {
            ok: false,
            error: error instanceof Error ? error.message : String(error),
          })
        })
    })
  } catch (error) {
    safeRespond(sendResponse, {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    })
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  try {
    if (!message || !message.type) {
      return false
    }

    if (message.type === 'LIGHTCLAW_EXTENSION_HEALTH') {
      safeRespond(sendResponse, {
        ok: true,
        payload: {
          extension_version: chrome.runtime.getManifest().version,
          runtime_available: true,
          browser_family: 'chromium',
          permissions: ['tabs', 'scripting', 'activeTab'],
        },
      })
      return false
    }

    if (message.type === 'LIGHTCLAW_GET_TABS') {
      queryAvailableTabs(sendResponse)
      return true
    }

    if (message.type === 'LIGHTCLAW_FOCUS_TAB') {
      focusTab(message, sendResponse)
      return true
    }

    if (message.type === 'LIGHTCLAW_GUI_OBSERVE') {
      withActiveTab(message, sendResponse, async (selectedTab) => {
        selectedTab = await focusAndWakeTab(selectedTab)
        const runObserve = (isRetry = false) => {
          chrome.scripting.executeScript(
            {
              target: { tabId: selectedTab.tab_id },
              func: buildInteractiveTreeInPage,
            },
            async (results) => {
              if (chrome.runtime.lastError) {
                if (!isRetry) {
                  await waitForTabComplete(selectedTab.tab_id)
                  runObserve(true)
                  return
                }

                safeRespond(sendResponse, {
                  ok: false,
                  error: await buildScriptingFailureDetails(selectedTab, chrome.runtime.lastError.message),
                })
                return
              }

              const observation = results?.[0]?.result
              if (!observation || !observation.nodes || !observation.metadata) {
                safeRespond(sendResponse, {
                  ok: false,
                  error: `No valid observation was returned from tab ${selectedTab.tab_id}.`,
                })
                return
              }

              let overlayId = null
              try {
                const overlayResults = await chrome.scripting.executeScript({
                  target: { tabId: selectedTab.tab_id },
                  func: drawSomOverlayInPage,
                  args: [observation.nodes],
                })
                overlayId = overlayResults?.[0]?.result || null

                const screenshotBase64 = await new Promise((resolve, reject) => {
                  chrome.tabs.captureVisibleTab(
                    selectedTab.window_id,
                    { format: 'jpeg', quality: 70 },
                    (dataUrl) => {
                      if (chrome.runtime.lastError) {
                        reject(new Error(chrome.runtime.lastError.message))
                        return
                      }
                      resolve(dataUrl || null)
                    },
                  )
                })
                const normalizedScreenshot = await normalizeCapturedScreenshot(screenshotBase64)

                safeRespond(sendResponse, {
                  ok: true,
                  payload: {
                    tab: selectedTab,
                    observation: {
                      ...observation,
                      screenshot_base64: normalizedScreenshot,
                    },
                  },
                })
              } catch (error) {
                safeRespond(sendResponse, {
                  ok: false,
                  error: error instanceof Error ? error.message : String(error),
                })
              } finally {
                if (overlayId) {
                  try {
                    await chrome.scripting.executeScript({
                      target: { tabId: selectedTab.tab_id },
                      func: removeSomOverlayInPage,
                      args: [overlayId],
                    })
                  } catch {
                  }
                }
              }
            }
          )
        }

        runObserve(false)
      })
      return true
    }

    if (message.type === 'LIGHTCLAW_GUI_ACTION') {
      withActiveTab(message, sendResponse, async (selectedTab) => {
        selectedTab = await focusAndWakeTab(selectedTab)
        const runAction = (isRetry = false) => {
          chrome.scripting.executeScript(
            {
              target: { tabId: selectedTab.tab_id },
              func: performAgentAction,
              args: [message.action],
            },
            async (results) => {
              if (chrome.runtime.lastError) {
                if (!isRetry) {
                  await waitForTabComplete(selectedTab.tab_id)
                  runAction(true)
                  return
                }

                safeRespond(sendResponse, {
                  ok: false,
                  error: await buildScriptingFailureDetails(selectedTab, chrome.runtime.lastError.message),
                })
                return
              }

              safeRespond(sendResponse, {
                ok: true,
                payload: {
                  tab: selectedTab,
                  result: results?.[0]?.result,
                },
              })
            }
          )
        }

        runAction(false)
      })
      return true
    }

    return false
  } catch (error) {
    console.error('[LightClaw Bridge] Unhandled background listener error:', error)
    safeRespond(sendResponse, {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    })
    return false
  }
})
