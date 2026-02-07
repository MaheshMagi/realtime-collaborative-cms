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
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                          # Imports orm_registry → Base.metadata
│   │   └── versions/
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                         # FastAPI app factory, lifespan, router mounting
│   │   │
│   │   ├── shared/                         # Cross-cutting concerns
│   │   │   ├── config.py                   # Pydantic Settings (DB, Redis, JWT)
│   │   │   ├── dependencies.py             # FastAPI Depends: get_db, get_redis, get_current_user
│   │   │   ├── exceptions.py               # NotFoundError, ConflictError, AuthorizationError
│   │   │   └── infrastructure/
│   │   │       ├── database.py             # Async SQLAlchemy engine, Base, session factory
│   │   │       ├── redis.py                # aioredis connection pool
│   │   │       └── orm_registry.py         # Imports all ORM models for Alembic
│   │   │
│   │   ├── auth/                           # ── AUTH MODULE ──
│   │   │   ├── domain/
│   │   │   │   ├── entities.py             # User dataclass
│   │   │   │   └── repository.py           # ABC UserRepository
│   │   │   ├── application/
│   │   │   │   └── use_cases.py            # RegisterUser, AuthenticateUser, VerifyToken
│   │   │   ├── infrastructure/
│   │   │   │   ├── orm_models.py           # UserModel → 'users' table
│   │   │   │   └── user_repository.py      # SqlAlchemyUserRepository
│   │   │   └── interfaces/
│   │   │       ├── schemas.py              # RegisterRequest, LoginRequest, TokenResponse
│   │   │       └── routes.py               # POST /register, /login, GET /me
│   │   │
│   │   ├── documents/                      # ── DOCUMENTS MODULE ──
│   │   │   ├── domain/
│   │   │   │   ├── entities.py             # Document, DocumentVersion dataclasses
│   │   │   │   └── repository.py           # ABC DocumentRepository, DocumentVersionRepository
│   │   │   ├── application/
│   │   │   │   └── use_cases.py            # CreateDocument, UpdateMetadata, SaveVersion, RestoreVersion
│   │   │   ├── infrastructure/
│   │   │   │   ├── orm_models.py           # DocumentModel, DocumentVersionModel
│   │   │   │   └── document_repository.py  # SqlAlchemy repos (optimistic locking)
│   │   │   └── interfaces/
│   │   │       ├── schemas.py              # CreateDocRequest, UpdateDocRequest, VersionResponse
│   │   │       └── routes.py               # CRUD + /versions + /restore/{version}
│   │   │
│   │   └── collaboration/                  # ── COLLABORATION MODULE ──
│   │       ├── domain/
│   │       │   ├── entities.py             # ActiveSession, PresenceInfo, CrdtSnapshot, CrdtUpdate
│   │       │   └── repository.py           # ABC CrdtStorageRepository, SessionRepository
│   │       ├── application/
│   │       │   └── use_cases.py            # JoinDocument, LeaveDocument, PersistCrdtUpdate,
│   │       │                               #   CreateSnapshot, LoadDocumentState
│   │       ├── infrastructure/
│   │       │   ├── orm_models.py           # SnapshotModel, UpdateModel, ActiveSessionModel
│   │       │   ├── crdt_storage_repository.py
│   │       │   ├── session_repository.py   # Redis-backed presence tracking
│   │       │   ├── redis_pubsub.py         # Cross-server update fanout
│   │       │   └── yjs_adapter.py          # Wraps pycrdt: create, apply, encode, extract text
│   │       └── interfaces/
│   │           ├── schemas.py              # WS message types, PresenceResponse
│   │           └── ws_handler.py           # WebSocket endpoint lifecycle + Yjs sync
│   │
│   └── tests/
│       ├── conftest.py                     # Shared fixtures: test DB, mock Redis
│       ├── auth/
│       ├── documents/
│       └── collaboration/
│
├── frontend/                               # Vite + React 18 + TipTap
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.tsx                        # React entry point
│   │   ├── App.tsx                         # Router + layout
│   │   ├── components/
│   │   │   ├── Editor.tsx                  # TipTap editor with Yjs collaboration
│   │   │   ├── PresenceBar.tsx             # Active users + cursors
│   │   │   ├── DocumentList.tsx            # Document listing page
│   │   │   └── VersionHistory.tsx          # Version sidebar with restore
│   │   ├── hooks/
│   │   │   ├── useYjsConnection.ts         # Yjs Y.Doc + WebSocket provider
│   │   │   └── usePresence.ts              # Awareness protocol (cursors, users)
│   │   └── lib/
│   │       └── api.ts                      # REST API client (fetch wrapper)
│   └── public/
└── scripts/
    └── seed.py
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development without Docker)
- Node.js 18+ (for frontend development)

### Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd realtime-collaborative-cms

# Start all services
docker compose up --build

# The application will be available at:
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000
# API docs:  http://localhost:8000/docs
```

### Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
# Serve with any static file server
python -m http.server 3000
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/cms` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `JWT_SECRET` | `changeme` | Secret key for JWT token signing |

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
# Run backend tests
cd backend
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Load testing (requires k6)
k6 run scripts/load_test.js
```

## Scaling

The system is designed to handle 10,000+ concurrent users:

- **Horizontal scaling** — Add server instances behind the load balancer; each manages in-memory CRDT documents independently
- **Redis pub/sub** — Bridges updates across server instances so clients on different servers stay in sync
- **Sticky sessions** — WebSocket connections are pinned to one server via the load balancer
- **PostgreSQL read replicas** — Offload version history and search queries from the primary

## License

MIT
