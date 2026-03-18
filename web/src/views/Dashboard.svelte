<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import { fetchObjectives, fetchTasks, fetchRoles } from '../lib/api'
  import { objectives, tasks, roles, navigate, clearAuth, showToast } from '../lib/stores.svelte'
  import { onWsMessage, disconnectWS } from '../lib/ws'
  import { roleVisuals } from '../lib/roles'
  import { timeAgo, repoShortName, threadState } from '../lib/utils'
  import RoleIcon from '../components/RoleIcon.svelte'
  import StatusBadge from '../components/StatusBadge.svelte'
  import ConnectionDot from '../components/ConnectionDot.svelte'

  let loading = $state(true)

  const running = $derived(tasks.list.filter(t => t.runtime_status === 'running').length)
  const review = $derived(tasks.list.filter(t => t.workflow_state === 'needs_review').length)
  const completed = $derived(tasks.list.filter(t => t.workflow_state === 'completed').length)
  const total = $derived(tasks.list.length)
  const openObjectives = $derived(objectives.list.filter(o => !['completed', 'failed', 'cancelled'].includes(o.objective_state)).length)

  const roleCounts = $derived(() => {
    const counts: Record<string, number> = {}
    for (const t of tasks.list) {
      const name = t.role_name || 'generic'
      counts[name] = (counts[name] || 0) + 1
    }
    return counts
  })

  async function load() {
    try {
      const [t, r, o] = await Promise.all([fetchTasks(), fetchRoles(), fetchObjectives()])
      tasks.list = t
      roles.list = r
      objectives.list = o
    } catch (e: any) {
      showToast(e.message)
    } finally {
      loading = false
    }
  }

  const unsub = onWsMessage((data) => {
    if (data.type === 'task_update') {
      const workflow = data.workflow_state ? `workflow ${data.workflow_state}` : data.workflow_status ? `workflow ${data.workflow_status}` : null
      const runtime = data.runtime_state ? `runtime ${data.runtime_state}` : data.runtime_status ? `runtime ${data.runtime_status}` : null
      showToast(`Task #${data.task_id} — ${workflow || runtime || data.message}`)
    } else if (data.type === 'task_created') {
      showToast(`Created: ${data.title}`)
    } else if (data.type === 'objective_created') {
      showToast(`Objective launched: ${data.title}`)
    } else if (data.type === 'decision_created') {
      showToast('Orchestrator needs input')
    }
    load()
  })

  onMount(load)
  onDestroy(unsub)

  function logout() {
    clearAuth()
    disconnectWS()
    navigate('login')
  }
</script>

