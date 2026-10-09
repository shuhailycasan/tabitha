<script setup>
// Tabitha chat window — streams answers from the backend about the active dataset.
import { ref, computed, watch, nextTick } from 'vue'
import OsWindow from './OsWindow.vue'
import ThinkSprite from './ThinkSprite.vue'
import { chat } from '../feature/chat/engine.js'
import { suggest } from '../feature/chat/commands.js'
import { datasets } from '../feature/datasets/engine.js'
import { files } from '../feature/files/engine.js'
import { windows } from '../feature/windows/engine.js'
import mascotHappy from '../assets/tabitha-happy.png'
import mascotWaving from '../assets/tabitha-waving.png'

const log = ref(null)
const input = ref('')

const pendingMsg = computed(() => {
  const m = chat.state.messages[chat.state.messages.length - 1]
  return m && m.role === 'assistant' ? m : null
})
const receiving = computed(() => !!(pendingMsg.value && pendingMsg.value.content))
const attached = computed(() => datasets.attached.value)
const ctxPct = computed(() => Math.min(100, Math.round(chat.state.ctx.tokens / chat.state.ctx.max * 100)))

// one mascot, two states: animates while the model thinks, default while it replies
const thinking = computed(() => chat.state.sending && !receiving.value)

// attach/detach markers — the conversation keeps going when the file set changes
watch(() => [...datasets.state.attachedIds], (ids, old = []) => {
  const name = i => datasets.state.list.find(d => d.id === i)?.name || 'file'
  const on = ids.filter(i => !old.includes(i)), off = old.filter(i => !ids.includes(i))
  if (on.length && !chat.state.messages.length) {
    const n = datasets.attached.value.flatMap(d => d.sheets).length
    chat.pushAssistant(`Ready to answer about ${on.map(i => `“${name(i)}”`).join(' and ')} — ${n} sheet${n === 1 ? '' : 's'} loaded. Ask me to summarize, find values, or calculate totals.`)
  } else {
    if (on.length) chat.note(`Attached ${on.map(name).join(', ')}`)
    if (off.length) chat.note(`Detached ${off.map(name).join(', ')}`)
  }
})

function scroll() {
  nextTick(() => { if (log.value) log.value.scrollTop = log.value.scrollHeight })
}
watch(() => chat.state.version, scroll)

function send() {
  const text = input.value
  if (!text.trim()) return
  input.value = ''
  ac.value = null
  chat.send(text)
}

// @file / /command suggestions (logic in feature/chat/commands.js)
const ta = ref(null)
const ac = ref(null)
function onInput(e) {
  ac.value = suggest(input.value, e.target.selectionStart, datasets.state.attachedIds, datasets.state.list)
}
function pick(item) {
  const a = ac.value
  input.value = input.value.slice(0, a.tokenStart) + item.label + ' ' + input.value.slice(a.pos)
  const p = a.tokenStart + item.label.length + 1
  ac.value = null
  nextTick(() => { ta.value.focus(); ta.value.setSelectionRange(p, p); onInput({ target: ta.value }) }) // chain: "/top " -> columns
}
function onKey(e) {
  const a = ac.value
  if (a) {
    const n = a.items.length
    if (e.key === 'ArrowDown') { a.i = (a.i + 1) % n; return e.preventDefault() }
    if (e.key === 'ArrowUp') { a.i = (a.i - 1 + n) % n; return e.preventDefault() }
    if (e.key === 'Enter' || e.key === 'Tab') { pick(a.items[a.i]); return e.preventDefault() }
    if (e.key === 'Escape') { ac.value = null; return }
  }
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
}
</script>

