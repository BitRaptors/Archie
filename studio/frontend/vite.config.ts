import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// '@' points at the VIEWER's src (not studio's) so the viewer's internal
// '@/lib/api'-style imports resolve when its components are imported here.
// Studio's own code therefore uses relative imports only.
const viewerSrc = path.resolve(__dirname, '../../npm-package/assets/viewer/src')

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': viewerSrc },
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:5848' },
  },
})
