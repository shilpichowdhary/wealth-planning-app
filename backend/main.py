from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from backend.config import settings, validate_secrets
from backend.database import create_tables
from backend.services.rate_limit import limiter, user_limiter
import backend.models  # noqa: F401 — ensures all models are registered with Base.metadata

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_secrets(settings)
    await create_tables()
    yield

app = FastAPI(title="Wealth Planning API", version="1.0.0", lifespan=lifespan)

# Accept any localhost / 127.0.0.1 port during local development so the
# frontend still works when Next falls back to 3001, 3002, etc.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://team-dashboard.lighthouse-canton.com:8081"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (SEC-02, AI-07). Two limiters share one middleware:
# - `limiter` keys by IP (auth endpoints, pre-login)
# - `user_limiter` keys by authenticated user_id (chat endpoints)
app.state.limiter = limiter
app.state.user_limiter = user_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

from backend.routers import auth as auth_router
app.include_router(auth_router.router)

from backend.routers import kb as kb_router
app.include_router(kb_router.router)

from backend.routers import cases as cases_router
app.include_router(cases_router.router)

from backend.routers import chat as chat_router
app.include_router(chat_router.router)

from backend.routers import reports as reports_router
app.include_router(reports_router.router)

from backend.routers import documents
app.include_router(documents.router)

from backend.routers import admin as admin_router
app.include_router(admin_router.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
