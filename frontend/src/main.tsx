import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

async function startApp() {
  // Start MSW in development mode
  // if (import.meta.env.DEV) {
  //   const { worker } = await import('./mocks/browser')
  //   await worker.start({
  //     onUnhandledRequest: 'bypass',
  //   })
  //   console.log('[MSW] Mock Service Worker started')
  // }

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}

startApp()