# System Architecture

## Purpose

`mobile_agents` is evolving from a task launcher into a developer-facing control plane for coding agents.

The system should let a technical user:

- define engineering objectives
- create and target explicit tasks
- dispatch agent runs against repos and branches
- inspect run history, thread state, failures, and outputs
- route work across specialized roles
- make approvals and follow-up decisions at clear control points

The system should abstract transport details like subprocesses, worktrees, and provider-specific resume mechanics.
It should not abstract away engineering intent such as task kind, branch target, review scope, or failure reason.

## Design Principles

### Control Plane, Not Prompt Box

The core object is not "a prompt". The core object is "a tracked engineering task with execution history".

### Explicit Over Magical

The user should always be able to see:

- what kind of task this is
- what target it is about
- what role is handling it
- what state it is in
- what happened during the last run
- what the recommended next action is

### Transport Is Implementation Detail

Threads, runners, subprocesses, and worktrees matter operationally, but they are not the product surface.

### Workflow State And Runtime State Must Be Separate

Human coordination state and machine execution state are different concerns and must not be collapsed into one field.

### Orchestration Must Be Auditable

If an orchestrator proposes or spawns work, the system must record what it decided, why, and what the user approved.

## Top-Level Domain Model

The system is organized around six first-class concepts:

1. Objective
2. Task
3. Thread
4. Run
5. Decision
6. Repo

### Objective

An Objective is the top-level engineering goal.

Examples:

- Review the raft implementation on branch `aika-generic-framework`
- Fix the issues found in the reviewer output
- Prepare branch `feature/x` for release

Objectives are where orchestration lives.
An Objective may own many Tasks and many Decisions.

#### Objective Fields

- `id`
- `title`
- `description`
- `repo_id`
- `created_by`
- `priority`
- `objective_state`
- `summary`
- `recommended_next_action`
- `created_at`
- `updated_at`

#### Objective States

- `draft`
- `active`
- `waiting_for_user`
- `blocked`
- `completed`
- `failed`
- `cancelled`

### Task

A Task is a concrete unit of work under an Objective.

Examples:

- Review branch diff `feature/x` against `main`
- Implement fixes for reviewer findings
- Audit current repo head for concurrency issues
- Validate test coverage after implementation

Tasks are the main unit of dispatch.

#### Task Fields

- `id`
- `objective_id`
- `parent_task_id`
- `title`
- `description`
- `task_kind`
- `role`
- `target_type`
- `repo_id`
- `target_branch`
- `base_branch`
- `commit_start`
- `commit_end`
- `path_scope`
- `workflow_state`
- `runtime_state`
- `thread_id`
- `active_run_id`
- `priority`
- `blocked_reason`
- `result_summary`
- `failure_reason`
- `next_action_hint`
- `created_at`
- `updated_at`

#### Task Kinds

- `implement`
- `review`
- `audit`
- `investigate`
- `fix`
- `refactor`
- `qa`
- `release`
- `orchestrate`

#### Target Types

- `repo_head`
- `branch_diff`
- `commit_range`
- `workspace_changes`
- `file_scope`
- `issue_followup`

### Thread

A Thread is the durable conversational context for an agent task.

For providers with native thread IDs, the Thread maps directly to the provider thread.
For providers without native thread IDs, the Thread may be emulated by persisted transcript state.

#### Thread Fields

- `id`
- `task_id`
- `provider`
- `provider_thread_id`
- `thread_state`
- `context_summary`
- `last_message_at`
- `created_at`
- `updated_at`

#### Thread States

- `active`
- `idle`
- `closed`
- `failed`

### Run

A Run is one execution attempt for a Task.

A Task may have many Runs over time.

#### Run Fields

- `id`
- `task_id`
- `thread_id`
- `provider`
- `runner_id`
- `trigger_type`
- `run_state`
- `dispatch_snapshot`
- `prompt_summary`
- `started_at`
- `finished_at`
- `exit_code`
- `error_type`
- `error_message`
- `output_summary`
- `raw_output_ref`

#### Trigger Types

- `manual_start`
- `resume`
- `message`
- `retry`
- `handoff`
- `orchestrator_dispatch`

#### Run States

- `queued`
- `starting`
- `running`
- `completed`
- `failed`
- `cancelled`
- `timed_out`

