import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      // dev: forward API calls to the Flask backend
      '/api': 'http://localhost:8777',
    },
  },
})
