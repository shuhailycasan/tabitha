// spreadsheet engine — view-only workbook windows. One window per desktop file icon;
// every window is bound to a desktop file item — no empty launcher windows.
// Parsing comes from excel-viewer-engine; this knows nothing about the backend.
import { reactive } from 'vue'
import { parseWorkbook } from '../excel-viewer-engine/index.js'
import { windows } from '../windows/engine.js'

const state = reactive({
  windows: [],   // { id: 'excel-N', itemId: string }
  views: {},     // itemId -> { workbook, activeSheet, loading, error }
  dragOver: false,
})
let seq = 0

function createWindow(itemId) {
  const w = { id: 'excel-' + (++seq), itemId }
  state.windows.push(w)
  const st = windows.ensure(w.id)
  // cascade so stacked windows peek out instead of covering each other exactly
  st.x = 48 + ((seq - 1) % 8) * 28
  st.y = 44 + ((seq - 1) % 8) * 24
  return w
}

// Parse an item's File into views[item.id] — once, cached after that.
async function ensureView(item) {
  // NB: read the view back through state.views so we hold the reactive proxy —
  // `v = state.views[id] = {...}` would hand us the raw object and mutations
  // (loading/workbook/error) would never trigger a re-render.
  if (!state.views[item.id]) state.views[item.id] = { workbook: null, activeSheet: 0, loading: false, error: '' }
  const v = state.views[item.id]
  if (v.workbook || v.loading || !item.file) return v
  v.loading = true
  v.error = ''
  try {
    v.workbook = await parseWorkbook(item.file)
    v.activeSheet = 0
  } catch (e) {
    v.error = e.message || 'Could not open that file.'
  } finally {
    v.loading = false
  }
  return v
}

// Open (or focus) the window for a desktop file item.
function openFor(item) {
  let win = state.windows.find(w => w.itemId === item.id)
  if (!win) {
    win = createWindow(item.id)
    ensureView(item)
  }
  windows.restore(win.id)
}

// Dock "Spreadsheet" button: focus the topmost open sheet window or revive a hidden one.
function dockFocus() {
  const open = [...state.windows].reverse().find(w => windows.isOpen(w.id))
  if (open) return windows.focus(open.id)
  if (state.windows.length) return windows.restore(state.windows[0].id)
}

// Drop a file's window + cached view (icon/dataset removed).
function removeFor(itemId) {
  for (const w of state.windows.filter(w => w.itemId === itemId)) windows.destroy(w.id)
  state.windows = state.windows.filter(w => w.itemId !== itemId)
  delete state.views[itemId]
}

function hasOpen() {
  return state.windows.some(w => windows.isOpen(w.id))
}

function selectSheet(itemId, i) {
  const v = state.views[itemId]
  if (v) v.activeSheet = i
}

// Truly close a spreadsheet window: drop its entry so the dock item disappears.
// The file icon and parsed view stay — reopening is instant.
function destroy(id) {
  state.windows = state.windows.filter(w => w.id !== id)
  windows.destroy(id)
}

export const spreadsheet = {
  state, createWindow, ensureView, openFor, removeFor, dockFocus, hasOpen, selectSheet, destroy,
}
