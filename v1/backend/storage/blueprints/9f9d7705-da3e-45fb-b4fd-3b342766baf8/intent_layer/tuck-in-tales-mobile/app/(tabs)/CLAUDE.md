# (tabs)/
> Tab-based navigation hub exposing Stories, Characters, Memories screens with shared family-scoped data queries and empty/loading/error state patterns.

## Patterns

- Every screen query-loads familyQuery + screen-specific query (stories/characters) before rendering content
- Three-tier render: loading spinner → error with retry → content (empty state or list)
- Empty state hierarchy: no family > family exists but no items > items exist with add button
- Helper functions (getStatusColor, calculateAge, getAvatarUrl) colocated in component files, not exported
- Pressable onPress handlers log TODO or navigate via router.push/replace; no navigation actually wired yet
- FlatList uses keyExtractor with .id; characters uses numColumns=2 with columnWrapperStyle for grid

## Navigation

**Parent:** [`app/`](../CLAUDE.md)
**Peers:** [`(auth)/`](../(auth)/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `_layout.tsx` | Tab navigation wrapper; configure tab bar styling centrally | Add/remove Tabs.Screen entries; adjust tabBarStyle colors, icons |
| `index.tsx` | Stories list with family header, generation entry point | Wire handleGenerateStory route; extend StoryCard metadata display |
| `characters.tsx` | Character grid with avatar fallback, age calculation | Connect character creation modal; enhance avatar error handling |
| `memories.tsx` | Placeholder stub for memory logging feature | Implement memory list fetch, card component, creation flow |

## Key Imports

- `from expo-router import useRouter (all screens navigate)`
- `from ../../src/hooks/queries import useFamilyDetails, useStories, useCharacters (tab data layer)`

## Add new list screen (characters model exists; memories is stub waiting)

1. Create screen file (e.g., memories.tsx); export default component
2. Add Tabs.Screen in _layout.tsx with name, title, tabBarIcon
3. Import useQuery hook; load familyQuery + screen-specific query
4. Implement loading/error/empty states; render FlatList with card component

## Usage Examples

### Empty state guard pattern used in all screens
```javascript
if (!familyQuery.data) {
  return (
    <View style={styles.emptyContainer}>
      <Text>No Family Yet</Text>
    </View>
  );
}
```

## Don't

- Don't hardcode navigation routes in TODO comments -- wire router.push immediately or remove TODOs
- Don't inline status/age calculations in render -- extract helper functions (already done; maintain pattern)
- Don't skip imageError state on Image components -- fallback to initials placeholder (already correct)

## Testing

- Mock useFamilyDetails and useStories; verify empty/loading/error states render correctly
- Test story/character card navigation by pressing items; verify router.push called with correct ID

## Debugging

- If avatar fails to load, check getAvatarUrl() converts Supabase storage path to public URL; imageError state triggers initials fallback
- If queries don't refetch on Retry button, ensure familyQuery.refetch() and storiesQuery.refetch() are wired; check hook implementation

## Why It's Built This Way

- Three-tier empty state (no family → no items → add button) prevents confusing UX; family is prerequisite
- Helper functions inline in component files keep screen logic self-contained; refactor to utils only if reused across tabs

## What Goes Here

- new_mobile_screen → `tuck-in-tales-mobile/app/(tabs)/{screen}.tsx or tuck-in-tales-mobile/app/{path}.tsx`

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (iOS/Android)`
