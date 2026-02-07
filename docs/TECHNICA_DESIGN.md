# Technical design document

**Author:** Mahesh Ravikumar

**Date:** 2026-02-07

---
## Executive Summary

**Challenge:** Design and prototype a collaborative Content Management System (CMS) that allows multiple users to edit the same document simultaneously while maintaining data integrity and version history.

**Proposed Solution:** A hybrid concurrency architecture using CRDTs (Yjs) for real-time document body editing like google docs, Last-Write-Wins with optimistic locking for metadata fields, WebSockets for transport, and Redis pub/sub for cross-server fanout. PostgreSQL serves as the durable store for binary CRDT snapshots, incremental updates, and version history.

**Impact:**
- **Users:** Able to handle around 10,000+ concurrent users with horizontal scaling.
- **Engineering:**
	- Minimal technical debt via well-separated concerns (CRDT for body, LWW for metadata)
	- Low maintenance overhead (Yjs handles merge complexity; no custom OT transforms)
	- Horizontal scalability through stateless server instances bridged by Redis

---
## Proposed Solution

### High-Level Architecture

```
                         ┌─────────────────┐
                         │  Load Balancer  │
                         │    (nginx)      │
                         └────────┬────────┘
                ┌─────────────────┼─────────────────┐
                ▼                 ▼                  ▼
         ┌────────────┐   ┌────────────┐   ┌────────────┐
         │  FastAPI   │   │  FastAPI   │   │  FastAPI   │
         │  Server 1  │   │  Server 2  │   │  Server 3  │
         │  (y-py)    │   │  (y-py)    │   │  (y-py)    │
         └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
               │                │                 │
               └────────┬───────┘─────────────────┘
                        │
                  ┌─────┴─────┐
                  │           │
                  ▼           ▼
         ┌──────────────┐ ┌──────────────┐
         │    Redis     │ │  PostgreSQL  │
         │  (pub/sub,   │ │  (durable    │
         │  presence,   │ │   storage,   │
         │  sessions)   │ │   versions)  │
         └──────────────┘ └──────────────┘
```

**Data flow:** Clients connect via WebSocket to any server instance. Edits are applied to an in-memory Yjs document, broadcast to peers via Redis pub/sub, and periodically persisted to PostgreSQL as binary snapshots.

### Detailed Design

#### Component 1: Real-Time Collaboration Engine (CRDT via Yjs)
**Purpose:** Handle concurrent document body edits across multiple users with guaranteed convergence and zero data loss.

**Key Decisions:**
- CRDT (Yjs) chosen over OT because it scales horizontally (no central operation sequence controller per document) and supports offline editing in the UI.
- Binary CRDT state stored as `BYTEA` in PostgreSQL rather than text, preserves merge metadata (character IDs, tombstones) needed for future sync
- Incremental updates stored between snapshots to reduce write amplification

---

#### Component 2: Metadata Management (Last-Write-Wins)
**Purpose:** Handle simple field updates (title, status, tags) where character-level merging is unnecessary.

**Implementation:**
```python
# Optimistic locking for metadata updates
async def update_document_metadata(
    db: AsyncSession, doc_id: UUID, title: str, expected_version: int
):
    result = await db.execute(
        update(Document)
        .where(Document.id == doc_id, Document.version == expected_version)
        .values(title=title, version=Document.version + 1, updated_at=func.now())
    )
    if result.rowcount == 0:
        raise ConflictError("Document was modified by another user. Please refresh.")
```

**Key Decisions:**
- Optimistic locking (version counter) rather than pessimistic locks - lower contention for metadata fields
- `WHERE version = :expected_version` pattern rejects stale writes at the SQL level
- Client must re-fetch and retry on conflict (409 response)

---

#### Component 3: WebSocket Transport + Redis Pub/Sub Bridge
**Purpose:** Deliver real-time updates between clients, even when connected to different server instances.

**Key Decisions:**
- One Redis pub/sub channel per document which isolates traffic
- Any server can independently load and merge CRDT state — no single-server bottleneck

---

#### Component 4: Version History & Snapshots
**Purpose:** Provide named save points, version browsing, and rollback capability.

