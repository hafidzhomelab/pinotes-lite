import { useEffect, useMemo, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import './App.css'
import { DisambiguationModal } from './components/DisambiguationModal'
import { LinkedMentions } from './components/LinkedMentions'
import { TableOfContents, extractHeadings } from './components/TableOfContents'
import { FloatingTocButton } from './components/FloatingTocButton'

const ATTACHMENTS_ROUTE = '/api/attachments'

// Extend the default sanitize schema to allow wikilink classes
const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    span: [
      ...(defaultSchema.attributes?.span || []),
      ['className', 'wikilink', 'wikilink-missing', 'ambiguous']
    ]
  }
}

function encodePathSegments(path) {
  return path
    .split('/')
    .map((segment) => encodeURIComponent(segment))
    .join('/')
}

function createAttachmentUrl(relativePath) {
  if (!relativePath) {
    return ATTACHMENTS_ROUTE
  }
  const normalized = relativePath.replace(/^\/+/, '')
  return `${ATTACHMENTS_ROUTE}/${encodePathSegments(normalized)}`
}

function expandDirectorySet(prevSet, notePath) {
  const next = new Set(prevSet)
  const segments = notePath.split('/')
  let current = ''
  for (let i = 0; i < segments.length - 1; i += 1) {
    current = current ? `${current}/${segments[i]}` : segments[i]
    next.add(current)
  }
  return next
}

function findFirstNotePath(node) {
  if (!node?.children?.length) {
    return null
  }
  for (const child of node.children) {
    if (child.type === 'file') {
      return child.path
    }
    if (child.type === 'dir') {
      const nested = findFirstNotePath(child)
      if (nested) {
        return nested
      }
    }
  }
  return null
}

function isAbsoluteOrRemote(src) {
  if (!src) {
    return true
  }
  const trimmed = src.trim()
  return (
    trimmed.startsWith('/') ||
    trimmed.startsWith('http://') ||
    trimmed.startsWith('https://') ||
    trimmed.startsWith('data:') ||
    trimmed.startsWith('//')
  )
}

function normalizeRelativePath(baseDir, relativePath) {
  const baseParts = baseDir ? baseDir.split('/').filter(Boolean) : []
  const parts = relativePath.split('/')
  const stack = [...baseParts]
  for (const part of parts) {
    if (!part || part === '.') {
      continue
    }
    if (part === '..') {
      if (stack.length) {
        stack.pop()
      }
      continue
    }
    stack.push(part)
  }
  return stack.join('/')
}

function rewriteObsidianEmbeds(body) {
  return body.replace(/!\[\[(.+?)\]\]/g, (_, inner) => {
    const [rawPath, rawAlt] = inner.split('|')
    const trimmedPath = rawPath?.trim()
    if (!trimmedPath) {
      return ''
    }
    const alt = rawAlt?.trim() ?? ''
    return `![${alt}](${createAttachmentUrl(`_attachments/${trimmedPath}`)})`
  })
}

function rewriteRelativeImages(body, notePath) {
  const noteDir = notePath.includes('/') ? notePath.slice(0, notePath.lastIndexOf('/')) : ''
  return body.replace(/!\[([^\]]*?)\]\(([^)]+)\)/g, (match, alt, src) => {
    const trimmedSrc = src.trim()
    if (!trimmedSrc || isAbsoluteOrRemote(trimmedSrc)) {
      return match
    }
    const resolved = normalizeRelativePath(noteDir, trimmedSrc)
    if (!resolved) {
      return match
    }
    return `![${alt}](${createAttachmentUrl(resolved)})`
  })
}

function rewriteNoteBody(note, noteIndex, onDisambiguate) {
  if (!note) {
    return ''
  }
  let markdown = note.body ?? ''
  markdown = rewriteObsidianEmbeds(markdown)
  markdown = rewriteRelativeImages(markdown, note.path)
  markdown = rewriteWikilinks(markdown, noteIndex, onDisambiguate)
  return markdown
}

