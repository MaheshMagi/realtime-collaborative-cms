# Realtime Collaborative CMS

A collaborative Content Management System that allows multiple users to edit the same document simultaneously while maintaining data integrity and full version history.

## Features

- **Real-time collaborative editing** — Multiple users can edit the same document at the same time with instant sync
- **Conflict-free merging** — Concurrent edits are merged automatically using CRDTs (Conflict-free Replicated Data Types) via Yjs, so no user's work is ever lost
- **Version history** — Save named versions, browse history, and restore any previous version
- **Live presence** — See who else is editing, with live cursor positions and user indicators
- **Offline support** — Continue editing without a connection; changes merge seamlessly on reconnect
- **Horizontal scaling** — Stateless server instances behind a load balancer, bridged by Redis pub/sub

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Browser    │     │   Browser    │     │   Browser    │
│  (Yjs +      │     │  (Yjs +      │     │  (Yjs +      │
│  WebSocket)  │     │  WebSocket)  │     │  WebSocket)  │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                     │
       └───────────────────-┘─────────────────────┘
                            ▼
                   ┌────────────────┐
                   │  Load Balancer │
                   └───────┬────────┘
               ┌───────────┼───────────┐
               ▼           ▼           ▼
          ┌─────────┐ ┌─────────┐ ┌─────────┐
          │ FastAPI │ │ FastAPI │ │ FastAPI │
          │ + y-py  │ │ + y-py  │ │ + y-py  │
          └────┬────┘ └────┬────┘ └────┬────┘
               │           │           │
               └─────────|─┘───────────┘
                         │
                   ┌─────┴─────┐
                   │           │
                   ▼           ▼
            ┌───────────┐ ┌───────────┐
            │   Redis   │ │ PostgreSQL│
            │ (pub/sub, │ │ (durable  │
            │ presence) │ │  storage) │
            └───────────┘ └───────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Real-time sync | Yjs (CRDT), y-py, y-websocket |
| Database | PostgreSQL 16 |
| Cache / Pub-Sub | Redis 7 |
| Frontend | React 18, Vite, TipTap, Yjs, y-websocket |
| Infrastructure | Docker Compose, Nginx |

## Concurrency Strategy

The system uses a **hybrid approach** for handling concurrent edits:

| Data | Strategy | Rationale |
|---|---|---|
| Document body | CRDT (Yjs) | Character-level merging, no data loss, supports offline |
| Metadata (title, status) | Last-Write-Wins + optimistic locking | Simple fields, low contention |
| Real-time transport | WebSocket + Redis pub/sub | Low-latency fan-out across server instances |

See the [Technical Design Document](docs/TECHNICAL_DESIGN.md) for a detailed comparison of OT, CRDTs, and Last-Write-Wins and how each interacts with PostgreSQL.

## Project Structure (Modular Clean Architecture)

The backend is organized into **feature modules** (`auth`, `documents`, `collaboration`), each following a 4-layer clean architecture:

