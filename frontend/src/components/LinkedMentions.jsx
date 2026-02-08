import { useState, useEffect } from 'react'
import './LinkedMentions.css'

export function LinkedMentions({ filename }) {
  const [backlinks, setBacklinks] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(true)

  useEffect(() => {
    if (!filename) return

    setLoading(true)
    setError('')

    fetch(`/api/notes/backlinks?filename=${encodeURIComponent(filename)}`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load backlinks')
        return res.json()
      })
      .then((data) => {
        setBacklinks(data)
      })
      .catch((err) => {
        setError(err.message)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [filename])

  if (backlinks.length === 0 && !loading) return null

  return (
    <section className="linked-mentions">
      <button
        className="linked-mentions-toggle"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <span className="toggle-icon">{expanded ? '▾' : '▸'}</span>
        <span>Linked Mentions ({backlinks.length})</span>
      </button>

      {expanded && (
        <div className="linked-mentions-content">
          {loading && <p className="linked-mentions-status">Loading...</p>}
          {error && <p className="linked-mentions-error">{error}</p>}

          {!loading && !error && (
            <ul className="backlink-list">
              {backlinks.map((backlink) => (
                <li key={backlink.path} className="backlink-item">
                  <button
                    className="backlink-button"
                    onClick={() => {
                      // Navigate to this note
                      window.dispatchEvent(
                        new CustomEvent('navigate-to-note', {
                          detail: { path: backlink.path }
                        })
                      )
                    }}
                  >
                    <strong className="backlink-title">{backlink.title}</strong>
                    <p className="backlink-snippet">{backlink.snippet}</p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
