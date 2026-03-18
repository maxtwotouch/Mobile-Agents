<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import {
    fetchTask, fetchUpdates, fetchMessages, startTask, stopTask as apiStop,
    getOutput, getDiff, getFileDiff, getCommits, pushTask, patchTask, fetchRuns, fetchRepos,
    sendMessage as apiSend,
    type Task, type Update, type Message, type Run, type Repo,
  } from '../lib/api'
  import { navigate, showToast } from '../lib/stores.svelte'
  import { onWsMessage } from '../lib/ws'
  import { roleVisuals } from '../lib/roles'
  import { timeAgo, repoShortName, colorDiff, renderRichText, threadState } from '../lib/utils'
  import RoleIcon from '../components/RoleIcon.svelte'
  import StatusBadge from '../components/StatusBadge.svelte'

  let { taskId }: { taskId: number } = $props()

  let task = $state<Task | null>(null)
  let updates = $state<Update[]>([])
  let messages = $state<Message[]>([])
  let output = $state('')
  let runs = $state<Run[]>([])
  let repos = $state<Repo[]>([])
  let outputInterval: ReturnType<typeof setInterval> | null = null
  let msgInput = $state('')
  let resumePrompt = $state('')
  let taskKindDraft = $state('investigate')
  let targetTypeDraft = $state('repo_head')
  let priorityDraft = $state('medium')
  let branchDraft = $state('')
  let baseBranchDraft = $state('')
  let commitStartDraft = $state('')
  let commitEndDraft = $state('')
  let pathScopeDraft = $state('')

  // Review state
  let showReview = $state(false)
  let reviewTab = $state<'files' | 'diff' | 'commits'>('files')
  let diffData = $state<any>(null)
  let commitData = $state<any[]>([])
  let fileDiffPath = $state<string | null>(null)
  let fileDiffContent = $state('')

  const visual = $derived(task?.role_name ? roleVisuals[task.role_name] || null : null)
  const isCodex = $derived(task?.agent_type === 'codex')
  const canResume = $derived(isCodex && task?.thread_id && ['waiting_for_user', 'needs_review', 'failed'].includes(task?.workflow_state || ''))
  const canStart = $derived(['ready', 'waiting_for_user', 'needs_review', 'failed'].includes(task?.workflow_state || ''))
  const runtime = $derived(task ? threadState(task) : null)
  const taskRepo = $derived(task ? repos.find((repo) => repo.path === task?.repo_url) || null : null)
  const branchOptions = $derived(taskRepo?.branches || [])
  const taskKindOptions = [
    ['implement', 'Implement'],
    ['review', 'Review'],
    ['audit', 'Audit'],
    ['investigate', 'Investigate'],
    ['fix', 'Fix'],
    ['refactor', 'Refactor'],
    ['qa', 'QA'],
    ['release', 'Release'],
    ['orchestrate', 'Orchestrate'],
  ] as const
  const targetTypeOptions = [
    ['repo_head', 'Repo head'],
    ['branch_diff', 'Branch diff'],
    ['commit_range', 'Commit range'],
    ['workspace_changes', 'Workspace changes'],
    ['file_scope', 'File scope'],
    ['issue_followup', 'Issue follow-up'],
  ] as const

  async function load() {
    try {
      const [t, u, m, r, repoList] = await Promise.all([
        fetchTask(taskId),
        fetchUpdates(taskId),
        fetchMessages(taskId),
        fetchRuns(taskId),
        fetchRepos(),
      ])
      task = t
      updates = u
      messages = m
      runs = r
      repos = repoList
      const repo = repoList.find((entry) => entry.path === t.repo_url) || null
      taskKindDraft = t.task_kind || 'investigate'
      targetTypeDraft = t.target_type || 'repo_head'
      priorityDraft = t.priority || 'medium'
      branchDraft = t.branch || ''
      baseBranchDraft = t.base_branch || repo?.default_branch || ''
      commitStartDraft = t.commit_start || ''
      commitEndDraft = t.commit_end || ''
      pathScopeDraft = t.path_scope || ''

      if (t.runtime_status === 'running') {
        refreshOutput()
        if (!outputInterval) outputInterval = setInterval(refreshOutput, 5000)
      } else {
        if (outputInterval) { clearInterval(outputInterval); outputInterval = null }
        output = ''
      }
    } catch (e: any) {
      showToast(e.message)
    }
  }

  async function refreshOutput() {
    try {
      const data = await getOutput(taskId)
      output = data.output || ''
    } catch (e: any) {
      output = e.message
      await load()
    }
  }

  async function handleStart(prompt?: string) {
    try {
      await startTask(taskId, prompt)
      await load()
    } catch (e: any) { showToast(e.message) }
  }

  async function handleStop() {
    try {
      await apiStop(taskId)
      await load()
    } catch (e: any) { showToast(e.message) }
  }

  async function handleSend() {
    if (!msgInput.trim()) return
    try {
      await apiSend(taskId, msgInput.trim())
      msgInput = ''
      await load()
    } catch (e: any) { showToast(e.message) }
  }

  async function handleComplete() {
    try {
      await patchTask(taskId, { workflow_state: 'completed' })
      await load()
    } catch (e: any) { showToast(e.message) }
  }

  async function saveTargeting() {
    try {
      await patchTask(taskId, {
        task_kind: taskKindDraft,
        target_type: targetTypeDraft,
        priority: priorityDraft,
        branch: branchDraft || null,
        base_branch: baseBranchDraft || null,
        commit_start: commitStartDraft || null,
        commit_end: commitEndDraft || null,
        path_scope: pathScopeDraft || null,
      })
      showToast('Task targeting updated')
      await load()
    } catch (e: any) { showToast(e.message) }
  }

  async function openReview() {
    showReview = true
    try {
      const [d, c] = await Promise.all([getDiff(taskId), getCommits(taskId)])
      diffData = d
      commitData = c
    } catch (e: any) { showToast(e.message) }
  }

  async function openFileDiff(path: string) {
    fileDiffPath = path
    fileDiffContent = 'Loading...'
    try {
      const data = await getFileDiff(taskId, path)
      fileDiffContent = data.diff || 'No changes.'
    } catch (e: any) { fileDiffContent = e.message }
  }

  async function handlePush(approve: boolean) {
    try {
      await pushTask(taskId, approve)
      showToast(approve ? 'Pushed' : 'Rejected')
      showReview = false
      await load()
    } catch (e: any) { showToast(e.message) }
  }

  async function handleResumeWithPrompt() {
    if (!resumePrompt.trim()) { showToast('Enter follow-up instructions'); return }
    await handleStart(resumePrompt.trim())
    resumePrompt = ''
  }

  const unsub = onWsMessage((data) => {
    if (data.task_id === taskId) load()
  })

  onMount(load)
  onDestroy(() => {
    unsub()
    if (outputInterval) clearInterval(outputInterval)
  })
