import jwt
import pytest

from auth.application.services import authenticate_user, register_user, verify_token
from auth.infrastructure.user_repository import DbUserRepository
from shared.config import settings
from shared.exceptions import AuthenticationError, ConflictError


@pytest.fixture
def repo(db):
    return DbUserRepository(db)


async def test_register_user(repo):
    user = await register_user(
        repo,
        username="alice",
        email="alice@example.com",
        first_name="Alice",
        last_name="Smith",
        password="secret123",
    )
    assert user.id is not None
    assert user.username == "alice"
    assert user.email == "alice@example.com"
    assert user.first_name == "Alice"
    assert user.password_hash != "secret123"


async def test_register_duplicate_email(repo):
    await register_user(
        repo,
        username="alice",
        email="alice@example.com",
        first_name="Alice",
        last_name="Smith",
        password="secret123",
    )
    with pytest.raises(ConflictError, match="Email already registered"):
        await register_user(
            repo,
            username="bob",
            email="alice@example.com",
            first_name="Bob",
            last_name="Jones",
            password="other123",
        )


async def test_register_duplicate_username(repo):
    await register_user(
        repo,
        username="alice",
        email="alice@example.com",
        first_name="Alice",
        last_name="Smith",
        password="secret123",
    )
    with pytest.raises(ConflictError, match="Username already taken"):
        await register_user(
            repo,
            username="alice",
            email="different@example.com",
            first_name="Alice",
            last_name="Two",
            password="other123",
        )


async def test_authenticate_user(repo):
    await register_user(
        repo,
        username="alice",
        email="alice@example.com",
        first_name="Alice",
        last_name="Smith",
        password="secret123",
    )
    user, token = await authenticate_user(repo, email="alice@example.com", password="secret123")
    assert user.username == "alice"
    assert token is not None

    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert payload["sub"] == str(user.id)
    assert "exp" in payload


async def test_authenticate_wrong_password(repo):
    await register_user(
        repo,
        username="alice",
        email="alice@example.com",
        first_name="Alice",
        last_name="Smith",
        password="secret123",
    )
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await authenticate_user(repo, email="alice@example.com", password="wrong")


async def test_authenticate_nonexistent_email(repo):
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await authenticate_user(repo, email="nobody@example.com", password="secret123")


async def test_verify_valid_token(repo):
    registered = await register_user(
        repo,
        username="alice",
        email="alice@example.com",
        first_name="Alice",
        last_name="Smith",
        password="secret123",
    )
    _, token = await authenticate_user(repo, email="alice@example.com", password="secret123")

    user = await verify_token(repo, token)
    assert user.id == registered.id


async def test_verify_invalid_token(repo):
    with pytest.raises(AuthenticationError, match="Invalid or expired token"):
        await verify_token(repo, "garbage.token.here")
