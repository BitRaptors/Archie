# To-Do List for Adding Regenerate Button

## Overview
Add a regenerate button to the character details page that allows users to regenerate character portraits when they're not satisfied with the current result.

## Tasks

### Frontend Updates
- [ ] Add regenerate button to CharacterDetailPage.tsx
- [ ] Position the button near the avatar display area
- [ ] Add loading state for regeneration process
- [ ] Handle regeneration state in the UI
- [ ] Show success/error messages for regeneration

### State Management
- [ ] Add regeneration state to track when regeneration is in progress
- [ ] Reset avatar status when regeneration starts
- [ ] Handle WebSocket reconnection for regeneration
- [ ] Clear previous avatar when regeneration begins

### User Experience
- [ ] Disable regenerate button during generation
- [ ] Show confirmation dialog before regeneration
- [ ] Display progress messages during regeneration
- [ ] Handle edge cases (no photos, already generating, etc.)

### Integration
- [ ] Use existing `generateCharacterAvatar` API method
- [ ] Integrate with existing WebSocket avatar generation flow
- [ ] Maintain consistent styling with existing UI components
- [ ] Ensure proper error handling and user feedback

### Testing
- [ ] Test regenerate button functionality
- [ ] Test with different avatar states
- [ ] Test WebSocket reconnection during regeneration
- [ ] Test error scenarios

## Implementation Details

### Button Placement
The regenerate button should be placed:
- Below the avatar display area
- Only visible when an avatar exists
- Styled consistently with other buttons on the page

### Button States
- **Default**: "Regenerate Avatar" (when avatar exists)
- **Loading**: "Regenerating..." with spinner (during generation)
- **Disabled**: When no photos available or already generating

### User Flow
1. User clicks "Regenerate Avatar" button
2. Confirmation dialog appears
3. Button shows loading state
4. Avatar generation process starts
5. WebSocket connection established for live updates
6. Progress messages displayed in chat area
7. New avatar appears when complete
