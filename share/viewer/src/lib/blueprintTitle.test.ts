import assert from 'node:assert/strict'
import { test } from 'node:test'

import { formatBlueprintTitle } from './blueprintTitle'

test('formats repository slugs as product blueprint titles', () => {
  assert.equal(formatBlueprintTitle('craft-agents'), 'The Craft Agents Blueprint')
  assert.equal(formatBlueprintTitle('bitraptors/craft_agents'), 'The Craft Agents Blueprint')
})

test('keeps the generic fallback when no repository is available', () => {
  assert.equal(formatBlueprintTitle(''), 'The Blueprint')
  assert.equal(formatBlueprintTitle(undefined), 'The Blueprint')
})
