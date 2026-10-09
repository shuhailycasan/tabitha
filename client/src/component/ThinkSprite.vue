<script setup>
// Animated "thinking" turtle — cycles the 12 cut sprite frames while mounted.
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import f01 from '../assets/think-frames/t01.png'
import f02 from '../assets/think-frames/t02.png'
import f03 from '../assets/think-frames/t03.png'
import f04 from '../assets/think-frames/t04.png'
import f05 from '../assets/think-frames/t05.png'
import f06 from '../assets/think-frames/t06.png'
import f07 from '../assets/think-frames/t07.png'
import f08 from '../assets/think-frames/t08.png'
import f09 from '../assets/think-frames/t09.png'
import f10 from '../assets/think-frames/t10.png'
import f11 from '../assets/think-frames/t11.png'
import f12 from '../assets/think-frames/t12.png'

const props = defineProps({
  interval: { type: Number, default: 140 }, // ms per frame (~7fps, gentle loop)
})

const frames = [f01, f02, f03, f04, f05, f06, f07, f08, f09, f10, f11, f12]
const i = ref(0)
const src = computed(() => frames[i.value])
let timer = null
onMounted(() => {
  timer = setInterval(() => { i.value = (i.value + 1) % frames.length }, props.interval)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <img :src="src" class="think-sprite" alt="Tabitha is thinking">
</template>

<style scoped>
.think-sprite { display: block; object-fit: contain; }
</style>
