import { useState } from 'react'
import './FloatingTocButton.css'

export function FloatingTocButton({ headings, activeId, onNavigate }) {
  const [isOpen, setIsOpen] = useState(false)

  if (headings.length === 0) return null

  return (
    <>
      <button
        className="toc-fab"
        onClick={() => setIsOpen(true)}
        aria-label="Open table of contents"
      >
        ☰
      </button>

      {isOpen && (
        <div className="toc-modal-overlay" onClick={() => setIsOpen(false)}>
          <div className="toc-modal" onClick={(e) => e.stopPropagation()}>
            <div className="toc-modal-header">
              <h3>Contents</h3>
              <button
                className="toc-modal-close"
                onClick={() => setIsOpen(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>
            
            <nav className="toc-modal-nav">
              {headings.map((heading) => (
                <button
                  key={heading.id}
                  className={`toc-modal-item level-${heading.level} ${activeId === heading.id ? 'active' : ''}`}
                  onClick={() => {
                    onNavigate(heading.id)
                    setIsOpen(false)
                  }}
                >
                  {heading.text}
                </button>
              ))}
            </nav>
          </div>
        </div>
      )}
    </>
  )
}
