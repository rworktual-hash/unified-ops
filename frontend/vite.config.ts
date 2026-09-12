import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/servers': 'http://127.0.0.1:8000',
      '/alerts': 'http://127.0.0.1:8000',
      '/agent-actions': 'http://127.0.0.1:8000',
      '/approvals': 'http://127.0.0.1:8000',
      '/chat': 'http://127.0.0.1:8000',
    },
  },
})
