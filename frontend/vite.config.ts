import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // In CI (GitHub Pages), VITE_BASE_PATH=/0050-/ is injected by the workflow.
  // Locally, base defaults to "/" so dev server works as-is.
  base: process.env.VITE_BASE_PATH ?? '/',
})
