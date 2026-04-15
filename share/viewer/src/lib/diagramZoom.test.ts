import assert from 'node:assert/strict'
import { test } from 'node:test'

import { getNextDiagramZoom } from './diagramZoom'

test('increases zoom by one step', () => {
  assert.equal(getNextDiagramZoom(1, 'in'), 1.15)
})

test('decreases zoom by one step', () => {
  assert.equal(getNextDiagramZoom(1, 'out'), 0.85)
})

test('clamps zoom to supported bounds', () => {
  assert.equal(getNextDiagramZoom(2.5, 'in'), 2.5)
  assert.equal(getNextDiagramZoom(0.5, 'out'), 0.5)
})

test('resets zoom to actual size', () => {
  assert.equal(getNextDiagramZoom(1.9, 'reset'), 1)
})
