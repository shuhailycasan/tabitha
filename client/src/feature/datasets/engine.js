// datasets engine — server-side workbooks: list, upload, delete, explicit attach set.
// Chat can only touch datasets the user attached (drag onto the chat window or @mention) —
// uploading or viewing a file never feeds it to the model.
import { reactive, computed } from 'vue'

const state = reactive({ list: [], attachedIds: [], uploading: false, error: '' })
const attached = computed(() => state.attachedIds.map(id => state.list.find(d => d.id === id)).filter(Boolean))

async function refresh() {
  try {
    const res = await fetch('/api/datasets')
    state.list = await res.json()
    state.attachedIds = state.attachedIds.filter(id => state.list.some(d => d.id === id))
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
    return data  // NB: not attached — the user attaches explicitly
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
  state.attachedIds = state.attachedIds.filter(i => i !== id)
}

function attach(id) {
  if (id && !state.attachedIds.includes(id)) state.attachedIds.push(id)
}

function detach(id) {
  state.attachedIds = state.attachedIds.filter(i => i !== id)
}

export const datasets = { state, attached, refresh, upload, remove, attach, detach }
