<script setup>
// Renders a chart spec from a tool result: {type, title, labels, values, note?}
import { onBeforeUnmount, onMounted, ref } from 'vue'
import Chart from 'chart.js/auto'

const props = defineProps({ spec: { type: Object, required: true } })
const el = ref(null)
let chart = null

// horizontal bars need height per row — ~30px each, capped
const height = Math.min(360, 60 + props.spec.labels.length * 30)

onMounted(() => {
  const s = props.spec
  chart = new Chart(el.value, {
    type: 'bar',
    data: {
      labels: s.labels,
      datasets: [{
        data: s.values,
        backgroundColor: 'rgba(47, 153, 85, .72)',
        hoverBackgroundColor: '#2f9955',
        borderRadius: 5,
        maxBarThickness: 20,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: s.title
          ? { display: true, text: s.title, align: 'start', color: '#173a20',
              font: { size: 11, weight: '600' }, padding: { bottom: 8 } }
          : { display: false },
      },
      scales: {
        x: { beginAtZero: true, grid: { color: 'rgba(23, 58, 32, .07)' },
             ticks: { color: '#69756a', font: { size: 10 }, precision: 0 } },
        y: { grid: { display: false },
             ticks: { color: '#264d30', font: { size: 10 } } },
      },
    },
  })
})
onBeforeUnmount(() => chart?.destroy())
</script>

<template>
  <div class="chartbox">
    <div class="chart-canvas" :style="{ height: height + 'px' }"><canvas ref="el"></canvas></div>
    <div v-if="spec.note" class="chart-note">{{ spec.note }}</div>
  </div>
</template>
