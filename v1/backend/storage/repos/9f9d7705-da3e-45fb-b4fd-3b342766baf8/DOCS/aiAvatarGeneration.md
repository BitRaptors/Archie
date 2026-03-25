# To-Do List for AI Avatar Generation & Chat Refinement

**Phase 1: Backend Generation Flow**
- [x] Review existing `POST /api/characters/{character_id}/generate_avatar` endpoint logic.
- [x] Set up LangGraph dependencies (`pip install langgraph langchain_openai`).
- [x] Create a new LangGraph graph definition (`src/graphs/avatar_generator.py`).
    - [x] Define graph state (character info, photo paths, prompt, summary, avatar path, messages).
    - [x] Implement `planner` node.
    - [x] Implement `prompt_generator` node (using vision model).
    - [x] Implement `image_generator` node (using DALL-E).
    - [x] Implement `update_db` node (save avatar path).
    - [x] Define graph edges and compilation.
- [x] Modify `POST /api/characters/{character_id}/generate_avatar` endpoint:
    - [x] Invoke the LangGraph graph asynchronously.
    - [x] Return immediately (e.g., 202 Accepted).
- [x] Set up WebSocket manager (`src/utils/websockets.py` if not already) to send progress updates from the graph.
- [x] Integrate WebSocket updates into the LangGraph nodes & background task.

**Phase 2: Frontend Trigger & Display**
- [x] Create `CharacterDetailPage.tsx` (`src/pages/`).
- [x] Add route for `/characters/{character_id}` in `App.tsx`.
- [x] Implement data fetching for character details on `CharacterDetailPage.tsx`.
- [x] Modify `CharacterCreationPage.tsx` to navigate to `CharacterDetailPage` after creation/upload.
- [x] Trigger the `generate_avatar` endpoint automatically when `CharacterDetailPage` loads (if no avatar exists).
- [x] Add WebSocket listener to `CharacterDetailPage` to receive progress/completion updates.
- [x] Display the generated `avatar_url` (needs function to get public URL from path) on `CharacterDetailPage`.
- [x] Display loading/progress state for avatar generation.

**Phase 3: Chat Interface & Refinement**
- [ ] Add Chat UI component (`src/components/ChatInterface.tsx`) to `CharacterDetailPage.tsx`.
- [ ] Add `chat_responder` node to LangGraph graph.
- [ ] Update `planner` node and graph edges to handle chat input/responses.
- [ ] Modify WebSocket logic to handle sending user messages to backend and receiving AI responses.
- [ ] Update `CharacterDetailPage` to send chat messages and display conversation history.
- [ ] Implement logic for chat messages to trigger graph re-runs for avatar refinement.

**General:**
- [ ] Update documentation (`docs/characters.md`, create `docs/avatar_generation.md`).
- [ ] Test each phase thoroughly. 