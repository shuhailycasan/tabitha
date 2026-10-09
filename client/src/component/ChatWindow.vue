<script setup>
// Tabitha chat window — streams answers from the backend about the active dataset.
import { ref, computed, watch, nextTick } from 'vue'
import OsWindow from './OsWindow.vue'
import { chat } from '../feature/chat/engine.js'
import { suggest } from '../feature/chat/commands.js'
import { datasets } from '../feature/datasets/engine.js'
import { files } from '../feature/files/engine.js'
import { spreadsheet } from '../feature/spreadsheet/engine.js'
import mascotHappy from '../assets/tabitha-happy.png'
import mascotThinking from '../assets/tabitha-thinking.png'
import mascotWorking from '../assets/tabitha-working.png'
import mascotWaving from '../assets/tabitha-waving.png'

const log = ref(null)
const input = ref('')

const suggestions = [
  'How many students are there?',
  'Who has the highest grade?',
  'What is the average score?',
]

const pendingMsg = computed(() => {
  const m = chat.state.messages[chat.state.messages.length - 1]
  return m && m.role === 'assistant' ? m : null
})
const receiving = computed(() => !!(pendingMsg.value && pendingMsg.value.content))
const dataset = computed(() => datasets.active.value)

// mascot reacts to what the model is doing
const avatar = computed(() => {
  if (!chat.state.sending) return mascotHappy
  return pendingMsg.value?.tool_log?.length ? mascotWorking : mascotThinking
})

// dataset switch wipes the conversation, then greets with the new context
watch(() => dataset.value?.id, (id, oldId) => {
  chat.reset()
  if (id) {
    const ds = dataset.value
    const n = ds.sheets.length
    chat.pushAssistant(`Ready to answer about “${ds.name}” — ${n} sheet${n === 1 ? '' : 's'} loaded. Ask me to summarize it, find values, or calculate a total.`)
  }
})

function scroll() {
  nextTick(() => { if (log.value) log.value.scrollTop = log.value.scrollHeight })
}
watch(() => chat.state.version, scroll)

function ask(q) {
  input.value = q
  send()
}

function removeDataset() {
  const id = datasets.state.activeId
  const it = files.state.items.find(i => i.datasetId === id)
  if (it) spreadsheet.removeFor(it.id)
  datasets.remove(id)
  files.removeByDataset(id)
}

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
  ac.value = suggest(input.value, e.target.selectionStart, datasets.state.activeId, datasets.state.list)
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
  <OsWindow id="chat" class="chat-window" :class="{ 'drop-target': files.state.overChat }" @close="windows.close('chat')"
            aria-label="Tabitha chat window" content-class="chat-content" header-class="chat-head">
    <template #title>
      <span class="chat-title">
        <img class="tabitha-avatar" :src="avatar" alt="">
        <span class="chat-title-text">
          <strong>Tabitha</strong>
          <small>Spreadsheet assistant · local</small>
        </span>
      </span>
    </template>

    <div v-if="datasets.state.list.length" class="chat-context">
      <span class="ctx-label">Asking about</span>
      <select :value="datasets.state.activeId" @change="datasets.select($event.target.value)">
        <option v-if="!datasets.state.activeId" :value="null" disabled>— pick a file —</option>
        <option v-for="d in datasets.state.list" :key="d.id" :value="d.id">{{ d.name }}</option>
      </select>
      <button class="ctx-del" aria-label="Remove dataset" title="Remove dataset"
              :disabled="!datasets.state.activeId"
              @click="removeDataset">×</button>
    </div>

    <div class="messages" ref="log" aria-live="polite">
      <div v-if="!dataset" class="welcome">
        <img :src="mascotWaving" alt="">
        <div class="bubble">Hi! I'm Tabitha<br>Open a spreadsheet and ask me to summarize it, find a value, or calculate totals.</div>
      </div>

      <template v-for="(m, i) in chat.state.messages" :key="i">
        <div v-for="(t, ti) in m.tool_log || []" :key="ti" class="toolchip" :class="{ bad: !t.ok }">
          {{ t.ok ? '⚙' : '✕' }} {{ t.tool }}({{ chat.shortArgs(t.args) }})
        </div>
        <details v-if="m.think" class="thinkbox" :open="chat.state.sending && i === chat.state.messages.length - 1">
          <summary>Model thinking</summary>
          <div class="think">{{ m.think }}</div>
        </details>
        <div v-if="m.content" class="bubble" :class="{ user: m.role === 'user' }" v-html="chat.md(m.content)"></div>
      </template>

      <div v-if="chat.state.sending && !receiving" class="bubble typing" aria-label="Tabitha is thinking">
        <i></i><i></i><i></i>
      </div>
    </div>

    <div v-if="chat.state.error" class="alert" role="alert">{{ chat.state.error }}</div>

    <div class="chat-compose">
      <label class="toggle">
        <input type="checkbox" v-model="chat.state.thinkEnabled" :disabled="chat.state.sending">
        Think step by step
      </label>
      <div v-if="dataset" class="attach-chip">
        📎 {{ dataset.name }}
        <button aria-label="Detach file" title="Detach file" @click="datasets.state.activeId = null">×</button>
      </div>
      <div class="compose-box">
        <div v-if="ac" class="ac" role="listbox">
          <button v-for="(it, i) in ac.items" :key="it.label" type="button" role="option"
                  :class="{ on: i === ac.i }" @mousedown.prevent="pick(it)">
            <span>{{ it.label }}</span><small>{{ it.hint }}</small>
          </button>
        </div>
        <textarea ref="ta" v-model="input" rows="2"
                  :placeholder="dataset ? 'Ask Tabitha… (@file to combine, / for commands)' : 'Open a spreadsheet first'"
                  :disabled="!dataset || chat.state.sending"
                  aria-label="Ask Tabitha about your spreadsheet"
                  @input="onInput" @keydown="onKey"></textarea>
        <button v-if="chat.state.sending" class="send cancel" aria-label="Stop" @click="chat.cancel()">■</button>
        <button v-else class="send" aria-label="Send message" :disabled="!dataset || !input.trim()" @click="send">↑</button>
      </div>
      <div class="chat-note">Your workbook stays on this device · Enter to send</div>
    </div>
  </OsWindow>
</template>
