# Architecture Document

## Overview

The Email Context & Summarization System is a multi-tenant API backend that enables CPA firms to capture, search, and intelligently summarise email conversations between their accountants and clients.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                            │
│   Web UI (Tailwind)  │  Swagger/OpenAPI  │  Any HTTP Client     │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTPS / JSON
┌───────────────────────────────▼─────────────────────────────────┐
│                      FastAPI Application                        │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Middleware Layer                                        │   │
│  │  - CORS (cross-origin requests)                         │   │
│  │  - Request Logging (request ID, latency tracking)       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Router / Controller Layer (thin — no business logic)   │   │
│  │  auth.py │ clients.py │ summaries.py │ reports.py       │   │
│  │  search.py │ conversation.py                            │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Service Layer (all business logic lives here)          │   │
│  │  auth_service       — JWT + bcrypt password hashing     │   │
│  │  encryption_service — Fernet at-rest encryption         │   │
│  │  cache_service      — TTL-based in-memory cache         │   │
│  │  gemini_service     — Gemini API with retry/backoff     │   │
│  │  summarization_service — orchestrates the full flow     │   │
│  │  search_service     — NL search across emails           │   │
│  │  conversation_service — multi-turn chat with memory     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Repository Layer (data access abstraction)             │   │
│  │  client_repo │ email_repo │ summary_repo                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │ SQLAlchemy Async
┌───────────────────────────────▼─────────────────────────────────┐
│                      Persistence Layer                          │
│            PostgreSQL (production) / SQLite (dev)               │
└─────────────────────────────────────────────────────────────────┘

External:
  Google Gemini API ← called by gemini_service for summarisation,
                      search, and conversational queries
```

## Layer Responsibilities

### Router Layer
- Parse and validate HTTP requests (via Pydantic schemas)
- Translate service exceptions into HTTP status codes
- Zero business logic — delegates everything to services

### Service Layer
- **auth_service**: Password hashing (bcrypt), JWT creation/validation
- **encryption_service**: Fernet encrypt/decrypt for summary payloads
- **cache_service**: In-memory TTL cache (pluggable for Redis)
- **gemini_service**: Prompt construction, API call with retry, response parsing
- **summarization_service**: Full orchestration — cache check, partial-refresh, Gemini call, encrypt, persist
- **search_service**: NL query → Gemini → matched clients/emails
- **conversation_service**: Session management + Gemini chat with history

### Repository Layer
- All database queries encapsulated here
- Firm-scoped access enforced at this level
- Portable across SQLite and PostgreSQL

## Authentication & Authorization Flow

```
Client → POST /api/auth/login {email, password}
       ← 200 {access_token: "eyJ..."}

Client → GET /api/clients
         Authorization: Bearer eyJ...
       → Middleware extracts JWT
       → dependencies.py decodes token → AccountantInfo{id, firm_id, role}
       → Router receives user object
       → Repository filters by firm_id (multi-tenancy)
       ← 200 {clients: [...]}
```

### Role Hierarchy
| Role | Permissions |
|------|------------|
| `accountant` | View own firm's clients, emails, summaries |
| `firm_admin` | All accountant permissions + firm reports |
| `superuser` | All permissions + global cross-firm reports |

## Summarisation Flow

```
1. POST /api/clients/{id}/summary
2. Check cache → hit? return cached response
3. Count emails in date range
4. Load existing summary from DB
5. Partial-refresh check: new_emails < 5? → skip, return existing
6. Fetch all emails → build prompt → call Gemini (with retries)
7. Gemini fails? → return existing summary (resilience guarantee)
8. Gemini succeeds → encrypt summary → upsert to DB → cache → return
```

## Security Model

| Threat | Mitigation |
|--------|-----------|
| Credential theft | Passwords hashed with bcrypt (salt + 12 rounds) |
| Token forgery | HS256 JWT signed with server-side secret |
| Cross-firm data access | All queries scoped by firm_id from JWT |
| Summary data exposure | Fernet AES-128 encryption before DB storage |
| API abuse | Rate limiting via Gemini's built-in quotas |

## Scalability Considerations

The system is designed for **50 firms × 10,000 clients × 100 emails** (~50M emails).

| Component | Current | Scale Path |
|-----------|---------|-----------|
| Database | SQLite / single PostgreSQL | Read replicas, connection pooling |
| Cache | In-memory (single process) | Redis cluster |
| API | Single uvicorn process | Multiple workers behind a load balancer |
| Gemini calls | Sequential per request | Async batch processing with job queue |
| Sessions | In-memory dict | Redis-backed session store |

## Technology Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.12 | Async ecosystem, Gemini SDK support, team familiarity |
| Framework | FastAPI | Auto OpenAPI docs, Pydantic validation, async-first |
| ORM | SQLAlchemy 2.0 async | Industry standard, portable across databases |
| Auth | JWT (stateless) | No session store needed, horizontal scaling |
| Encryption | Fernet | Simple, secure, no key management infrastructure needed |
| AI | Gemini 2.5 Flash | Cost-effective, fast, structured JSON output mode |
