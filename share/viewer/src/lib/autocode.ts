/**
 * Auto-wrap code-like tokens in markdown backticks (for ReactMarkdown)
 * and provide a React component for plain text rendering.
 */

/** Patterns that look like code — order matters (longer/more specific first) */
const CODE_PATTERNS = [
  // Route-like paths: /localization
  /\/[a-zA-Z0-9_.-]+(?:\/[a-zA-Z0-9_.-]+)*\/?/,
  // Slash-separated paths: common/domain/api, util/services/
  /[a-zA-Z_][\w]*(?:\/[\w.*]+){1,}\/?/,
  // Dotted identifiers (3+ segments): com.bitraptors.babyweather
  /[a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*){2,}/,
  // Generic types: BaseDataSource<T>, List<String>
  /[A-Z][\w]*<[\w?,\s]*>/,
  // Wildcard identifiers: page_*, *_impl, *Impl
  /\w+_\*|\*_\w+|\*[A-Z][A-Za-z0-9_]*/,
  // snake_case identifiers (2+ segments): page_dashboard
  /[a-z][a-z0-9]*(?:_[a-z0-9]+)+/,
  // PascalCase compound names: MainActivity, SharedPreferences
  /[A-Z][a-z]+(?:[A-Z][a-z]+){1,}/,
]

/** Combined pattern matching any code-like token */
const COMBINED_RE = new RegExp(
  '(' + CODE_PATTERNS.map(p => p.source).join('|') + ')',
  'g'
)

// ── Markdown helper (for ReactMarkdown) ──

export function autoBacktick(text: string): string {
  if (!text) return text

  const BACKTICK_RE = /`[^`]+`/g
  const parts: string[] = []
  let last = 0
  for (const m of text.matchAll(BACKTICK_RE)) {
    if (m.index! > last) parts.push(wrapPlain(text.slice(last, m.index!)))
    parts.push(m[0])
    last = m.index! + m[0].length
  }
  if (last < text.length) parts.push(wrapPlain(text.slice(last)))
  return parts.join('')
}

function wrapPlain(segment: string): string {
  return segment.replace(COMBINED_RE, '`$1`')
}

// ── React helper (for plain text in JSX) ──

import { createElement, Fragment, type ReactNode } from 'react'

export const codeInlineClassName =
  'inline rounded-md bg-[#e4f1f5] px-1.5 py-0.5 font-mono text-[0.92em] font-semibold text-[#4b98ad] box-decoration-clone'

/**
 * Split text into plain spans and <code> elements.
 * Use: <AutoCode text={someString} />
 */
export function AutoCode({ text }: { text: string }): ReactNode {
  if (!text) return null

  const parts: ReactNode[] = []
  let last = 0
  let key = 0

  for (const m of text.matchAll(COMBINED_RE)) {
    if (m.index! > last) {
      parts.push(text.slice(last, m.index!))
    }
    parts.push(createElement('code', { key: key++, className: codeInlineClassName }, m[0]))
    last = m.index! + m[0].length
  }
  if (last < text.length) parts.push(text.slice(last))

  return createElement(Fragment, null, ...parts)
}
