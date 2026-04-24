export type AgentElementRole =
  | 'link'
  | 'button'
  | 'input'
  | 'textarea'
  | 'select'
  | 'checkbox'
  | 'radio'
  | 'tab'
  | 'menuitem'
  | 'generic'

export interface ViewportMetadata {
  url: string
  title: string
  viewport_width: number
  viewport_height: number
  scroll_x: number
  scroll_y: number
  timestamp: string
}

export interface InteractiveNode {
  agent_id: string
  tag: string
  role: AgentElementRole
  text: string
  aria_label?: string
  placeholder?: string
  href?: string
  value?: string
  disabled: boolean
  checked?: boolean
  rect: {
    x: number
    y: number
    width: number
    height: number
  }
  context_text?: string
}

export interface InteractiveTreeObservation {
  metadata: ViewportMetadata
  nodes: InteractiveNode[]
  som_text: string
  screenshot_base64?: string
}

const AGENT_ID_ATTR = 'data-agent-id'
const INTERACTIVE_SELECTOR = [
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

function isProbablyInteractive(element: HTMLElement): boolean {
  if (element.matches(INTERACTIVE_SELECTOR)) {
    return true
  }

  const style = window.getComputedStyle(element)
  if (style.cursor === 'pointer') {
    return true
  }

  const role = (element.getAttribute('role') || '').toLowerCase()
  return ['button', 'link', 'tab', 'menuitem'].includes(role)
}

function isVisible(element: HTMLElement): boolean {
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

function deriveRole(element: HTMLElement): AgentElementRole {
  const explicitRole = (element.getAttribute('role') || '').toLowerCase()
  if (explicitRole === 'button') return 'button'
  if (explicitRole === 'link') return 'link'
  if (explicitRole === 'tab') return 'tab'
  if (explicitRole === 'menuitem') return 'menuitem'

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

function normalizeText(value: string | null | undefined): string {
  return (value || '').replace(/\s+/g, ' ').trim()
}

function extractOwnText(element: HTMLElement): string {
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

function extractContextText(element: HTMLElement): string {
  const candidates = [
    element.closest('label'),
    element.closest('[aria-labelledby]'),
    element.parentElement,
    element.previousElementSibling,
  ].filter(Boolean) as HTMLElement[]

  for (const candidate of candidates) {
    const text = normalizeText(candidate.innerText)
    if (text && text !== extractOwnText(element)) {
      return text.slice(0, 200)
    }
  }

  return ''
}

function ensureAgentId(element: HTMLElement, index: number): string {
  const existing = element.getAttribute(AGENT_ID_ATTR)
  if (existing) {
    return existing
  }

  const id = `agent-${index + 1}`
  element.setAttribute(AGENT_ID_ATTR, id)
  return id
}

function extractStaticTextSnippets(elements: HTMLElement[]): string[] {
  const textTags = new Set(['div', 'span', 'p', 'td', 'th', 'li', 'h1', 'h2', 'h3', 'h4', 'strong'])
  const snippets: string[] = []
  const seen = new Set<string>()

  for (const element of elements) {
    const tag = element.tagName.toLowerCase()
    if (!textTags.has(tag)) {
      continue
    }

    if (element.matches(INTERACTIVE_SELECTOR) || element.closest(`[${AGENT_ID_ATTR}]`)) {
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

function shouldKeepNode(node: InteractiveNode): boolean {
  if (node.disabled) {
    return false
  }

  if (!node.text && !node.aria_label && !node.placeholder && node.role !== 'input') {
    return false
  }

  return true
}

export function buildInteractiveTree(root: ParentNode = document): InteractiveTreeObservation {
  const metadata: ViewportMetadata = {
    url: window.location.href,
    title: document.title,
    viewport_width: window.innerWidth,
    viewport_height: window.innerHeight,
    scroll_x: window.scrollX,
    scroll_y: window.scrollY,
    timestamp: new Date().toISOString(),
  }

  const rawElements = Array.from(root.querySelectorAll<HTMLElement>('body *'))
  const interactiveElements = rawElements.filter((element) => {
    if (!isProbablyInteractive(element)) {
      return false
    }
    return isVisible(element)
  })

  const nodes = interactiveElements
    .map((element, index): InteractiveNode => {
      const rect = element.getBoundingClientRect()
      const tag = element.tagName.toLowerCase()
      const role = deriveRole(element)
      const text = extractOwnText(element)
      const agentId = ensureAgentId(element, index)

      return {
        agent_id: agentId,
        tag,
        role,
        text,
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
        rect: {
          x: Math.round(rect.left),
          y: Math.round(rect.top),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        },
        context_text: extractContextText(element) || undefined,
      }
    })
    .filter(shouldKeepNode)

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
    metadata,
    nodes,
    som_text: somText,
  }
}
