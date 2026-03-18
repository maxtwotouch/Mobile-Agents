<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import {
    answerDecision,
    fetchDecisions,
    fetchObjective,
    fetchTasks,
    type Decision,
    type Objective,
    type Task,
  } from '../lib/api'
  import { navigate, showToast } from '../lib/stores.svelte'
  import { onWsMessage } from '../lib/ws'
  import { repoShortName, threadState, timeAgo } from '../lib/utils'
  import StatusBadge from '../components/StatusBadge.svelte'

  let { objectiveId }: { objectiveId: number } = $props()

  let objective = $state<Objective | null>(null)
  let decisions = $state<Decision[]>([])
  let tasks = $state<Task[]>([])
  let loading = $state(true)

  const openDecisions = $derived(decisions.filter((d) => d.decision_state === 'open'))
  const orchestrator = $derived(tasks.find((task) => task.task_kind === 'orchestrate') || null)
  const childTasks = $derived(tasks.filter((task) => task.task_kind !== 'orchestrate'))

  async function load() {
    try {
      const [o, d, t] = await Promise.all([
        fetchObjective(objectiveId),
        fetchDecisions({ objective_id: objectiveId }),
        fetchTasks(undefined, objectiveId),
      ])
      objective = o
      decisions = d
      tasks = t
    } catch (e: any) {
      showToast(e.message)
    } finally {
      loading = false
    }
  }

  async function handleDecision(id: number, option: string) {
    try {
      await answerDecision(id, option)
      await load()
    } catch (e: any) {
      showToast(e.message)
    }
  }

  const unsub = onWsMessage((data) => {
    if (data.objective_id === objectiveId || (data.task_id && tasks.some((t) => t.id === data.task_id))) {
      load()
    }
  })

  onMount(load)
  onDestroy(unsub)
</script>

