import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/slots': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/candidates': 'http://localhost:8000'
    }
  },
  build: {
    outDir: path.resolve(__dirname, '../dist'),
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('react-dom') || id.includes('/react/')) {
              return 'react-vendor'
            }
            if (id.includes('@tanstack/react-router')) {
              return 'router'
            }
            if (id.includes('@tanstack/react-query')) {
              return 'query'
            }
            if (id.includes('lucide-react')) {
              return 'icons'
            }
          }
        }
      }
    }
  }
})
