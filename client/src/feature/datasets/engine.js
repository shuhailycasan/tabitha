// datasets engine — server-side workbooks: list, upload, delete, active selection.
// These are the datasets the chat backend can answer questions about.
import { reactive, computed } from 'vue'

const state = reactive({ list: [], activeId: null, uploading: false, error: '' })
const active = computed(() => state.list.find(d => d.id === state.activeId) || null)

async function refresh() {
  try {
    const res = await fetch('/api/datasets')
    state.list = await res.json()
    if (!state.activeId && state.list.length) state.activeId = state.list[0].id
    if (state.activeId && !state.list.some(d => d.id === state.activeId)) {
      state.activeId = state.list[0]?.id || null
    }
  } catch (e) {
    state.error = 'Could not reach the server.'
  }
}

async function upload(file) {
  state.uploading = true
  state.error = ''
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch('/api/upload', { method: 'POST', body: fd })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || 'Upload failed')
    state.list.push(data)
    state.activeId = data.id
    return data
  } catch (e) {
    state.error = e.message
    return null
  } finally {
    state.uploading = false
  }
}

async function remove(id) {
  await fetch('/api/datasets/' + id, { method: 'DELETE' })
  state.list = state.list.filter(d => d.id !== id)
  if (state.activeId === id) state.activeId = state.list[0]?.id || null
}

function select(id) {
  state.activeId = id
}

export const datasets = { state, active, refresh, upload, remove, select }
