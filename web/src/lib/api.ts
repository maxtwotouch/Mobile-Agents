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
  branches: string[]
  last_commit?: string
}

export async function fetchRepos(): Promise<Repo[]> {
  return api('/repos')
}

export async function cloneRepo(url: string): Promise<Repo> {
  return api('/repos', { method: 'POST', body: JSON.stringify({ url }) })
}

// --- Objectives ---

export interface Objective {
  id: number
  title: string
  description: string
  repo_url: string | null
  created_by: string | null
  priority: string
  objective_state: string
  summary: string | null
  recommended_next_action: string | null
  created_at: string
  updated_at: string
}

export interface ObjectiveCreate {
  title: string
  description?: string
  repo_url?: string | null
  priority?: string
  agent_type?: string
}

export async function fetchObjectives(): Promise<Objective[]> {
  return api('/objectives')
}

export async function fetchObjective(id: number): Promise<Objective> {
  return api(`/objectives/${id}`)
}

export async function createObjective(body: ObjectiveCreate): Promise<Objective> {
  return api('/objectives', { method: 'POST', body: JSON.stringify(body) })
}

// --- Tasks ---

export interface Task {
  id: number
  objective_id: number | null
  title: string
  description: string
  repo_url: string
  branch: string | null
  base_branch: string | null
  agent_type: string
  task_kind: string
  target_type: string
  priority: string
  status: string
  workflow_state: string
  workflow_status: string
  runtime_state: string
  runtime_status: string
  commit_start: string | null
  commit_end: string | null
  path_scope: string | null
  active_run_id: number | null
  blocked_reason: string | null
  result_summary: string | null
  failure_reason: string | null
  next_action_hint: string | null
  thread_id: string | null
  runner_id: string | null
  codex_session_id: string | null
  worktree_path: string | null
  last_run_started_at: string | null
  last_run_finished_at: string | null
  last_heartbeat_at: string | null
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
  objective_id?: number | null
  branch?: string | null
  base_branch?: string | null
  agent_type: string
  role_id?: number | null
  task_kind?: string | null
  target_type?: string | null
  priority?: string
  commit_start?: string | null
  commit_end?: string | null
  path_scope?: string | null
}

export async function fetchTasks(status?: string, objectiveId?: number): Promise<Task[]> {
  const search = new URLSearchParams()
  if (status) search.set('status', status)
  if (objectiveId !== undefined) search.set('objective_id', String(objectiveId))
  const q = search.toString()
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
  return api<{ task_id: number; alive: boolean; ended: boolean; output: string }>(`/tasks/${id}/output?lines=${lines}`)
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

export interface Run {
  id: number
  task_id: number
  thread_id: string | null
  runner_id: string
  provider: string | null
  trigger_type: string
  run_state: string
  status: string
  prompt: string | null
  dispatch_snapshot: string | null
  prompt_summary: string | null
  exit_code: number | null
  error_type: string | null
  error: string | null
  output_summary: string | null
  raw_output_ref: string | null
  started_at: string
  finished_at: string | null
}

export async function fetchRuns(taskId: number): Promise<Run[]> {
  return api(`/tasks/${taskId}/runs`)
}

// --- Decisions ---

export interface Decision {
  id: number
  objective_id: number | null
  task_id: number | null
  decision_type: string
  decision_state: string
  question: string
  options: string[] | null
  recommended_option: string | null
  chosen_option: string | null
  answered_by: string | null
  answered_at: string | null
  created_at: string
}

export async function fetchDecisions(params: { objective_id?: number; task_id?: number } = {}): Promise<Decision[]> {
  const search = new URLSearchParams()
  if (params.objective_id !== undefined) search.set('objective_id', String(params.objective_id))
  if (params.task_id !== undefined) search.set('task_id', String(params.task_id))
  const q = search.toString()
  return api(`/decisions${q ? `?${q}` : ''}`)
}

export async function answerDecision(id: number, chosen_option: string): Promise<Decision> {
  return api(`/decisions/${id}/answer`, {
    method: 'POST',
    body: JSON.stringify({ chosen_option }),
  })
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
