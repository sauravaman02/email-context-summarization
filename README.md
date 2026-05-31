# Email Context & Summarization System

A production-grade API backend that captures and summarises email discussions between CPA firm accountants and their clients, providing a unified source of truth.

## Architecture

```
Routers (thin controllers)
    ↓
Services (business logic, Gemini integration, caching, encryption)
    ↓
Repositories (data access, query building)
    ↓
Database (PostgreSQL / SQLite)
```

**Key design decisions:**
- **Layered architecture** — business logic never leaks into controllers; repositories abstract all DB access
- **Application-level encryption** — email summaries are Fernet-encrypted at rest, opaque even to DB admins
- **In-memory TTL cache** — pluggable for Redis in multi-instance deployments
- **Exponential backoff retries** — Gemini API failures never corrupt existing summaries
- **Partial refresh** — skips re-summarisation when < 5 new emails arrive (saves API costs)

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | Python 3.12 + FastAPI |
| Database | PostgreSQL (production) / SQLite (development) |
| ORM | SQLAlchemy 2.0 (async) |
| Auth | JWT (python-jose + bcrypt) |
| Encryption | Fernet (cryptography library) |
| AI | Google Gemini API |
| Testing | pytest + pytest-asyncio + httpx |
| CI | GitHub Actions (lint → test → build) |

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/<your-username>/email-context-summarization.git
cd email-context-summarization
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set:
- `GEMINI_API_KEY` — get a free key at [Google AI Studio](https://aistudio.google.com/)
- `ENCRYPTION_KEY` — generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `JWT_SECRET_KEY` — any random string

### 3. Seed the database

```bash
python seed.py
```

This creates 3 firms, 9 accountants, 9 clients, and ~50 realistic tax-related email conversations.

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

API docs available at: **http://localhost:8000/docs**

### 5. Login and test

```bash
# Login as a superuser
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "robert@clarkfinancial.com", "password": "password123"}'

# Use the returned access_token in subsequent requests
curl http://localhost:8000/api/clients \
  -H "Authorization: Bearer <access_token>"
```

## Docker (Recommended)

The easiest way to run everything locally — one command spins up PostgreSQL, seeds the database, and starts the API:

```bash
# Optional: set your Gemini API key for summarization
export GEMINI_API_KEY=your-key-here

# Start everything
docker-compose up --build
```

This will:
1. Start a PostgreSQL 16 database
2. Wait for the database to be healthy
3. Automatically seed 3 firms, 9 accountants, 9 clients, and ~50 emails
4. Start the API server with hot-reload

Access at: **http://localhost:8000/docs** (interactive Swagger UI)

```bash
# Stop everything
docker-compose down

# Stop and wipe all data (fresh start)
docker-compose down -v
```

## Running Tests

```bash
pytest -v --cov=app --cov-report=term-missing
```

Tests use an in-memory SQLite database — no external dependencies required.

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/login` | Public | Get JWT token |
| `GET` | `/api/clients` | Accountant+ | List clients for current firm |
| `GET` | `/api/clients/{id}` | Accountant+ | Client details + email count |
| `GET` | `/api/clients/{id}/emails` | Accountant+ | Paginated email list |
| `POST` | `/api/clients/{id}/summary` | Accountant+ | Get/generate summary (cached) |
| `POST` | `/api/clients/{id}/summary/refresh` | Accountant+ | Force re-summarisation |
| `GET` | `/api/reports/firm` | Firm Admin | Clients with summaries in firm |
| `GET` | `/api/reports/global` | Superuser | Cross-firm summary report |
| `POST` | `/api/search` | Accountant+ | Natural language email search |
| `POST` | `/api/chat` | Accountant+ | Conversational AI interface |
| `GET` | `/api/health` | Public | Health check |

### Summary Request Body (optional)

```json
{
  "start_date": "2025-01-01T00:00:00Z",
  "end_date": "2025-12-31T23:59:59Z"
}
```

- Both fields optional. Partial ranges get sensible defaults.
- `start_date > end_date` returns 400.

### Summary Response

```json
{
  "client_id": "uuid",
  "summary": {
    "actors": [{"name": "...", "role": "...", "involvement": "..."}],
    "concluded_discussions": [{"topic": "...", "resolution": "...", "resolved_date": "..."}],
    "open_action_items": [{"item": "...", "assigned_to": "...", "priority": "high", "context": "..."}]
  },
  "emails_analysed_count": 8,
  "last_refreshed_at": "2025-06-01T10:00:00Z",
  "input_tokens": 2450,
  "output_tokens": 680,
  "skipped": false,
  "skip_reason": null
}
```

## Test Accounts

| Email | Role | Firm |
|-------|------|------|
| `sarah@anderson-cpa.com` | Firm Admin | Anderson & Associates |
| `mike@anderson-cpa.com` | Accountant | Anderson & Associates |
| `james@bakertax.com` | Firm Admin | Baker Tax Group |
| `robert@clarkfinancial.com` | **Superuser** | Clark Financial |
| `jennifer@clarkfinancial.com` | Firm Admin | Clark Financial |

All passwords: `password123`

## Documentation

- **[Architecture Document](docs/ARCHITECTURE.md)** — system design, layer responsibilities, auth flow, scalability
- **[DDL Document](docs/DDL.md)** — database schema, table definitions, indexes, scale assumptions

## Security

- **Authentication**: JWT with configurable expiry (default 60 min)
- **Authorization**: Role-based access control (accountant → firm_admin → superuser)
- **Firm scoping**: Accountants can only access their own firm's clients
- **Encryption at rest**: Email summaries encrypted with Fernet before DB storage
- **Password hashing**: bcrypt with salt

## Observability

- **Structured logging**: Every request logged with request ID, method, path, status, and latency
- **Token tracking**: Input/output token counts stored per summarisation call for cost monitoring
- **Request IDs**: `X-Request-ID` header returned on every response for tracing