function rewriteWikilinks(body, noteIndex, onDisambiguate) {
  // Replace [[target|alias]] or [[target]] with markdown links or styled spans
  return body.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (match, target, alias) => {
    const display = (alias || target).trim()
    const targetName = target.trim()
    const matches = noteIndex[targetName] || []

    if (matches.length === 0) {
      // Missing note - use HTML span that won't be escaped
      return `<span class="wikilink-missing">${escapeHtml(display)}</span>`
    }

    if (matches.length === 1) {
      // Single match - create markdown link
      const encodedPath = encodePathSegments(matches[0])
      return `[${display}](/notes/${encodedPath})`
    }

    // Multiple matches - use special marker that will be handled by click handler
    // We'll use a data attribute approach with HTML
    const pathsAttr = matches.map(p => encodePathSegments(p)).join(',')
    return `<span class="wikilink ambiguous" data-target="${escapeHtml(targetName)}" data-paths="${pathsAttr}">${escapeHtml(display)}</span>`
  })
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function formatMetaValue(key, value) {
  if (key === 'created' || key === 'updated') {
    const parsed = new Date(value)
    if (!Number.isNaN(parsed.valueOf())) {
      return parsed.toLocaleString()
    }
  }
  if (Array.isArray(value)) {
    return value.join(', ')
  }
  if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value)
  }
  if (value === null || value === undefined) {
    return ''
  }
  return String(value)
}

function encodeNotePath(path) {
  return encodePathSegments(path)
}

function ImageWithFallback({ src, alt }) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return (
      <div className="image-placeholder">
        <span>{alt || 'Image not available'}</span>
        <small>Image could not be loaded.</small>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}

// Custom component for ReactMarkdown to handle wikilink clicks and TOC
function createMarkdownComponents({ onNavigate, onDisambiguate, headings }) {
  // Create heading components with data-heading-id
  const headingComponents = {}
  ;['h1', 'h2', 'h3', 'h4'].forEach((level, index) => {
    headingComponents[level] = ({ node, children, ...props }) => {
      const headingIndex = headings.findIndex(
        (h) => h.level === index + 1 && h.text === children?.[0]
      )
      const headingId = headingIndex >= 0 ? headings[headingIndex].id : undefined
      const Tag = level
      return (
        <Tag {...props} data-heading-id={headingId}>
          {children}
        </Tag>
      )
    }
  })

  return {
    ...headingComponents,
    img: ({ src, alt }) => <ImageWithFallback src={src} alt={alt} />,
    a: ({ href, children }) => {
      // Check if href is a wikilink-style reference to notes
      if (href?.startsWith('/notes/')) {
        return (
          <a
            href={href}
            className="wikilink"
            onClick={(e) => {
              e.preventDefault()
              onNavigate(href.replace('/notes/', ''))
            }}
          >
            {children}
          </a>
        )
      }
      return (
        <a href={href} target="_blank" rel="noreferrer">
          {children}
        </a>
      )
    },
    span: ({ node, children, ...props }) => {
      const className = props.className || ''
      
      // Handle missing wikilinks
      if (className.includes('wikilink-missing')) {
        return <span className="wikilink-missing">{children}</span>
      }
      
      // Handle ambiguous wikilinks
      if (className.includes('wikilink') && className.includes('ambiguous')) {
        const target = props['data-target']
        const pathsStr = props['data-paths']
        const paths = pathsStr ? pathsStr.split(',') : []
        
        return (
          <span
            className="wikilink ambiguous"
            onClick={() => onDisambiguate(target, paths, children)}
            style={{ cursor: 'pointer' }}
          >
            {children}
          </span>
        )
      }
      
      return <span {...props}>{children}</span>
    },
  }
}

