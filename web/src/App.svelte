<script lang="ts">
  import { onMount } from 'svelte'
  import { nav, token, navigate } from './lib/stores.svelte'
  import { checkAuthStatus } from './lib/api'
  import { connectWS } from './lib/ws'
  import Login from './views/Login.svelte'
  import Dashboard from './views/Dashboard.svelte'
  import CreateTask from './views/CreateTask.svelte'
  import TaskDetail from './views/TaskDetail.svelte'
  import CreateObjective from './views/CreateObjective.svelte'
  import ObjectiveDetail from './views/ObjectiveDetail.svelte'
  import Toast from './components/Toast.svelte'

  onMount(async () => {
    const authDisabled = await checkAuthStatus()
    if (authDisabled) {
      token.value = '_disabled'
      localStorage.setItem('ma_token', '_disabled')
      navigate('dashboard')
      connectWS()
    } else if (token.value) {
      navigate('dashboard')
      connectWS()
    } else {
      navigate('login')
    }
  })
</script>

{#if nav.view === 'login'}
  <Login />
{:else if nav.view === 'dashboard'}
  <Dashboard />
{:else if nav.view === 'create'}
  <CreateTask />
{:else if nav.view === 'orchestrate'}
  <CreateObjective />
{:else if nav.view === 'detail' && nav.taskId}
  <TaskDetail taskId={nav.taskId} />
{:else if nav.view === 'objective' && nav.objectiveId}
  <ObjectiveDetail objectiveId={nav.objectiveId} />
{/if}

<Toast />
