export interface PrdFileRef {
  name: string
  path: string
}

// Spaces and hyphens are equivalent so [[Login Flow]] finds login-flow.md.
const norm = (s: string) => s.toLowerCase().replace(/\.md$/, '').replace(/[\s-]+/g, '-')

// Obsidian-style resolution: bare names match by basename (case-insensitive,
// .md optional); names containing '/' match as a path suffix on segment
// boundaries. On collisions the shortest path wins (Obsidian's "shortest
// path when unique" flavor).
export function resolveWikilink(target: string, files: PrdFileRef[]): string | null {
  const wanted = norm(target.trim())
  const matches = files.filter((f) => {
    if (!wanted.includes('/')) return norm(f.name) === wanted
    const path = norm(f.path)
    return path === wanted || path.endsWith('/' + wanted)
  })
  if (matches.length === 0) return null
  return matches.sort((a, b) => a.path.length - b.path.length)[0].path
}

// Rewrite [[Target]] / [[Target|Label]] into standard markdown links carrying
// a wikilink: scheme; ProductTab's anchor renderer intercepts them. Unresolved
// targets get `unresolved:` so they render muted instead of as dead links.
// Known MVP limitation: also rewrites inside fenced code blocks.
export function transformWikilinks(md: string, files: PrdFileRef[]): string {
  return md.replace(
    /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,
    (_all, target: string, label?: string) => {
      const resolved = resolveWikilink(target, files)
      const text = label ?? target
      return resolved
        ? `[${text}](wikilink:${encodeURIComponent(resolved)})`
        : `[${text}](unresolved:)`
    }
  )
}
