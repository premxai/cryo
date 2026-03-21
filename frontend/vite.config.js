import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy API calls to FastAPI backend in dev — avoids CORS issues
    proxy: {
      '/search': { target: 'http://localhost:8000', changeOrigin: true },
      '/semantic-search': { target: 'http://localhost:8000', changeOrigin: true },
      '/score': { target: 'http://localhost:8000', changeOrigin: true },
      '/healthz': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
