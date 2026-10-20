from pathlib import Path
import sys

from fastapi.responses import FileResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.batches import router as batches_router
from app.api.routes.health import router as health_router
from app.api.routes.prospects import router as prospects_router
from app.api.routes.webhooks import router as webhooks_router
from app.api.routes.internal_contacts import router as internal_contacts_router
from app.core.logging import configure_logging
from app.core.config import get_settings

configure_logging()

app = FastAPI(title="Lead Scoring API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(health_router)
app.include_router(batches_router)
app.include_router(prospects_router)
app.include_router(webhooks_router)
app.include_router(internal_contacts_router)


@app.get("/runtime-config", tags=["configuration"])
def runtime_config() -> dict:
    """Public mode information only; never return credentials or provider configuration."""
    from app.providers.demo import sample_prospects
    mode = get_settings().app_mode
    return {"mode": mode, "sample_prospects": sample_prospects() if mode == "demo" else []}


@app.get("/", include_in_schema=False)
@app.get("/lead-scoring-prioritisation-system.html", include_in_schema=False)
def dashboard() -> FileResponse:
    installed = Path(sys.prefix) / "share/lead-scoring/lead-scoring-prioritisation-system.html"
    source = Path(__file__).resolve().parents[1] / "Leadscorefrontend/lead-scoring-prioritisation-system.html"
    return FileResponse(source if source.is_file() else installed, media_type="text/html")
