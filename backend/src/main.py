from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.exceptions import (
    AppError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
)
from shared.infrastructure.database import engine
from shared.infrastructure.redis import get_redis_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
    redis = get_redis_pool()
    await redis.aclose()


app = FastAPI(
    title="Collaborative CMS",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NotFoundError)
async def not_found_handler(request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(ConflictError)
async def conflict_handler(request, exc: ConflictError):
    return JSONResponse(status_code=409, content={"detail": exc.message})


@app.exception_handler(AuthenticationError)
async def auth_error_handler(request, exc: AuthenticationError):
    return JSONResponse(status_code=401, content={"detail": exc.message})


@app.exception_handler(AppError)
async def app_error_handler(request, exc: AppError):
    return JSONResponse(status_code=500, content={"detail": exc.message})


@app.get("/health")
async def health_check():
    return {"status": "ok"}
