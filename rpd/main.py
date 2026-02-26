"""RPD: Universal File Metadata & Extraction Comparison Service - FastAPI application."""

from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from rpd.api.comparison import router as compare_router
from rpd.api.extraction import router as extract_router
from rpd.api.ingest import router as ingest_router
from rpd.config import settings
from rpd.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.result_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    yield


app = FastAPI(
    title="RPD: Universal File Metadata & Extraction Comparison Service",
    description="Extracts metadata and structured content from files; compares across runs/models/sources.",
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

app.include_router(extract_router)
app.include_router(compare_router)
app.include_router(ingest_router)

# Static files for UI - use multiple path strategies for reliability
def _find_static() -> tuple[Path | None, str | None]:
    """Find static dir and load index.html. Works from any cwd/install."""
    candidates = [
        Path(__file__).resolve().parent / "static",
        Path.cwd() / "rpd" / "static",
        Path.cwd() / "static",
    ]
    for d in candidates:
        idx = d / "index.html"
        if idx.exists():
            return d, idx.read_text(encoding="utf-8")
    return None, None

_static_dir, _ = _find_static()
if _static_dir:
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


def _get_index_html() -> str | None:
    """Load index.html from disk (always fresh, no startup cache)."""
    if not _static_dir:
        return None
    idx = _static_dir / "index.html"
    if idx.exists():
        return idx.read_text(encoding="utf-8")
    return None


def _get_intranet_html() -> str | None:
    """Load intranet.html for intranet landing page."""
    if not _static_dir:
        return None
    path = _static_dir / "intranet.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


@app.get("/intranet")
async def intranet():
    """Intranet landing page with links to app, docs, health."""
    from fastapi.responses import HTMLResponse, RedirectResponse
    content = _get_intranet_html()
    if content:
        return HTMLResponse(content)
    return RedirectResponse("/", status_code=302)


@app.get("/")
async def root():
    """Serve UI or API info."""
    from fastapi.responses import HTMLResponse, JSONResponse
    content = _get_index_html()
    if content:
        return HTMLResponse(
            content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return JSONResponse({
        "service": "RPD Meta Extractor",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "extract_sync": "POST /extract/sync",
            "extract_async": "POST /extract/async",
            "extract_job": "GET /extract/jobs/{job_id}",
            "extract_result": "GET /extract/jobs/{job_id}/result",
            "compare": "POST /compare",
            "compare_async": "POST /compare/async",
            "compare_job": "GET /compare/jobs/{job_id}",
            "compare_report": "GET /compare/jobs/{job_id}/report",
        },
    })


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/config")
async def get_config():
    """Return client config (e.g. max_upload_mb for UI display)."""
    return {"max_upload_mb": settings.max_upload_mb}
