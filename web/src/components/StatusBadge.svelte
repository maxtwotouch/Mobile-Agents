<script lang="ts">
  import { statusConfig } from '../lib/roles'

  let { status }: { status: string } = $props()

  const config = $derived(statusConfig[status] || { label: status, color: '#5c564e' })
  const isRunning = $derived(status === 'running')
</script>

<span class="status-badge" style="color: {config.color};">
  {#if isRunning}
    <span class="pulse-dot" style="background: {config.color};"></span>
  {/if}
  {config.label}
</span>

<style>
  .status-badge {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    white-space: nowrap;
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }

  .pulse-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    animation: pulse 2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
</style>
