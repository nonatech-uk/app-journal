import fs from 'fs'
import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const sharedUiPath = fs.existsSync('/mees-shared-ui/src')
  ? '/mees-shared-ui/src'
  : path.resolve(__dirname, '../../mees-shared-ui/src')

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@mees/shared-ui': sharedUiPath,
    },
    dedupe: ['react', 'react-dom', '@tanstack/react-query'],
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
