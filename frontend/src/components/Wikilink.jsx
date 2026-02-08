import { useState, useCallback } from 'react'
import './Wikilink.css'

export function Wikilink({ raw, noteIndex, onNavigate, onDisambiguate }) {
  // Parse [[target|alias]] or [[target]]
  const match = raw.match(/^\[\[([^\]|]+)(?:\|([^\]]+))?\]\]$/)
  if (!match) return <span>{raw}</span>

  const target = match[1].trim()
  const display = (match[2] || match[1]).trim()

  // Look up in index
  const matches = noteIndex[target] || []

  if (matches.length === 0) {
    // Missing note - gray text
    return <span className="wikilink-missing">{display}</span>
  }

  if (matches.length === 1) {
    // Single match - direct link
    const path = matches[0]
    return (
      <a
        href="#"
        className="wikilink"
        onClick={(e) => {
          e.preventDefault()
          onNavigate(path)
        }}
      >
        {display}
      </a>
    )
  }

  // Multiple matches - show disambiguation
  return (
    <a
      href="#"
      className="wikilink ambiguous"
      onClick={(e) => {
        e.preventDefault()
        onDisambiguate(target, matches, display)
      }}
    >
      {display}
    </a>
  )
}