<div class="objective-detail">
  <button class="back-btn" onclick={() => navigate('dashboard')}>Back</button>

  {#if objective}
    <section class="top">
      <div class="title-block">
        <span class="eyebrow">Objective</span>
        <h1>{objective.title}</h1>
        {#if objective.description}
          <p>{objective.description}</p>
        {/if}
        <div class="meta-line">
          <StatusBadge status={objective.objective_state} />
          {#if objective.repo_url}
            <span>{repoShortName(objective.repo_url)}</span>
          {/if}
          <span>{objective.priority}</span>
        </div>
      </div>

      <div class="summary-panel">
        <span class="panel-label">Orchestrator</span>
        {#if orchestrator}
          {@const runtime = threadState(orchestrator)}
          <div class="summary-line">
            <span class="runtime-chip rc-{runtime.tone}">{runtime.label}</span>
            <span>workflow {orchestrator.workflow_state}</span>
          </div>
          {#if orchestrator.result_summary}
            <p>{orchestrator.result_summary}</p>
          {/if}
          {#if orchestrator.next_action_hint}
            <div class="next-callout">
              <span>Next</span>
              <p>{orchestrator.next_action_hint}</p>
            </div>
          {/if}
        {:else}
          <p>Preparing orchestration task…</p>
        {/if}
      </div>
    </section>

    <section class="main-grid">
      <div class="left-column">
        <div class="panel decisions">
          <div class="panel-head">
            <span class="panel-label">Clarifications</span>
            <span class="count">{openDecisions.length}</span>
          </div>
          {#if openDecisions.length === 0}
            <p class="empty">No open questions right now. The orchestrator will keep going until it needs a decision.</p>
          {:else}
            {#each openDecisions as decision}
              <div class="decision-card">
                <div class="decision-type">{decision.decision_type}</div>
                <h3>{decision.question}</h3>
                <div class="decision-options">
                  {#each decision.options || [] as option}
                    <button
                      class:selected={decision.recommended_option === option}
                      onclick={() => handleDecision(decision.id, option)}
                    >
                      {option}
                    </button>
                  {/each}
                </div>
              </div>
            {/each}
          {/if}
        </div>

        <div class="panel">
          <div class="panel-head">
            <span class="panel-label">Task Graph</span>
            <span class="count">{tasks.length}</span>
          </div>
          {#if loading}
            <p class="empty">Loading objective…</p>
          {:else if tasks.length === 0}
            <p class="empty">No tasks yet.</p>
          {:else}
            <div class="task-stack">
              {#if orchestrator}
                <button class="task-card orchestrator" onclick={() => navigate('detail', orchestrator.id)}>
                  <div>
                    <div class="task-kicker">Orchestrator</div>
                    <div class="task-title">{orchestrator.title}</div>
                  </div>
                  <StatusBadge status={orchestrator.workflow_state} />
                </button>
              {/if}
              {#each childTasks as task}
                {@const runtime = threadState(task)}
                <button class="task-card child" onclick={() => navigate('detail', task.id)}>
                  <div class="task-main">
                    <div class="task-topline">
                      <span class="task-kind">{task.task_kind}</span>
                      <span class="task-time">{timeAgo(task.updated_at)}</span>
                    </div>
                    <div class="task-title">{task.title}</div>
                    <div class="task-meta">
                      {task.role_name || 'generic'} · {task.target_type}
                      {task.branch ? ` · ${task.branch}` : ''}
                    </div>
                  </div>
                  <div class="task-side">
                    <span class="runtime-chip rc-{runtime.tone}">{runtime.label}</span>
                    <StatusBadge status={task.workflow_state} />
                  </div>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <div class="right-column">
        <div class="panel">
          <div class="panel-head">
            <span class="panel-label">Decision History</span>
            <span class="count">{decisions.length}</span>
          </div>
          <div class="history-list">
            {#each decisions as decision}
              <div class="history-item">
                <div class="history-top">
                  <span>{decision.decision_type}</span>
                  <span>{decision.decision_state}</span>
                </div>
                <div class="history-question">{decision.question}</div>
                {#if decision.chosen_option}
                  <div class="history-answer">Answered: {decision.chosen_option}</div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      </div>
    </section>
  {/if}
</div>

<style>
  .objective-detail {
    max-width: 1100px;
    margin: 0 auto;
    padding: 18px 24px 56px;
  }

  .back-btn {
    border: none;
    background: none;
    color: var(--text-dim);
    font: inherit;
    cursor: pointer;
    padding: 0 0 16px;
  }

  .top {
    display: grid;
    grid-template-columns: 1.4fr 0.9fr;
    gap: 22px;
    align-items: start;
    margin-bottom: 22px;
  }

  .eyebrow, .panel-label, .task-kicker {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #8b4d2b;
  }

  .title-block h1 {
    margin: 8px 0 0;
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: clamp(2.2rem, 6vw, 4rem);
    line-height: 0.96;
    font-weight: 400;
    max-width: 11ch;
  }

  .title-block p {
    margin: 16px 0 0;
    max-width: 56ch;
    color: var(--text-dim);
    line-height: 1.65;
  }

  .meta-line {
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 18px;
    color: var(--text-dim);
    font-size: 13px;
  }

  .summary-panel,
  .panel {
    border: 1px solid color-mix(in oklch, var(--border), #b66a42 20%);
    border-radius: 18px;
    background: linear-gradient(180deg, color-mix(in oklch, var(--bg-raised), #b66a42 9%), var(--bg-raised));
    padding: 18px;
  }

  .summary-line {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 10px;
    color: var(--text-dim);
  }

  .summary-panel p {
    margin: 14px 0 0;
    line-height: 1.6;
  }

  .next-callout {
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px solid var(--border);
  }

  .next-callout span {
    display: inline-block;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--text-faint);
  }

  .next-callout p { margin: 8px 0 0; }

  .main-grid {
    display: grid;
    grid-template-columns: 1.3fr 0.8fr;
    gap: 18px;
  }

  .left-column, .right-column {
    display: grid;
    gap: 18px;
    align-content: start;
  }

  .panel-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }

  .count {
    color: var(--text-faint);
    font-size: 12px;
  }

  .empty {
    color: var(--text-dim);
    line-height: 1.55;
    margin: 0;
  }

  .decision-card {
    padding: 14px 0;
    border-top: 1px solid var(--border);
  }

  .decision-card:first-of-type { border-top: none; padding-top: 4px; }

  .decision-type {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-faint);
  }

  .decision-card h3 {
    margin: 8px 0 12px;
    font-size: 1.05rem;
    font-weight: 600;
    line-height: 1.35;
  }

  .decision-options {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .decision-options button {
    padding: 9px 12px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text);
    cursor: pointer;
    font: inherit;
  }

  .decision-options button.selected {
    border-color: #8b4d2b;
    background: color-mix(in oklch, #8b4d2b, transparent 90%);
  }

  .task-stack {
    display: grid;
    gap: 10px;
  }

  .task-card {
    width: 100%;
    display: flex;
    justify-content: space-between;
    gap: 14px;
    align-items: start;
    text-align: left;
    padding: 14px;
    border-radius: 16px;
    border: 1px solid var(--border);
    background: color-mix(in oklch, var(--bg), white 2%);
    color: var(--text);
    cursor: pointer;
  }

  .task-card.orchestrator {
    border-color: color-mix(in oklch, var(--border), #8b4d2b 30%);
    background: color-mix(in oklch, var(--bg), #8b4d2b 4%);
  }

  .task-topline, .task-meta, .task-time {
    color: var(--text-faint);
    font-size: 12px;
  }

  .task-topline {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }

  .task-title {
    margin-top: 4px;
    font-size: 15px;
    line-height: 1.4;
  }

  .task-meta { margin-top: 6px; }

  .task-side {
    display: grid;
    gap: 8px;
    justify-items: end;
  }

  .history-list {
    display: grid;
    gap: 10px;
  }

  .history-item {
    padding: 12px 0;
    border-top: 1px solid var(--border);
  }

  .history-item:first-child { border-top: none; padding-top: 2px; }

  .history-top {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    color: var(--text-faint);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .history-question {
    margin-top: 8px;
    line-height: 1.45;
  }

  .history-answer {
    margin-top: 8px;
    color: var(--text-dim);
    font-size: 13px;
  }

  @media (max-width: 860px) {
    .top, .main-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
