<script setup>
import { desktop } from '../feature/desktop/engine.js'
</script>

<template>
  <div class="toast" :class="{ show: desktop.state.toastVisible }" role="status">
    {{ desktop.state.toast }}
  </div>
</template>
