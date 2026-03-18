<script lang="ts">
  import { onMount } from 'svelte'
  import { fetchRepos, fetchRoles, cloneRepo as apiClone, createTask as apiCreate, type Repo, type Role } from '../lib/api'
  import { roles, navigate, showToast } from '../lib/stores.svelte'
  import { roleVisuals } from '../lib/roles'
  import RoleIcon from '../components/RoleIcon.svelte'

  let repos = $state<Repo[]>([])
  let selectedRepo = $state<string | null>(null)
  let cloneUrl = $state('')

  let title = $state('')
  let description = $state('')
  let branch = $state('')
  let baseBranch = $state('')
  let agentType = $state('claude')
  let roleId = $state<number | null>(null)
  let taskKind = $state('investigate')
  let targetType = $state('repo_head')
  let priority = $state('medium')
  let commitStart = $state('')
  let commitEnd = $state('')
  let pathScope = $state('')
  let creating = $state(false)

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

  const selectedRepoData = $derived(repos.find((repo) => repo.path === selectedRepo) || null)
  const availableBranches = $derived(selectedRepoData?.branches || [])

  onMount(async () => {
    try {
      const [r, ro] = await Promise.all([fetchRepos(), fetchRoles()])
      repos = r
      roles.list = ro
    } catch (e: any) {
      showToast(e.message)
    }
  })

  function selectRepo(path: string) {
    selectedRepo = selectedRepo === path ? null : path
    const repo = repos.find((r) => r.path === path)
    baseBranch = repo?.default_branch || ''
    branch = targetType === 'branch_diff' ? '' : branch
  }

  async function handleClone() {
    if (!cloneUrl.trim()) return
    try {
      showToast('Cloning...')
      const repo = await apiClone(cloneUrl.trim())
      repos = [...repos, repo]
      selectedRepo = repo.path
      baseBranch = repo.default_branch || ''
      cloneUrl = ''
      showToast(`Cloned ${repo.name}`)
    } catch (e: any) {
      showToast(e.message)
    }
  }

  async function handleCreate() {
    if (!title.trim() || !selectedRepo) {
      showToast('Title and repository are required')
      return
    }
    creating = true
    try {
      await apiCreate({
        title: title.trim(),
        description: description.trim(),
        repo_url: selectedRepo,
        branch: branch.trim() || null,
        base_branch: baseBranch.trim() || null,
        agent_type: agentType,
        role_id: roleId,
        task_kind: taskKind,
        target_type: targetType,
        priority,
        commit_start: commitStart.trim() || null,
        commit_end: commitEnd.trim() || null,
        path_scope: pathScope.trim() || null,
      })
      navigate('dashboard')
    } catch (e: any) {
      showToast(e.message)
    } finally {
      creating = false
    }
  }
</script>

