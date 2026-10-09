// windows engine — floating window manager: z-order, focus, drag, minimize/maximize/close.
import { reactive } from 'vue'

let zTop = 10
const state = reactive({ windows: {} })

function ensure(id) {
  if (!state.windows[id]) {
    state.windows[id] = { z: ++zTop, active: false, hidden: false, maximized: false, x: null, y: null }
  }
  return state.windows[id]
}

function focus(id) {
  const w = ensure(id)
  for (const k in state.windows) state.windows[k].active = false
  w.active = true
  w.z = ++zTop
}

function minimize(id) { ensure(id).hidden = true }
function close(id) { minimize(id) }

function restore(id) {
  const w = ensure(id)
  w.hidden = false
  focus(id)
}

function toggleMax(id) {
  const w = ensure(id)
  w.maximized = !w.maximized
  focus(id)
}

function restoreAll() {
  for (const id in state.windows) restore(id)
}

function isOpen(id) {
  const w = state.windows[id]
  return !!w && !w.hidden
}

function destroy(id) { delete state.windows[id] }

// Drag from a window's header. Reads the live position on first drag, then tracks x/y in px.
function startDrag(id, e, winEl) {
  if (e.button !== 0 || e.target.closest('.controls') || e.target.closest('button')) return
  const w = ensure(id)
  if (w.maximized) return
  focus(id)

  const r = winEl.getBoundingClientRect()
  const bound = winEl.parentElement.getBoundingClientRect()
  const dx = e.clientX - r.left
  const dy = e.clientY - r.top
  w.x = r.left - bound.left
  w.y = r.top - bound.top

  // Drag via a composited CSS transform on the element itself — writing reactive
  // state per pointermove would re-render the whole window (table included) and
  // force a layout pass each frame. Reactive x/y is committed once on release.
  let pending = null
  const move = ev => {
    const x = Math.max(0, Math.min(bound.width - winEl.offsetWidth, ev.clientX - bound.left - dx))
    const y = Math.max(0, Math.min(bound.height - 60, ev.clientY - bound.top - dy))
    winEl.style.left = '0px'
    winEl.style.top = '0px'
    winEl.style.transform = `translate(${x}px, ${y}px)`
    pending = { x, y }
  }
  const done = () => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', done)
    window.removeEventListener('pointercancel', done)
    if (pending) {
      winEl.style.transform = '' // hand position back to the reactive left/top binding
      w.x = pending.x
      w.y = pending.y
    }
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', done)
  window.addEventListener('pointercancel', done)
}

export const windows = { state, ensure, focus, minimize, close, restore, toggleMax, restoreAll, isOpen, destroy, startDrag }
