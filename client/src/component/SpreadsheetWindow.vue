<script setup>
// Spreadsheet window — one per desktop file (win.itemId), or an untitled launcher (itemId=null).
// View-only rendering powered by excel-viewer-engine via the spreadsheet engine.
import { ref, computed } from 'vue'
import OsWindow from './OsWindow.vue'
import ThinkSprite from './ThinkSprite.vue'
import { spreadsheet } from '../feature/spreadsheet/engine.js'
import { files } from '../feature/files/engine.js'
import { columnName, viewSlice } from '../feature/excel-viewer-engine/index.js'
import mascotWorking from '../assets/tabitha-working.png'

const props = defineProps({
  win: { type: Object, required: true }, // { id, itemId }
})
const emit = defineEmits(['attach-file'])

const attachInput = ref(null)

const item = computed(() => (props.win.itemId ? files.byId(props.win.itemId) : null))
const view = computed(() => (item.value ? spreadsheet.state.views[item.value.id] : null))
const wb = computed(() => view.value?.workbook || null)
const sheet = computed(() => wb.value?.sheets[view.value.activeSheet] || null)
const slice = computed(() => (sheet.value ? viewSlice(sheet.value) : { rows: [], cols: 0, truncated: false }))
const colHeaders = computed(() => Array.from({ length: slice.value.cols }, (_, i) => columnName(i)))
const title = computed(() => item.value?.name || 'Spreadsheet')

function pickAttach() { attachInput.value?.click() }
function onPickAttach() {
  const f = attachInput.value?.files?.[0]
  attachInput.value.value = ''
  if (f && item.value) emit('attach-file', item.value, f)
}
</script>

<template>
  <OsWindow :id="win.id" class="excel-window" :aria-label="`Spreadsheet: ${title}`" content-class="excel-body" @close="spreadsheet.destroy(win.id)">
    <template #title>
      <span class="window-icon">
        <svg viewBox="0 0 24 24"><path d="M4 4.5h9l6 6v9A1.5 1.5 0 0 1 17.5 21h-12A1.5 1.5 0 0 1 4 19.5v-15Z"/><path d="M13 5v6h6M8 14l4 5m0-5-4 5"/></svg>
      </span>
      <span>{{ title }}</span>
    </template>

    <div class="excel-area">
      <div v-if="!item" class="empty-sheet"><p>This file was removed.</p></div>

      <!-- bound to a server-only dataset: no local File to render -->
      <div v-else-if="!item.file" class="empty-sheet" :class="{ 'drag-over': spreadsheet.state.dragOver }">
        <img class="big-logo" :src="mascotWorking" alt="Tabitha tortoise mascot">
        <h1>{{ item.name }}</h1>
        <p>Tabitha can already answer questions about this file. To view it here, pick the file from your device.</p>
        <button class="primary" @click="pickAttach">Pick file to view</button>
      </div>

      <div v-else-if="view?.loading" class="empty-sheet">
        <ThinkSprite class="loading-sprite" />
        <p>Reading {{ item.name }}…</p>
      </div>
      <div v-else-if="view?.error" class="empty-sheet">
        <h1>Could not open that file</h1>
        <p>{{ view.error }}</p>
        <button class="secondary" @click="pickAttach">Try another file</button>
      </div>

      <div v-else-if="wb" class="sheet-holder visible">
        <table class="sheet-table">
          <thead>
            <tr>
              <th class="row-head"></th>
              <th v-for="h in colHeaders" :key="h">{{ h }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, r) in slice.rows" :key="r">
              <th class="row-head">{{ r + 1 }}</th>
              <td v-for="c in slice.cols" :key="c" :title="row[c - 1] ?? ''">{{ row[c - 1] ?? '' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="slice.truncated" class="truncated-note">Showing first {{ slice.rows.length }} rows</div>
      </div>
    </div>

    <div v-if="wb && wb.sheets.length > 1" class="sheet-tabs">
      <button
        v-for="(s, i) in wb.sheets" :key="i"
        class="sheet-tab" :class="{ active: i === view.activeSheet }"
        @click="spreadsheet.selectSheet(item.id, i)"
      >{{ s.name }}</button>
    </div>

    <input ref="attachInput" class="file-input" type="file" accept=".xlsx,.csv,.tsv" @change="onPickAttach">
  </OsWindow>
</template>
