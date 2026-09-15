import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    port: 3001,
    host: true,
    proxy: {
      '/health': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/memory': 'http://localhost:8000',
      '/approvals': 'http://localhost:8000',
      '/metrics': 'http://localhost:8000',
      '/stt': 'http://localhost:8000',
      '/tts': 'http://localhost:8000',
      '/connections': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true }
    }
  },
  build: {
    outDir: '../src/jefrey/static',
    emptyOutDir: true,
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          query: ['@tanstack/react-query'],
          charts: ['recharts'],
          ui: ['clsx', 'tailwind-merge', 'class-variance-authority', 'lucide-react']
        }
      }
    }
  },
  define: { 'process.env': process.env }
})
