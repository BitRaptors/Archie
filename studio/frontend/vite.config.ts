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
    // REQUIRED for mounting viewer components (e.g. LocalPage in the
    // Architecture tab): viewer sources live outside this project root, so
    // Rollup resolves their bare imports ('lucide-react', 'mermaid', ...) by
    // walking up from npm-package/assets/viewer/src — where no node_modules
    // exists — and the build fails with "failed to resolve import". dedupe
    // pins these packages to studio's own node_modules (mirrors the "*" paths
    // fallback in tsconfig.json, which solves the same problem for tsc).
    // Keep in sync with npm-package/assets/viewer/package.json dependencies.
    dedupe: [
      'react', 'react-dom', 'react-router-dom', 'lucide-react', 'mermaid',
      'react-markdown', 'remark-gfm', 'rehype-highlight', 'highlight.js',
      'clsx', 'tailwind-merge', 'class-variance-authority',
    ],
  },
  server: {
    // 5848 is server.py's DEFAULT_PORT. If the server port-falls-back (5848
    // busy), this dev proxy breaks -- free the port and restart the server
    // with --port 5848.
    proxy: { '/api': 'http://127.0.0.1:5848' },
  },
})
