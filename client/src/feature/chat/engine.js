// chat engine — talks to the backend's NDJSON stream (/api/chat) and tracks message state.
// Events handled: status / think / tool / delta / done / error. Cancel via /api/cancel/<id>.
import { reactive, readonly } from 'vue'
import { datasets } from '../datasets/engine.js'
import { COMMANDS, scopeIds, cleanMentions, parseCommand } from './commands.js'

const state = reactive({
  messages: [],        // { role, content, think?, tool_log? }
  sending: false,
  status: '',          // last "status" event text
  error: '',
  thinkEnabled: true,
  version: 0,          // bumped per stream event — components watch it to autoscroll
})

let abortCtrl = null
let reqId = null

function bump() { state.version++ }

function reset() {
  state.messages = []
  state.error = ''
}

function pushAssistant(text) {
  state.messages.push({ role: 'assistant', content: text })
  bump()
}

// /commands run backend tools directly (POST /api/run) — instant, no LLM
async function command(text) {
  const { activeId, list } = datasets.state
  const c = parseCommand(text, activeId, list)
  state.error = ''
  if (c.local === 'clear') return reset()
  if (c.local === 'fast') { state.thinkEnabled = false; return pushAssistant('Fast mode on — answers skip the thinking step.') }
  if (c.local === 'think') { state.thinkEnabled = true; return pushAssistant('Thinking mode on — slower, shows reasoning.') }
  if (c.local === 'help') {
    return pushAssistant(COMMANDS.map(x => `**${x.label}** — ${x.hint}`).join('\n') + '\n\nTip: @file adds another uploaded file to your question.')
  }
  if (c.error) return pushAssistant(c.error)
  state.messages.push({ role: 'user', content: text })
  bump()
  try {
    const res = await fetch('/api/run', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_ids: c.ids, tool: c.tool, args: c.args }),
    })
    const data = await res.json()
    state.messages.push({
      role: 'assistant', content: data.ok ? data.text : `Error: ${data.error}`,
      tool_log: [{ tool: c.tool, args: c.args, ok: !!data.ok }],
    })
  } catch (e) {
    state.error = e.message + ' — try again.'
  }
  bump()
}

async function send(text) {
  text = (text || '').trim()
  if (!text || state.sending) return
  if (text.startsWith('/')) return command(text)
  const { activeId, list } = datasets.state
  const ids = scopeIds(text, activeId, list)
  if (!ids.length) return
  const clean = cleanMentions(text, list)

  state.error = ''
  state.sending = true
  state.status = 'Thinking…'
  abortCtrl = new AbortController()
  reqId = crypto.randomUUID()

  state.messages.push({ role: 'user', content: text })
  state.messages.push({ role: 'assistant', content: '', tool_log: [], think: '' })
  const pending = state.messages[state.messages.length - 1]
  bump()

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: abortCtrl.signal,
      body: JSON.stringify({
        dataset_ids: ids,
        request_id: reqId,
        think: state.thinkEnabled,
        messages: [...state.messages.filter(m => m !== pending).map(m => ({ role: m.role, content: m.content })).slice(0, -1),
          { role: 'user', content: clean }], // the model sees @file as a quoted file name, the chat shows what was typed
      }),
    })
    if (!res.ok) {
      let msg = 'Chat failed'
      try { msg = (await res.json()).error || msg } catch {}
      throw new Error(msg)
    }

    const reader = res.body.getReader()
    const dec = new TextDecoder()
    let buf = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      let i
      while ((i = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, i).trim()
        buf = buf.slice(i + 1)
        if (!line) continue
        const e = JSON.parse(line)
        if (e.type === 'status') state.status = e.text
        else if (e.type === 'think') pending.think += e.text
        else if (e.type === 'tool') pending.tool_log.push(e)
        else if (e.type === 'delta') pending.content += e.text
        else if (e.type === 'done') pending.content = e.reply || pending.content
        else if (e.type === 'error') throw new Error(e.error)
        bump()
      }
    }
  } catch (e) {
    const idx = state.messages.indexOf(pending)
    if (idx >= 0) state.messages.splice(idx, 1)
    if (e.name !== 'AbortError') state.error = e.message + ' — try again.'
  }

  state.sending = false
  abortCtrl = null
  state.status = ''
  bump()
}

function cancel() {
  if (abortCtrl) abortCtrl.abort()
  if (reqId) fetch('/api/cancel/' + reqId, { method: 'POST' })
}

function shortArgs(args) {
  return Object.entries(args || {}).map(([k, v]) => `${k}=${v}`).join(', ')
}

// minimal markdown (HTML-escaped first): **bold** and | tables | — the only things the model emits
function md(t) {
  const L = (t || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').split('\n')
  const row = l => /^\s*\|.*\|\s*$/.test(l)
  const cells = l => l.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim())
  const out = []
  for (let i = 0; i < L.length;) {
    if (row(L[i]) && i + 1 < L.length && /^\s*\|[\s:|-]+\|\s*$/.test(L[i + 1])) {
      const head = cells(L[i]); i += 2
      let body = ''
      while (i < L.length && row(L[i])) body += '<tr>' + cells(L[i++]).map(c => `<td>${c}</td>`).join('') + '</tr>'
      out.push(`<div class="tablewrap"><table><thead><tr>${head.map(c => `<th>${c}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>`)
    } else out.push(L[i++])
  }
  return out.join('\n').replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
}

export const chat = { state, send, cancel, reset, pushAssistant, shortArgs, md }
