<script lang="ts">
  import { login, checkAuthStatus } from '../lib/api'
  import { setAuth, navigate, showToast } from '../lib/stores.svelte'
  import { connectWS } from '../lib/ws'
  import { onMount } from 'svelte'

  let username = $state('admin')
  let password = $state('')
  let error = $state('')
  let loading = $state(false)

  onMount(async () => {
    const disabled = await checkAuthStatus()
    if (disabled) {
      setAuth('_disabled')
      navigate('dashboard')
      connectWS()
    }
  })

  async function handleLogin() {
    if (loading) return
    loading = true
    error = ''
    try {
      const t = await login(username, password)
      setAuth(t)
      navigate('dashboard')
      connectWS()
    } catch (e: any) {
      error = e.message
    } finally {
      loading = false
    }
  }

  function handleKey(e: KeyboardEvent) {
    if (e.key === 'Enter') handleLogin()
  }
</script>

<div class="login-container">
  <div class="login-inner">
    <h1 class="login-title">agents</h1>
    <p class="login-sub">orchestration hub</p>

    <div class="login-form">
      <div class="field">
        <label for="username">Username</label>
        <input id="username" bind:value={username} autocomplete="username" />
      </div>

      <div class="field">
        <label for="password">Password</label>
        <input
          id="password"
          type="password"
          bind:value={password}
          autocomplete="current-password"
          onkeydown={handleKey}
          placeholder="Enter password"
        />
      </div>

      <button class="login-btn" onclick={handleLogin} disabled={loading}>
        {loading ? 'Signing in...' : 'Sign in'}
      </button>

      {#if error}
        <p class="login-error">{error}</p>
      {/if}
    </div>
  </div>
</div>

<style>
  .login-container {
    min-height: 100dvh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  .login-inner {
    width: 100%;
    max-width: 320px;
  }

  .login-title {
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: 3rem;
    font-weight: 400;
    font-style: italic;
    letter-spacing: -0.03em;
    color: var(--text);
    line-height: 1;
  }

  .login-sub {
    font-size: 12px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-faint);
    margin-top: 6px;
    margin-bottom: 40px;
  }

  .field {
    margin-bottom: 16px;
  }

  .field label {
    display: block;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 6px;
  }

  .field input {
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

  .field input:focus {
    outline: none;
    border-color: var(--accent-dim);
  }

  .login-btn {
    width: 100%;
    padding: 11px;
    margin-top: 8px;
    background: var(--accent);
    border: 1px solid var(--accent);
    border-radius: 4px;
    color: var(--bg);
    font-family: var(--sans);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .login-btn:hover { opacity: 0.85; }
  .login-btn:disabled { opacity: 0.5; cursor: wait; }

  .login-error {
    color: var(--red);
    font-size: 13px;
    margin-top: 10px;
  }
</style>
