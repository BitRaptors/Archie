import { describe, it, expect } from 'vitest'
import { generateId, extractText, parseNavigation } from './blueprint-toc'

// ---------------------------------------------------------------------------
// generateId
// ---------------------------------------------------------------------------

describe('generateId', () => {
    it('lowercases and slugifies plain text', () => {
        expect(generateId('Architecture Overview')).toBe('architecture-overview')
    })

    it('handles numbered headings', () => {
        expect(generateId('1. Architecture Overview')).toBe('1-architecture-overview')
    })

    it('collapses special chars into single dash', () => {
        expect(generateId('API/Presentation Layer [backend]')).toBe('api-presentation-layer-backend')
    })

    it('strips leading and trailing dashes', () => {
        expect(generateId('  Hello World!  ')).toBe('hello-world')
    })

    it('handles empty string', () => {
        expect(generateId('')).toBe('')
    })
})

// ---------------------------------------------------------------------------
// extractText
// ---------------------------------------------------------------------------

describe('extractText', () => {
    it('returns plain strings as-is', () => {
        expect(extractText('hello')).toBe('hello')
    })

    it('converts numbers to strings', () => {
        expect(extractText(42)).toBe('42')
    })

    it('joins arrays', () => {
        expect(extractText(['hello', ' ', 'world'])).toBe('hello world')
    })

    it('extracts text from React-like element with props.children', () => {
        // Simulates <strong>bold text</strong>
        const fakeElement = { props: { children: 'bold text' } }
        expect(extractText(fakeElement)).toBe('bold text')
    })

    it('handles nested React elements', () => {
        // Simulates <em><strong>deep</strong></em>
        const inner = { props: { children: 'deep' } }
        const outer = { props: { children: inner } }
        expect(extractText(outer)).toBe('deep')
    })

    it('handles mixed arrays of strings and elements', () => {
        // Simulates: ["Architecture ", <strong>Overview</strong>]
        const bold = { props: { children: 'Overview' } }
        expect(extractText(['Architecture ', bold])).toBe('Architecture Overview')
    })

    it('handles null/undefined', () => {
        expect(extractText(null)).toBe('')
        expect(extractText(undefined)).toBe('')
    })
})

// ---------------------------------------------------------------------------
// parseNavigation
// ---------------------------------------------------------------------------

describe('parseNavigation', () => {
    it('extracts h2 sections', () => {
        const md = '## Architecture Overview\n\nSome content\n\n## Technology Stack'
        const nav = parseNavigation(md)
        expect(nav).toHaveLength(2)
        expect(nav[0]).toEqual({ title: 'Architecture Overview', id: 'architecture-overview', items: [] })
        expect(nav[1]).toEqual({ title: 'Technology Stack', id: 'technology-stack', items: [] })
    })

    it('nests h3 items under their h2 parent', () => {
        const md = '## Components\n\n### API Layer\n\n### Domain Layer'
        const nav = parseNavigation(md)
        expect(nav).toHaveLength(1)
        expect(nav[0].items).toHaveLength(2)
        expect(nav[0].items[0]).toEqual({ title: 'API Layer', id: 'api-layer' })
        expect(nav[0].items[1]).toEqual({ title: 'Domain Layer', id: 'domain-layer' })
    })

    it('ignores headings inside code blocks', () => {
        const md = '## Real Heading\n\n```\n## Not a heading\n```\n\n## Another Real Heading'
        const nav = parseNavigation(md)
        expect(nav).toHaveLength(2)
        expect(nav[0].title).toBe('Real Heading')
        expect(nav[1].title).toBe('Another Real Heading')
    })

    it('strips markdown formatting from titles', () => {
        const md = '## **Bold** Section\n\n## [Link Text](http://example.com) Section'
        const nav = parseNavigation(md)
        expect(nav[0].title).toBe('Bold Section')
        expect(nav[1].title).toBe('Link Text Section')
    })

    it('handles numbered headings like the real blueprint', () => {
        const md = '## 1. Architecture Overview\n## 2. Components & Layers\n### API/Presentation Layer [backend]'
        const nav = parseNavigation(md)
        expect(nav).toHaveLength(2)
        expect(nav[0].id).toBe('1-architecture-overview')
        expect(nav[1].id).toBe('2-components-layers')
        expect(nav[1].items[0].id).toBe('api-presentation-layer-backend')
    })

    it('orphan h3 before any h2 is skipped', () => {
        const md = '### Orphan\n\n## Parent\n\n### Child'
        const nav = parseNavigation(md)
        expect(nav).toHaveLength(1)
        expect(nav[0].title).toBe('Parent')
        expect(nav[0].items).toHaveLength(1)
    })

    it('returns empty for no headings', () => {
        expect(parseNavigation('just some text')).toEqual([])
    })
})

// ---------------------------------------------------------------------------
// ID contract: parseNavigation IDs must match what heading components produce
// ---------------------------------------------------------------------------

describe('ID contract (parseNavigation ↔ heading component)', () => {
    const realHeadings = [
        '## 1. Architecture Overview',
        '## 4. Components & Layers',
        '### API/Presentation Layer [backend]',
        '### Clean Architecture + DDD for Backend; React Hooks + Context API for Frontend',
        '## 9. Developer Recipes',
        '### Add a new API endpoint (e.g., POST /analyses/{id}/regenerate)',
    ]

    for (const heading of realHeadings) {
        it(`IDs match for: ${heading}`, () => {
            const level = heading.startsWith('###') ? 3 : 2
            const prefix = level === 3 ? '### ' : '## '
            const rawText = heading.replace(prefix, '').trim()

            // parseNavigation side: strip markdown formatting then generateId
            const navTitle = rawText
                .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
                .replace(/(\*\*|__|_|\*|`)/g, '')
            const navId = generateId(navTitle)

            // ReactMarkdown side: children is the raw text (no markdown since it's rendered)
            // react-markdown strips formatting and passes plain text as children for simple headings
            const reactId = generateId(extractText(rawText))

            expect(navId).toBe(reactId)
        })
    }
})