<div class="dashboard">
  <header class="header">
    <div class="header-left">
      <h1 class="logo">agents</h1>
      <ConnectionDot />
    </div>
    <div class="header-right">
      <button class="btn btn-ghost" onclick={() => navigate('orchestrate')}>Objective</button>
      <button class="btn btn-ghost" onclick={logout}>Sign out</button>
      <button class="btn btn-accent" onclick={() => navigate('create')}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        New task
      </button>
    </div>
  </header>

  <div class="stats-strip">
    <div class="stat">
      <span class="stat-value" style="color: #8b4d2b;">{openObjectives}</span>
      <span class="stat-label">objectives</span>
    </div>
    <div class="stat-sep"></div>
    <div class="stat">
      <span class="stat-value" style="color: #6b9a5c;">{running}</span>
      <span class="stat-label">running</span>
    </div>
    <div class="stat-sep"></div>
    <div class="stat">
      <span class="stat-value" style="color: #c45c4a;">{review}</span>
      <span class="stat-label">review</span>
    </div>
    <div class="stat-sep"></div>
    <div class="stat">
      <span class="stat-value" style="color: #5c8ab0;">{completed}</span>
      <span class="stat-label">done</span>
    </div>
    <div class="stat-sep"></div>
    <div class="stat">
      <span class="stat-value">{total}</span>
      <span class="stat-label">total</span>
    </div>
  </div>

  <div class="mode-band">
    <button class="mode-card mode-card-objective" onclick={() => navigate('orchestrate')}>
      <div class="mode-kicker">Orchestration</div>
      <div class="mode-title">Launch an objective</div>
      <p>Give the system a broader goal. It can clarify requirements, spawn specialist agents, and keep coordinating the work.</p>
    </button>
    <button class="mode-card mode-card-task" onclick={() => navigate('create')}>
      <div class="mode-kicker">Direct Dispatch</div>
      <div class="mode-title">Create a single task</div>
      <p>Use this when you already know the branch, target, and role you want one agent to handle.</p>
    </button>
  </div>

  {#if objectives.list.length > 0}
    <div class="objective-section">
      <div class="section-head">
        <h2>Objectives</h2>
        <button class="text-link" onclick={() => navigate('orchestrate')}>New objective</button>
      </div>
      <div class="objective-list">
        {#each objectives.list as objective}
          <button class="objective-item" onclick={() => navigate('objective', objective.id)}>
            <div class="objective-copy">
              <div class="objective-title">{objective.title}</div>
              <div class="objective-meta">
                {objective.repo_url ? `${repoShortName(objective.repo_url)} · ` : ''}{objective.priority}
              </div>
              {#if objective.summary}
                <p>{objective.summary}</p>
              {/if}
            </div>
            <StatusBadge status={objective.objective_state} />
          </button>
        {/each}
      </div>
    </div>
  {/if}

  {#if roles.list.length > 0}
    <div class="role-strip">
      {#each roles.list as role}
        {@const visual = roleVisuals[role.name]}
        {@const count = roleCounts()[role.name] || 0}
        {#if visual}
          <div class="role-chip" style="border-color: {count > 0 ? visual.color : 'var(--border)'};">
            <RoleIcon name={role.name} size={14} />
            <span class="role-chip-label">{visual.label}</span>
            {#if count > 0}
              <span class="role-chip-count" style="color: {visual.color};">{count}</span>
            {/if}
          </div>
        {/if}
      {/each}
    </div>
  {/if}

  <div class="task-list">
    {#if loading}
      <p class="empty-text">Loading...</p>
    {:else if tasks.list.length === 0}
      <div class="empty-state">
        <div class="empty-icons">
          {#each Object.entries(roleVisuals) as [_, v]}
            <svg width="28" height="28" viewBox="0 0 24 24" fill={v.color} opacity="0.3"><path d={v.icon} /></svg>
          {/each}
        </div>
        <h2 class="empty-title">No direct tasks yet</h2>
        <p class="empty-desc">Start with an objective if you want the system to coordinate work, or create a direct task if you already know exactly what should run.</p>
      </div>
    {:else}
      <div class="section-head tasks-head">
        <h2>Direct Tasks</h2>
      </div>
      {#each tasks.list as task (task.id)}
        {@const visual = roleVisuals[task.role_name || ''] || null}
        {@const runtime = threadState(task)}
        <button class="task-item" onclick={() => navigate('detail', task.id)}>
          <div class="task-item-left">
            {#if visual}
              <div class="task-icon" style="background: {visual.color}15; border-color: {visual.color}30;">
                <RoleIcon name={task.role_name} size={18} />
              </div>
            {:else}
              <div class="task-icon task-icon-generic">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="var(--text-faint)"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
              </div>
            {/if}
            <div class="task-info">
              <span class="task-title">{task.title}</span>
              <span class="task-meta">
                {task.agent_type}{task.role_name ? ` · ${task.role_name}` : ''}
                · {repoShortName(task.repo_url)}
                {task.branch ? ` · ${task.branch}` : ''}
                · {timeAgo(task.created_at)}
              </span>
              <span class="runtime-chip rc-{runtime.tone}">{runtime.label}</span>
            </div>
          </div>
          <StatusBadge status={task.workflow_state} />
        </button>
      {/each}
    {/if}
  </div>
</div>

<style>
  .dashboard {
    max-width: 860px;
    margin: 0 auto;
    padding: 0 20px 44px;
  }

  .header {
    padding: 20px 0 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .header-left, .header-right {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .logo {
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: clamp(1.6rem, 5vw, 2rem);
    font-weight: 400;
    font-style: italic;
    letter-spacing: -0.02em;
    color: var(--text);
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    border: 1px solid var(--border-light);
    border-radius: 4px;
    background: transparent;
    color: var(--text);
    font-family: var(--sans);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
  }
  .btn:hover { background: var(--bg-raised); }

  .btn-accent {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
  }

  .btn-ghost {
    border: none;
    color: var(--text-dim);
    padding-inline: 10px;
  }

  .stats-strip {
    display: flex;
    align-items: center;
    padding: 14px 0;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
  }

  .stat {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }

  .stat-value {
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.02em;
  }

  .stat-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-faint);
  }

  .stat-sep {
    width: 1px;
    height: 28px;
    background: var(--border);
  }

  .mode-band {
    display: grid;
    grid-template-columns: 1.1fr 0.9fr;
    gap: 12px;
    padding: 18px 0 10px;
  }

  .mode-card {
    text-align: left;
    padding: 18px;
    border-radius: 18px;
    border: 1px solid var(--border);
    background: none;
    color: var(--text);
    cursor: pointer;
  }

  .mode-card-objective {
    background: linear-gradient(135deg, color-mix(in oklch, var(--bg-raised), #b66a42 14%), color-mix(in oklch, var(--bg), #8b4d2b 2%));
    border-color: color-mix(in oklch, var(--border), #b66a42 32%);
  }

  .mode-card-task {
    background: linear-gradient(180deg, var(--bg-raised), color-mix(in oklch, var(--bg), white 2%));
  }

  .mode-kicker {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--text-faint);
  }

  .mode-title {
    margin-top: 8px;
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: 1.55rem;
  }

  .mode-card p {
    margin: 10px 0 0;
    color: var(--text-dim);
    line-height: 1.55;
    max-width: 36ch;
  }

  .section-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }

  .section-head h2 {
    margin: 0;
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: 1.45rem;
    font-weight: 400;
  }

  .text-link {
    border: none;
    background: none;
    color: var(--text-dim);
    cursor: pointer;
    font: inherit;
  }

  .objective-section {
    padding-top: 8px;
  }

  .objective-list {
    display: grid;
    gap: 10px;
    margin-bottom: 8px;
  }

  .objective-item {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: start;
    gap: 14px;
    padding: 15px 0;
    border: none;
    border-bottom: 1px solid var(--border);
    background: none;
    color: var(--text);
    text-align: left;
    cursor: pointer;
  }

  .objective-title {
    font-size: 1rem;
    font-weight: 600;
  }

  .objective-meta {
    margin-top: 4px;
    font-size: 12px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-faint);
  }

  .objective-copy p {
    margin: 8px 0 0;
    color: var(--text-dim);
    line-height: 1.5;
  }

  .role-strip {
    display: flex;
    gap: 6px;
    padding: 12px 0;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .role-strip::-webkit-scrollbar { display: none; }

  .role-chip {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 5px 10px;
    border: 1px solid var(--border);
    border-radius: 20px;
    font-size: 11px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .role-chip-label { color: var(--text-dim); }
  .role-chip-count { font-weight: 600; }

  .task-list {
    padding-top: 6px;
  }

  .tasks-head {
    margin-top: 10px;
  }

  .task-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    padding: 14px 0;
    border: none;
    border-bottom: 1px solid var(--border);
    background: none;
    cursor: pointer;
    text-align: left;
    color: var(--text);
  }
  .task-item:first-of-type { border-top: 1px solid var(--border); }

  .task-item-left {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
    flex: 1;
  }

  .task-icon {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    border: 1px solid;
  }

  .task-icon-generic {
    background: var(--bg-raised);
    border-color: var(--border);
  }

  .task-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .task-title {
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: clamp(1rem, 3vw, 1.15rem);
    font-weight: 400;
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .task-meta {
    font-size: 11px;
    color: var(--text-faint);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .runtime-chip {
    width: fit-content;
    padding: 3px 7px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border: 1px solid var(--border-light);
  }

  .rc-running {
    color: var(--green);
    border-color: color-mix(in oklch, var(--green), transparent 70%);
    background: color-mix(in oklch, var(--green), transparent 92%);
  }

  .rc-idle {
    color: var(--accent);
    border-color: color-mix(in oklch, var(--accent), transparent 70%);
    background: color-mix(in oklch, var(--accent), transparent 92%);
  }

  .rc-empty {
    color: var(--text-faint);
    border-color: var(--border);
    background: var(--bg-raised);
  }

  .empty-state {
    padding: 56px 0 36px;
  }

  .empty-icons {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
  }

  .empty-title {
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: 1.5rem;
    font-weight: 400;
    margin: 0 0 8px;
  }

  .empty-desc {
    color: var(--text-dim);
    line-height: 1.6;
    max-width: 48ch;
  }

  .empty-text {
    color: var(--text-dim);
    padding: 18px 0;
  }

  @media (max-width: 760px) {
    .dashboard { padding-inline: 16px; }
    .mode-band { grid-template-columns: 1fr; }
    .header { align-items: flex-start; gap: 12px; }
    .header-right { flex-wrap: wrap; justify-content: flex-end; }
  }
</style>
