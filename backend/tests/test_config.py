from shared.config import Settings


def test_default_settings():
    s = Settings()
    assert "postgresql+asyncpg" in s.DATABASE_URL
    assert "redis" in s.REDIS_URL
    assert s.JWT_ALGORITHM == "HS256"
    assert s.JWT_EXPIRATION_MINUTES == 60


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@db:5432/testdb")
    monkeypatch.setenv("REDIS_URL", "redis://redis-test:6379")
    monkeypatch.setenv("JWT_SECRET", "supersecret")

    s = Settings()
    assert s.DATABASE_URL == "postgresql+asyncpg://test:test@db:5432/testdb"
    assert s.REDIS_URL == "redis://redis-test:6379"
    assert s.JWT_SECRET == "supersecret"
