---
id: backend-implementation
title: Implementation Guide
category: backend
tags: [implementation, python, fastapi, setup]
related: [backend-layers, backend-contracts]
---

# Implementation Guide

This section provides a complete, opinionated guide to implementing this architecture from scratch using Python.

## Technology Stack

### Core Framework

| Component         | Technology         | Purpose                                               |
| ----------------- | ------------------ | ----------------------------------------------------- |
| **Web Framework** | FastAPI            | Async-first API framework with automatic OpenAPI docs |
| **ASGI Server**   | Gunicorn + Uvicorn | Production server (4 workers)                         |
| **Validation**    | Pydantic v2        | Data validation and settings (`model_dump()` syntax)  |

### Database & Storage

| Component          | Technology            | Purpose                                  |
| ------------------ | --------------------- | ---------------------------------------- |
| **Database**       | Supabase (PostgreSQL) | Managed PostgreSQL with auth and storage |
| **File Storage**   | Supabase Storage      | Document and file storage                |
| **Vector Search**  | pgvector (Supabase)   | Semantic search for ideas and documents  |
| **Cache/Sessions** | Redis                 | Session storage and caching              |

### AI/LLM Providers

| Component          | Technology             | Purpose                            |
| ------------------ | ---------------------- | ---------------------------------- |
| **Primary AI**     | OpenAI (Responses API) | Primary AI provider                |
| **Alternative AI** | Google Gemini          | Alternative AI provider            |
| **Abstraction**    | Provider Factory       | Unified interface for AI providers |

### Authentication

| Component       | Technology    | Purpose                                     |
| --------------- | ------------- | ------------------------------------------- |
| **Auth**        | Supabase Auth | JWT-based authentication                    |
| **JWT Library** | PyJWT         | Token validation using Supabase JWT secrets |

### Real-time Communication

| Component     | Technology               | Purpose                            |
| ------------- | ------------------------ | ---------------------------------- |
| **Streaming** | Server-Sent Events (SSE) | Streaming AI responses to frontend |

### Dependency Injection

| Component        | Technology          | Purpose                                    |
| ---------------- | ------------------- | ------------------------------------------ |
| **DI Container** | dependency-injector | Explicit DI with scopes and lifecycle mgmt |
| **Wiring**       | Auto-wiring         | Automatic injection into FastAPI endpoints |

### Background Tasks

| Component      | Technology | Purpose                              |
| -------------- | ---------- | ------------------------------------ |
| **Task Queue** | ARQ        | Async-native, Redis-based task queue |
| **Broker**     | Redis      | Shared with cache/sessions           |
| **Scheduling** | ARQ cron   | Periodic task execution              |

### Deployment

| Component            | Technology         | Purpose                                              |
| -------------------- | ------------------ | ---------------------------------------------------- |
| **Containerization** | Docker             | Container builds (Dockerfile, Dockerfile.production) |
| **Cloud Platform**   | Google Cloud Run   | Serverless container deployment                      |
| **Server**           | Gunicorn + Uvicorn | 4 workers configured                                 |

## Project Setup

See the original blueprint document for complete setup instructions, directory structure, and code templates.


