import { token, wsConnected, showToast } from './stores.svelte'

let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null

type WsHandler = (data: any) => void
const handlers: WsHandler[] = []

export function onWsMessage(handler: WsHandler) {
  handlers.push(handler)
  return () => {
    const i = handlers.indexOf(handler)
    if (i >= 0) handlers.splice(i, 1)
  }
}

export function connectWS() {
  if (ws) ws.close()
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${proto}//${location.host}/ws`)

  ws.onopen = () => {
    if (token.value) ws!.send(token.value)
    wsConnected.value = true
  }

  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (data.type === 'authenticated') return
      handlers.forEach(h => h(data))
    } catch {}
  }

  ws.onclose = () => {
    wsConnected.value = false
    if (token.value) {
      reconnectTimer = setTimeout(connectWS, 3000)
    }
  }
}

export function disconnectWS() {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  if (ws) ws.close()
  ws = null
  wsConnected.value = false
}
