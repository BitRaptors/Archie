# Technical Architecture for Tuck-In Tales

## Overview
Tuck-In Tales is built with a modern tech stack to ensure scalability, real-time interactions, and a seamless user experience.

## Components
- **Frontend**: React with TypeScript for a responsive, mobile-friendly UI.
- **Backend**: FastAPI (Python) for high-performance APIs and real-time features.
- **Database**: Supabase for structured data (PostgreSQL) and vector storage (`pgvector`).
- **Authentication**: Firebase Authentication for secure user management.
- **AI Services**: LangGraph orchestrates AI tasks (story generation, image creation).
- **Real-Time Communication**: Websockets for streaming story generation updates.

## Data Flow
1. **User Interaction**: Users interact with the React frontend to create characters, log memories, and generate stories.
2. **API Requests**: The frontend sends requests to the FastAPI backend for data operations.
3. **Data Storage**: Supabase stores characters, stories, and memories; Firebase handles authentication.
4. **AI Generation**: LangGraph coordinates with external APIs (e.g., OpenAI for text, Stable Diffusion for images).
5. **Real-Time Updates**: Websockets push generation progress to the frontend in real-time.

## Scalability Considerations
- **Backend**: FastAPI handles concurrent requests efficiently.
- **Database**: Supabase scales with usage; vector search is optimized for memory retrieval.
- **AI**: External AI services are scalable and can handle multiple requests.