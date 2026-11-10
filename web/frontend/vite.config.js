import { defineConfig } from 'vite'

// Vite sends /api/* to local FastAPI, eliminating browser CORS setup.
export default defineConfig({
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
  esbuild: { jsx: 'automatic' },
})
