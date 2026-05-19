import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api/site-a': { target: 'http://127.0.0.1:5001', rewrite: (p) => p.replace('/api/site-a', '') },
      '/api/site-b': { target: 'http://127.0.0.1:5002', rewrite: (p) => p.replace('/api/site-b', '') },
      '/api/site-c': { target: 'http://127.0.0.1:5003', rewrite: (p) => p.replace('/api/site-c', '') },
    }
  }
})
