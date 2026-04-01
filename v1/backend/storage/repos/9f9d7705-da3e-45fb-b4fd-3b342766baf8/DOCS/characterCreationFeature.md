# To-Do List for Character Creation Feature

- [x] Design character data model (name, description, avatar_url, family_id, user_id). (Done in backend)
- [x] Add Shadcn components needed for the form (Input, Textarea, Label, Button, Card). (File input pending)
- [x] Implement basic form structure in `CharacterCreationPage.tsx`.
- [x] Add state management for form fields (name, description).
- [x] Implement image upload functionality.
  - [x] Set up Supabase storage bucket for avatars.
  - [x] Add function to upload image to Supabase storage.
  - [x] Handle file selection and preview in the form.
- [ ] Implement logic to save character data to Supabase database.
- [ ] Add form validation. (Basic name validation added)
- [ ] Add user feedback (loading states, success/error messages). (Basic added)
- [ ] Test character creation flow.
- [ ] Update main `DOCS/Todo.md`. 