**Implementation:**
```python
async def save_version(doc_id: UUID, user_id: UUID, label: str):
    doc_manager = active_documents[doc_id]
    version_num = await get_next_version(doc_id)

    await db.execute(
        insert(DocumentVersion).values(
            document_id=doc_id,
            version=version_num,
            label=label,
            snapshot=doc_manager.encode_state(),      
            content_text=doc_manager.get_text(),
            created_by=user_id,
        )
    )
```

**Key Decisions:**
- Dual storage: `BYTEA` snapshot for restoration + `TEXT` content for SQL full-text search
- Periodic automatic snapshots (every 100 updates) to bound recovery time
- Old incremental updates pruned after snapshot — keeps `document_updates` table small

### Data Model Changes


#### Entity Relationship Diagram

```
┌──────────────────────┐
│        users         │
├──────────────────────┤
│ id          UUID  PK │
│ username    VARCHAR   │
│ email       VARCHAR   │
│ password_hash TEXT    │
│ created_at  TIMESTAMPTZ│
│ updated_at  TIMESTAMPTZ│
└──────────┬───────────┘
           │
           │ owner_id          user_id           created_by         user_id
           ▼                      ▼                   ▼                 ▼
┌─────────────────────┐  ┌──────────────────┐  ┌───────────────────┐  ┌──────────────────┐
│     documents       │  │ document_updates │  │ document_versions │  │ active_sessions  │
├─────────────────────┤  ├──────────────────┤  ├───────────────────┤  ├──────────────────┤
│ id       UUID    PK │  │ id     BIGSERIAL │  │ id     BIGSERIAL  │  │ id      UUID  PK │
│ title    VARCHAR    │  │ document_id UUID │  │ document_id UUID  │  │ document_id UUID │
│ status   VARCHAR    │  │ update_data BYTEA│  │ version INTEGER   │  │ user_id     UUID │
│ owner_id UUID    FK │  │ update_seq  INT  │  │ label   VARCHAR   │  │ connected_at     │
│ version  INTEGER    │  │ user_id    UUID  │  │ snapshot BYTEA    │  │ last_seen        │
│ created_at          │  │ created_at       │  │ content_text TEXT │  └──────────────────┘
│ updated_at          │  └───────┬──────────┘  │ created_by UUID   │           ▲
└─────────┬────────── ┘         │              │ created_at        │           │
          │                     │              └────────┬──────────┘           │
          │ document_id         │ document_id          │ document_id          │ document_id
          │                     │                      │                      │
          ├─────────────────────┴──────────────────────┴──────────────────────┘
          │
          │ document_id
          ▼
┌─────────────────────────┐
│   document_snapshots    │
├─────────────────────────┤
│ id           BIGSERIAL  │
│ document_id  UUID    FK │
│ snapshot     BYTEA      │
│ state_vector BYTEA      │
│ update_seq   INTEGER    │
│ created_at   TIMESTAMPTZ│
└─────────────────────────┘

Relationships:
  users         1 ──< N  documents            (owner_id)
  users         1 ──< N  document_updates     (user_id)
  users         1 ──< N  document_versions    (created_by)
  users         1 ──< N  active_sessions      (user_id)
  documents     1 ──< N  document_snapshots   (document_id, ON DELETE CASCADE)
  documents     1 ──< N  document_updates     (document_id, ON DELETE CASCADE)
  documents     1 ──< N  document_versions    (document_id, ON DELETE CASCADE)
  documents     1 ──< N  active_sessions      (document_id, ON DELETE CASCADE)
```


#### Redis Key Patterns

```
# Pub/Sub channels (one per document)
doc:{document_id}:updates      → binary Yjs updates (cross-server sync)

# Session store
session:{session_id}           → {user_id, document_id, server_id}  TTL: 1 hour

# Presence (sorted set, score = last-seen timestamp)
doc:{document_id}:active_users → ZADD user_id score=timestamp
                                  ZRANGEBYSCORE to get active users
                                  ZREMRANGEBYSCORE to expire stale entries
```

