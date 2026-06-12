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
    // 5848 is server.py's DEFAULT_PORT. If the server port-falls-back (5848
    // busy), this dev proxy breaks -- free the port and restart the server
    // with --port 5848.
    proxy: { '/api': 'http://127.0.0.1:5848' },
  },
})