<div class="create-view">
  <button class="back-btn" onclick={() => navigate('dashboard')}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
    Back
  </button>

  <h2 class="page-title">New task</h2>

  <!-- Repository -->
  <div class="field">
    <span class="field-label">Repository</span>
    {#if repos.length === 0}
      <p class="hint">No repos yet. Clone one below.</p>
    {:else}
      <div class="repo-list">
        {#each repos as repo}
          <button
            class="repo-item"
            class:selected={selectedRepo === repo.path}
            onclick={() => selectRepo(repo.path)}
          >
            <div class="repo-info">
              <span class="repo-name">{repo.name}</span>
              <span class="repo-meta">{repo.remote_url || repo.path} · {repo.default_branch || ''}</span>
            </div>
            <div class="repo-check" class:checked={selectedRepo === repo.path}></div>
          </button>
        {/each}
      </div>
    {/if}
    <div class="clone-row">
      <input bind:value={cloneUrl} placeholder="Or paste a git URL to clone..." class="input clone-input" />
      <button class="btn btn-sm" onclick={handleClone}>Clone</button>
    </div>
  </div>

  <!-- Title -->
  <div class="field">
    <label for="c-title">Title</label>
    <input id="c-title" class="input" bind:value={title} placeholder="What should the agent do?" />
  </div>

  <!-- Description -->
  <div class="field">
    <label for="c-desc">Instructions</label>
    <textarea id="c-desc" class="input textarea" bind:value={description} placeholder="Describe the task in detail."></textarea>
  </div>

  <!-- Role selector -->
  <div class="field">
    <span class="field-label">Role</span>
    <div class="role-grid">
      <button
        class="role-option"
        class:selected={roleId === null}
        onclick={() => roleId = null}
      >
        <div class="role-option-icon generic">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="var(--text-faint)"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
        </div>
        <span class="role-option-name">Generic</span>
      </button>
      {#each roles.list as role}
        {@const visual = roleVisuals[role.name]}
        {#if visual}
          <button
            class="role-option"
            class:selected={roleId === role.id}
            onclick={() => roleId = roleId === role.id ? null : role.id}
            style={roleId === role.id ? `border-color: ${visual.color}50;` : ''}
          >
            <div class="role-option-icon" style="background: {visual.color}15;">
              <RoleIcon name={role.name} size={18} />
            </div>
            <span class="role-option-name">{visual.label}</span>
            <span class="role-option-desc">{role.description}</span>
          </button>
        {/if}
      {/each}
    </div>
  </div>

  <div class="row-3">
    <div class="field">
      <label for="c-kind">Task kind</label>
      <select id="c-kind" class="input select" bind:value={taskKind}>
        {#each taskKindOptions as [value, label]}
          <option value={value}>{label}</option>
        {/each}
      </select>
    </div>
    <div class="field">
      <label for="c-target-type">Target type</label>
      <select id="c-target-type" class="input select" bind:value={targetType}>
        {#each targetTypeOptions as [value, label]}
          <option value={value}>{label}</option>
        {/each}
      </select>
    </div>
    <div class="field">
      <label for="c-priority">Priority</label>
      <select id="c-priority" class="input select" bind:value={priority}>
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
      </select>
    </div>
  </div>

  <!-- Branch targeting -->
  {#if targetType === 'branch_diff'}
    <div class="row-2">
      <div class="field">
        <label for="c-branch">Focus Branch</label>
        <select id="c-branch" class="input select" bind:value={branch} disabled={!selectedRepoData}>
          <option value="">Create new task branch</option>
          {#each availableBranches as repoBranch}
            <option value={repoBranch}>{repoBranch}</option>
          {/each}
        </select>
        <p class="hint">Pick the branch to review or continue. Leave blank to create a new task branch.</p>
      </div>
      <div class="field">
        <label for="c-base-branch">Base Branch</label>
        <select id="c-base-branch" class="input select" bind:value={baseBranch} disabled={!selectedRepoData}>
          <option value="">Auto-detect</option>
          {#each availableBranches as repoBranch}
            <option value={repoBranch}>{repoBranch}</option>
          {/each}
        </select>
        <p class="hint">This is the baseline for diff and review scope.</p>
      </div>
    </div>
  {/if}

  {#if targetType === 'commit_range'}
    <div class="row-2">
      <div class="field">
        <label for="c-commit-start">Commit start</label>
        <input id="c-commit-start" class="input" bind:value={commitStart} placeholder="Older SHA" />
      </div>
      <div class="field">
        <label for="c-commit-end">Commit end</label>
        <input id="c-commit-end" class="input" bind:value={commitEnd} placeholder="Newer SHA or HEAD" />
      </div>
    </div>
  {/if}

  {#if targetType === 'file_scope'}
    <div class="field">
      <label for="c-path-scope">Path scope</label>
      <input id="c-path-scope" class="input" bind:value={pathScope} placeholder="pkg/aika, cmd/app, README.md" />
      <p class="hint">Limit the task to one file or subtree.</p>
    </div>
  {/if}

  <!-- Agent type -->
  <div class="row-2">
    <div class="field">
      <label for="c-agent">Agent</label>
      <select id="c-agent" class="input select" bind:value={agentType}>
        <option value="claude">Claude Code</option>
        <option value="codex">Codex</option>
      </select>
    </div>
  </div>

  <button class="btn btn-accent btn-full" onclick={handleCreate} disabled={creating}>
    {creating ? 'Creating...' : 'Create task'}
  </button>
</div>

<style>
  .create-view {
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

  .page-title {
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: clamp(1.4rem, 5vw, 1.8rem);
    font-weight: 400;
    margin-bottom: 24px;
  }

  .field { margin-bottom: 20px; }
  .field label, .field-label {
    display: block;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 6px;
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
    transition: border-color 0.2s;
  }
  .input:focus { outline: none; border-color: var(--accent-dim); }

  .textarea { resize: vertical; min-height: 100px; line-height: 1.6; }
  .select { appearance: none; cursor: pointer; }

  .hint {
    color: var(--text-faint);
    font-size: 13px;
    padding: 8px 0;
  }

  /* Repos */
  .repo-list { margin-bottom: 12px; }

  .repo-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    padding: 12px 0;
    border: none;
    border-bottom: 1px solid var(--border);
    background: none;
    cursor: pointer;
    text-align: left;
    font-family: var(--sans);
    color: var(--text);
    transition: opacity 0.15s;
  }
  .repo-item:first-child { border-top: 1px solid var(--border); }
  .repo-item:hover { opacity: 0.7; }
  .repo-item.selected { border-color: var(--accent); }

  .repo-info { display: flex; flex-direction: column; gap: 2px; }
  .repo-name { font-family: 'Instrument Serif', Georgia, serif; font-size: 1.05rem; }
  .repo-meta { font-size: 11px; color: var(--text-faint); }

  .repo-check {
    width: 18px; height: 18px;
    border: 1px solid var(--border-light);
    border-radius: 3px;
    flex-shrink: 0;
    position: relative;
    transition: all 0.15s;
  }
  .repo-check.checked {
    background: var(--accent);
    border-color: var(--accent);
  }
  .repo-check.checked::after {
    content: '';
    position: absolute;
    top: 4px; left: 3px;
    width: 8px; height: 5px;
    border-left: 2px solid var(--bg);
    border-bottom: 2px solid var(--bg);
    transform: rotate(-45deg);
  }

  .clone-row {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }
  .clone-input { flex: 1; font-size: 13px; padding: 8px 12px; }

  /* Role grid */
  .role-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 8px;
  }

  .role-option {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 14px 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: none;
    cursor: pointer;
    font-family: var(--sans);
    color: var(--text);
    transition: border-color 0.2s, background 0.2s;
  }
  .role-option:hover { background: var(--bg-raised); }
  .role-option.selected { border-color: var(--accent-dim); background: var(--bg-raised); }

  .role-option-icon {
    width: 36px; height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .role-option-icon.generic { background: var(--bg-input); }

  .role-option-name { font-size: 12px; font-weight: 600; }
  .role-option-desc {
    font-size: 10px;
    color: var(--text-faint);
    text-align: center;
    line-height: 1.3;
    line-clamp: 2;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  /* Layout */
  .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }

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
  .btn-accent:disabled { opacity: 0.5; cursor: wait; }

  .btn-full { width: 100%; justify-content: center; padding: 11px; font-size: 14px; }

  @media (max-width: 720px) {
    .row-2, .row-3 { grid-template-columns: 1fr; }
  }
</style>