</script>

<div class="detail-view">
  <button class="back-btn" onclick={() => navigate('dashboard')}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
    Back
  </button>

  {#if task}
    <!-- Header -->
    <div class="detail-header">
      <div class="detail-header-top">
        {#if visual}
          <div class="detail-role-icon" style="background: {visual.color}15; border-color: {visual.color}30;">
            <RoleIcon name={task.role_name} size={22} />
          </div>
        {/if}
        <div class="detail-header-text">
          <div class="detail-title-row">
            <h1 class="detail-title">{task.title}</h1>
            <StatusBadge status={task.workflow_state} />
          </div>
          {#if runtime}
            <div class="runtime-row">
              <span class="runtime-chip rc-{runtime.tone}">{runtime.label}</span>
              {#if task.thread_id}
                <span class="runtime-thread">thread {task.thread_id}</span>
              {/if}
            </div>
          {/if}
          {#if task.description}
            <p class="detail-desc">{task.description}</p>
          {/if}
          <div class="detail-meta">
            {task.agent_type}{task.role_name ? ` · ${task.role_name}` : ''}
            · {task.task_kind}
            · {task.target_type}
            · {repoShortName(task.repo_url)}
            · {task.branch || 'branch pending'}
            {task.base_branch ? ` (from ${task.base_branch})` : ''}
          </div>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="action-bar">
      {#if canResume}
        <button class="btn btn-accent" onclick={() => handleStart()}>Resume</button>
      {:else if canStart}
        <button class="btn btn-accent" onclick={() => handleStart()}>Start agent</button>
      {/if}
      {#if task.runtime_status === 'running'}
        <button class="btn btn-danger" onclick={handleStop}>Stop</button>
      {/if}
      {#if task.workflow_state === 'needs_review'}
        {#if task.branch}
          <button class="btn btn-approve" onclick={openReview}>Review changes</button>
        {/if}
        <button class="btn" onclick={handleComplete}>Mark done</button>
      {/if}
    </div>

    <div class="section">
      <span class="section-label">Task Targeting</span>
      <div class="row-3">
        <div class="field-tight">
          <label for="t-kind">Task Kind</label>
          <select id="t-kind" class="input select" bind:value={taskKindDraft}>
            {#each taskKindOptions as [value, label]}
              <option value={value}>{label}</option>
            {/each}
          </select>
        </div>
        <div class="field-tight">
          <label for="t-target-type">Target Type</label>
          <select id="t-target-type" class="input select" bind:value={targetTypeDraft}>
            {#each targetTypeOptions as [value, label]}
              <option value={value}>{label}</option>
            {/each}
          </select>
        </div>
        <div class="field-tight">
          <label for="t-priority">Priority</label>
          <select id="t-priority" class="input select" bind:value={priorityDraft}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>
      </div>

      {#if targetTypeDraft === 'branch_diff'}
        <div class="row-2">
          <div class="field-tight">
            <label for="t-branch">Focus Branch</label>
            <select id="t-branch" class="input select" bind:value={branchDraft}>
              <option value="">Create new task branch</option>
              {#each branchOptions as repoBranch}
                <option value={repoBranch}>{repoBranch}</option>
              {/each}
            </select>
          </div>
          <div class="field-tight">
            <label for="t-base-branch">Base Branch</label>
            <select id="t-base-branch" class="input select" bind:value={baseBranchDraft}>
              <option value="">Auto-detect</option>
              {#each branchOptions as repoBranch}
                <option value={repoBranch}>{repoBranch}</option>
              {/each}
            </select>
          </div>
        </div>
      {/if}

      {#if targetTypeDraft === 'commit_range'}
        <div class="row-2">
          <div class="field-tight">
            <label for="t-commit-start">Commit Start</label>
            <input id="t-commit-start" class="input" bind:value={commitStartDraft} placeholder="Older SHA" />
          </div>
          <div class="field-tight">
            <label for="t-commit-end">Commit End</label>
            <input id="t-commit-end" class="input" bind:value={commitEndDraft} placeholder="Newer SHA or HEAD" />
          </div>
        </div>
      {/if}

      {#if targetTypeDraft === 'file_scope'}
        <div class="field-tight">
          <label for="t-path-scope">Path Scope</label>
          <input id="t-path-scope" class="input" bind:value={pathScopeDraft} placeholder="pkg/aika, cmd/app, README.md" />
        </div>
      {/if}

      <button class="btn btn-sm" onclick={saveTargeting}>Save targeting</button>
    </div>

    {#if canResume}
      <div class="composer">
        <input class="input" bind:value={resumePrompt} placeholder="Follow-up instructions..." onkeydown={(e) => e.key === 'Enter' && handleResumeWithPrompt()} />
        <button class="btn btn-accent btn-sm" onclick={handleResumeWithPrompt}>Resume with prompt</button>
      </div>
    {/if}

    <!-- Live output -->
    {#if task.runtime_status === 'running'}
      <div class="section">
        <div class="section-head">
          <span class="section-label">Live output</span>
          <button class="btn btn-ghost btn-sm" onclick={refreshOutput}>Refresh</button>
        </div>
        <pre class="terminal">{output || 'Waiting for output...'}</pre>
      </div>
    {/if}

    <!-- Review section -->
    {#if showReview && diffData}
      <div class="section">
        <span class="section-label">Code review</span>

        <div class="diff-summary">
          <span class="diff-files">{diffData.stats.files_changed} file{diffData.stats.files_changed !== 1 ? 's' : ''}</span>
          <span class="diff-add">+{diffData.stats.total_additions}</span>
          <span class="diff-del">-{diffData.stats.total_deletions}</span>
        </div>

        <div class="tabs">
          <button class="tab" class:active={reviewTab === 'files'} onclick={() => { reviewTab = 'files'; fileDiffPath = null }}>Files</button>
          <button class="tab" class:active={reviewTab === 'diff'} onclick={() => { reviewTab = 'diff'; fileDiffPath = null }}>Full diff</button>
          <button class="tab" class:active={reviewTab === 'commits'} onclick={() => reviewTab = 'commits'}>Commits</button>
        </div>

        {#if reviewTab === 'files'}
          <div class="file-list">
            {#each diffData.stats.files || [] as f}
              <button class="file-item" onclick={() => openFileDiff(f.path)}>
                <span class="file-name">{f.path}</span>
                <span class="file-stats">
                  <span class="diff-add">+{f.additions}</span>
                  <span class="diff-del">-{f.deletions}</span>
                </span>
              </button>
            {/each}
          </div>

          {#if fileDiffPath}
            <div class="file-diff-viewer">
              <div class="file-diff-head">
                <span class="file-name">{fileDiffPath}</span>
                <button class="btn btn-ghost btn-sm" onclick={() => fileDiffPath = null}>Close</button>
              </div>
              <pre class="diff-block">{@html colorDiff(fileDiffContent)}</pre>
            </div>
          {/if}
        {:else if reviewTab === 'diff'}
          <pre class="diff-block">{@html colorDiff(diffData.diff || 'No changes.')}</pre>
        {:else if reviewTab === 'commits'}
          {#each commitData as c}
            <div class="commit-item">
              <span class="commit-sha">{c.short_sha}</span>
              <span class="commit-msg">{c.message}</span>
              <div class="commit-meta">{c.author} · {c.date}</div>
            </div>
          {/each}
        {/if}

        <div class="action-bar" style="margin-top: 12px;">
          <button class="btn btn-approve" onclick={() => handlePush(true)}>Approve & push</button>
          <button class="btn btn-danger" onclick={() => handlePush(false)}>Reject</button>
        </div>
      </div>
    {/if}

    <!-- Parent/child relationships -->
    {#if task.parent_task_id}
      <div class="section">
        <span class="section-label">Parent task</span>
        <button class="task-link" onclick={() => navigate('detail', task!.parent_task_id!)}>
          Task #{task.parent_task_id}
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </button>
      </div>
    {/if}

    <!-- Activity -->
    <div class="section">
      <span class="section-label">Activity</span>
      {#if updates.length === 0}
        <p class="hint">No activity yet. Start the agent to begin.</p>
      {:else}
        {#each updates as u}
          <div class="update-item">
            <span class="update-tag ut-{u.type}">{u.type}</span>
            <div class="update-body rich-text">
              {@html renderRichText(u.content)}
              {#if u.commit_sha}
                <span class="update-sha">{u.commit_sha.slice(0, 7)}</span>
              {/if}
            </div>
            <span class="update-time">{timeAgo(u.created_at)}</span>
          </div>
        {/each}
      {/if}
    </div>

    <div class="section">
      <span class="section-label">Runs</span>
      {#if runs.length === 0}
        <p class="hint">No runs yet.</p>
      {:else}
        {#each runs as run}
          <div class="update-item">
            <span class="update-tag ut-summary">{run.status}</span>
            <div class="update-body rich-text">
              {@html renderRichText(run.prompt || 'Run dispatched')}
              {#if run.exit_code !== null}
                <span class="update-sha">exit {run.exit_code}</span>
              {/if}
            </div>
            <span class="update-time">{timeAgo(run.started_at)}</span>
          </div>
        {/each}
      {/if}
    </div>

    <!-- Messages -->
    <div class="section">
      <span class="section-label">Messages</span>
      <div class="messages">
        {#if messages.length === 0}
          <p class="hint">Send an instruction to guide the agent.</p>
        {:else}
          {#each messages as m}
            <div class="msg" class:msg-out={m.direction === 'user_to_agent'} class:msg-in={m.direction !== 'user_to_agent'}>
              <div class="rich-text">
                {@html renderRichText(m.content)}
              </div>
              <div class="msg-time">{timeAgo(m.created_at)}</div>
            </div>
          {/each}
        {/if}
      </div>
      <div class="composer">
        <input class="input" bind:value={msgInput} placeholder="Send instruction to agent..." onkeydown={(e) => e.key === 'Enter' && handleSend()} />
        <button class="btn btn-accent btn-sm" onclick={handleSend}>Send</button>
      </div>
    </div>

    <div style="height: 40px;"></div>
  {/if}
</div>

<style>
  .detail-view {
    max-width: 680px;
    margin: 0 auto;
    padding: 0 20px 40px;
  }

  .back-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: var(--text-dim);
    cursor: pointer;
    padding: 14px 0;
    border: none;
    background: none;
    font-family: var(--sans);
  }
  .back-btn:hover { color: var(--text); }

  /* Header */
  .detail-header { margin-bottom: 16px; }

  .detail-header-top {
    display: flex;
    gap: 14px;
    align-items: flex-start;
  }

  .detail-role-icon {
    width: 44px; height: 44px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    border: 1px solid;
    margin-top: 2px;
  }

  .detail-header-text { min-width: 0; flex: 1; }

  .detail-title-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
  }

  .detail-title {
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: clamp(1.3rem, 5vw, 1.7rem);
    font-weight: 400;
    line-height: 1.2;
  }

  .runtime-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-top: 8px;
  }

  .runtime-chip {
    width: fit-content;
    padding: 3px 8px;
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

  .runtime-thread {
    font-size: 11px;
    color: var(--text-faint);
    font-family: var(--sans);
  }

  .detail-desc {
    font-size: 14px;
    color: var(--text-dim);
    line-height: 1.6;
    margin: 6px 0 2px;
  }

  .detail-meta {
    font-size: 12px;
    color: var(--text-faint);
    margin-top: 4px;
  }

  /* Actions */
  .action-bar { display: flex; gap: 8px; flex-wrap: wrap; }

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
    transition: background 0.15s;
    white-space: nowrap;
  }
  .btn:hover { background: var(--bg-raised); }

  .btn-sm { padding: 5px 10px; font-size: 12px; }

  .btn-accent {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
    font-weight: 600;
  }
  .btn-accent:hover { opacity: 0.85; background: var(--accent); }

  .btn-danger { border-color: var(--red); color: var(--red); }
  .btn-danger:hover { background: color-mix(in oklch, var(--red), transparent 88%); }

  .btn-approve { border-color: var(--green); color: var(--green); }
  .btn-approve:hover { background: color-mix(in oklch, var(--green), transparent 88%); }

  .btn-ghost { border: none; color: var(--text-dim); padding: 7px 10px; }
  .btn-ghost:hover { color: var(--text); background: transparent; }

  /* Sections */
  .section { padding-top: 20px; }

  .row-2 {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }

  .row-3 {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }

  .field-tight {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
  }

  .field-tight label {
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-dim);
  }

  .input {
    width: 100%;
    padding: 10px 14px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg-input);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
  }

  @media (max-width: 720px) {
    .row-2, .row-3 {
      grid-template-columns: 1fr;
    }
  }

  .select {
    appearance: none;
    cursor: pointer;
  }

  .section-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .section-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-faint);
    margin-bottom: 10px;
    display: block;
  }

  /* Terminal */
  .terminal {
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 14px;
    font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
    font-size: 12px;
    line-height: 1.6;
    color: var(--text-dim);
    white-space: pre-wrap;
    word-wrap: break-word;
    max-height: 360px;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--border-light) transparent;
    margin: 0;
  }

  /* Input */
  .input {
    width: 100%;
    padding: 10px 14px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg-input);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
    transition: border-color 0.2s;
  }
  .input:focus { outline: none; border-color: var(--accent-dim); }

  .composer {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }

  /* Diff & review */
  .diff-summary {
    display: flex;
    gap: 16px;
    align-items: center;
    padding: 10px 14px;
    background: var(--bg-raised);
    border: 1px solid var(--border);
    border-radius: 4px;
    margin-bottom: 12px;
    font-size: 13px;
  }
  .diff-files { color: var(--text-dim); }
  .diff-add { color: var(--green); font-weight: 600; }
  .diff-del { color: var(--red); font-weight: 600; }

  .tabs {
    display: flex;
    border-bottom: 1px solid var(--border);
    margin-bottom: 12px;
  }

  .tab {
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text-faint);
    cursor: pointer;
    border: none;
    background: none;
    font-family: var(--sans);
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: color 0.15s, border-color 0.15s;
  }
  .tab:hover { color: var(--text-dim); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }

  .file-list { margin-bottom: 12px; }

  .file-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid var(--border);
    background: none;
    cursor: pointer;
    font-family: var(--sans);
    color: var(--text);
    font-size: 13px;
    transition: background 0.15s;
    text-align: left;
  }
  .file-item:first-child { border-top: 1px solid var(--border); }
  .file-item:hover { background: var(--bg-raised); }

  .file-name {
    font-family: 'SF Mono', monospace;
    font-size: 12px;
    word-break: break-all;
    flex: 1;
    min-width: 0;
  }

  .file-stats {
    display: flex;
    gap: 8px;
    font-family: 'SF Mono', monospace;
    font-size: 11px;
    flex-shrink: 0;
    margin-left: 12px;
  }

  .diff-block {
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 14px;
    font-family: 'SF Mono', 'Cascadia Code', monospace;
    font-size: 12px;
    line-height: 1.7;
    white-space: pre-wrap;
    word-wrap: break-word;
    max-height: 480px;
    overflow-y: auto;
    margin-bottom: 12px;
    scrollbar-width: thin;
    scrollbar-color: var(--border-light) transparent;
  }

  :global(.d-add) { color: var(--green); }
  :global(.d-del) { color: var(--red); }
  :global(.d-hdr) { color: var(--blue); }

  .file-diff-viewer { margin-top: 12px; }
  .file-diff-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  /* Commits */
  .commit-item {
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
  }
  .commit-item:first-child { border-top: 1px solid var(--border); }
  .commit-sha {
    font-family: 'SF Mono', monospace;
    font-size: 11px;
    color: var(--accent);
    margin-right: 8px;
  }
  .commit-msg { font-size: 13px; }
  .commit-meta { font-size: 11px; color: var(--text-faint); margin-top: 2px; }

  /* Updates */
  .update-item {
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    display: flex;
    gap: 10px;
  }
  .update-item:last-child { border-bottom: none; }

  .update-tag {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    flex-shrink: 0;
    padding-top: 2px;
  }
  :global(.ut-progress) { color: var(--blue); }
  :global(.ut-commit) { color: var(--green); }
  :global(.ut-error) { color: var(--red); }
  :global(.ut-summary) { color: var(--accent); }

  .update-body { color: var(--text-dim); flex: 1; min-width: 0; }
  .update-sha {
    font-family: 'SF Mono', monospace;
    font-size: 11px;
    color: var(--green);
    margin-left: 4px;
  }
  .update-time { font-size: 11px; color: var(--text-faint); flex-shrink: 0; }

  /* Messages */
  .messages {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
  }

  .msg {
    max-width: 85%;
    padding: 10px 14px;
    font-size: 14px;
    line-height: 1.5;
    border-radius: 4px;
  }
  .msg-out {
    align-self: flex-end;
    background: var(--accent-dim);
    color: var(--text);
    border-bottom-right-radius: 0;
  }
  .msg-in {
    align-self: flex-start;
    background: var(--bg-raised);
    border: 1px solid var(--border);
    color: var(--text-dim);
    border-bottom-left-radius: 0;
  }
  .msg-time { font-size: 10px; color: var(--text-faint); margin-top: 4px; }

  .hint { color: var(--text-faint); font-size: 13px; padding: 8px 0; }

  .rich-text {
    min-width: 0;
  }

  :global(.rich-text .rt-heading) {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text);
    margin: 0 0 8px;
  }

  :global(.rich-text .rt-paragraph) {
    margin: 0 0 10px;
    white-space: normal;
  }

  :global(.rich-text .rt-paragraph:last-child) {
    margin-bottom: 0;
  }

  :global(.rich-text .rt-list) {
    margin: 0 0 10px 18px;
    padding: 0;
    display: grid;
    gap: 10px;
  }

  :global(.rich-text .rt-list:last-child) {
    margin-bottom: 0;
  }

  :global(.rich-text .rt-link) {
    color: var(--accent);
    text-decoration: none;
    word-break: break-all;
  }

  :global(.rich-text .rt-link:hover) {
    text-decoration: underline;
  }

  :global(.rich-text .rt-code) {
    font-family: 'SF Mono', monospace;
    font-size: 0.92em;
    color: var(--text);
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1px 4px;
  }

  .task-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--accent);
    font-size: 13px;
    border: none;
    background: none;
    cursor: pointer;
    font-family: var(--sans);
    padding: 4px 0;
  }
  .task-link:hover { opacity: 0.7; }
</style>