| Layer | Responsibility |
|---|---|
| **domain/** | Pure entities (dataclasses), repository interfaces (ABCs) |
| **application/** | Use cases orchestrating domain objects and repository calls |
| **infrastructure/** | Repository implementations (SQLAlchemy/Redis), ORM models, adapters |
| **interfaces/** | FastAPI routes, WebSocket handlers, Pydantic schemas (DTOs) |

```
realtime-collaborative-cms/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.in                     # Unpinned dependencies
│   ├── requirements.txt                    # Pinned (pip-compile output)
│   ├── pytest.ini
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                          # Imports all ORM models → Base.metadata
│   │   └── versions/
│   │
│   ├── src/
│   │   ├── main.py                         # FastAPI app, lifespan, exception handlers, router mounting
│   │   │
│   │   ├── shared/                         # Cross-cutting concerns
│   │   │   ├── config.py                   # Pydantic Settings (DB, Redis, JWT)
│   │   │   ├── dependencies.py             # FastAPI Depends: get_db, get_current_user
│   │   │   ├── exceptions.py               # NotFoundError, ConflictError, AuthorizationError
│   │   │   └── infrastructure/
│   │   │       ├── database.py             # Async SQLAlchemy engine, Base, session factory
│   │   │       └── redis.py               # Redis connection pool
│   │   │
│   │   ├── auth/                           # ── AUTH MODULE ──
│   │   │   ├── domain/
│   │   │   │   ├── entities.py             # User dataclass
│   │   │   │   └── repository.py           # UserRepository Protocol
│   │   │   ├── application/
│   │   │   │   └── services.py             # register_user, authenticate_user, verify_token
│   │   │   ├── infrastructure/
│   │   │   │   ├── models.py               # UserModel → 'users' table
│   │   │   │   └── user_repository.py      # DbUserRepository
│   │   │   └── interfaces/
│   │   │       ├── schemas.py              # RegisterRequest, LoginRequest, TokenResponse
│   │   │       └── routes.py               # POST /register, /login, GET /me
│   │   │
│   │   └── documents/                      # ── DOCUMENTS MODULE ──
│   │       ├── domain/
│   │       │   ├── entities.py             # Document dataclass, DocumentStatus enum
│   │       │   └── repository.py           # DocumentRepository Protocol
│   │       ├── application/
│   │       │   └── services.py             # create, get, list, update, delete
│   │       ├── infrastructure/
│   │       │   ├── models.py               # DocumentModel (optimistic locking via version)
│   │       │   └── document_repository.py  # DbDocumentRepository
│   │       └── interfaces/
│   │           ├── schemas.py              # CreateDocRequest, UpdateDocRequest
│   │           └── routes.py               # CRUD /api/documents/
│   │
│   └── tests/
│       ├── conftest.py                     # Shared fixtures: test DB, auth helpers
│       ├── auth/
│       │   ├── test_services.py
│       │   └── test_routes.py
│       └── documents/
│           ├── test_services.py
│           └── test_routes.py
│
└── frontend/                               # Vite + React 18 + TipTap
    ├── index.html
    ├── package.json
    ├── vite.config.ts                      # API proxy → backend :8000
    └── src/
        ├── main.tsx
        ├── App.tsx                         # Router + auth guards
        ├── lib/
        │   ├── api.ts                      # REST API client (fetch wrapper)
        │   └── auth.tsx                    # AuthContext + useAuth hook
        └── pages/
            ├── Login.tsx
            ├── Register.tsx
            ├── DocumentList.tsx
            └── Editor.tsx                  # TipTap rich text editor
```

## Getting Started

### Prerequisites

- Docker and Docker Compose (for PostgreSQL and Redis)
- Python 3.12+
- Node.js 18+

### 1. Start Infrastructure

```bash
docker compose up postgres redis -d
```

### 2. Backend

```bash
# Create and activate virtual env
python -m venv .venv
source .venv/bin/activate

# Install dependencies
cd backend
pip install -r requirements.txt

# Run migrations
PYTHONPATH=src alembic upgrade head

# Start the server
PYTHONPATH=src uvicorn main:app --reload --port 8000
```

Backend API available at http://localhost:8000 (Swagger docs at `/docs`).

### 3. Frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Frontend available at http://localhost:5173 (proxies `/api` requests to backend).

### Running Tests

```bash
cd backend

# Create test database (one-time)
docker compose exec postgres psql -U postgres -c "CREATE DATABASE cms_test"

# Run tests
PYTHONPATH=src python -m pytest tests/ -v
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/cms` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `JWT_SECRET` | `dev-secret` | Secret key for JWT token signing |
| `JWT_EXPIRATION_MINUTES` | `60` | Token expiry time |

## API Overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/documents` | Create a new document |
| `GET` | `/api/documents` | List all documents |
| `GET` | `/api/documents/{id}` | Get document metadata |
| `PATCH` | `/api/documents/{id}` | Update metadata (title, status) |
| `GET` | `/api/documents/{id}/versions` | List version history |
| `POST` | `/api/documents/{id}/versions` | Save a named version |
| `POST` | `/api/documents/{id}/restore/{version}` | Restore a previous version |
| `WS` | `/ws/doc/{id}` | Real-time collaborative editing |

Full API documentation is available at `/docs` (Swagger UI) when the backend is running.

## Database Schema

The system uses six PostgreSQL tables:

- **users** — User accounts and authentication
- **documents** — Document metadata with optimistic locking (LWW)
- **document_snapshots** — Periodic CRDT state captures (binary)
- **document_updates** — Incremental CRDT updates between snapshots (binary)
- **document_versions** — User-saved named versions with plaintext extraction
- **active_sessions** — Currently connected editing sessions

## Testing

```bash
cd backend
PYTHONPATH=src python -m pytest tests/ -v
```

## Scaling

The system is designed to handle 10,000+ concurrent users:

- **Horizontal scaling** — Add server instances behind the load balancer; each manages in-memory CRDT documents independently
- **Redis pub/sub** — Bridges updates across server instances so clients on different servers stay in sync
- **Sticky sessions** — WebSocket connections are pinned to one server via the load balancer
- **PostgreSQL read replicas** — Offload version history and search queries from the primary

## License

MIT
