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
