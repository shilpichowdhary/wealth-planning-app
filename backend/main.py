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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.routers import auth as auth_router
app.include_router(auth_router.router)

from backend.routers import kb as kb_router
app.include_router(kb_router.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
