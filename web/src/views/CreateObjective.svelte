<script lang="ts">
  import { onMount } from 'svelte'
  import { cloneRepo, createObjective, fetchRepos, type Repo } from '../lib/api'
  import { navigate, showToast } from '../lib/stores.svelte'

  let repos = $state<Repo[]>([])
  let selectedRepo = $state<string | null>(null)
  let cloneUrl = $state('')
  let title = $state('')
  let description = $state('')
  let priority = $state('medium')
  let agentType = $state('codex')
  let creating = $state(false)

  onMount(async () => {
    try {
      repos = await fetchRepos()
    } catch (e: any) {
      showToast(e.message)
    }
  })

  async function handleClone() {
    if (!cloneUrl.trim()) return
    try {
      showToast('Cloning repository...')
      const repo = await cloneRepo(cloneUrl.trim())
      repos = [...repos, repo]
      selectedRepo = repo.path
      cloneUrl = ''
      showToast(`Cloned ${repo.name}`)
    } catch (e: any) {
      showToast(e.message)
    }
  }

  async function handleCreate() {
    if (!title.trim()) {
      showToast('Goal is required')
      return
    }
    creating = true
    try {
      const objective = await createObjective({
        title: title.trim(),
        description: description.trim(),
        repo_url: selectedRepo,
        priority,
        agent_type: agentType,
      })
      navigate('objective', objective.id)
    } catch (e: any) {
      showToast(e.message)
    } finally {
      creating = false
    }
  }
</script>

<div class="objective-create">
  <button class="back-btn" onclick={() => navigate('dashboard')}>Back</button>

  <div class="hero">
    <span class="hero-kicker">Orchestration Mode</span>
    <h1>Give the system an objective and let it coordinate the work.</h1>
    <p>
      This mode is for broader goals. The orchestrator can ask clarifying questions,
      spawn specialist agents, and keep driving the objective forward.
    </p>
  </div>

  <div class="panel">
    <div class="field">
      <label for="o-title">Objective</label>
      <input id="o-title" class="input" bind:value={title} placeholder="Build X, review Y, prepare Z for release" />
    </div>

    <div class="field">
      <label for="o-desc">Initial Instructions</label>
      <textarea id="o-desc" class="input textarea" bind:value={description} placeholder="Give context, constraints, repo expectations, and what the orchestrator should optimize for."></textarea>
    </div>

    <div class="row-3">
      <div class="field">
        <label for="o-repo">Repository</label>
        <select id="o-repo" class="input select" bind:value={selectedRepo}>
          <option value={null}>None / ask later</option>
          {#each repos as repo}
            <option value={repo.path}>{repo.name}</option>
          {/each}
        </select>
      </div>
      <div class="field">
        <label for="o-priority">Priority</label>
        <select id="o-priority" class="input select" bind:value={priority}>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
      </div>
      <div class="field">
        <label for="o-agent">Orchestrator Agent</label>
        <select id="o-agent" class="input select" bind:value={agentType}>
          <option value="codex">Codex</option>
          <option value="claude">Claude</option>
        </select>
      </div>
    </div>

    <div class="field">
      <label for="o-clone">Add Repository</label>
      <div class="clone-row">
        <input
          id="o-clone"
          class="input"
          bind:value={cloneUrl}
          placeholder="Paste a fresh GitHub repo URL to clone locally..."
        />
        <button class="clone-btn" onclick={handleClone}>Clone</button>
      </div>
      <p class="hint">Useful when you create a new repo on GitHub first and want the orchestrator to work against that local clone.</p>
    </div>

    <div class="tips">
      <div>
        <strong>Good objective:</strong>
        “Ship the new orchestration UI for agent objectives in this repo. Ask me if branch target is unclear.”
      </div>
      <div>
        <strong>How it behaves:</strong>
        It will start with a planner-style orchestrator, ask questions only when needed, and create child tasks for concrete work.
      </div>
    </div>

    <button class="launch-btn" onclick={handleCreate} disabled={creating}>
      {creating ? 'Launching orchestration...' : 'Launch Objective'}
    </button>
  </div>
</div>

<style>
  .objective-create {
    max-width: 860px;
    margin: 0 auto;
    padding: 20px 24px 48px;
  }

  .back-btn {
    border: none;
    background: none;
    color: var(--text-dim);
    font: inherit;
    cursor: pointer;
    padding: 0 0 16px;
  }

  .hero {
    padding: 0 0 28px;
  }

  .hero-kicker {
    display: inline-block;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #8b4d2b;
    margin-bottom: 10px;
  }

  .hero h1 {
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: clamp(2.1rem, 6vw, 3.8rem);
    line-height: 0.95;
    font-weight: 400;
    max-width: 10ch;
    margin: 0;
  }

  .hero p {
    margin: 16px 0 0;
    max-width: 56ch;
    color: var(--text-dim);
    line-height: 1.6;
  }

  .panel {
    padding: 24px;
    background:
      linear-gradient(180deg, color-mix(in oklch, var(--bg-raised), #b66a42 10%) 0%, var(--bg-raised) 100%);
    border: 1px solid color-mix(in oklch, var(--border), #b66a42 24%);
    border-radius: 20px;
    box-shadow: 0 24px 60px color-mix(in oklch, var(--bg), transparent 75%);
  }

  .field { margin-bottom: 18px; }

  label {
    display: block;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-dim);
    margin-bottom: 8px;
  }

  .input {
    width: 100%;
    padding: 12px 14px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: color-mix(in oklch, var(--bg-input), white 6%);
    color: var(--text);
    font: inherit;
  }

  .textarea {
    min-height: 150px;
    resize: vertical;
    line-height: 1.55;
  }

  .select { appearance: none; }

  .row-3 {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }

  .clone-row {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 10px;
  }

  .clone-btn {
    padding: 0 18px;
    border: 1px solid color-mix(in oklch, var(--border), #8b4d2b 20%);
    border-radius: 10px;
    background: color-mix(in oklch, var(--bg), #8b4d2b 4%);
    color: var(--text);
    font: inherit;
    cursor: pointer;
  }

  .hint {
    margin: 8px 0 0;
    color: var(--text-faint);
    font-size: 12px;
    line-height: 1.45;
  }

  .tips {
    display: grid;
    gap: 10px;
    margin: 10px 0 22px;
    color: var(--text-dim);
    line-height: 1.5;
  }

  .launch-btn {
    width: 100%;
    padding: 14px 18px;
    border: none;
    border-radius: 999px;
    background: #8b4d2b;
    color: #f5ecdf;
    font: inherit;
    font-weight: 600;
    letter-spacing: 0.02em;
    cursor: pointer;
  }

  .launch-btn:disabled { opacity: 0.6; cursor: wait; }

  @media (max-width: 720px) {
    .row-3 { grid-template-columns: 1fr; }
    .clone-row { grid-template-columns: 1fr; }
    .objective-create { padding-inline: 18px; }
  }
</style>
