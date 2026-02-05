import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [health, setHealth] = useState(null) // null | 'ok' | 'error'

  useEffect(() => {
    fetch('/api/healthz')
      .then((res) => res.json())
      .then((data) => setHealth(data.status))
      .catch(() => setHealth('error'))
  }, [])

  return (
    <div className="app">
      <header className="app-header">
        <h1>🔥 PiNotes Lite</h1>
      </header>

      <main className="app-main">
        <p className="health-status">
          Backend: <span className={`health-badge health-${health ?? 'pending'}`}>{health ?? 'checking…'}</span>
        </p>
        <p className="placeholder-note">
          Scaffold complete. Next: auth, file tree, note reader.
        </p>
      </main>
    </div>
  )
}

export default App
