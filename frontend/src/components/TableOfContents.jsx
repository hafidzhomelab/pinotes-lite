import { useMemo } from 'react'
import './TableOfContents.css'

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
}

export function extractHeadings(markdown) {
  if (!markdown) return []
  
  const regex = /^(#{1,4})\s+(.+)$/gm
  const matches = [...markdown.matchAll(regex)]
  
  return matches.map((match, index) => ({
    level: match[1].length,
    text: match[2].trim(),
    id: `heading-${index}-${slugify(match[2])}`
  }))
}

export function TableOfContents({ headings, activeId, onNavigate, isCollapsed, onToggle }) {
  if (headings.length === 0) return null

  return (
    <aside className={`toc-sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      <div className="toc-header">
        {!isCollapsed && <h3>Contents</h3>}
        <button
          className="toc-toggle"
          onClick={onToggle}
          aria-label={isCollapsed ? 'Expand contents' : 'Collapse contents'}
        >
          {isCollapsed ? '◀' : '▶'}
        </button>
      </div>
      
      {!isCollapsed && (
        <nav className="toc-nav">
          {headings.map((heading) => (
            <a
              key={heading.id}
              href={`#${heading.id}`}
              className={`toc-item level-${heading.level} ${activeId === heading.id ? 'active' : ''}`}
              onClick={(e) => {
                e.preventDefault()
                onNavigate(heading.id)
              }}
            >
              {heading.text}
            </a>
          ))}
        </nav>
      )}
    </aside>
  )
}
