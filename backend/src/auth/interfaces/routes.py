from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.application.services import authenticate_user, register_user
from auth.domain.entities import User
from auth.infrastructure.user_repository import DbUserRepository
from auth.interfaces.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from shared.dependencies import get_current_user, get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    repo = DbUserRepository(db)
    user = await register_user(
        repo,
        username=body.username,
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        password=body.password,
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    repo = DbUserRepository(db)
    _, token = await authenticate_user(repo, email=body.email, password=body.password)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
