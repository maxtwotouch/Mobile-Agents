<script lang="ts">
  import { getRoleVisual } from '../lib/roles'

  let { name, size = 20 }: { name: string | null; size?: number } = $props()

  const visual = $derived(getRoleVisual(name))
</script>

{#if visual}
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill={visual.color}
    class="role-icon"
    style="flex-shrink: 0;"
  >
    <path d={visual.icon} />
  </svg>
{/if}
