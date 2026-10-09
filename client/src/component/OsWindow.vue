<script setup>
// Generic desktop window: header drag, focus/z-order, minimize/maximize/close.
// Initial position comes from CSS classes; after the first drag the engine tracks x/y in px.
import { ref, computed } from 'vue'
import { windows } from '../feature/windows/engine.js'

const props = defineProps({
  id: { type: String, required: true },
  ariaLabel: { type: String, default: '' },
  contentClass: { type: String, default: '' },
  headerClass: { type: String, default: '' },
})
const emit = defineEmits(['close'])

windows.ensure(props.id)
const el = ref(null)
const st = computed(() => windows.state.windows[props.id])

const style = computed(() => ({
  zIndex: st.value.z,
  left: st.value.x != null ? st.value.x + 'px' : undefined,
  top: st.value.y != null ? st.value.y + 'px' : undefined,
}))

function onHeaderDown(e) {
  windows.startDrag(props.id, e, el.value)
}
</script>

<template>
  <section
    ref="el"
    class="window"
    :class="{ active: st.active, hidden: st.hidden, maximized: st.maximized }"
    :style="style"
    :aria-label="ariaLabel"
    @pointerdown="windows.focus(id)"
  >
    <header class="window-header" :class="headerClass" @pointerdown="onHeaderDown">
      <div class="window-name"><slot name="title" /></div>
      <div class="controls">
        <button aria-label="Minimize" @click.stop="windows.minimize(id)">−</button>
        <button aria-label="Maximize" @click.stop="windows.toggleMax(id)">{{ st.maximized ? '❐' : '□' }}</button>
        <button class="close" aria-label="Close" @click.stop="emit('close')">×</button>
      </div>
    </header>
    <div class="window-content" :class="contentClass"><slot /></div>
  </section>
</template>