### Decision

A Decision records a question, choice, or approval point.

This is what allows the system to support orchestration without becoming opaque.

#### Decision Fields

- `id`
- `objective_id`
- `task_id`
- `decision_type`
- `decision_state`
- `question`
- `options`
- `recommended_option`
- `chosen_option`
- `answered_by`
- `answered_at`
- `created_at`

#### Decision Types

- `clarification`
- `approval`
- `branch_selection`
- `next_action`
- `handoff`
- `retry_policy`

#### Decision States

- `open`
- `answered`
- `expired`
- `cancelled`

### Repo

A Repo is the version-controlled workspace target.

#### Repo Fields

- `id`
- `name`
- `path`
- `remote_url`
- `default_branch`
- `branches_snapshot`
- `last_fetched_at`

## State Machine

The system needs strict state semantics.

### Task Workflow State

Workflow state describes the human coordination state.

Allowed values:

- `draft`
- `ready`
- `in_progress`
- `waiting_for_user`
- `blocked`
- `needs_review`
- `approved`
- `completed`
- `failed`
- `cancelled`

#### Meaning

- `draft`: insufficiently specified, not dispatchable
- `ready`: dispatchable, no active blocker
- `in_progress`: work is underway conceptually
- `waiting_for_user`: paused pending user decision
- `blocked`: cannot proceed due to dependency or failure
- `needs_review`: output exists and requires inspection or approval
- `approved`: reviewed and accepted
- `completed`: done
- `failed`: no viable continuation without intervention
- `cancelled`: intentionally abandoned

### Task Runtime State

Runtime state describes execution only.

Allowed values:

- `idle`
- `queued`
- `starting`
- `running`
- `stopping`
- `stopped`
- `failed`

#### Meaning

- `idle`: no active run
- `queued`: accepted for execution
- `starting`: dispatch in progress
- `running`: active run
- `stopping`: shutdown requested
- `stopped`: intentionally halted
- `failed`: runtime failure on the current active run

### Valid Combined States

Examples of valid combinations:

- `ready` + `idle`
- `in_progress` + `queued`
- `in_progress` + `running`
- `waiting_for_user` + `idle`
- `needs_review` + `idle`
- `failed` + `failed`

Examples of invalid combinations:

- `completed` + `running`
- `draft` + `running`
- `cancelled` + `running`

### Valid Workflow Transitions

- `draft -> ready`
- `ready -> in_progress`
- `in_progress -> waiting_for_user`
- `in_progress -> needs_review`
- `in_progress -> blocked`
- `waiting_for_user -> ready`
- `waiting_for_user -> cancelled`
- `blocked -> ready`
- `blocked -> failed`
- `needs_review -> approved`
- `needs_review -> in_progress`
- `needs_review -> failed`
- `approved -> completed`
- `approved -> in_progress`
- `any nonterminal -> cancelled`

### Valid Runtime Transitions

- `idle -> queued`
- `queued -> starting`
- `starting -> running`
- `running -> idle`
- `running -> stopping`
- `running -> failed`
- `stopping -> stopped`
- `stopped -> queued`
- `failed -> queued`

## Orchestration Model

The orchestrator is a first-class role, not a hidden meta-agent.

### Responsibilities

The orchestrator may:

- clarify user intent
- create Objectives
- decompose Objectives into Tasks
- assign Roles
- recommend next actions
- create Decisions
- spawn child Tasks with explicit traceability
- summarize outcomes

The orchestrator should not:

- silently mutate task targets
- silently spawn excessive work
- auto-approve risky actions
- hide why it made a recommendation

### Authority Levels

#### Level 1: Recommend

The orchestrator only suggests actions.

#### Level 2: Prepare

The orchestrator drafts task graphs or follow-up tasks for explicit user approval.

#### Level 3: Auto-dispatch Within Policy

The orchestrator may automatically dispatch narrowly scoped safe work under user-configured rules.

The system should begin with Level 1 and Level 2.

## Task Relationships

Tasks need explicit relationships.

### Parent / Child

Used for:

- a review spawning a fix task
- an implementation spawning QA
- an orchestrator spawning specialized worker tasks

### Dependencies

Used for:

