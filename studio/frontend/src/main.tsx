import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
// The VIEWER's stylesheet (theme vars + Tailwind layers), intentionally
// pulled in through the @ alias.
import '@/index.css'
import 'highlight.js/styles/atom-one-dark.min.css'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