#### How CRDT State Flows Through the Database

```
1. CLIENT CONNECTS
   Server loads: latest snapshot + all updates after it
   ┌───────────────────────────────────────────────┐
   │ SELECT snapshot, state_vector, update_seq     │
   │ FROM document_snapshots                       │
   │ WHERE document_id = :id                       │
   │ ORDER BY update_seq DESC LIMIT 1;             │
   │                                               │
   │ SELECT update_data FROM document_updates      │
   │ WHERE document_id = :id                       │
   │   AND update_seq > :snapshot_seq              │
   │ ORDER BY update_seq ASC;                      │
   └───────────────────────────────────────────────┘
   Server reconstructs Y.Doc in memory → sends full state to client via WebSocket

2. CLIENT EDITS
   Client sends binary Yjs update → Server:
   a) Applies to in-memory Y.Doc (instant merge, no conflicts by design)
   b) INSERT INTO document_updates (small binary diff, ~50-200 bytes per keystroke)
   c) PUBLISH to Redis → other server instances receive and apply to their Y.Doc copies
   d) Those servers forward to their connected WebSocket clients

3. PERIODIC SNAPSHOT (every 100 updates or 30 seconds of inactivity)
   Server encodes full Y.Doc state → INSERT INTO document_snapshots
   DELETE FROM document_updates WHERE document_id = :id AND update_seq <= :snapshot_seq
   This bounds the updates table size per document

4. VERSION SAVE (user clicks "Save Version")
   Encode current Y.Doc state → INSERT INTO document_versions
   Extract plaintext → stored in content_text column for full-text search
   Versions are immutable — never deleted or modified
```

### State Management
- **Server-side:** In-memory Yjs `Y.Doc` per active document, loaded from PostgreSQL on first connection, evicted after all clients disconnect
- **Client-side:** Yjs `Y.Doc` with `y-websocket` provider — handles sync protocol, awareness (cursors/presence), and automatic reconnection
- **Cross-server:** Redis pub/sub ensures all server instances maintain consistent in-memory CRDT state

### UI/UX Changes
- Rich text editor powered by TipTap (ProseMirror-based) with Yjs collaboration via `y-prosemirror`
- Live cursor positions and user names displayed in the editor (via Yjs awareness protocol)
- Document list page (React) with status badges and "last edited by" indicators
- Version history sidebar with restore capability
- Built with Vite + React 18 for fast dev experience and HMR

---

## Alternative Approaches Considered

### Alternative 1: Operational Transformation (OT)
**Description:** Every edit is expressed as an operation (insert/delete at position). A central server assigns a global sequence number and applies a transform function to adjust concurrent operations so both can be applied without conflict.

**Pros:**
- Proven at scale (Google Docs has used OT)
- Full audit trail — every operation stored as a structured row, queryable with SQL
- Mature theoretical foundation with well-understood convergence properties

**Cons:**
- Transform functions are notoriously difficult to implement correctly, also it needs to be done at the server side.
- Requires a **central server per document** to assign `seq_num` — creates a bottleneck that is hard to scale horizontally
- Cannot support offline editing — operations must be ordered by the server before applying
- `SELECT MAX(seq_num) + 1` requires serialization (advisory lock or `SELECT FOR UPDATE`), adding latency under contention
- Operations table grows unboundedly — needs periodic compaction and archival
- Grouping of the data happens at the server side which might consume lot of memory.

**Why Not Chosen:** The central sequencing requirement creates a per-document bottleneck that contradicts our goal of handling 10,000+ concurrent users across horizontally scaled servers. The implementation complexity of transform functions is high and error-prone, while CRDTs achieve the same convergence guarantee with less operational complexity.

### Alternative 2: Last-Write-Wins (LWW) for Document Body
**Description:** Each edit overwrites the entire document body with a timestamp. When concurrent edits arrive, the one with the latest timestamp wins and the other is silently discarded.

**Pros:**
- Extremely simple to implement — standard SQL `UPDATE` with a version check
- Lowest storage overhead — only the current state is stored, no operation logs or binary blobs
- SQL-searchable — document body is plain `TEXT`, works with `LIKE`, full-text search, etc.
- No special libraries required