- QA depends on implementation completion
- release depends on approval
- follow-up review depends on fix completion

### Handoffs

Used for:

- reviewer -> developer
- developer -> QA
- architect -> developer

The handoff should record:

- source task
- destination task
- reason
- findings or summary that motivated it

## Prompt Construction

Prompt generation should be metadata-driven, not user-text-only.

Inputs:

- task kind
- target type
- repo
- branch target
- base branch
- commit range
- role
- user description
- expected output shape

Example:

A `review` task with `target_type=branch_diff` should generate a very different prompt frame than an `implement` task with `target_type=repo_head`.

## Review Semantics

Review must be explicit.

There should be no generic "review this" ambiguity.

Every review task should encode:

- what is being reviewed
- relative to what baseline
- what output format is expected

Review target examples:

- repo head audit
- branch diff vs base
- commit range
- workspace changes

## Failure Model

Failures must be surfaced at the correct level.

### Runtime Failure

Examples:

- CLI exited with code 1
- runner crashed
- prompt was invalid
- transport failed

These primarily affect:

- Run
- runtime_state

### Workflow Failure

Examples:

- task target invalid
- branch missing
- review cannot proceed without user clarification
- task result invalid for requested objective

These affect:

- Task
- workflow_state

The UI should show:

- raw failure detail
- summarized failure reason
- recommended next actions

## UI Surfaces

The UI should expose the model clearly.

### Objectives View

Shows:

- objective title
- status
- repo
- active tasks
- waiting decisions
- current recommendation

### Task Detail

Shows:

- task kind
- target type
- target branch / base branch
- role
- workflow state
- runtime state
- thread summary
- run history
- messages
- updates
- decisions
- next recommended action

### Run Detail

Shows:

- run trigger
- start / finish time
- exit code
- output summary
- raw output
- failure detail

### Decision View

Shows:

- question
- options
- recommended option
- what spawned the decision
- what happens next depending on choice

## Services

The application should conceptually be split into these services:

### Objective Service

Creates, updates, and summarizes top-level goals.

### Task Service

Validates task metadata, target semantics, state transitions, and relationships.

### Thread Service

Maintains provider-specific thread identity and continuity.

### Run Service

Dispatches runs, records results, and manages runtime transitions.

### Decision Service

Creates and resolves structured clarification and approval points.

### Orchestration Service

Handles decomposition, recommendation, and task spawning.

### Repo Service

Manages repo metadata, branches, worktrees, and target resolution.

## API Direction

Key API concepts that should exist:

- `POST /objectives`
- `GET /objectives`
- `GET /objectives/{id}`
- `POST /tasks`
- `PATCH /tasks/{id}`
- `POST /tasks/{id}/start`
- `POST /tasks/{id}/stop`
- `GET /tasks/{id}/runs`
- `GET /tasks/{id}/thread`
- `POST /tasks/{id}/messages`
- `GET /tasks/{id}/decisions`
- `POST /decisions/{id}/answer`

The API should be task- and decision-oriented, not transport-oriented.

## Migration Path

Recommended implementation order:

1. add Objective model
2. add `task_kind`
3. add `target_type`
4. tighten workflow/runtime enums and transition validation
5. expand Run metadata
6. add Decision model
7. add parent/child and dependency semantics
8. add prompt builder based on task metadata
9. add orchestration service

## Non-Goals

The system should not become:

- a generic terminal proxy
- a generic multi-agent framework
- a replacement for GitHub, CI, or issue tracking
- an opaque autonomous manager

It should remain:

- a developer control plane for agent-mediated engineering work

## Definition Of Success

The architecture is successful when the system can represent and execute a flow like this without ambiguity:

1. Create Objective: review branch `feature/x`
2. Create Task: `review`, target `branch_diff`, base `main`, role `reviewer`
3. Dispatch Run: provider `codex`, thread resumed if available
4. Review finishes: Task enters `needs_review`, Run enters `completed`
5. Orchestrator creates Decision: spawn fix task?
6. User answers yes
7. Child Task created: `fix`, same target branch
8. Developer run completes
9. Follow-up review task created
10. Objective eventually moves to `completed`

At each step, the system should be able to answer:

- what is happening
- why it is happening
- what the current state is
- what happened previously
- what should happen next
