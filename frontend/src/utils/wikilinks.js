// Pre-process markdown to convert wikilinks to HTML spans
// This runs before ReactMarkdown processes the content

export function preprocessWikilinks(markdown, noteIndex) {
  if (!markdown) return ''

  // Replace [[target|alias]] or [[target]] with HTML spans
  return markdown.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (match, target, alias) => {
    const display = (alias || target).trim()
    const targetName = target.trim()

    // Check if note exists
    const matches = noteIndex[targetName] || []

    if (matches.length === 0) {
      // Missing note - gray span
      return `<span class="wikilink-missing" data-target="${escapeHtml(targetName)}">${escapeHtml(display)}</span>`
    }

    if (matches.length === 1) {
      // Single match - clickable span with data attribute
      return `<span class="wikilink" data-target="${escapeHtml(targetName)}" data-path="${escapeHtml(matches[0])}">${escapeHtml(display)}</span>`
    }

    // Multiple matches - ambiguous link
    const pathsJson = JSON.stringify(matches).replace(/"/g, '&quot;')
    return `<span class="wikilink ambiguous" data-target="${escapeHtml(targetName)}" data-paths="${pathsJson}">${escapeHtml(display)}</span>`
  })
}

function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}