<template>
  <OsWindow id="chat" class="chat-window" :class="{ 'drop-target': files.state.overChat, deepthink: chat.state.thinkEnabled }" @close="windows.close('chat')"
            aria-label="Tabitha chat window" content-class="chat-content" header-class="chat-head">
    <template #title>
      <span class="chat-title">
        <ThinkSprite v-if="thinking" class="tabitha-avatar" />
        <img v-else class="tabitha-avatar" :src="mascotHappy" alt="">
        <span class="chat-title-text">
          <strong>Tabitha</strong>
          <small>Spreadsheet assistant · local</small>
        </span>
      </span>
    </template>

    <div class="messages" ref="log" aria-live="polite">
      <div v-if="!chat.state.messages.length" class="welcome">
        <img :src="mascotWaving" alt="">
        <div class="bubble">Hi! I'm Tabitha<br>Ask me anything — or drag a spreadsheet onto this window (or @mention it) and I'll summarize it, find values, or calculate totals.</div>
      </div>
      <template v-for="(m, i) in chat.state.messages" :key="i">
        <div v-if="m.role === 'note'" class="ctx-note">{{ m.content }}</div>
        <template v-else>
          <div v-for="(t, ti) in m.tool_log || []" :key="ti" class="toolchip" :class="{ bad: !t.ok }">
            {{ t.ok ? '⚙' : '✕' }} {{ t.tool }}({{ chat.shortArgs(t.args) }})
          </div>
          <details v-if="m.think" class="thinkbox" :open="chat.state.sending && i === chat.state.messages.length - 1">
            <summary>Deep Think</summary>
            <div class="think">{{ m.think }}</div>
          </details>
          <div v-if="m.content" class="bubble" :class="{ user: m.role === 'user' }" v-html="chat.md(m.content)"></div>
        </template>
      </template>

      <div v-if="chat.state.sending && !receiving" class="bubble typing" aria-label="Tabitha is thinking">
        <i></i><i></i><i></i>
      </div>
    </div>

    <div v-if="chat.state.error" class="alert" role="alert">{{ chat.state.error }}</div>

    <div class="chat-compose">
      <label class="toggle">
        <input type="checkbox" v-model="chat.state.thinkEnabled" :disabled="chat.state.sending">
        Deep Think
      </label>
      <div v-for="d in attached" :key="d.id" class="attach-chip">
        📎 {{ d.name }}
        <button aria-label="Detach file" title="Detach file" @click="datasets.detach(d.id)">×</button>
      </div>
      <div v-if="chat.state.queued" class="queue-chip" title="Enter again to interrupt and send now">
        ⏳ {{ chat.state.queued }}
      </div>
      <div class="compose-box">
        <div v-if="ac" class="ac" role="listbox">
          <button v-for="(it, i) in ac.items" :key="it.label" type="button" role="option"
                  :class="{ on: i === ac.i }" @mousedown.prevent="pick(it)">
            <span>{{ it.label }}</span><small>{{ it.hint }}</small>
          </button>
        </div>
        <textarea ref="ta" v-model="input" rows="2"
                  :placeholder="chat.state.sending ? 'Enter to queue · Enter again to interrupt' : 'Ask Tabitha… (@file to attach a spreadsheet, / for commands)'"
                  aria-label="Chat with Tabitha"
                  @input="onInput" @keydown="onKey"></textarea>
        <button v-if="chat.state.sending" class="send cancel" aria-label="Stop" @click="chat.cancel()">■</button>
        <button v-else class="send" aria-label="Send message" :disabled="!input.trim()" @click="send">↑</button>
      </div>
      <div v-if="chat.state.ctx.tokens" class="ctxbar"
           :title="`≈${chat.state.ctx.tokens} of ${chat.state.ctx.max} tokens — auto-compacts at 60%`">
        <div class="ctxbar-track"><i :style="{ width: ctxPct + '%' }" :class="{ hot: ctxPct >= 50 }"></i></div>
        <span>ctx {{ ctxPct }}%</span>
      </div>
      <div class="chat-note">Your workbook stays on this device · Enter to send{{ chat.state.sending ? ' · Enter again to interrupt' : '' }}</div>
    </div>
  </OsWindow>
</template>
