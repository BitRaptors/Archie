// The viewer's tailwind config require()s its plugins (tailwindcss-animate,
// @tailwindcss/typography) relative to its own location, where no node_modules
// exists. While loading it as a preset, fall back to studio's node_modules for
// any require that would otherwise fail. The hook is restored immediately after.
const Module = require('module')

function loadViewerPreset() {
  const origResolve = Module._resolveFilename
  Module._resolveFilename = function (request, ...rest) {
    try {
      return origResolve.call(this, request, ...rest)
    } catch (err) {
      if (err.code !== 'MODULE_NOT_FOUND') throw err
      try {
        return require.resolve(request, { paths: [__dirname] })
      } catch {
        // Re-throw the ORIGINAL error: it carries the viewer-relative lookup
        // paths that explain the problem.
        throw err
      }
    }
  }
  try {
    return require('../../npm-package/assets/viewer/tailwind.config.js')
  } finally {
    Module._resolveFilename = origResolve
  }
}

/** @type {import('tailwindcss').Config} */
module.exports = {
  presets: [loadViewerPreset()],
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
    '../../npm-package/assets/viewer/src/**/*.{js,ts,jsx,tsx}',
  ],
}