**Cons:**
- **Destructive** — concurrent edits are silently lost, only the last writer's version survives
- No character-level merging — if User A edits paragraph 1 and User B edits paragraph 3, one user's work is completely overwritten
- Poor user experience for real-time collaboration — users see their changes disappear
- Optimistic lock conflicts force the losing client to re-fetch and manually redo their changes

**Why Not Chosen:** The core requirement is simultaneous editing by multiple users. LWW fundamentally cannot merge concurrent edits to the document body — it discards one user's work entirely. However, LWW **is** used in the chosen approach for metadata fields (title, status) where field-level overwrite is acceptable.

### Alternative 3: PostgreSQL Advisory Locks with Pessimistic Locking
**Description:** Use `pg_advisory_lock(doc_id)` to grant exclusive write access to one user at a time. Other users must wait or are shown a "document locked" message.

**Pros:**
- Eliminates conflicts entirely — only one writer at a time
- Simple to implement with standard PostgreSQL features

**Cons:**
- **Not collaborative** — defeats the purpose of multi-user simultaneous editing
- Users experience blocking or "locked by another user" errors
- Long-held locks can cause deadlocks or starvation

**Why Not Chosen:** Fundamentally incompatible with the requirement for simultaneous multi-user editing.

### Comparison: Database Impact Summary

| Aspect | LWW | OT | CRDT (Yjs) |
|---|---|---|---|
| **What's stored in DB** | Final field value | Every operation as a row | Binary state + diffs |
| **Storage format** | `TEXT` columns | Structured `INSERT` rows | `BYTEA` blobs |
| **Write pattern** | `UPDATE` (overwrite) | `INSERT` (append-only log) | `INSERT` (binary diffs) |
| **Read pattern** | Simple `SELECT` | Replay ops from log | Load snapshot + apply diffs |
| **SQL searchable** | Yes (directly) | Yes (replay to text) | No (need extracted `content_text` column) |
| **Storage growth** | Constant per field | Unbounded (needs compaction) | Moderate (snapshot + prune) |
| **Conflict handling** | In SQL (`WHERE version=`) | In app server (transform fn) | In memory (CRDT merge) |
| **DB locking needs** | Optimistic lock | Advisory lock per doc | Minimal (append-only) |
| **Horizontal scaling** | Easy | Hard (serialize per doc) | Easy (any server can merge) |

---

## Technical Considerations

### Dependencies
- **External Libraries:**
  - `fastapi` + `uvicorn` — async Python web framework and ASGI server
  - `ypy-websocket` + `y-py` — Yjs CRDT Python bindings and WebSocket sync
  - `sqlalchemy[asyncio]` + `asyncpg` — async PostgreSQL ORM
  - `redis[hiredis]` + `aioredis` — async Redis client with pub/sub
  - `alembic` — database migration management
  - `react` + `react-dom` (frontend) — React 18 UI framework
  - `vite` (frontend) — Build tool and dev server
  - `@tiptap/react` + `@tiptap/starter-kit` (frontend) — ProseMirror-based rich text editor for React
  - `yjs` + `y-prosemirror` + `y-websocket` (frontend) — CRDT library, TipTap/ProseMirror binding, WebSocket provider
- **Internal Dependencies:** PostgreSQL 16, Redis 7

### Performance
- **Expected Impact:** Positive — CRDT merges happen in-memory (microseconds); database writes are batched via periodic snapshots
- **Optimization Strategies:**
  - In-memory Y.Doc cache per active document — avoids DB reads during active editing
  - Periodic snapshots (every 100 updates) with pruning of old incremental updates
  - Redis pub/sub for cross-server sync (sub-millisecond latency)
  - PostgreSQL read replicas for version history queries
  - Connection pooling via `asyncpg` (pool size tuned per server instance)
- **Load Testing:** Locust scripts or similar simulating 10,000 concurrent WebSocket connections across 3 server instances

