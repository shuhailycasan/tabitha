<script setup>
// Backdrop upload prompt — not a window. Shows for ~20s after load, then fades
// out completely (CSS animation handles the hide). Upload stays available via
// the top-bar button and drag-drop.
import { spreadsheet } from '../feature/spreadsheet/engine.js'
import mascotWorking from '../assets/tabitha-working.png'

const emit = defineEmits(['upload'])
</script>

<template>
  <div class="upload-prompt" :class="{ 'drag-over': spreadsheet.state.dragOver }">
    <img class="big-logo" :src="mascotWorking" alt="Tabitha tortoise mascot">
    <h1>Upload an Excel workbook</h1>
    <p>Drop it anywhere on the desktop, or pick a file. Tabitha can answer questions about it.</p>
    <button class="primary" @click="emit('upload')">Upload Excel</button>
    <span class="drop-note">.xlsx, .csv, or .tsv · up to 20 MB</span>
  </div>
</template>
