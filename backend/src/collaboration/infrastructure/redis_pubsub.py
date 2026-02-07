import asyncio
from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

from redis.asyncio import Redis


def _channel_name(document_id: UUID) -> str:
    return f"doc:{document_id}:updates"


async def publish_update(redis: Redis, document_id: UUID, data: bytes) -> None:
    await redis.publish(_channel_name(document_id), data)


async def subscribe(
    redis: Redis,
    document_id: UUID,
    callback: Callable[[bytes], Coroutine[Any, Any, None]],
) -> asyncio.Task:
    """Subscribe to document updates. Returns a task that can be cancelled to unsubscribe."""
    pubsub = redis.pubsub()
    await pubsub.subscribe(_channel_name(document_id))

    async def _listen():
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await callback(message["data"])
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(_channel_name(document_id))
            await pubsub.aclose()

    return asyncio.create_task(_listen())
