"""Extraction API endpoints (FR - sync/async extraction)."""

import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from rpd.config import settings
from rpd.models import ExtractionResult
from rpd.services.extraction_pipeline import run_extraction

MAX_BYTES = settings.max_upload_mb * 1024 * 1024

router = APIRouter(prefix="/extract", tags=["extraction"])

# In-memory job store (replace with Redis/DB for production)
_jobs: dict[str, dict[str, Any]] = {}
_results_by_run: dict[str, ExtractionResult] = {}


@router.post("/sync")
async def extract_sync(
    file: UploadFile = File(...),
    source_uri: str | None = Form(None),
    source_system: str = Form(""),
    run_id: str | None = Form(None),
    ocr_enabled: bool = Form(True),
    geolocation_lookup: bool | None = Form(None),  # None = use config
) -> ExtractionResult:
    """
    Synchronous extraction. Accepts file upload, returns canonical ExtractionResult.
    """
    try:
        data = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum {settings.max_upload_mb} MB per file.",
        )

    result = run_extraction(
        data=data,
        filename=file.filename or "",
        source_uri=source_uri,
        run_id=run_id,
        source_system=source_system,
        ocr_enabled=ocr_enabled,
        geolocation_lookup=geolocation_lookup,
    )
    _results_by_run[result.provenance.run_id] = result
    return result


@router.post("/bulk")
async def extract_bulk(
    files: list[UploadFile] = File(...),
    source_system: str = Form(""),
    ocr_enabled: bool = Form(True),
    geolocation_lookup: bool | None = Form(None),
) -> list[dict]:
    """
    Bulk extraction. Accepts multiple file uploads, returns list of ExtractionResults.
    Each item has 'result' (ExtractionResult) and 'filename', or 'error' if failed.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files per batch")

    results: list[dict] = []
    for upload in files:
        item: dict = {"filename": upload.filename or "unknown"}
        try:
            data = await upload.read()
            if len(data) > MAX_BYTES:
                item["error"] = f"File too large. Maximum {settings.max_upload_mb} MB per file."
                results.append(item)
                continue
            result = run_extraction(
                data=data,
                filename=upload.filename or "",
                source_system=source_system,
                ocr_enabled=ocr_enabled,
                geolocation_lookup=geolocation_lookup,
            )
            _results_by_run[result.provenance.run_id] = result
            item["result"] = result
            item["run_id"] = result.provenance.run_id
        except Exception as e:
            item["error"] = str(e)
        results.append(item)
    return results


@router.post("/async")
async def extract_async(
    file: UploadFile = File(...),
    source_uri: str | None = Form(None),
    source_system: str = Form(""),
    ocr_enabled: bool = Form(True),
) -> dict:
    """
    Asynchronous extraction. Returns job_id for polling.
    """
    job_id = str(uuid.uuid4())
    try:
        data = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum {settings.max_upload_mb} MB per file.",
        )

    _jobs[job_id] = {
        "status": "running",
        "result": None,
        "error": None,
        "params": {"filename": file.filename, "source_uri": source_uri},
    }

    # Run extraction (blocking - in production use Celery)
    try:
        result = run_extraction(
            data=data,
            filename=file.filename or "",
            source_uri=source_uri,
            run_id=job_id,
            source_system=source_system,
            ocr_enabled=ocr_enabled,
        )
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = result
        _results_by_run[job_id] = result
    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)

    return {"job_id": job_id, "status": "submitted"}


@router.get("/jobs/{job_id}")
async def get_extraction_job(job_id: str) -> dict:
    """Get extraction job status."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    j = _jobs[job_id]
    return {
        "job_id": job_id,
        "status": j["status"],
        "error": j.get("error"),
    }


@router.get("/jobs/{job_id}/result")
async def get_extraction_result(job_id: str) -> ExtractionResult:
    """Get extraction result by job_id or run_id (from sync extraction)."""
    if job_id in _jobs:
        j = _jobs[job_id]
        if j["status"] != "completed":
            raise HTTPException(status_code=202, detail=f"Job not completed: {j['status']}")
        if j.get("error"):
            raise HTTPException(status_code=500, detail=j["error"])
        return j["result"]
    if job_id in _results_by_run:
        return _results_by_run[job_id]
    raise HTTPException(status_code=404, detail="Job or run not found")
