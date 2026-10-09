<script setup>
// Tabitha Desktop — a Linux-style workspace: wallpaper bar, floating windows, dock, file icons.
// Feature logic lives in src/feature/*/engine.js; this file only wires them together.
import { ref, onMounted } from 'vue'
import TopBar from './component/TopBar.vue'
import UploadPrompt from './component/UploadPrompt.vue'
import SpreadsheetWindow from './component/SpreadsheetWindow.vue'
import ChatWindow from './component/ChatWindow.vue'
import DesktopIcon from './component/DesktopIcon.vue'
import Dock from './component/Dock.vue'
import Toast from './component/Toast.vue'
import ConfirmModal from './component/ConfirmModal.vue'
import { windows } from './feature/windows/engine.js'
import { desktop } from './feature/desktop/engine.js'
import { datasets } from './feature/datasets/engine.js'
import { spreadsheet } from './feature/spreadsheet/engine.js'
import { files } from './feature/files/engine.js'

const SERVER_UPLOAD_EXTS = ['xlsx', 'xls', 'csv'] // what the backend accepts
const picker = ref(null)
const pendingRemove = ref(null) // file item awaiting delete confirmation

async function uploadForChat(file) {
  const ext = file.name.split('.').pop().toLowerCase()
  if (!SERVER_UPLOAD_EXTS.includes(ext)) {
    desktop.toast('Viewing locally — Tabitha can only query .xlsx and .csv files')
    return null
  }
  const ds = await datasets.upload(file)
  if (!ds && datasets.state.error) desktop.toast(datasets.state.error)
  return ds?.id || null
}

// One call per file: desktop icon (highlighted) + upload for Tabitha.
// Does NOT open a window — double-click the icon to view it.
async function openFiles(list) {
  for (const file of list) {
    const datasetId = await uploadForChat(file)
    files.add({ name: file.name, file, datasetId })
    desktop.toast(file.name + ' is on your desktop — double-click to open')
  }
}

function openPicker() { picker.value?.click() }
function onPicked() {
  const list = [...(picker.value?.files || [])]
  picker.value.value = ''
  if (list.length) openFiles(list)
}

// Pick a file from disk for a server-side dataset icon so it becomes viewable.
async function attachFile(item, file) {
  item.file = file
  spreadsheet.ensureView(item)
  if (!item.datasetId) item.datasetId = await uploadForChat(file)
  files.persist(item)
}

function onDrop(e) {
  spreadsheet.state.dragOver = false
  const list = [...e.dataTransfer.files]
  if (list.length) openFiles(list)
}

// Confirmed delete: window + icon + IndexedDB record + server dataset (if any).
async function removeFile(item) {
  pendingRemove.value = null
  spreadsheet.removeFor(item.id)
  if (item.datasetId) {
    try { await datasets.remove(item.datasetId) }
    catch { desktop.toast('Server copy may still exist — backend unreachable') }
  }
  files.remove(item.id)
  desktop.toast('Removed ' + item.name)
}

// Seed the bundled sample workbooks as desktop icons on first run —
// restored icons/datasets already on the desktop are skipped by name.
const SAMPLES = ['sample_grades.xlsx', 'sample_attendance.xlsx', 'sample_tests.xlsx']
async function seedSamples() {
  for (const name of SAMPLES) {
    if (files.state.items.some(i => i.name === name)) continue
    try {
      const res = await fetch('/samples/' + name)
      if (!res.ok) continue
      const file = new File([await res.blob()], name)
      const datasetId = await uploadForChat(file)
      files.add({ name, file, datasetId })
    } catch { /* samples are best-effort */ }
  }
}

function attachToChat(item) {
  windows.restore('chat')
  if (!item.datasetId) {
    desktop.toast(`Tabitha can't query “${item.name}” — it was never uploaded`)
    return
  }
  datasets.select(item.datasetId)
  desktop.toast(`Tabitha will answer about “${item.name}”`)
}

onMounted(async () => {
  desktop.start()
  await files.restore() // icons + File objects saved in IndexedDB from previous sessions
  await datasets.refresh()
  // datasets already on the server get desktop icons too (view needs a local re-open)
  for (const d of datasets.state.list) files.add({ name: d.name, datasetId: d.id })
  seedSamples()
})
</script>

<template>
  <div class="desktop">
    <TopBar @upload="openPicker" />

    <main
      class="workspace"
      @dragover.prevent="spreadsheet.state.dragOver = true"
      @dragleave="spreadsheet.state.dragOver = false"
      @drop.prevent="onDrop"
    >
      <UploadPrompt @upload="openPicker" />
      <div
        v-if="files.state.ghost" class="grid-ghost"
        :style="{ left: files.state.ghost.x + 'px', top: files.state.ghost.y + 'px' }"
      ></div>
      <DesktopIcon
        v-for="f in files.state.items" :key="f.id" :item="f"
        @open="spreadsheet.openFor" @drop-on-chat="attachToChat"
        @remove="pendingRemove = $event"
      />
      <SpreadsheetWindow
        v-for="w in spreadsheet.state.windows" :key="w.id" :win="w"
        @attach-file="attachFile"
      />
      <ChatWindow />
    </main>

    <Dock />
    <Toast />
    <ConfirmModal
      v-if="pendingRemove"
      title="Remove file?"
      :message="`Remove “${pendingRemove.name}” from the desktop${pendingRemove.datasetId ? ' and delete its uploaded copy' : ''}?`"
      confirm-label="Remove"
      @confirm="removeFile(pendingRemove)"
      @cancel="pendingRemove = null"
    />
    <input ref="picker" class="file-input" type="file" accept=".xlsx,.csv,.tsv" multiple @change="onPicked">
  </div>
</template>