function App() {
  const [authenticated, setAuthenticated] = useState(null)
  const [health, setHealth] = useState(null)
  const [tree, setTree] = useState(null)
  const [treeError, setTreeError] = useState('')
  const [selectedPath, setSelectedPath] = useState('')
  const [note, setNote] = useState(null)
  const [noteError, setNoteError] = useState('')
  const [loadingNote, setLoadingNote] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [loggingIn, setLoggingIn] = useState(false)
  const [lockoutUntil, setLockoutUntil] = useState(null)
  const [expandedDirs, setExpandedDirs] = useState(() => new Set(['']))
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [frontmatterOpen, setFrontmatterOpen] = useState(false)

  // Wikilink state
  const [noteIndex, setNoteIndex] = useState({})
  const [disambiguation, setDisambiguation] = useState(null)

  // Table of Contents state
  const [tocActiveId, setTocActiveId] = useState(null)
  const [tocCollapsed, setTocCollapsed] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    setFrontmatterOpen(window.innerWidth >= 768)
  }, [])

  useEffect(() => {
    fetch('/api/auth/me')
      .then((res) => res.json())
      .then((data) => setAuthenticated(data.authenticated))
      .catch(() => setAuthenticated(false))
  }, [])

  useEffect(() => {
    if (!authenticated) {
      return
    }
    setTree(null)
    setTreeError('')
    fetch('/api/notes/tree')
      .then((res) => {
        if (!res.ok) {
          throw new Error('Unable to load vault')
        }
        return res.json()
      })
      .then((data) => setTree(data))
      .catch((error) => setTreeError(error.message || 'Unable to load vault tree'))
  }, [authenticated])

  useEffect(() => {
    if (!authenticated) {
      return
    }
    fetch('/api/healthz')
      .then((res) => res.json())
      .then((data) => setHealth(data.status))
      .catch(() => setHealth('error'))
  }, [authenticated])

  // Fetch note index for wikilinks
  useEffect(() => {
    if (!authenticated) {
      return
    }
    fetch('/api/notes/index')
      .then((res) => res.json())
      .then((data) => setNoteIndex(data.index || {}))
      .catch(() => setNoteIndex({}))
  }, [authenticated])

  useEffect(() => {
    if (!tree) {
      return
    }
    if (selectedPath) {
      return
    }
    const first = findFirstNotePath(tree)
    if (first) {
      setExpandedDirs((prev) => expandDirectorySet(prev, first))
      setSelectedPath(first)
    }
  }, [tree, selectedPath])

  useEffect(() => {
    if (!selectedPath) {
      setNote(null)
      setNoteError('')
      return
    }
    setLoadingNote(true)
    setNoteError('')
    fetch(`/api/notes/${encodeNotePath(selectedPath)}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error('Note not available')
        }
        return res.json()
      })
      .then((data) => setNote(data))
      .catch((error) => setNoteError(error.message || 'Unable to load note.'))
      .finally(() => setLoadingNote(false))
  }, [selectedPath])

  useEffect(() => {
    if (searchQuery.trim()) {
      return
    }
    setSearchResults([])
    setSearchError('')
  }, [searchQuery])

  // Listen for navigation events from LinkedMentions
  useEffect(() => {
    const handleNavigate = (e) => {
      if (e.detail?.path) {
        handleSelectNote(e.detail.path)
      }
    }
    window.addEventListener('navigate-to-note', handleNavigate)
    return () => window.removeEventListener('navigate-to-note', handleNavigate)
  }, [])

  // Table of Contents: IntersectionObserver for active heading
  useEffect(() => {
    if (!note) {
      setTocActiveId(null)
      return
    }

    const headings = document.querySelectorAll('[data-heading-id]')
    if (headings.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        // Find the most visible heading
        const visible = entries.filter((e) => e.isIntersecting)
        if (visible.length > 0) {
          // Use the first visible one (topmost)
          setTocActiveId(visible[0].target.dataset.headingId)
        }
      },
      {
        rootMargin: '-20% 0px -60% 0px',
        threshold: 0,
      }
    )

    headings.forEach((h) => observer.observe(h))
    return () => observer.disconnect()
  }, [note, transformedBody])

  // Define handleDisambiguate BEFORE transformedBody useMemo
  const handleDisambiguate = useCallback((target, matches, displayText) => {
    setDisambiguation({ target, matches, displayText })
  }, [])

  const transformedBody = useMemo(() => rewriteNoteBody(note, noteIndex, handleDisambiguate), [note, noteIndex, handleDisambiguate])

  const handleLogin = async (event) => {
    event.preventDefault()
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
        setLockoutUntil(null)
        return
      }

      if (res.status === 429) {
        const data = await res.json()
        const lockTime = new Date(data.locked_until)
        setLockoutUntil(lockTime)
        const hh = String(lockTime.getHours()).padStart(2, '0')
        const mm = String(lockTime.getMinutes()).padStart(2, '0')
        setLoginError(`Account locked. Try again at ${hh}:${mm}.`)
        return
      }

      setLoginError('Invalid username or password.')
    } catch {
      setLoginError('Network error. Check your connection.')
    } finally {
      setLoggingIn(false)
    }
  }

  const handleLogout = async () => {
    await fetch('/api/auth/logout', { method: 'POST' })
    window.location.reload()
  }

  const toggleDirectory = (path) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }

  const handleSelectNote = useCallback((path) => {
    setExpandedDirs((prev) => expandDirectorySet(prev, path))
    setSelectedPath(path)
  }, [])

  const handleSearch = async (event) => {
    event.preventDefault()
    const query = searchQuery.trim()
    if (!query) {
      setSearchResults([])
      return
    }
    setSearching(true)
    setSearchError('')
    try {
      const res = await fetch(`/api/notes/search?q=${encodeURIComponent(query)}`)
      if (!res.ok) {
        throw new Error('Search failed')
      }
      const data = await res.json()
      setSearchResults(data)
    } catch (error) {
      setSearchError(error.message || 'Search is currently unavailable.')
    } finally {
      setSearching(false)
    }
  }

  const handleSearchResultClick = (path) => {
    handleSelectNote(path)
  }

  // Table of Contents: scroll to heading
  const scrollToHeading = useCallback((headingId) => {
    const element = document.querySelector(`[data-heading-id="${headingId}"]`)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [])

  // Extract headings for TOC
  const tocHeadings = useMemo(() => extractHeadings(note?.body || ''), [note])

  const handleDisambiguationSelect = (path) => {
    setDisambiguation(null)
    handleSelectNote(path)
  }

  const markdownComponents = useMemo(
    () =>
      createMarkdownComponents({
        onNavigate: handleSelectNote,
        onDisambiguate: handleDisambiguate,
        headings: tocHeadings,
      }),
    [handleSelectNote, handleDisambiguate, tocHeadings]
  )

  if (authenticated === null) {
    return (
      <div className="app">
        <div className="login-card">
          <p>Checking authentication…</p>
        </div>
      </div>
    )
  }

  if (!authenticated) {
    const isLocked = lockoutUntil && new Date() < lockoutUntil
    return (
      <div className="app">
        <div className="login-card">
          <h1>PiNotes Lite</h1>
          <form onSubmit={handleLogin} className="login-form">
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              disabled={isLocked}
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              disabled={isLocked}
              required
            />
            <button type="submit" disabled={loggingIn || isLocked}>
              {loggingIn ? 'Signing in…' : 'Sign in'}
            </button>
            {loginError && <p className="login-error">{loginError}</p>}
          </form>
        </div>
      </div>
    )
  }

  const noteTitle = note?.frontmatter?.title
    ? note.frontmatter.title
    : selectedPath?.split('/').pop()

  // Get filename for backlinks (without .md extension)
  const noteFilename = note ? selectedPath?.split('/').pop()?.replace(/\.md$/, '') : null

  return (
    <div className="app">
      <div className="app-shell">
        <header className="app-header">
          <div>
            <p className="eyebrow">PiNotes Lite · Tailscale-only notes viewer</p>
            <h1>PiNotes Lite</h1>
          </div>
          <div className="header-actions">
            <div className="health-status">
              Backend:{' '}
              <span className={`health-badge health-${health ?? 'pending'}`}>
                {health ?? 'checking…'}
              </span>
            </div>
            <button className="logout-btn" onClick={handleLogout}>
              Logout
            </button>
          </div>
        </header>

        {treeError && <div className="alert error">{treeError}</div>}

        <div className="app-body">
          <aside className="sidebar">
            <div className="sidebar-section">
              <h2>Search notes</h2>
              <form onSubmit={handleSearch} className="search-form">
                <input
                  type="search"
                  placeholder="Search the vault"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                />
                <button type="submit" disabled={searching}>
                  {searching ? 'Searching…' : 'Search'}
                </button>
              </form>
              {searchError && <p className="search-error">{searchError}</p>}
              {searchResults.length > 0 ? (
                <ul className="search-results">
                  {searchResults.map((result) => (
                    <li key={result.path}>
                      <button type="button" onClick={() => handleSearchResultClick(result.path)}>
                        <strong>{result.title}</strong>
                        <p
                          className="search-snippet"
                          dangerouslySetInnerHTML={{ __html: result.snippet }}
                        />
                        <span className="search-path">{result.path}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                searchQuery.trim() && !searching ? (
                  <p className="search-empty">No matches found.</p>
                ) : null
              )}
            </div>

            <div className="sidebar-section tree-section">
              <div className="tree-header">
                <h2>Vault tree</h2>
                <span>{tree ? tree.children?.length ?? 0 : '…'} nodes</span>
              </div>
              {tree ? (
                <nav className="tree-nav" aria-label="Vault notes">
                  {tree.children?.length ? (
                    renderTree(tree.children, '', expandedDirs, selectedPath, handleSelectNote, toggleDirectory)
                  ) : (
                    <p className="empty-state">No notes found in the vault.</p>
                  )}
                </nav>
              ) : (
                <p className="empty-state">Loading vault…</p>
              )}
            </div>
          </aside>

          <section className="content">
            {noteError && <div className="alert error">{noteError}</div>}
            {loadingNote && <p className="status">Loading note…</p>}
            {!loadingNote && !note && (
              <p className="status">Select a note to start reading.</p>
            )}
            {note && (
              <article className="note-card">
                <header className="note-header">
                  <div>
                    <p className="note-path">{note.path}</p>
                    <h2>{noteTitle}</h2>
                  </div>
                </header>

                {note.frontmatter && Object.keys(note.frontmatter).length > 0 && (
                  <section className="metadata-card">
                    <div className="metadata-header">
                      <strong>Metadata</strong>
                      <button
                        type="button"
                        className="metadata-toggle"
                        onClick={() => setFrontmatterOpen((prev) => !prev)}
                      >
                        {frontmatterOpen ? 'Hide metadata' : 'Show metadata'}
                      </button>
                    </div>
                    {frontmatterOpen && (
                      <div className="metadata-content">
                        {Array.isArray(note.frontmatter.tags) && note.frontmatter.tags.length > 0 && (
                          <div className="metadata-tags">
                            {note.frontmatter.tags.map((tag) => (
                              <span key={tag} className="tag">
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                        <div className="metadata-grid">
                          {Object.entries(note.frontmatter).map(([key, value]) => {
                            if (['tags'].includes(key)) {
                              return null
                            }
                            const formatted = formatMetaValue(key, value)
                            if (!formatted) {
                              return null
                            }
                            return (
                              <div key={key} className="metadata-row">
                                <span className="metadata-key">{key}</span>
                                <span className="metadata-value">{formatted}</span>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </section>
                )}

                <div className="note-body">
                  <ReactMarkdown
                    children={transformedBody}
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[[rehypeSanitize, sanitizeSchema], rehypeHighlight]}
                    components={markdownComponents}
                  />
                </div>

                {noteFilename && <LinkedMentions filename={noteFilename} />}
              </article>
            )}
          </section>

          {/* Table of Contents - Desktop sidebar */}
          {note && tocHeadings.length > 0 && (
            <TableOfContents
              headings={tocHeadings}
              activeId={tocActiveId}
              onNavigate={scrollToHeading}
              isCollapsed={tocCollapsed}
              onToggle={() => setTocCollapsed((prev) => !prev)}
            />
          )}
        </div>
      </div>

      {/* Floating TOC Button - Mobile */}
      {note && tocHeadings.length > 0 && (
        <FloatingTocButton
          headings={tocHeadings}
          activeId={tocActiveId}
          onNavigate={scrollToHeading}
        />
      )}

      {disambiguation && (
        <DisambiguationModal
          target={disambiguation.target}
          matches={disambiguation.matches}
          displayText={disambiguation.displayText}
          onSelect={handleDisambiguationSelect}
          onCancel={() => setDisambiguation(null)}
        />
      )}
    </div>
  )
}

function renderTree(nodes, parentPath, expandedDirs, selectedPath, selectNote, toggleDir, depth = 0) {
  return (
    <ul className="tree-list">
      {nodes.map((node) => {
        if (node.type === 'dir') {
          const dirPath = parentPath ? `${parentPath}/${node.name}` : node.name
          const isExpanded = expandedDirs.has(dirPath)
          return (
            <li key={dirPath} className="tree-node tree-dir">
              <button
                type="button"
                className="tree-link"
                style={{ '--tree-depth': depth }}
                onClick={() => toggleDir(dirPath)}
                aria-expanded={isExpanded}
              >
                <span className="tree-toggle" aria-hidden="true">
                  {isExpanded ? '▾' : '▸'}
                </span>
                <span>{node.name}</span>
              </button>
              {isExpanded &&
                renderTree(
                  node.children ?? [],
                  dirPath,
                  expandedDirs,
                  selectedPath,
                  selectNote,
                  toggleDir,
                  depth + 1
                )}
            </li>
          )
        }
        if (node.type === 'file') {
          const isActive = selectedPath === node.path
          return (
            <li key={node.path} className={`tree-node tree-file${isActive ? ' active' : ''}`}>
              <button
                type="button"
                className="tree-link"
                style={{ '--tree-depth': depth }}
                onClick={() => selectNote(node.path)}
              >
                <span>{node.name}</span>
              </button>
            </li>
          )
        }
        return null
      })}
    </ul>
  )
}

export default App
