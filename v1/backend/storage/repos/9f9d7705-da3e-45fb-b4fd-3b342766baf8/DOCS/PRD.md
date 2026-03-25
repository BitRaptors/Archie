# Product Requirements Document (PRD) for Tuck-In Tales

## Product Overview
Tuck-In Tales is a mobile-friendly web application designed to create personalized bedtime stories for children aged 1-10. It allows parents to craft characters, log daily memories, and generate multi-page stories with AI-generated text and images. The app aims to make bedtime a delightful, interactive experience for families.

## Target Audience
- Parents of young children (ages 1-10).
- Families looking for a creative way to engage with their children at bedtime.

## Features
- **Character Creation and Management**
  - Add characters with names, bios, photos, and birth dates.
  - Generate cartoon avatars from uploaded photos.
  - Store characters in a family-based schema for shared access.
- **Memory Logging**
  - Log daily events or memories tied to the family.
  - Store memories in a searchable vector database for story generation.
- **Story Generation**
  - Multi-step process: initial description and cover, user feedback, full story creation.
  - Interactive editing: select segments and add prompts for modifications.
  - Real-time streaming of story generation progress.
- **Story Viewer**
  - Paginated display of stories with text and images.
  - Simple navigation controls for easy reading.
- **Profile and Settings**
  - Manage family members and their access.
  - Set the child's birth date for age-appropriate content.
  - Select preferred language for stories.

## User Flows
1. **Onboarding**
   - User signs up and creates a family.
   - Adds family members (optional).
   - Sets the child's birth date and preferred language.
2. **Character Creation**
   - User uploads a photo and enters character details.
   - AI generates a cartoon avatar.
   - Character is saved to the family's database.
3. **Memory Logging**
   - User enters a memory with a date.
   - Memory is stored and embedded for future retrieval.
4. **Story Generation**
   - User selects characters and themes.
   - AI generates a description and cover; user provides feedback.
   - AI creates the full story with pages; user can edit interactively.
5. **Reading a Story**
   - User selects a story from the list.
   - Story is displayed with text and images, navigable by pages.

## Technical Requirements
- **Frontend**: React with TypeScript, mobile-friendly design.
- **Backend**: FastAPI with Poetry for dependency management.
- **Database**: Supabase for structured data and vector storage.
- **Authentication**: Firebase Authentication.
- **AI**: LangGraph for orchestrating story and image generation.
- **Real-Time Updates**: Websockets for streaming generation progress.
- **Localization**: Support for multiple languages via `react-i18next`.

## Success Metrics
- Number of active families using the app.
- Average number of stories generated per family.
- User retention and engagement rates.
- Positive feedback on story quality and personalization.    