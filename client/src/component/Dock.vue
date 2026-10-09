<script setup>
import { windows } from '../feature/windows/engine.js'
import { spreadsheet } from '../feature/spreadsheet/engine.js'
import { files } from '../feature/files/engine.js'
import mascotHappy from '../assets/tabitha-happy.png'

function toggleChat() {
  windows.isOpen('chat') ? windows.focus('chat') : windows.restore('chat')
}
// Taskbar toggle: minimized → restore, focused → minimize, else focus.
function onWindow(w) {
  const st = windows.state.windows[w.id]
  if (!st || st.hidden) return windows.restore(w.id)
  st.active ? windows.minimize(w.id) : windows.focus(w.id)
}
function winLabel(w) {
  return files.byId(w.itemId)?.name || 'Spreadsheet'
}
</script>

<template>
  <nav class="dock" aria-label="Desktop dock">
    <button
      v-for="w in spreadsheet.state.windows" :key="w.id"
      class="dock-win"
      :class="{
        running: windows.isOpen(w.id),
        active: windows.state.windows[w.id]?.active,
        minimized: !windows.isOpen(w.id),
      }"
      :title="winLabel(w)"
      @click="onWindow(w)"
    >
      <span class="excel-mark">X</span><span class="dock-win-label">{{ winLabel(w) }}</span>
    </button>
    <button :class="{ running: windows.isOpen('chat'), active: windows.state.windows.chat?.active }" @click="toggleChat">
      <img :src="mascotHappy" alt=""><span>Tabitha</span>
    </button>
  </nav>
</template>
