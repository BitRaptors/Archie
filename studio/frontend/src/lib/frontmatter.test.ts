import { describe, expect, it } from 'vitest'
import { parseFrontmatter } from './frontmatter'

describe('parseFrontmatter', () => {
  it('splits frontmatter from content', () => {
    const md = '---\nstatus: draft\nowner: gabor\n---\n# Title\nBody'
    const { data, content } = parseFrontmatter(md)
    expect(data).toEqual({ status: 'draft', owner: 'gabor' })
    expect(content).toBe('# Title\nBody')
  })

  it('returns whole doc when no frontmatter', () => {
    const { data, content } = parseFrontmatter('# Just a doc')
    expect(data).toEqual({})
    expect(content).toBe('# Just a doc')
  })

  it('trims trailing whitespace from values', () => {
    const { data } = parseFrontmatter('---\nstatus: draft \n---\nx')
    expect(data.status).toBe('draft')
  })

  it('strips surrounding quotes from values', () => {
    const { data } = parseFrontmatter('---\ntitle: "Login Flow"\n---\nx')
    expect(data.title).toBe('Login Flow')
  })

  it('does not treat a mid-document hr as frontmatter', () => {
    const md = '# Doc\n\n---\n\nmore'
    expect(parseFrontmatter(md).content).toBe(md)
  })
})
