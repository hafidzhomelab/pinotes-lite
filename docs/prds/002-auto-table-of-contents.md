---
title: "PRD: Auto Table of Contents"
created: "2026-02-08"
version: "1.0"
status: "ready-for-dev"
---

# PRD: Auto Table of Contents

## Overview

Auto-generate a table of contents from note headings, enabling quick navigation to sections. Includes scroll position tracking and smooth animations.

## User Stories

| ID | Story | Priority |
|----|-------|----------|
| US-1 | As a reader, I want to see a TOC so I can jump to any section quickly | P0 |
| US-2 | As a reader, I want the current section highlighted so I know where I am | P0 |
| US-3 | As a mobile reader, I want a floating TOC button so I can access it without scrolling | P0 |
| US-4 | As a reader, I want smooth scrolling so navigation feels polished | P1 |

## Requirements

### Functional

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| F1 | Extract headings h1-h4 | Parser finds all `#{1,4} Heading` patterns |
| F2 | Generate TOC items | Each heading becomes a clickable item with proper indentation |
| F3 | Desktop sidebar | Fixed right sidebar, collapsible |
| F4 | Mobile floating button | Bottom-right corner, opens TOC modal |
| F5 | Click to navigate | Click TOC item → smooth scroll to heading |
| F6 | Highlight current | IntersectionObserver tracks visible heading |
| F7 | Collapsible | Desktop: toggle button; Mobile: close on select |

### Non-Functional

| ID | Requirement | Target |
|----|-------------|--------|
| NF1 | TOC generation | < 50ms for notes with < 100 headings |
| NF2 | Scroll tracking | < 16ms (60fps) |
| NF3 | Mobile button | Min 44x44px touch target |

## UI/UX Specification

### Desktop (Right Sidebar)

- **Position:** Fixed right sidebar, `top: header-height`, `height: calc(100vh - header)`
- **Width:** 200px (collapsible to 40px)
- **Content:** TOC items with indentation based on heading level
- **Active item:** Left border highlight + different background
- **Toggle:** Chevron button to collapse/expand

```
┌────────────────┬──────────────────┬─────────────┐
│   Tree Nav     │    Note Body     │  ▾ Contents │
│                │                  │  ─────────  │
│                │   # Intro        │  ● Intro    │
│                │                  │  ○ Setup    │
│                │   ## Setup       │    ○ 2.1    │
│                │   ### 2.1        │    ○ 2.2    │
│                │   ### 2.2        │  ○ Usage    │
│                │                  │    ○ 3.1    │
│                │                  │    ○ 3.2    │
└────────────────┴──────────────────┴─────────────┘
```

### Mobile (Floating Button)

- **Button:** Bottom-right, 56px diameter, circular
- **Icon:** List/menu icon
- **Modal:** Bottom sheet (80vh height)
- **Items:** Full-width, tap to close + navigate

```
┌─────────────────┐
│  Note content   │
│                 │
│                 │  ┌────┐
│                 │  │ ≡  │ ← FAB
│                 │  └────┘
└─────────────────┘
```

## Technical Design

### Data Flow

```
Note Body (Markdown)
       ↓
Extract Headings (h1-h4)
       ↓
Generate TOC Items [{level, text, id}]
       ↓
Render TOC Sidebar (desktop) / Modal (mobile)
       ↓
IntersectionObserver → Update active item
       ↓
Click → smooth scroll to heading
```

### Components

**TableOfContents.jsx**
```javascript
function TableOfContents({ markdown }) {
  const headings = useMemo(() => extractHeadings(markdown), [markdown])
  const [activeId, setActiveId] = useState(null)
  
  useEffect(() => {
    // IntersectionObserver setup
  }, [headings])
  
  return (
    <aside className="toc-sidebar">
      <h3>Contents</h3>
      <nav>
        {headings.map(h => (
          <a
            key={h.id}
            href={`#${h.id}`}
            className={`toc-item level-${h.level} ${activeId === h.id ? 'active' : ''}`}
            onClick={(e) => {
              e.preventDefault()
              scrollToHeading(h.id)
            }}
          >
            {h.text}
          </a>
        ))}
      </nav>
    </aside>
  )
}
```

**FloatingTocButton.jsx**
```javascript
function FloatingTocButton({ headings, activeId, onNavigate }) {
  const [isOpen, setIsOpen] = useState(false)
  
  return (
    <>
      <button className="toc-fab" onClick={() => setIsOpen(true)}>
        ☰
      </button>
      {isOpen && (
        <TocModal
          headings={headings}
          activeId={activeId}
          onNavigate={(id) => {
            onNavigate(id)
            setIsOpen(false)
          }}
          onClose={() => setIsOpen(false)}
        />
      )}
    </>
  )
}
```

### Helper Functions

```javascript
function extractHeadings(markdown) {
  const regex = /^(#{1,4})\s+(.+)$/gm
  const matches = [...markdown.matchAll(regex)]
  
  return matches.map((match, index) => ({
    level: match[1].length,
    text: match[2].trim(),
    id: `heading-${index}-${slugify(match[2])}`
  }))
}

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
}
```

### CSS

```css
/* Desktop sidebar */
.toc-sidebar {
  position: fixed;
  right: 0;
  top: var(--header-height);
  width: 200px;
  height: calc(100vh - var(--header-height));
  overflow-y: auto;
  padding: 1rem;
  border-left: 1px solid var(--border-color);
}

.toc-item {
  display: block;
  padding: 0.25rem 0.5rem;
  text-decoration: none;
  color: inherit;
}

.toc-item.level-1 { padding-left: 0.5rem; }
.toc-item.level-2 { padding-left: 1rem; }
.toc-item.level-3 { padding-left: 1.5rem; }
.toc-item.level-4 { padding-left: 2rem; }

.toc-item.active {
  border-left: 2px solid var(--primary-color);
  background: var(--active-bg);
}

/* Mobile FAB */
.toc-fab {
  position: fixed;
  bottom: 1rem;
  right: 1rem;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  /* ... */
}

/* Smooth scroll */
html {
  scroll-behavior: smooth;
}
```

## Testing Strategy

### Unit Tests
- Extract headings from various markdown patterns
- Slugify function edge cases

### Integration Tests
- Click TOC → scrolls to correct heading
- Scroll to heading → TOC highlights correctly
- Mobile FAB opens/closes correctly

### Manual Tests
- Long notes (100+ headings)
- Notes with no headings (TOC hidden)
- Notes with special characters in headings
- Mobile touch targets

## Success Metrics

- [ ] TOC renders for all notes with headings
- [ ] Active section tracking works smoothly
- [ ] Mobile FAB accessible and usable
- [ ] No performance degradation on large notes

## Out of Scope

- Editable TOC (drag to reorder)
- Collapsible sections within TOC
- TOC in exported/printed notes

## Open Questions

None — all design decisions finalized.

## Related Documents

- Ideation: `02-projects/pinotes-lite/pinotes-lite-auto-toc-ideation.md`
- Previous feature: `docs/prds/001-wikilink-navigation.md`

---

**Status:** Ready for development  
**Estimated effort:** 1 day  
**Branch naming:** `feature/auto-table-of-contents`
