import asyncio
from uuid import UUID

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from collaboration.application.services import load_document_state, persist_update
from collaboration.infrastructure.crdt_storage_repository import DbCrdtStorageRepository
from collaboration.infrastructure.redis_pubsub import publish_update, subscribe
from collaboration.infrastructure.yjs_adapter import encode_state_as_update
from shared.config import settings
from shared.infrastructure.database import async_session
from shared.infrastructure.redis import get_redis_pool

router = APIRouter()

# In-memory set of connected websockets per document
_connections: dict[UUID, set[WebSocket]] = {}


def _authenticate(token: str) -> str | None:
    """Validate JWT and return user_id, or None if invalid."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload["sub"]
    except jwt.PyJWTError:
        return None


@router.websocket("/ws/doc/{document_id}")
async def websocket_endpoint(websocket: WebSocket, document_id: UUID):
    # Authenticate via query param: ?token=xxx
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    user_id = _authenticate(token)
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()

    # Track connection
    if document_id not in _connections:
        _connections[document_id] = set()
    _connections[document_id].add(websocket)

    redis = get_redis_pool()

    # Subscribe to Redis pub/sub for this document
    async def on_redis_message(data: bytes):
        """Forward updates from other servers/connections to this client."""
        for ws in _connections.get(document_id, set()):
            if ws != websocket:
                try:
                    await ws.send_bytes(data)
                except Exception:
                    pass

    sub_task = await subscribe(redis, document_id, on_redis_message)

    try:
        # Send current document state on connect
        async with async_session() as db:
            repo = DbCrdtStorageRepository(db)
            doc = await load_document_state(repo, document_id)
            state = encode_state_as_update(doc)
            await websocket.send_bytes(state)

        # Listen for updates from this client
        while True:
            data = await websocket.receive_bytes()

            # Persist the update
            async with async_session() as db:
                repo = DbCrdtStorageRepository(db)
                await persist_update(repo, document_id, UUID(user_id), data)

            # Broadcast via Redis (reaches other servers + local on_redis_message)
            await publish_update(redis, document_id, data)

    except WebSocketDisconnect:
        pass
    finally:
        _connections[document_id].discard(websocket)
        if not _connections[document_id]:
            del _connections[document_id]
        sub_task.cancel()
        try:
            await sub_task
        except asyncio.CancelledError:
            pass
