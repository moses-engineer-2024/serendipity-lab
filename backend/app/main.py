from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Loads the gitignored `.env` (GEMINI_API_KEY etc.) before the gateway reads it.
from app.core.config.settings import load_env_once

load_env_once()

from app.api.routes import router as api_router  # noqa: E402

# The dev frontend runs on another port, so the browser needs CORS to read the stream.
# Set CORS_ORIGINS (comma separated) to override; never use "*" with credentials.
DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://localhost:8081"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]

app = FastAPI(
    title="Serendipity Lab API",
    version="0.1.0",
    description="Backend service for the Serendipity Lab research-collision workflow.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "accept"],
)

app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Serendipity Lab backend is running."}
