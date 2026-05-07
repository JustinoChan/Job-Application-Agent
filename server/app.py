from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

from server import dependencies
from server.auth import verify_request
from server.routers import applications, dashboard
from server.schemas import ReloadConfigResponse
from src import config

if load_dotenv is not None:
    load_dotenv()


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(title="Job Application Agent API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    config.ensure_directories()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


api_dependencies = [Depends(verify_request)]
app.include_router(applications.router, prefix="/api", dependencies=api_dependencies)
app.include_router(dashboard.router, prefix="/api", dependencies=api_dependencies)


@app.post("/api/reload-config", response_model=ReloadConfigResponse, dependencies=api_dependencies)
def reload_config() -> ReloadConfigResponse:
    dependencies.clear_config_cache()
    return ReloadConfigResponse(message="Configuration cache reloaded.")
