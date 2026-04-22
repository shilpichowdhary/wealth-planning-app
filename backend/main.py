from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import create_tables
import backend.models  # noqa: F401 — ensures all models are registered with Base.metadata

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield

app = FastAPI(title="Wealth Planning API", version="1.0.0", lifespan=lifespan)

# Accept any localhost / 127.0.0.1 port during local development so the
# frontend still works when Next falls back to 3001, 3002, etc.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
