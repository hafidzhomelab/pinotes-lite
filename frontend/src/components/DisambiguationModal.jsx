import { useState } from 'react'
import './DisambiguationModal.css'

export function DisambiguationModal({ target, matches, displayText, onSelect, onCancel }) {
  const [selected, setSelected] = useState(matches[0])

  const handleSubmit = (e) => {
    e.preventDefault()
    onSelect(selected)
  }

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onCancel()
    }
  }

  return (
    <div className="modal-backdrop" onClick={handleBackdropClick}>
      <div className="modal-content" role="dialog" aria-modal="true">
        <h3>Multiple matches for "{target}"</h3>
        
        <form onSubmit={handleSubmit}>
          <div className="match-list">
            {matches.map((path) => (
              <label key={path} className="match-item">
                <input
                  type="radio"
                  name="match"
                  value={path}
                  checked={selected === path}
                  onChange={() => setSelected(path)}
                />
                <span className="match-path">{path}</span>
              </label>
            ))}
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onCancel}>
              Cancel
            </button>
            <button type="submit" className="btn-primary">
              Open
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
