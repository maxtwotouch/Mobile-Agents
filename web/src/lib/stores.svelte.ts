import type { Task, Role } from './api'

// --- Auth ---
export const token = $state<{ value: string | null }>({ value: localStorage.getItem('ma_token') })
export function isAuthed() { return !!token.value }

export function setAuth(t: string) {
  token.value = t
  localStorage.setItem('ma_token', t)
}

export function clearAuth() {
  token.value = null
  localStorage.removeItem('ma_token')
}

// --- App state ---
export const tasks = $state<{ list: Task[] }>({ list: [] })
export const roles = $state<{ list: Role[] }>({ list: [] })
export const wsConnected = $state<{ value: boolean }>({ value: false })
export const toastMsg = $state<{ value: string; visible: boolean }>({ value: '', visible: false })

let toastTimer: ReturnType<typeof setTimeout> | null = null
export function showToast(msg: string) {
  toastMsg.value = msg
  toastMsg.visible = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastMsg.visible = false }, 4000)
}

// --- Navigation ---
export type View = 'login' | 'dashboard' | 'create' | 'detail'
export const nav = $state<{ view: View; taskId: number | null }>({ view: 'login', taskId: null })

export function navigate(view: View, taskId?: number) {
  nav.view = view
  nav.taskId = taskId ?? null
}
