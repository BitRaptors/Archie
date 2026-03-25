# To-Do List for Memory Logging Feature

- [ ] Design memory data model (memory_id, user_id, family_id, text_content, vector_embedding, timestamp).
- [ ] Implement backend logic for:
  - [ ] Saving memory text to database.
  - [ ] Generating vector embedding for the memory text.
  - [ ] Storing the embedding in the database.
- [x] Add Shadcn components needed (Textarea, Button, Card, Label).
- [x] Implement basic form structure in `MemoryLoggingPage.tsx`.
- [x] Add state management for the memory text input.
- [ ] Implement frontend logic to call backend API for saving memory.
- [x] Add user feedback (loading states, success/error messages). (Basic added)
- [ ] Test memory logging flow.
- [ ] Update main `DOCS/Todo.md`. 