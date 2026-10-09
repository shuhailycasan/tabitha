// desktop engine — chrome-level stuff: topbar clock, toast notifications.
import { reactive, readonly } from 'vue'

const state = reactive({ clock: '', toast: '', toastVisible: false })
let toastTimer = null

function tick() {
  state.clock = new Intl.DateTimeFormat(undefined, {
    weekday: 'short', hour: '2-digit', minute: '2-digit',
  }).format(new Date())
}

function start() {
  tick()
  setInterval(tick, 30000)
}

function toast(text) {
  state.toast = text
  state.toastVisible = true
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { state.toastVisible = false }, 2400)
}

export const desktop = { state: readonly(state), start, toast }
