"""FastAPI application entry point.

Configures the app with:
  - Lifespan handler for database initialisation
  - CORS middleware (permissive for development)
  - Request logging middleware with request-ID tracing
  - All API routers (auth, clients, summaries, reports, search, chat)
  - Static file serving for the built-in UI
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.middleware import RequestLoggingMiddleware
from app.routers import auth, clients, conversation, reports, search, summaries
from app.schemas import HealthResponse

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run database migrations on startup (creates tables if they don't exist)."""
    await init_db()
    logging.getLogger(__name__).info("Database tables created / verified")
    yield


app = FastAPI(
    title="Email Context & Summarization API",
    description=(
        "Captures and summarises all email discussions between CPA firm "
        "accountants and their clients, providing a unified source of truth."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(summaries.router)
app.include_router(reports.router)
app.include_router(search.router)
app.include_router(conversation.router)


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Liveness probe — returns 200 if the API is running."""
    return HealthResponse()


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_ui():
    """Serve the built-in web UI at the root URL."""
    return FileResponse(str(STATIC_DIR / "index.html"))
