export interface Frontmatter {
  data: Record<string, string>
  content: string
}

// Minimal YAML frontmatter: top-level `key: value` scalars only. PRD metadata
// is flat in practice; nested YAML lines are simply skipped.
export function parseFrontmatter(md: string): Frontmatter {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(md)
  if (!match) return { data: {}, content: md }
  const data: Record<string, string> = {}
  for (const line of match[1].split(/\r?\n/)) {
    const m = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(line)
    if (m) data[m[1]] = m[2].replace(/^['"]|['"]$/g, '')
  }
  return { data, content: md.slice(match[0].length) }
}
