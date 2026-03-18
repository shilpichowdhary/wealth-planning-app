from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import create_tables

app = FastAPI(title="Wealth Planning API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await create_tables()

@app.get("/health")
async def health():
    return {"status": "ok"}
