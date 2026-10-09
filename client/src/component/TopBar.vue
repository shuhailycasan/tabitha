<script setup>
import { desktop } from '../feature/desktop/engine.js'
import mascotWorking from '../assets/tabitha-working.png'

const emit = defineEmits(['upload'])
</script>

<template>
  <header class="topbar">
    <div class="top-left">
      <div class="top-app">
        <img class="logo-small" :src="mascotWorking" alt="Tabitha tortoise mascot">
        <span>Tabitha</span>
      </div>
      <button class="upload-excel" @click="emit('upload')">↑ Upload Excel</button>
    </div>
    <div class="top-right">
      <span class="top-state"><i class="online-dot"></i>Local mode</span>
      <span class="clock">{{ desktop.state.clock }}</span>
      <button class="top-menu" aria-label="System menu" @click="desktop.toast('Tabitha Desktop · local mode')">⋮</button>
    </div>
  </header>
</template>
