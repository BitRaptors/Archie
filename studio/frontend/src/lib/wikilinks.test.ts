import { describe, expect, it } from 'vitest'
import { resolveWikilink, transformWikilinks } from './wikilinks'

const files = [
  { name: 'overview.md', path: 'overview.md' },
  { name: 'login-flow.md', path: 'features/login-flow.md' },
  { name: 'login-flow.md', path: 'archive/old/login-flow.md' },
]

describe('resolveWikilink', () => {
  it('matches by basename, case-insensitive, .md optional', () => {
    expect(resolveWikilink('Login-Flow', files)).toBe('features/login-flow.md')
    expect(resolveWikilink('overview.md', files)).toBe('overview.md')
  })

  it('prefers the shortest path on basename collisions', () => {
    expect(resolveWikilink('login-flow', files)).toBe('features/login-flow.md')
  })

  it('matches path-style targets as a path suffix', () => {
    expect(resolveWikilink('old/login-flow', files)).toBe('archive/old/login-flow.md')
  })

  it('returns null when unresolved', () => {
    expect(resolveWikilink('missing-doc', files)).toBeNull()
  })

  it('respects segment boundaries in path-style targets', () => {
    const tricky = [
      { name: 'login-flow.md', path: 'harold/login-flow.md' },
      { name: 'login-flow.md', path: 'archive/old/login-flow.md' },
    ]
    expect(resolveWikilink('old/login-flow', tricky)).toBe('archive/old/login-flow.md')
  })
})

describe('transformWikilinks', () => {
  it('rewrites resolved links to the wikilink: scheme', () => {
    expect(transformWikilinks('See [[Login-Flow]].', files)).toBe(
      'See [Login-Flow](wikilink:features%2Flogin-flow.md).'
    )
  })

  it('uses the alias as link text', () => {
    expect(transformWikilinks('[[login-flow|the login spec]]', files)).toBe(
      '[the login spec](wikilink:features%2Flogin-flow.md)'
    )
  })

  it('marks unresolved links', () => {
    expect(transformWikilinks('[[Missing]]', files)).toBe('[Missing](unresolved:)')
  })
})
