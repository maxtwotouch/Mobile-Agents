<script lang="ts">
  import { wsConnected } from '../lib/stores.svelte'
</script>

<span class="dot" class:live={wsConnected.value} title={wsConnected.value ? 'Connected' : 'Disconnected'}></span>

<style>
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #5c564e;
    transition: background 0.4s;
    display: inline-block;
  }
  .dot.live {
    background: #6b9a5c;
  }
</style>
