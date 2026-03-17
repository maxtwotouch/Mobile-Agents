export function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return 'now'
  const m = Math.floor(s / 60)
  if (m < 60) return m + 'm'
  const h = Math.floor(m / 60)
  if (h < 24) return h + 'h'
  return Math.floor(h / 24) + 'd'
}

export function repoShortName(path: string): string {
  if (!path) return ''
  return path.split('/').pop() || ''
}

export function threadState(task: { runtime_status: string; thread_id?: string | null }) {
  if (task.runtime_status === 'running') {
    return { label: 'Running', tone: 'running' as const }
  }
  if (task.thread_id) {
    return { label: 'Idle thread', tone: 'idle' as const }
  }
  return { label: 'No thread yet', tone: 'empty' as const }
}

export function colorDiff(diff: string): string {
  return diff.split('\n').map(line => {
    const escaped = escapeHtml(line)
    if (line.startsWith('+') && !line.startsWith('+++')) return `<span class="d-add">${escaped}</span>`
    if (line.startsWith('-') && !line.startsWith('---')) return `<span class="d-del">${escaped}</span>`
    if (line.startsWith('@@') || line.startsWith('diff ') || line.startsWith('index ')) return `<span class="d-hdr">${escaped}</span>`
    return escaped
  }).join('\n')
}

export function escapeHtml(s: string): string {
  const d = document.createElement('div')
  d.textContent = s || ''
  return d.innerHTML
}

function formatInlineMarkdown(text: string): string {
  let html = escapeHtml(text)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a class="rt-link" href="$2">$1</a>')
  html = html.replace(/`([^`]+)`/g, '<code class="rt-code">$1</code>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  return html
}

export function renderRichText(text: string): string {
  const normalized = (text || '')
    .replace(/\r\n/g, '\n')
    .replace(/(\d+\.\s+\*\*Severity)/g, '\n$1')
    .replace(/(\*\*Summary\*\*)/g, '\n\n$1')
    .trim()

  if (!normalized) return ''

  const blocks = normalized.split(/\n\s*\n/)
  return blocks.map((block) => {
    const lines = block.split('\n').map((line) => line.trim()).filter(Boolean)
    if (lines.length === 0) return ''

    const ordered = lines.every((line) => /^\d+\.\s+/.test(line))
    if (ordered) {
      const items = lines.map((line) => {
        const item = line.replace(/^\d+\.\s+/, '')
        return `<li>${formatInlineMarkdown(item)}</li>`
      }).join('')
      return `<ol class="rt-list">${items}</ol>`
    }

    if (lines.length === 1 && /^\*\*[^*]+\*\*$/.test(lines[0])) {
      return `<h4 class="rt-heading">${formatInlineMarkdown(lines[0])}</h4>`
    }

    const content = lines.map((line) => formatInlineMarkdown(line)).join('<br>')
    return `<p class="rt-paragraph">${content}</p>`
  }).join('')
}
