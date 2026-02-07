from redis.asyncio import Redis, ConnectionPool

from shared.config import settings

pool = ConnectionPool.from_url(settings.REDIS_URL)


def get_redis_pool() -> Redis:
    return Redis(connection_pool=pool)
