// files engine — desktop file icons. Keeps the File handle so an opened workbook can be
// re-viewed or dragged onto Tabitha to make it the chat context. Session-scoped, like the backend.
import { reactive } from 'vue'

const ICON_W = 84, ICON_H = 96
const GRID_X = 100, GRID_Y = 106, MARGIN = 12

const state = reactive({
  items: [],          // { id, name, file: File|null, datasetId: string|null, x, y }
  overChat: false,    // an icon is being dragged over the chat window
  ghost: null,        // { x, y } snap-preview cell while an icon is dragged
})

let seq = 0

// ---- IndexedDB persistence: File objects structured-clone straight into IDB,
// so desktop icons survive reloads and stay viewable/draggable forever.
const DB = 'tabitha-desktop', STORE = 'files'
let dbp = null
function db() {
  dbp ??= new Promise((res, rej) => {
    const req = indexedDB.open(DB, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(STORE)
    req.onsuccess = () => res(req.result)
    req.onerror = () => rej(req.error)
  })
  return dbp
}
async function persist(item) {
  try {
    const d = await db()
    d.transaction(STORE, 'readwrite').objectStore(STORE).put(
      { id: item.id, name: item.name, file: item.file, datasetId: item.datasetId, x: item.x, y: item.y },
      item.id)
  } catch { /* persistence is best-effort */ }
}
async function unpersist(id) {
  try { (await db()).transaction(STORE, 'readwrite').objectStore(STORE).delete(id) } catch {}
}
// Call once at startup. Returns stored items; caller decides what to re-add.
async function loadPersisted() {
  try {
    const d = await db()
    return await new Promise(res => {
      const rq = d.transaction(STORE).objectStore(STORE).getAll()
      rq.onsuccess = () => res(rq.result || [])
      rq.onerror = () => res([])
    })
  } catch { return [] }
}

// Windows-style placement: first free grid cell, filling the leftmost column
// top→bottom before moving to the next column.
function firstFreeCell() {
  const taken = new Set()
  for (const i of state.items) {
    if (i.x == null) continue
    taken.add(Math.round((i.x - MARGIN) / GRID_X) + ',' + Math.round((i.y - MARGIN) / GRID_Y))
  }
  const h = window.innerHeight - 132 // workspace ≈ viewport minus topbar + dock
  const rows = Math.max(1, Math.floor((h - ICON_H - MARGIN) / GRID_Y) + 1)
  for (let gx = 0; ; gx++)
    for (let gy = 0; gy < rows; gy++)
      if (!taken.has(gx + ',' + gy)) return { x: MARGIN + gx * GRID_X, y: MARGIN + gy * GRID_Y }
}

// The grid cell (top-left px) an icon at x/y would snap to, clamped to bounds.
function snapCell(x, y, bound) {
  const maxGx = Math.max(0, Math.floor((bound.width - ICON_W - MARGIN) / GRID_X))
  const maxGy = Math.max(0, Math.floor((bound.height - ICON_H - MARGIN) / GRID_Y))
  const gx = Math.max(0, Math.min(maxGx, Math.round((x - MARGIN) / GRID_X)))
  const gy = Math.max(0, Math.min(maxGy, Math.round((y - MARGIN) / GRID_Y)))
  return { x: MARGIN + gx * GRID_X, y: MARGIN + gy * GRID_Y }
}

// cyan-green "new here" highlight — fades out after a few seconds or on first touch.
function flash(item) {
  item.fresh = true
  setTimeout(() => { item.fresh = false }, 4000)
}

// Register a locally opened file. `file` may be a File (re-viewable) or null (server-side dataset only).
function add({ name, file = null, datasetId = null }) {
  const dupe = state.items.find(i =>
    (datasetId && i.datasetId === datasetId) ||
    (file && i.file && i.file.name === file.name && i.file.size === file.size && i.file.lastModified === file.lastModified))
  if (dupe) {
    if (datasetId && !dupe.datasetId) dupe.datasetId = datasetId
    if (file && !dupe.file) dupe.file = file
    flash(dupe)
    persist(dupe)
    return dupe
  }
  const item = { id: 'file-' + (++seq), name, file, datasetId, ...firstFreeCell() }
  state.items.push(item)
  flash(item)
  persist(item)
  return item
}

// Bring back icons saved in IndexedDB (called once at startup).
async function restore() {
  for (const rec of await loadPersisted()) {
    if (state.items.some(i => i.id === rec.id)) continue
    state.items.push({ file: null, datasetId: null, fresh: false, ...rec })
    const n = Number((rec.id.match(/file-(\d+)/) || [])[1])
    if (n > seq) seq = n // keep generated ids unique
  }
}

function byId(id) {
  return state.items.find(i => i.id === id) || null
}

function remove(id) {
  state.items = state.items.filter(i => i.id !== id)
  unpersist(id)
}

function removeByDataset(datasetId) {
  for (const i of state.items.filter(i => i.datasetId === datasetId)) unpersist(i.id)
  state.items = state.items.filter(i => i.datasetId !== datasetId)
}

// Icon drag: pointermove updates x/y; on pointerup we check what's under the cursor
// (the icon gets pointer-events:none while dragging so elementFromPoint sees through it).
function startIconDrag(id, e, el, { onDropOnChat } = {}) {
  if (e.button !== 0 || e.target.closest('button')) return
  const f = state.items.find(i => i.id === id)
  if (!f) return

  f.fresh = false
  const bound = el.parentElement.getBoundingClientRect()
  const r = el.getBoundingClientRect()
  const dx = e.clientX - r.left, dy = e.clientY - r.top
  const orig = { x: f.x, y: f.y }
  f.x = r.left - bound.left
  f.y = r.top - bound.top

  let moved = false // click vs drag — pointer-events must stay on for click/dblclick to fire
  const move = ev => {
    if (!moved) {
      if (Math.abs(ev.clientX - e.clientX) < 4 && Math.abs(ev.clientY - e.clientY) < 4) return
      moved = true
      el.style.pointerEvents = 'none' // now dragging — let elementFromPoint see through
      el.style.zIndex = 2000          // above windows while dragging
    }
    f.x = Math.max(0, Math.min(bound.width - ICON_W, ev.clientX - bound.left - dx))
    f.y = Math.max(0, Math.min(bound.height - ICON_H, ev.clientY - bound.top - dy))
    state.overChat = !!document.elementFromPoint(ev.clientX, ev.clientY)?.closest('.chat-window')
    state.ghost = state.overChat ? null : snapCell(f.x, f.y, bound)
  }
  const done = ev => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', done)
    window.removeEventListener('pointercancel', done)
    el.style.pointerEvents = ''
    el.style.zIndex = ''
    state.overChat = false
    state.ghost = null
    if (!moved) { // it was a click — leave the icon where it was
      f.x = orig.x; f.y = orig.y
      return
    }
    const overChat = !!document.elementFromPoint(ev.clientX, ev.clientY)?.closest('.chat-window')
    if (overChat && onDropOnChat) {
      f.x = orig.x; f.y = orig.y // dropped "into" chat — icon snaps back to its spot
      onDropOnChat(f)
    } else {
      Object.assign(f, snapCell(f.x, f.y, bound)) // grid snap — nearest cell, clamped
      persist(f) // remember the new spot across reloads
    }
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', done)
  window.addEventListener('pointercancel', done)
}

export const files = { state, add, byId, remove, removeByDataset, startIconDrag, restore, persist }
