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
 * Tailwind for the hover-path-collapse case. Visually identical to
 * codeInlineClassName but adds a dotted underline + cursor:help affordance
 * so users see "this token has more info on hover."
 */
const codeWithTooltipClassName =
  codeInlineClassName +
  ' cursor-help underline decoration-dotted decoration-[#4b98ad]/40 underline-offset-2'

/**
 * Matches the "<Identifier> (<path-with-extension>[:line[-line]])" shape:
 *   BabyWeatherAnalyticsManager (app/src/.../BabyWeatherAnalyticsManager.kt)
 *   LocationDataSource (app/src/.../LocationDataSource.kt:80)
 *   FooBar (lib/foo/bar.go:18-21)
 *
 * Captured groups: 1 = identifier (rendered visibly), 2 = full path
 * (carried into the tooltip's title attribute, never rendered as text).
 *
 * Constraints to keep false positives low:
 *   - Identifier must start with a letter and be PascalCase / camelCase /
 *     snake_case (no spaces, no punctuation other than _).
 *   - Path must contain at least one `/` AND end with `.<ext>` (1–5 lc).
 *   - Optional `:line` or `:line-line` suffix is captured into the path,
 *     not the identifier.
 *   - Trailing close-paren is required.
 */
const OBJECT_WITH_PATH_RE =
  /\b([A-Za-z_][A-Za-z0-9_]*)\s*\(([A-Za-z0-9_.\-/]*\/[A-Za-z0-9_.\-/]+\.[a-z]{1,5}(?::\d+(?:-\d+)?)?)\)/g

/**
 * Tokenize a span of text using the existing CODE_PATTERNS regex —
 * everything is rendered as plain or <code>; no tooltip handling.
 * Used for the in-between segments after the path-collapse pre-pass.
 */
function tokenizeCodeOnly(segment: string, getKey: () => number): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  for (const m of segment.matchAll(COMBINED_RE)) {
    if (m.index! > last) out.push(segment.slice(last, m.index!))
    out.push(createElement('code', { key: getKey(), className: codeInlineClassName }, m[0]))
    last = m.index! + m[0].length
  }
  if (last < segment.length) out.push(segment.slice(last))
  return out
}

/**
 * Split text into plain spans, <code> elements, and tooltip-spans.
 *
 * Tooltip-span: when the source text contains the "<Identifier> (<path>)"
 * shape, we render *only* the identifier as a chip-styled <span>, attach
 * the full path to its `title` attribute, and discard the visible parens
 * + path. The user sees a clean identifier and can hover for the full
 * path. Long file paths no longer dominate the layout.
 *
 * Use: <AutoCode text={someString} />
 */
export function AutoCode({ text }: { text: string }): ReactNode {
  if (!text) return null

  const parts: ReactNode[] = []
  let key = 0
  const getKey = () => key++
  let last = 0

  for (const m of text.matchAll(OBJECT_WITH_PATH_RE)) {
    // Tokenize anything before this match through the normal code pipeline.
    if (m.index! > last) {
      parts.push(...tokenizeCodeOnly(text.slice(last, m.index!), getKey))
    }
    // Render the identifier as a tooltip-bearing chip; full path lives in title=.
    parts.push(
      createElement(
        'span',
        { key: getKey(), className: codeWithTooltipClassName, title: m[2] },
        m[1],
      ),
    )
    last = m.index! + m[0].length
  }
  if (last < text.length) {
    parts.push(...tokenizeCodeOnly(text.slice(last), getKey))
  }

  return createElement(Fragment, null, ...parts)
}
