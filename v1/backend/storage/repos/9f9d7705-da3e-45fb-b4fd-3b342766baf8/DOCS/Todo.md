# TODO List for Tuck-In Tales App Development

### 1. Backend Setup with FastAPI and LangGraph
- [x] Initialize a new FastAPI project using Poetry.
  - [x] Run `poetry new tuck-in-tales-backend` to create the project structure.
  - [x] Navigate into the project directory: `cd tuck-in-tales-backend`.
- [x] Set up environment variables.
  - [x] Create a `.env` file for sensitive information (e.g., API keys, database URLs).
  - [x] Use `python-dotenv` to load environment variables in the application.
- [x] Define API routes.
  - [x] Create routes for characters, stories, and memories (e.g., `/characters`, `/stories`, `/memories`).
  - [x] Implement GET and POST methods for each route (using Supabase).
- [ ] Add websocket support for real-time updates.
  - [ ] Set up a websocket endpoint (e.g., `/ws/story-updates`).
- [ ] Integrate LangGraph for AI tasks.
  - [ ] Install LangGraph: `poetry add langgraph`.
  - [ ] Create AI agents for story generation, image generation, and validation.
  - [ ] Implement memory retrieval using RAG with vector search.
- [ ] Implement streaming for story generation.
  - [ ] Use asynchronous generators to stream partial results to the frontend.

### 2. Database and Storage with Supabase and Firebase
- [x] Set up Supabase for the family-based schema.
  - [x] Create a new Supabase project. (Assumed done - ID provided)
  - [x] Integrate Supabase client (`supabase-py`) into FastAPI backend.
  - [ ] Define database tables: `families`, `users`, `characters`, `stories`, `memories`. (Needs verification)
  - [ ] Set up foreign key relationships. (Needs verification)
  - [ ] Create storage buckets for photos, avatars, and story images.
- [ ] Implement vector storage for memories.
  - [ ] Enable `pgvector` extension in Supabase. (Needs verification)
  - [ ] Add a `vector` column to the `memories` table. (Needs verification)
  - [ ] Write a function to generate and store embeddings.
  - [ ] Implement similarity search for memory retrieval.
- [ ] Configure Firebase.
  - [ ] Set up a Firebase project.
  - [ ] Enable Firebase Authentication.
  - [ ] Integrate Firebase Analytics.
  - [ ] Configure Firebase Remote Config.

### 3. Frontend Development with React
- [ ] Create a new React app.
  - [ ] Run `npx create-react-app tuck-in-tales-frontend --template typescript`.
  - [ ] Install React Router: `npm install react-router-dom`.
- [ ] Set up routing.
  - [ ] Define routes for characters, stories, memories, and profile.
- [ ] Build core pages.
  - [ ] Character creation page.
  - [ ] Memory logging page.
  - [ ] Story generation page with multi-step form.
  - [ ] Story viewer page.
  - [ ] Profile/settings page.
- [ ] Implement real-time updates.
  - [ ] Install Socket.IO: `npm install socket.io-client`.
  - [ ] Connect to the backend websocket endpoint.
- [ ] Design the iterative story creation flow.
  - [ ] Create a multi-step form for story generation.
  - [ ] Implement user feedback and editing capabilities.

### 4. Localization and Language Support
- [ ] Set up localization with `react-i18next`.
  - [ ] Install `react-i18next` and `i18next`.
  - [ ] Create translation files (e.g., `en.json`, `es.json`).
- [ ] Ensure AI supports multiple languages.
  - [ ] Pass the selected language to the LLM.
  - [ ] Store the language in the `stories` table.

### 5. Testing and Deployment
- [ ] Write backend tests.
  - [ ] Use `pytest` to test API endpoints and AI agents.
- [ ] Write frontend tests.
  - [ ] Use Jest and React Testing Library to test user flows.
- [ ] Deploy the backend.
  - [ ] Choose a deployment platform (e.g., Heroku, AWS).
  - [ ] Set up a CI/CD pipeline.
- [ ] Deploy the frontend.
  - [ ] Build the React app: `npm run build`.
  - [ ] Deploy to Netlify or Vercel.
- [ ] Set up monitoring and logging.
  - [ ] Integrate Sentry for error tracking.
  - [ ] Add logging in the backend and frontend.