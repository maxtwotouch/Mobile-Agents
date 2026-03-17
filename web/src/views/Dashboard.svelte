<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import { fetchTasks, fetchRoles, type Task, type Role } from '../lib/api'
  import { tasks, roles, navigate, clearAuth, showToast } from '../lib/stores.svelte'
  import { onWsMessage, disconnectWS } from '../lib/ws'
  import { roleVisuals, statusConfig } from '../lib/roles'
  import { timeAgo, repoShortName } from '../lib/utils'
  import RoleIcon from '../components/RoleIcon.svelte'
  import StatusBadge from '../components/StatusBadge.svelte'
  import ConnectionDot from '../components/ConnectionDot.svelte'

  let loading = $state(true)

  // Derived stats
  const running = $derived(tasks.list.filter(t => t.status === 'running').length)
  const review = $derived(tasks.list.filter(t => t.status === 'needs_review').length)
  const completed = $derived(tasks.list.filter(t => t.status === 'completed').length)
  const total = $derived(tasks.list.length)

  // Role distribution
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
      const [t, r] = await Promise.all([fetchTasks(), fetchRoles()])
      tasks.list = t
      roles.list = r
    } catch (e: any) {
      showToast(e.message)
    } finally {
      loading = false
    }
  }

  const unsub = onWsMessage((data) => {
    if (data.type === 'task_update') {
      showToast(`Task #${data.task_id} — ${data.status || data.message}`)
    } else if (data.type === 'task_created') {
      showToast(`Created: ${data.title}`)
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
  <!-- Header -->
  <header class="header">
    <div class="header-left">
      <h1 class="logo">agents</h1>
      <ConnectionDot />
    </div>
    <div class="header-right">
      <button class="btn btn-ghost" onclick={logout}>Sign out</button>
      <button class="btn btn-accent" onclick={() => navigate('create')}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        New task
      </button>
    </div>
  </header>

  <!-- Stats strip -->
  <div class="stats-strip">
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

  <!-- Role legend -->
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

  <!-- Task list -->
  <div class="task-list">
    {#if loading}
      <p class="empty-text">Loading...</p>
    {:else if tasks.list.length === 0}
      <div class="empty-state">
        <div class="empty-icons">
          {#each Object.entries(roleVisuals) as [name, v]}
            <svg width="28" height="28" viewBox="0 0 24 24" fill={v.color} opacity="0.3"><path d={v.icon} /></svg>
          {/each}
        </div>
        <h2 class="empty-title">No agents running</h2>
        <p class="empty-desc">Create a task to dispatch an AI coding agent. Choose a role to give it a specific personality and skillset.</p>
        <button class="btn btn-accent" onclick={() => navigate('create')}>Create first task</button>
      </div>
    {:else}
      {#each tasks.list as task (task.id)}
        {@const visual = roleVisuals[task.role_name || ''] || null}
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
            </div>
          </div>
          <StatusBadge status={task.status} />
        </button>
      {/each}
    {/if}
  </div>
</div>

<style>
  .dashboard {
    max-width: 680px;
    margin: 0 auto;
    padding: 0 20px 40px;
  }

  /* Header */
  .header {
    padding: 20px 0 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .header-right {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .logo {
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: clamp(1.6rem, 5vw, 2rem);
    font-weight: 400;
    font-style: italic;
    letter-spacing: -0.02em;
    color: var(--text);
  }

  /* Buttons */
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
    transition: background 0.15s, border-color 0.15s;
    white-space: nowrap;
  }
  .btn:hover { background: var(--bg-raised); border-color: var(--text-faint); }
  .btn:active { transform: scale(0.98); }

  .btn-accent {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
    font-weight: 600;
  }
  .btn-accent:hover { opacity: 0.85; background: var(--accent); }

  .btn-ghost {
    border: none;
    color: var(--text-dim);
    padding: 7px 10px;
  }
  .btn-ghost:hover { color: var(--text); background: transparent; }

  /* Stats */
  .stats-strip {
    display: flex;
    align-items: center;
    gap: 0;
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
    color: var(--text);
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

  /* Role strip */
  .role-strip {
    display: flex;
    gap: 6px;
    padding: 12px 0;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
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
    transition: border-color 0.2s;
  }

  .role-chip-label { color: var(--text-dim); }
  .role-chip-count { font-weight: 600; }

  /* Task list */
  .task-list {
    padding-top: 4px;
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
    font-family: var(--sans);
    transition: opacity 0.15s;
    color: var(--text);
  }
  .task-item:first-child { border-top: 1px solid var(--border); }
  .task-item:hover { opacity: 0.75; }

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
    gap: 2px;
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
    letter-spacing: 0.01em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Empty state */
  .empty-state {
    padding: 60px 0 40px;
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
    font-style: italic;
    color: var(--text-dim);
    margin-bottom: 8px;
  }

  .empty-desc {
    font-size: 14px;
    color: var(--text-faint);
    max-width: 380px;
    line-height: 1.6;
    margin-bottom: 20px;
  }

  .empty-text {
    color: var(--text-faint);
    font-size: 13px;
    padding: 40px 0;
  }
</style>
