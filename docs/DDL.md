# Database Design Document (DDL)

## Overview

The persistence layer uses 5 core tables with a relational schema optimised for the primary access patterns: firm-scoped client listing, date-range email filtering, and one-summary-per-client storage.

## Entity Relationship Diagram

```
┌──────────┐       ┌──────────────┐       ┌──────────┐
│  firms   │──1:N──│  accountants │       │          │
│          │       │              │       │          │
│          │──1:N──│   clients    │──1:N──│  emails  │
│          │       │              │       │          │
└──────────┘       │              │──1:1──│  email_  │
                   └──────────────┘       │summaries │
                                          └──────────┘
```

## Table Definitions

### firms

The top-level organisational entity — a CPA firm.

```sql
CREATE TABLE firms (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

### accountants

Users within a firm. The `role` column drives the RBAC system.

```sql
CREATE TABLE accountants (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id         UUID         NOT NULL REFERENCES firms(id),
    email           VARCHAR(255) NOT NULL UNIQUE,
    full_name       VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role            VARCHAR(20)  NOT NULL DEFAULT 'accountant',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Login lookup
CREATE INDEX idx_accountants_email ON accountants(email);
-- Firm-scoped queries
CREATE INDEX idx_accountants_firm_id ON accountants(firm_id);
```

**Role values**: `accountant`, `firm_admin`, `superuser`

### clients

External entities being serviced by a firm.

```sql
CREATE TABLE clients (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id     UUID         NOT NULL REFERENCES firms(id),
    name        VARCHAR(255) NOT NULL,
    email       VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- List clients by firm (most common query)
CREATE INDEX idx_clients_firm_id ON clients(firm_id);
-- Find client by email
CREATE INDEX idx_clients_email ON clients(email);
```

### emails

Individual emails with sender, recipients, timestamp, and body. Recipients are stored as a JSON array to avoid a join table for this read-heavy, write-once data.

```sql
CREATE TABLE emails (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id    UUID         NOT NULL REFERENCES clients(id),
    sender_email VARCHAR(255) NOT NULL,
    sender_name  VARCHAR(255) NOT NULL,
    recipients   JSONB        NOT NULL,
    subject      VARCHAR(500),
    body         TEXT         NOT NULL,
    sent_at      TIMESTAMPTZ  NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Primary query pattern: emails for a client, filtered by date range
CREATE INDEX idx_emails_client_id ON emails(client_id);
CREATE INDEX idx_emails_sent_at ON emails(sent_at);
```

**Recipients JSON format**:
```json
[
    {"name": "Sarah Anderson", "email": "sarah@anderson-cpa.com"},
    {"name": "Akshar Patel", "email": "akshar.patel@gmail.com"}
]
```

### email_summaries

AI-generated summaries with at-rest encryption. One summary per client (enforced by UNIQUE constraint).

```sql
CREATE TABLE email_summaries (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id            UUID        NOT NULL UNIQUE REFERENCES clients(id),
    encrypted_summary    TEXT        NOT NULL,
    emails_analysed_count INTEGER    NOT NULL DEFAULT 0,
    last_refreshed_at    TIMESTAMPTZ,
    input_tokens         INTEGER     NOT NULL DEFAULT 0,
    output_tokens        INTEGER     NOT NULL DEFAULT 0,
    date_range_start     TIMESTAMPTZ,
    date_range_end       TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_summaries_client_id ON email_summaries(client_id);
```

## Column Design Decisions

| Column | Decision | Rationale |
|--------|----------|-----------|
| `id` (all tables) | UUID v4 | Prevents sequential enumeration attacks; safe for distributed systems |
| `recipients` | JSON/JSONB | Variable recipient count; avoids a join table for read-heavy, write-once data |
| `encrypted_summary` | TEXT | Fernet-encrypted JSON blob; application-level encryption so even DB admins can't read it |
| `emails_analysed_count` | INTEGER | Drives partial-refresh logic: `total_emails - count < 5 → skip` |
| `input_tokens` / `output_tokens` | INTEGER | Per-call Gemini token tracking for cost monitoring |
| `role` | VARCHAR(20) | Simple string enum; avoids a separate roles table for 3 fixed values |

## Scale Assumptions

| Entity | Expected Volume | Index Strategy |
|--------|----------------|---------------|
| Firms | ~50 | Full table scan acceptable |
| Accountants | ~500 (10/firm) | Index on `email` for login, `firm_id` for listing |
| Clients | ~500,000 (10K/firm) | Index on `firm_id` for firm-scoped listing |
| Emails | ~50,000,000 (100/client) | Composite query on `(client_id, sent_at)` via B-tree indexes |
| Summaries | ~500,000 (1/client) | Unique index on `client_id` |

## Query Patterns

### Most frequent queries and their index usage:

1. **Login**: `SELECT * FROM accountants WHERE email = ?` → uses `idx_accountants_email`
2. **List clients**: `SELECT * FROM clients WHERE firm_id = ? ORDER BY name` → uses `idx_clients_firm_id`
3. **Client emails (date range)**: `SELECT * FROM emails WHERE client_id = ? AND sent_at BETWEEN ? AND ? ORDER BY sent_at` → uses `idx_emails_client_id` + `idx_emails_sent_at`
4. **Email count**: `SELECT COUNT(*) FROM emails WHERE client_id = ?` → uses `idx_emails_client_id`
5. **Summary lookup**: `SELECT * FROM email_summaries WHERE client_id = ?` → uses `idx_summaries_client_id`
6. **Firm report**: `SELECT COUNT(*) FROM email_summaries JOIN clients ON ... WHERE firm_id = ?` → index join

## Migration Strategy

Tables are created automatically via SQLAlchemy's `Base.metadata.create_all()` on application startup. For production schema evolution, Alembic is included in the dependencies and can be configured for versioned migrations.
