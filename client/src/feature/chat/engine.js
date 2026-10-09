// chat engine — talks to the backend's NDJSON stream (/api/chat) and tracks message state.
// Events handled: status / think / tool / delta / done / error. Cancel via /api/cancel/<id>.
import { reactive, readonly } from 'vue'
import { datasets } from '../datasets/engine.js'
import { COMMANDS, scopeIds, cleanMentions, parseCommand } from './commands.js'

const state = reactive({
  messages: [],        // { role, content, think?, tool_log? } — role 'note' is a UI-only divider
  sending: false,
  queued: null,        // text typed while busy — a second Enter interrupts and sends it instead
  ctx: { tokens: 0, max: 8192 },  // server's prompt estimate vs the context window
  status: '',          // last "status" event text
  error: '',
  thinkEnabled: false,
  version: 0,          // bumped per stream event — components watch it to autoscroll
})

let abortCtrl = null
let reqId = null

function bump() { state.version++ }

function reset() {
  cancel()
  state.messages = []
  state.queued = null
  state.ctx = { tokens: 0, max: 8192 }
  state.error = ''
}

function pushAssistant(text) {
  state.messages.push({ role: 'assistant', content: text })
  bump()
}

// UI-only divider (filtered out of the request server-side) — e.g. attach/detach markers
function note(text) {
  state.messages.push({ role: 'note', content: text })
  bump()
}

// /commands run backend tools directly (POST /api/run) — instant, no LLM
async function command(text) {
  const { attachedIds, list } = datasets.state
  const c = parseCommand(text, attachedIds, list)
  state.error = ''
  if (c.local === 'clear') return reset()
  if (c.local === 'fast') { state.thinkEnabled = false; return pushAssistant('Deep Think off — fast answers, no reasoning step.') }
  if (c.local === 'think') { state.thinkEnabled = true; return pushAssistant('Deep Think on — slower, shows reasoning.') }
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
      chart: data.chart || null,
    })
  } catch (e) {
    state.error = e.message + ' — try again.'
  }
  bump()
}

async function send(text) {
  text = (text || '').trim()
  if (!text && !state.queued) return
  if (text.startsWith('/')) return command(text)  // commands are instant — never queued
  if (state.sending) {
    // first Enter while busy queues; second Enter interrupts — newest input wins, else flush the queue
    if (state.queued == null) { state.queued = text; return bump() }
    const next = text || state.queued
    state.queued = null
    cancel()
    text = next
  }
  if (!text) return
  const { attachedIds, list } = datasets.state
  const ids = scopeIds(text, attachedIds, list)  // may be empty — plain chatbot mode, no tools
  const clean = cleanMentions(text, list)

  state.error = ''
  state.sending = true
  state.status = 'Thinking…'
  const myCtrl = new AbortController()
  abortCtrl = myCtrl
  reqId = crypto.randomUUID()

  state.messages.push({ role: 'user', content: text })
  // segments: chronological think/tool/text pieces of this reply (Claude-style transcript)
  state.messages.push({ role: 'assistant', content: '', tool_log: [], think: '', segments: [] })
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
        else if (e.type === 'ctx') state.ctx = { tokens: e.tokens, max: e.max }
        else if (e.type === 'compact') {
          const j = state.messages.indexOf(pending)
          state.messages.splice(j < 0 ? state.messages.length : j, 0,
            { role: 'note', content: `Context compacted — ${e.dropped} earlier message(s) dropped` })
        }
        else if (e.type === 'think') {
          pending.think += e.text
          const last = pending.segments.at(-1)
          if (last?.type === 'think') last.text += e.text
          else pending.segments.push({ type: 'think', text: e.text })
        }
        else if (e.type === 'tool') {
          pending.tool_log.push(e)
          pending.segments.push({ type: 'tool', tool: e.tool, args: e.args, ok: e.ok })
        }
        else if (e.type === 'chart') pending.segments.push({ type: 'chart', chart: e.chart })
        else if (e.type === 'delta') {
          pending.content += e.text
          const last = pending.segments.at(-1)
          if (last?.type === 'text') last.text += e.text
          else pending.segments.push({ type: 'text', text: e.text })
        }
        else if (e.type === 'done') {
          pending.content = e.reply || pending.content
          if (e.reply) {  // reply = final round's text — replace/append the trailing text segment
            const last = pending.segments.at(-1)
            if (last?.type === 'text') last.text = e.reply
            else pending.segments.push({ type: 'text', text: e.reply })
          }
          if (e.ctx) state.ctx = e.ctx
        }
        else if (e.type === 'error') throw new Error(e.error)
        bump()
      }
    }
  } catch (e) {
    const idx = state.messages.indexOf(pending)
    if (e.name === 'AbortError') {
      // interrupted — keep whatever streamed in, marked as stopped
      if (idx >= 0) {
        pending.content = pending.content ? pending.content.trimEnd() + '\n\n(stopped)' : '(stopped)'
        const last = pending.segments?.at(-1)
        if (last?.type === 'text') last.text += '\n\n(stopped)'
        else pending.segments?.push({ type: 'text', text: '(stopped)' })
      }
    } else {
      if (idx >= 0) state.messages.splice(idx, 1)
      state.error = e.message + ' — try again.'
    }
  }

  // an interrupt replaces abortCtrl mid-flight — only the owner may clear the busy flag
  const mine = abortCtrl === myCtrl
  if (mine) { state.sending = false; abortCtrl = null }
  state.status = ''
  bump()
  if (mine && state.queued) { const q = state.queued; state.queued = null; send(q) }
}

function cancel() {
  state.queued = null  // stop means stop — don't fire a queued message afterwards
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

export const chat = { state, send, cancel, reset, pushAssistant, note, shortArgs, md }
