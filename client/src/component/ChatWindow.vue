<script setup>
// Tabitha chat window — streams answers from the backend about the active dataset.
import { ref, computed, watch, nextTick } from 'vue'
import OsWindow from './OsWindow.vue'
import ThinkSprite from './ThinkSprite.vue'
import { chat } from '../feature/chat/engine.js'
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

// mascot reacts to what the model is doing — thinking plays the sprite animation
const thinking = computed(() => chat.state.sending && !pendingMsg.value?.tool_log?.length)
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
  chat.send(text, dataset.value?.id)
}
</script>

<template>
  <OsWindow id="chat" class="chat-window" :class="{ 'drop-target': files.state.overChat }" @close="windows.close('chat')"
            aria-label="Tabitha chat window" content-class="chat-content" header-class="chat-head">
    <template #title>
      <span class="chat-title">
        <ThinkSprite v-if="thinking" class="tabitha-avatar" />
        <img v-else class="tabitha-avatar" :src="avatar" alt="">
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
      <div v-if="!dataset" class="think-demo">
        <div class="bubble typing" aria-hidden="true">
          <ThinkSprite class="typing-sprite" />
          <i></i><i></i><i></i>
        </div>
        <span class="think-demo-label">…this is me thinking</span>
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
        <ThinkSprite class="typing-sprite" />
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
        <textarea v-model="input" rows="2"
                  :placeholder="dataset ? 'Ask Tabitha about your spreadsheet…' : 'Open a spreadsheet first'"
                  :disabled="!dataset || chat.state.sending"
                  aria-label="Ask Tabitha about your spreadsheet"
                  @keydown.enter.exact.prevent="send"></textarea>
        <button v-if="chat.state.sending" class="send cancel" aria-label="Stop" @click="chat.cancel()">■</button>
        <button v-else class="send" aria-label="Send message" :disabled="!dataset || !input.trim()" @click="send">↑</button>
      </div>
      <div class="chat-note">Your workbook stays on this device · Enter to send</div>
    </div>
  </OsWindow>
</template>
