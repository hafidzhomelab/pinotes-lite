---
title: "PRD: Wikilink Navigation"
created: "2026-02-08"
version: "1.0"
status: "ready-for-dev"
---

# PRD: Wikilink Navigation

## Overview

Enable clickable wikilink navigation in PiNotes Lite, allowing users to follow `[[Note Name]]` references and discover linked mentions.

## User Stories

| ID | Story | Priority |
|----|-------|----------|
| US-1 | As a reader, I want to click `[[Note Name]]` to navigate to that note | P0 |
| US-2 | As a reader, I want to see `[[Note\|Alias]]` display "Alias" but navigate to "Note" | P0 |
| US-3 | As a reader, I want to see which notes link to the current one | P1 |
| US-4 | As a reader, I want to know when a wikilink has no target | P1 |

## Requirements

### Functional

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| F1 | Parse wikilinks from Markdown | Regex: `\[\[([^\]|]+)(?:\|([^\]]+))?\]\]` |
| F2 | Render as clickable links | Click navigates to note; blue color; hover state |
| F3 | Support display aliases | `[[Note\|Alias]]` shows "Alias", navigates to "Note" |
| F4 | Handle missing notes | Gray plain text; no click; no special cursor |
| F5 | Handle duplicate filenames | Show disambiguation list with full paths |
| F6 | Show linked mentions | Collapsible section at bottom of note |
| F7 | Case-sensitive matching | `[[Note]]` matches `Note.md`, not `note.md` |
| F8 | Filename-only matching | `[[Note]]` matches `Note.md` anywhere in vault |

### Non-Functional

| ID | Requirement | Target |
|----|-------------|--------|
| NF1 | Index build time | < 500ms for 1000 notes (on-demand) |
| NF2 | Navigation response | < 100ms after click |
| NF3 | Backlinks query | < 200ms |
| NF4 | Mobile friendly | Touch targets ≥ 44px; collapsible fits small screens |

## API Specification

### GET /api/notes/index
Returns filename-to-paths mapping for wikilink resolution.

**Response:**
```json
{
  "index": {
    "Note Name": ["02-projects/pinotes-lite/Note Name.md"],
    "ideas": ["02-projects/ideas.md", "03-areas/writing/ideas.md"]
  }
}
```

**Caching:** Built on-demand, cached per session (in-memory).

### GET /api/notes/backlinks
Returns notes that link to a given filename.

**Query Parameters:**
- `filename` (required): The filename to search for (e.g., "Note Name")

**Response:**
```json
[
  {
    "path": "02-projects/pinotes-lite.md",
    "title": "PiNotes Lite",
    "snippet": "...see also [[Note Name]] for more..."
  }
]
```

## UI/UX Specification

### Wikilink Rendering

| State | Visual |
|-------|--------|
| Valid (single match) | Blue text, underline on hover, pointer cursor |
| Valid (multiple matches) | Blue text, dotted underline, pointer cursor |
| Missing | Gray text (`#6b7280`), no underline, default cursor |

### Disambiguation Modal

```
┌──────────────────────────────────────┐
│  Multiple matches for "ideas"        │
├──────────────────────────────────────┤
│  ○ 02-projects/pinotes-lite/ideas.md │
│  ○ 03-areas/writing/ideas.md         │
│                                      │
│        [Cancel]  [Open]              │
└──────────────────────────────────────┘
```

- Shows full vault path for context
- First item selected by default
- Clicking row selects that item
- ESC or Cancel closes modal

### Linked Mentions Section

```
┌──────────────────────────────────────┐
│  ▾ Linked Mentions (3)               │
├──────────────────────────────────────┤
│  • Project Roadmap                   │
│    "...as discussed in [[Note Name]] │
│    regarding the timeline..."        │
│                                      │
│  • Weekly Review                     │
│    "...linked to [[Note Name]] for   │
│    reference..."                     │
└──────────────────────────────────────┘
```

- Collapsed by default on mobile
- Expanded by default on desktop
- Shows note title + contextual snippet
- Click row to navigate to source note

## Technical Design

### Backend Changes

**New file: `app/wikilinks.py`**
```python
class WikilinkIndex:
    def __init__(self):
        self._cache = None
    
    def get_index(self) -> dict[str, list[str]]:
        # Lazy build on first call
        pass
    
    def find_backlinks(self, filename: str) -> list[dict]:
        # Scan all notes for wikilinks to filename
        pass
```

**Modified: `app/main.py`**
- Add routes `/api/notes/index` and `/api/notes/backlinks`
- Inject wikilink index as dependency

### Frontend Changes

**New file: `frontend/src/components/Wikilink.jsx`**
```jsx
function Wikilink({ raw, noteIndex, onNavigate }) {
  // Parse [[target|alias]]
  // Lookup in noteIndex
  // Render link or span
}
```

**New file: `frontend/src/components/DisambiguationModal.jsx`**
```jsx
function DisambiguationModal({ matches, onSelect, onCancel }) {
  // Show list of paths
  // Handle selection
}
```

**New file: `frontend/src/components/LinkedMentions.jsx`**
```jsx
function LinkedMentions({ filename }) {
  // Fetch /api/notes/backlinks
  // Render collapsible section
}
```

**Modified: `frontend/src/App.jsx`**
- Add wikilink preprocessing to Markdown
- Add LinkedMentions at bottom of note view
- Add modal state for disambiguation

## Data Flow

```
User clicks [[Note Name]]
       ↓
Frontend looks up in cached noteIndex
       ↓
├─ Single match → Navigate directly
├─ Multiple matches → Show DisambiguationModal
└─ No match → Do nothing (already rendered as gray)
       ↓
On navigation → Fetch note + backlinks
       ↓
Render note + LinkedMentions section
```

## Testing Strategy

### Unit Tests (Backend)
- Index building with duplicate filenames
- Backlink detection with various wikilink formats
- Case-sensitive matching

### Unit Tests (Frontend)
- Wikilink regex parsing
- Disambiguation modal selection
- Collapsible section toggle

### Integration Tests
- Click wikilink → navigate to note
- Multiple matches → disambiguation → navigation
- Backlinks appear correctly

### Manual Testing
- Mobile: Touch targets, collapsible behavior
- Large vault: Performance with 1000+ notes
- Edge cases: Special characters in filenames

## Success Metrics

- [ ] All `[[Note]]` in vault are clickable
- [ ] Missing links clearly distinguished (gray)
- [ ] Backlinks discovered correctly
- [ ] Navigation feels instant (< 100ms perceived)

## Out of Scope

- Heading anchors (`[[Note#Heading]]`)
- Embedded transclusion (`![[Note]]`)
- Graph visualization
- Fuzzy/case-insensitive matching

## Open Questions

None — all design decisions finalized in ideation phase.

## Related Documents

- Ideation: `02-projects/pinotes-lite/pinotes-lite-wikilink-ideation.md` (notes vault)
- Architecture: `docs/architecture/` (if ADR needed)

---

**Status:** Ready for development  
**Estimated effort:** 1-2 days  
**Branch naming:** `feature/wikilink-navigation`