### Security
- **Authentication/Authorization:** JWT-based token auth; tokens validated on WebSocket upgrade
- **Data Privacy:** Document access controlled per-user; WebSocket channels scoped to authorized documents
- **Vulnerabilities:** Input sanitization on document titles (prevent XSS); rate limiting on WebSocket messages; binary Yjs updates validated before applying

### Scalability
- **Target Scale:** 10,000+ concurrent users editing across multiple documents
- **Scaling Strategy:**
  - **Horizontal:** Add more FastAPI server instances behind the load balancer; each independently manages in-memory Y.Docs
  - **Redis pub/sub** bridges state across servers — no server is a single point of truth for any document
  - **Sticky sessions** at the load balancer ensure WebSocket connections persist to one server
  - **PostgreSQL:** Primary for writes, read replicas for version history/search queries
  - **Document sharding:** Under extreme load, partition documents across Redis clusters by `doc_id` hash

### Error Handling
- **Error States:** WebSocket disconnections trigger automatic client reconnection with state re-sync via Yjs state vector diffing
- **Monitoring:** Structured logging (JSON), Prometheus metrics for active connections/documents/update rates
- **Fallback Mechanisms:** If Redis is temporarily unavailable, updates are applied locally and re-synced when Redis recovers; if PostgreSQL is down, in-memory edits continue and are persisted when the connection restores

### Accessibility
- **WCAG Compliance:** AA level — editor built on accessible components (TipTap/ProseMirror have built-in a11y)
- **Keyboard Navigation:** Full keyboard support for editor, document list, and version history
- **Screen Reader Support:** ARIA labels on collaboration indicators (user presence, cursor positions)

### Browser/Device Compatibility
- **Supported Browsers:** Chrome 90+, Firefox 90+, Safari 15+, Edge 90+
- **Mobile Support:** Responsive layout; touch-friendly editor controls
- **Progressive Enhancement:** Core editing works without WebSocket (REST fallback with polling), but real-time sync requires WebSocket support

---

## Deployment Plan

### Rollout Strategy
- **Feature Flag:** No (greenfield — deploy as complete system)
- **Phased Rollout:**
  1. Deploy to staging with Docker Compose
  2. Internal team testing (5-10 users)
  3. Production deployment with monitoring
- **Rollback Plan:** `docker compose down && docker compose up` with previous image tags; database migrations are reversible via Alembic downgrade

### Migration Steps
1. Provision PostgreSQL and Redis instances
2. Run `alembic upgrade head` to create database schema
3. Deploy backend containers behind load balancer
4. Deploy frontend static assets
5. Run seed script for initial test data

### Environment Checklist
- [ ] Development environment setup (Docker Compose)
- [ ] PostgreSQL provisioned and accessible
- [ ] Redis provisioned and accessible
- [ ] Environment variables configured (`DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`)
- [ ] Load balancer configured with sticky sessions for WebSocket



## Risks & Mitigations

| Risk | Probability | Impact | Mitigation Strategy |
|------|-------------|--------|---------------------|
| Yjs binary state corruption in PostgreSQL | Low | High | Checksums on snapshots; validate state on load; keep previous snapshot as fallback |
| Redis pub/sub message loss under high load | Medium | Medium | Yjs state vector diffing on reconnect fills any gaps; Redis Streams as alternative if needed |
| Memory pressure from large in-memory Y.Docs | Medium | Medium | Evict idle documents after timeout; cap max document size; monitor per-doc memory usage |
| WebSocket connection storms after server restart | Medium | High | Exponential backoff with jitter on client reconnect; connection rate limiting at load balancer |
| PostgreSQL write bottleneck from update inserts | Low | Medium | Batch updates in write-behind buffer; increase snapshot frequency to reduce update rows |

---

## Success Criteria

### Definition of Done
- [ ] All acceptance criteria met
- [ ] Code reviewed and approved
- [ ] Tests written and passing (>80% coverage)
- [ ] Documentation updated
- [ ] Deployed to staging with Docker Compose
- [ ] Two concurrent users can edit the same document in real-time without data loss
- [ ] Version history works — save, browse, and restore previous versions
- [ ] System handles 100+ concurrent WebSocket connections on a single instance
