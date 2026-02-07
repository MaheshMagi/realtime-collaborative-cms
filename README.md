# Realtime Collaborative CMS

A collaborative Content Management System that allows multiple users to edit the same document simultaneously while maintaining data integrity.

## Features

- **Real-time collaborative editing** — Multiple users can edit the same document at the same time with instant sync
- **Conflict-free merging** — Concurrent edits are merged automatically using CRDTs (Conflict-free Replicated Data Types) via Yjs, so no user's work is ever lost
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
| Real-time sync | Yjs (CRDT), pycrdt |
| Database | PostgreSQL 16 |
| Cache / Pub-Sub | Redis 7 |
| Frontend | React 18, Vite, TipTap, Yjs |
| Infrastructure | Docker Compose |

## Concurrency Strategy

The system uses a **hybrid approach** for handling concurrent edits:

| Data | Strategy | Rationale |
|---|---|---|
| Document body | CRDT (Yjs) | Character-level merging, no data loss, supports offline |
| Metadata (title, status) | Last-Write-Wins + optimistic locking | Simple fields, low contention |
| Real-time transport | WebSocket + Redis pub/sub | Low-latency fan-out across server instances |

See the [Technical Design Document](docs/TECHNICAL_DESIGN.md) for a detailed comparison of OT, CRDTs, and Last-Write-Wins and how each interacts with PostgreSQL.

## Project Structure

The backend is organized into **feature modules** (`auth`, `documents`, `collaboration`), each following a 4-layer clean architecture:

| Layer | Responsibility |
|---|---|
| **domain/** | Pure entities (dataclasses), repository interfaces (Protocols) |
| **application/** | Service functions orchestrating domain objects and repository calls |
| **infrastructure/** | Repository implementations (SQLAlchemy/Redis), ORM models, adapters |
| **interfaces/** | FastAPI routes, WebSocket handlers, Pydantic schemas (DTOs) |

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for frontend dev server)

### 1. Start Backend Services

```bash
# Start PostgreSQL, Redis, and backend
docker compose up -d

# Run migrations (one-time)
docker compose exec backend alembic upgrade head
```

Backend API available at http://localhost:8000 (Swagger docs at `/docs`).
Local file changes auto-reload inside the container via volume mount.

### 2. Start Frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Frontend available at http://localhost:5173 (proxies `/api` and `/ws` requests to backend).

### Running Tests

```bash
# Create test database (one-time)
docker compose exec postgres psql -U postgres -c "CREATE DATABASE cms_test"

# Run tests
docker compose exec backend python -m pytest tests/ -v
```

### Seed Demo Data

```bash
# With backend running, seed 2 demo users and sample documents
python scripts/seed.py
```

Default credentials: `alice` / `password123` and `bob` / `password123`.

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
| `POST` | `/api/auth/register` | Register a new user |
| `POST` | `/api/auth/login` | Authenticate and receive JWT token |
| `GET` | `/api/auth/me` | Get current user profile |
| `POST` | `/api/documents` | Create a new document |
| `GET` | `/api/documents` | List all documents |
| `GET` | `/api/documents/{id}` | Get document metadata |
| `PATCH` | `/api/documents/{id}` | Update metadata (title, status) |
| `DELETE` | `/api/documents/{id}` | Delete a document |
| `WS` | `/ws/doc/{id}` | Real-time collaborative editing |

Full API documentation is available at `/docs` (Swagger UI) when the backend is running.

## Database Schema

The system uses four PostgreSQL tables:

- **users** — User accounts and authentication
- **documents** — Document metadata with optimistic locking (LWW)
- **document_snapshots** — Periodic CRDT state captures (binary)
- **document_updates** — Incremental CRDT updates between snapshots (binary)

## Scaling

The system is designed to handle 10,000+ concurrent users:

- **Horizontal scaling** — Add server instances behind the load balancer; each manages in-memory CRDT documents independently
- **Redis pub/sub** — Bridges updates across server instances so clients on different servers stay in sync
- **Sticky sessions** — WebSocket connections are pinned to one server via the load balancer
- **PostgreSQL read replicas** — Offload version history and search queries from the primary

## License

MIT
