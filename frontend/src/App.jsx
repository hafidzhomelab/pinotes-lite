import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [authenticated, setAuthenticated] = useState(null) // null = checking
  const [health, setHealth] = useState(null) // null | 'ok' | 'error'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [loggingIn, setLoggingIn] = useState(false)

  // Check auth state on mount
  useEffect(() => {
    fetch('/api/auth/me')
      .then((res) => res.json())
      .then((data) => setAuthenticated(data.authenticated))
      .catch(() => setAuthenticated(false))
  }, [])

  // Fetch health when authenticated
  useEffect(() => {
    if (authenticated) {
      fetch('/api/healthz')
        .then((res) => res.json())
        .then((data) => setHealth(data.status))
        .catch(() => setHealth('error'))
    }
  }, [authenticated])

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoggingIn(true)
    setLoginError('')

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })

      if (res.ok) {
        setAuthenticated(true)
        setUsername('')
        setPassword('')
      } else {
        setLoginError('Invalid credentials')
      }
    } catch {
      setLoginError('Network error')
    } finally {
      setLoggingIn(false)
    }
  }

  const handleLogout = async () => {
    await fetch('/api/auth/logout', { method: 'POST' })
    window.location.reload()
  }

  // Loading state
  if (authenticated === null) {
    return (
      <div className="app">
        <div className="login-card">
          <p>Loading...</p>
        </div>
      </div>
    )
  }

  // Login form
  if (!authenticated) {
    return (
      <div className="app">
        <div className="login-card">
          <h1>PiNotes Lite</h1>
          <form onSubmit={handleLogin} className="login-form">
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
            <button type="submit" disabled={loggingIn}>
              {loggingIn ? 'Signing in...' : 'Sign in'}
            </button>
            {loginError && <p className="login-error">{loginError}</p>}
          </form>
        </div>
      </div>
    )
  }

  // Authenticated view
  return (
    <div className="app">
      <header className="app-header">
        <h1>PiNotes Lite</h1>
        <button onClick={handleLogout} className="logout-btn">
          Logout
        </button>
      </header>

      <main className="app-main">
        <p className="health-status">
          Backend: <span className={`health-badge health-${health ?? 'pending'}`}>{health ?? 'checking...'}</span>
        </p>
        <p className="placeholder-note">
          Scaffold complete. Next: file tree, note reader.
        </p>
      </main>
    </div>
  )
}

export default App
