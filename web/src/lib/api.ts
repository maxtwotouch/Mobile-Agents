import { token, clearAuth } from './stores.svelte'

const API = '/api'

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string> || {}),
  }
  if (token.value) headers['Authorization'] = `Bearer ${token.value}`

  const res = await fetch(API + path, { ...opts, headers })

  if (res.status === 401) {
    clearAuth()
    throw new Error('Session expired')
  }
  if (!res.ok) {
    const text = await res.text()
    let msg = text
    try { msg = JSON.parse(text).detail || text } catch {}
    throw new Error(msg)
  }
  return res.json()
}

// --- Auth ---

export async function login(username: string, password: string): Promise<string> {
  const res = await fetch(API + '/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) throw new Error('Wrong username or password')
  const data = await res.json()
  return data.access_token
}

export async function checkAuthStatus(): Promise<boolean> {
  try {
    const res = await fetch(API + '/auth/status')
    const data = await res.json()
    return data.auth_disabled === true
  } catch {
    return false
  }
}

// --- Roles ---

export interface Role {
  id: number
  name: string
  description: string
  can_spawn: string[] | null
}

export async function fetchRoles(): Promise<Role[]> {
  return api('/roles')
}

// --- Repos ---

export interface Repo {
  name: string
  path: string
  remote_url: string
  default_branch: string
  last_commit?: string
}

export async function fetchRepos(): Promise<Repo[]> {
  return api('/repos')
}

export async function cloneRepo(url: string): Promise<Repo> {
  return api('/repos', { method: 'POST', body: JSON.stringify({ url }) })
}

// --- Tasks ---

export interface Task {
  id: number
  title: string
  description: string
  repo_url: string
  branch: string | null
  base_branch: string | null
  agent_type: string
  status: string
  tmux_session: string | null
  codex_session_id: string | null
  worktree_path: string | null
  role_id: number | null
  role_name: string | null
  parent_task_id: number | null
  created_at: string
  updated_at: string
}

export interface TaskCreate {
  title: string
  description: string
  repo_url: string
  branch?: string | null
  agent_type: string
  role_id?: number | null
}

export async function fetchTasks(status?: string): Promise<Task[]> {
  const q = status ? `?status=${status}` : ''
  return api('/tasks' + q)
}

export async function fetchTask(id: number): Promise<Task> {
  return api(`/tasks/${id}`)
}

export async function createTask(body: TaskCreate): Promise<Task> {
  return api('/tasks', { method: 'POST', body: JSON.stringify(body) })
}

export async function patchTask(id: number, body: Record<string, any>): Promise<Task> {
  return api(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
}

export async function startTask(id: number, prompt?: string): Promise<Task> {
  return api(`/tasks/${id}/start`, {
    method: 'POST',
    body: JSON.stringify(prompt ? { prompt } : {}),
  })
}

export async function stopTask(id: number): Promise<Task> {
  return api(`/tasks/${id}/stop`, { method: 'POST' })
}

export async function getOutput(id: number, lines = 80) {
  return api<{ task_id: number; alive: boolean; output: string }>(`/tasks/${id}/output?lines=${lines}`)
}

export async function pushTask(id: number, approve: boolean): Promise<Task> {
  return api(`/tasks/${id}/push`, { method: 'POST', body: JSON.stringify({ approve }) })
}

export async function getDiff(id: number) {
  return api<{ task_id: number; branch: string; base: string; diff: string; stats: any }>(`/tasks/${id}/diff`)
}

export async function getFileDiff(id: number, filePath: string) {
  return api<{ file: string; diff: string }>(`/tasks/${id}/diff/${encodeURIComponent(filePath)}`)
}

export async function getCommits(id: number) {
  return api<any[]>(`/tasks/${id}/commits`)
}

// --- Updates ---

export interface Update {
  id: number
  task_id: number
  type: string
  content: string
  commit_sha: string | null
  branch: string | null
  created_at: string
}

export async function fetchUpdates(taskId: number): Promise<Update[]> {
  return api(`/tasks/${taskId}/updates`)
}

// --- Messages ---

export interface Message {
  id: number
  task_id: number
  direction: string
  content: string
  created_at: string
}

export async function fetchMessages(taskId: number): Promise<Message[]> {
  return api(`/tasks/${taskId}/messages`)
}

export async function sendMessage(taskId: number, content: string): Promise<Message> {
  return api(`/tasks/${taskId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}
