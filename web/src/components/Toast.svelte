<script lang="ts">
  import { toastMsg } from '../lib/stores.svelte'
</script>

<div class="toast" class:show={toastMsg.visible}>
  {toastMsg.value}
</div>

<style>
  .toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(20px);
    padding: 10px 20px;
    background: #1c1a17;
    border: 1px solid #3a3630;
    border-radius: 6px;
    font-size: 13px;
    color: #d8d0c4;
    opacity: 0;
    transition: opacity 0.25s ease-out, transform 0.25s ease-out;
    pointer-events: none;
    z-index: 100;
    max-width: 90vw;
    text-align: center;
  }
  .toast.show {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
</style>
