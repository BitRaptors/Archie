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

/** Trigger chip — same chip styling, plus dotted underline + cursor:help to advertise the tooltip. */
const codeWithTooltipTriggerClassName =
  codeInlineClassName +
  ' cursor-help underline decoration-dotted decoration-[#4b98ad]/40 underline-offset-2'

/** Wrapper around the trigger that hosts the popover. Uses Tailwind `group`
 *  so the popover only appears on hover/focus. ``inline-block`` keeps the
 *  whole assembly inline with surrounding prose. */
const codeWithTooltipWrapperClassName = 'group relative inline-block align-baseline'

/** Popover bubble — hidden by default, shown on group-hover/focus. Wraps
 *  long paths instead of forcing horizontal overflow. */
const tooltipPopoverClassName =
  'pointer-events-none absolute left-0 top-full z-50 mt-1 ' +
  'max-w-[min(36rem,calc(100vw-2rem))] break-all whitespace-normal ' +
  'rounded-md bg-ink/95 px-2.5 py-1.5 ' +
  'font-mono text-[11px] leading-snug text-papaya-50 shadow-lg ' +
  'opacity-0 transition-opacity duration-100 ' +
  'group-hover:opacity-100 group-focus-within:opacity-100'

/**
 * Matches the "<Identifier> (<path-with-extension>[:line[-line]])" shape:
 *   BabyWeatherAnalyticsManager (app/src/.../BabyWeatherAnalyticsManager.kt)
 *   LocationDataSource (app/src/.../LocationDataSource.kt:80)
 *   FooBar (lib/foo/bar.go:18-21)
 *
 * Captured groups: 1 = identifier (rendered visibly), 2 = full path
 * (carried into the tooltip's title attribute, never rendered as text).
 */
const OBJECT_WITH_PATH_RE =
  /\b([A-Za-z_][A-Za-z0-9_]*)\s*\(([A-Za-z0-9_.\-/]*\/[A-Za-z0-9_.\-/]+\.[a-z]{1,5}(?::\d+(?:-\d+)?)?)\)/g

/**
 * Matches a standalone long file path in prose (no parens). Triggers when the
 * path has at least 3 directory segments before the basename — short paths
 * like `src/foo.kt` are left intact. Captured groups:
 *   1 = directory portion (rendered as the tooltip's prefix, hidden in chip)
 *   2 = basename + optional :line[-line] (rendered visibly as the chip text)
 *
 * Examples that match:
 *   app/src/main/java/com/.../FooViewModel.kt
 *   common/domain/repository/subscription/SubscriptionRepositoryImpl.kt:32
 * Examples that don't match (too short — kept inline as <code>):
 *   src/foo.kt
 *   util/Bar.kt
 */
const STANDALONE_LONG_PATH_RE =
  /\b((?:[A-Za-z0-9_.\-]+\/){3,})([A-Za-z0-9_.\-]+\.[a-z]{1,5}(?::\d+(?:-\d+)?)?)\b/g

/**
 * Build a tooltip element: a chip-styled trigger showing ``visible`` text,
 * with a hover popover bearing the ``hoverPath`` content. Native title= is
 * also set as a fallback for non-pointer browsers and accessibility tools.
 */
function makeTooltip(visible: string, hoverPath: string, key: string | number): ReactNode {
  return createElement(
    'span',
    { key, className: codeWithTooltipWrapperClassName },
    createElement(
      'span',
      {
        key: 'trigger',
        className: codeWithTooltipTriggerClassName,
        tabIndex: 0,
        title: hoverPath,
      },
      visible,
    ),
    createElement(
      'span',
      { key: 'popover', className: tooltipPopoverClassName, role: 'tooltip' },
      hoverPath,
    ),
  )
}

/** A merged regex that finds whichever path-collapse pattern matches first
 *  in a left-to-right scan. We tag the alternatives by named groups so the
 *  caller can dispatch on which one fired. */
const COLLAPSE_RE = new RegExp(
  '(?<objWithPath>' + OBJECT_WITH_PATH_RE.source + ')|(?<longPath>' + STANDALONE_LONG_PATH_RE.source + ')',
  'g',
)

/**
 * Split text into plain spans, <code> elements, and tooltip-spans.
 *
 * Tooltip-span fires for two shapes — both render only a chip with hover-on
 * popover carrying the long stuff:
 *   (1) ``<Identifier> (<long/path/file.ext>)`` — show identifier, hide parens+path
 *   (2) Standalone path with ≥3 directory segments — show basename, hide directory
 *
 * Use: <AutoCode text={someString} />
 */
export function AutoCode({ text }: { text: string }): ReactNode {
  if (!text) return null

  const parts: ReactNode[] = []
  let key = 0
  const getKey = () => key++
  let last = 0

  // First pass: walk the COLLAPSE_RE matches; tokenize in-between text via CODE_PATTERNS.
  for (const m of text.matchAll(COLLAPSE_RE)) {
    if (m.index! > last) {
      const between = text.slice(last, m.index!)
      // Tokenize the in-between text through the existing PascalCase / path / etc. patterns.
      let bLast = 0
      for (const cm of between.matchAll(COMBINED_RE)) {
        if (cm.index! > bLast) parts.push(between.slice(bLast, cm.index!))
        parts.push(createElement('code', { key: getKey(), className: codeInlineClassName }, cm[0]))
        bLast = cm.index! + cm[0].length
      }
      if (bLast < between.length) parts.push(between.slice(bLast))
    }

    const groups = m.groups || {}
    if (groups.objWithPath) {
      // Object(path) shape — captured groups inside OBJECT_WITH_PATH_RE are at
      // m[1] (identifier) and m[2] (path).
      parts.push(makeTooltip(m[1], m[2], getKey()))
    } else {
      // Standalone long path — m[3] = directory prefix, m[4] = basename + optional :line.
      // Visible chip carries the basename; popover carries the full path.
      const dir = m[3] ?? ''
      const basename = m[4] ?? ''
      parts.push(makeTooltip(basename, dir + basename, getKey()))
    }
    last = m.index! + m[0].length
  }
  if (last < text.length) {
    const tail = text.slice(last)
    let bLast = 0
    for (const cm of tail.matchAll(COMBINED_RE)) {
      if (cm.index! > bLast) parts.push(tail.slice(bLast, cm.index!))
      parts.push(createElement('code', { key: getKey(), className: codeInlineClassName }, cm[0]))
      bLast = cm.index! + cm[0].length
    }
    if (bLast < tail.length) parts.push(tail.slice(bLast))
  }

  return createElement(Fragment, null, ...parts)
}
