from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from auth.domain.entities import User
from auth.domain.repository import UserRepository
from shared.config import settings
from shared.exceptions import AuthenticationError, ConflictError


async def register_user(
    repo: UserRepository,
    username: str,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
) -> User:
    if await repo.get_by_email(email):
        raise ConflictError("Email already registered")
    if await repo.get_by_username(username):
        raise ConflictError("Username already taken")

    user = User(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
    )
    return await repo.create(user)


async def authenticate_user(
    repo: UserRepository, email: str, password: str
) -> tuple[User, str]:
    user = await repo.get_by_email(email)
    if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        raise AuthenticationError("Invalid email or password")

    token = _create_token(str(user.id))
    return user, token


async def verify_token(repo: UserRepository, token: str) -> User:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        raise AuthenticationError("Invalid or expired token")

    user = await repo.get_by_id(payload["sub"])
    if not user:
        raise AuthenticationError("User not found")
    return user


def _create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
