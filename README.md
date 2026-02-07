# Realtime Collaborative CMS

A collaborative Content Management System where multiple users edit the same document simultaneously with conflict-free merging, built with FastAPI, React, and CRDTs.

## Quick Start

**Prerequisites:** Docker and Docker Compose, Node.js 18+

```bash
# 1. Start backend (PostgreSQL + Redis + FastAPI)
docker compose up -d
docker compose exec backend alembic upgrade head

# 2. Seed demo data (2 users + sample documents)
pip install httpx   # if not already installed
python scripts/seed.py

# 3. Start frontend
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173** — login as `alice@example.com` / `password123`.

To test real-time collaboration, open a second browser window and login as `bob@example.com` / `password123`, then open the same document in both windows and type.

Backend Swagger docs: **http://localhost:8000/docs**

## Run Tests

```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE cms_test"
docker compose exec backend python -m pytest tests/ -v
```

## What's Implemented

| Feature | Status | Notes |
|---|---|---|
| JWT authentication (register/login) | Done | Stateless tokens, bcrypt password hashing |
| Document CRUD | Done | Create, list, get, update, delete |
| Real-time collaborative editing | Done | WebSocket + CRDT — two users editing simultaneously |
| CRDT persistence | Done | Binary snapshots + incremental updates in PostgreSQL |
| Cross-server sync | Done | Redis pub/sub bridges updates between server instances |
| Offline support | Native | CRDTs merge seamlessly on reconnect |
| Optimistic locking for metadata | Done | `WHERE version = :expected` prevents stale writes |

## Key Design Decisions

Full rationale in the [Technical Design Document](docs/TECHNICAL_DESIGN.md), including a comparison of OT vs CRDTs vs Last-Write-Wins with trade-off analysis.

**Why CRDTs over Operational Transformation?**
CRDTs (via Yjs/pycrdt) guarantee convergence without a central sequencing server per document, enabling horizontal scaling. OT requires a single-server bottleneck per document for operation ordering and can't support offline editing.

**Why a hybrid concurrency strategy?**

| Data | Strategy | Why |
|---|---|---|
| Document body | CRDT (Yjs) | Character-level merging, no data loss, works offline |
| Metadata (title, status) | Last-Write-Wins + optimistic locking | Simple fields, low contention — CRDT overhead unnecessary |
| Real-time transport | WebSocket + Redis pub/sub | Low-latency fan-out across server instances |

## Architecture

```
┌──────────────┐     ┌──────────────┐
│   Browser    │     │   Browser    │
│  (React +    │     │  (React +    │
│  TipTap +    │     │  TipTap +    │
│  WebSocket)  │     │  WebSocket)  │
└──────┬───────┘     └──────┬───────┘
       │                    │
       └────────┬───────────┘
                ▼
       ┌────────────────┐
       │    FastAPI      │
       │  (pycrdt +      │
       │   WebSocket)    │
       └───────┬─────────┘
           ┌───┴───┐
           ▼       ▼
     ┌─────────┐ ┌───────────┐
     │  Redis  │ │ PostgreSQL│
     │ pub/sub │ │  storage  │
     └─────────┘ └───────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Real-time sync | Yjs (CRDT), pycrdt |
| Database | PostgreSQL 16, SQLAlchemy (async) |
| Cache / Pub-Sub | Redis 7 |
| Frontend | React 18, Vite, TipTap (rich text editor) |
| Infrastructure | Docker Compose |

## Project Structure

The backend uses **feature modules** (`auth`, `documents`, `collaboration`) with 4-layer clean architecture:

```
backend/src/
├── auth/                         # Authentication module
│   ├── domain/                   #   Entities, repository protocol
│   ├── application/              #   Service layer (register, login, get_current_user)
│   ├── infrastructure/           #   SQLAlchemy models + repository impl
│   └── interfaces/               #   FastAPI routes + Pydantic schemas
├── documents/                    # Document CRUD module
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   └── interfaces/
├── collaboration/                # Real-time editing module
│   ├── domain/
│   ├── application/
│   ├── infrastructure/           #   CRDT storage, Redis pub/sub, Yjs adapter
│   └── interfaces/               #   WebSocket handler
├── shared/                       # Config, DB, Redis, exceptions, DI
└── main.py                       # App entrypoint + router registration

frontend/src/
├── pages/                        # Login, Register, DocumentList, Editor
├── lib/                          # API client, auth context, useCollaboration hook
└── App.tsx                       # Router setup
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Register a new user |
| `POST` | `/api/auth/login` | Authenticate and get JWT token |
| `GET` | `/api/auth/me` | Get current user profile |
| `POST` | `/api/documents` | Create a document |
| `GET` | `/api/documents` | List all documents |
| `GET` | `/api/documents/{id}` | Get document by ID |
| `PATCH` | `/api/documents/{id}` | Update title/status (optimistic lock) |
| `DELETE` | `/api/documents/{id}` | Delete a document |
| `WS` | `/ws/doc/{id}` | Real-time collaborative editing |

Interactive docs at `/docs` (Swagger UI) when the backend is running.

## Database Schema

Four PostgreSQL tables:

- **users** — accounts + bcrypt password hashes
- **documents** — metadata with `version` column for optimistic locking
- **document_snapshots** — periodic full CRDT state captures (`BYTEA`)
- **document_updates** — incremental CRDT diffs between snapshots (`BYTEA`)

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/cms` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `JWT_SECRET` | `dev-secret` | JWT signing key |
| `JWT_EXPIRATION_MINUTES` | `60` | Token expiry |
