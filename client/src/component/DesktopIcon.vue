<script setup>
// Desktop file icon — drag to rearrange, drop on Tabitha to attach, double-click to reopen.
import { ref } from 'vue'
import { files } from '../feature/files/engine.js'

const props = defineProps({
  item: { type: Object, required: true },
})
const emit = defineEmits(['open', 'drop-on-chat', 'remove'])

const el = ref(null)

function onPointerDown(e) {
  files.startIconDrag(props.item.id, e, el.value, {
    onDropOnChat: f => emit('drop-on-chat', f),
  })
}
</script>

<template>
  <div
    ref="el"
    class="desk-icon"
    :class="{ 'no-file': !item.file, fresh: item.fresh }"
    :style="{
      left: item.x != null ? item.x + 'px' : undefined,
      right: item.x != null ? undefined : '405px',
      top: item.y + 'px',
    }"
    :title="item.file ? item.name : item.name + ' (server copy — reopen to view)'"
    @pointerdown="onPointerDown"
    @dblclick="item.fresh = false; emit('open', item)"
  >
    <button
      class="icon-del" aria-label="Remove file" title="Remove"
      @click.stop="emit('remove', item)" @dblclick.stop
    >×</button>
    <span class="desk-icon-img">
      <svg viewBox="0 0 24 24"><path d="M4 4.5h9l6 6v9A1.5 1.5 0 0 1 17.5 21h-12A1.5 1.5 0 0 1 4 19.5v-15Z"/><path d="M13 5v6h6M8 14l4 5m0-5-4 5"/></svg>
    </span>
    <span class="desk-icon-label">{{ item.name }}</span>
  </div>
</template>
