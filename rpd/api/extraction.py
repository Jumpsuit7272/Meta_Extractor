"""Extraction API endpoints (FR - sync/async extraction)."""

import csv
import io
import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

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


def _result_to_row(result: ExtractionResult) -> dict:
    """Flatten an ExtractionResult into a single CSV-friendly dict."""
    tech = result.document.technical_metadata
    content = result.document.content_metadata
    emb = result.document.embedded_metadata
    return {
        "run_id": result.provenance.run_id,
        "file_name": tech.file_name,
        "mime_type": tech.mime_type,
        "extension": tech.extension,
        "file_size_bytes": tech.file_size_bytes,
        "hash_sha256": tech.hash_sha256,
        "hash_md5": tech.hash_md5 or "",
        "page_count": (content.page_count or "") if content else "",
        "word_count": (content.word_count or 0) if content else 0,
        "table_count": (content.table_count or 0) if content else 0,
        "text_length": (content.text_length or 0) if content else 0,
        "language": (content.language or "") if content else "",
        "title": (emb.title or "") if emb else "",
        "author": (emb.author or "") if emb else "",
        "creator": (emb.creator or "") if emb else "",
        "producer": (emb.producer or "") if emb else "",
        "creation_date": (emb.creation_date or "") if emb else "",
        "modified_date": (emb.modified_date or "") if emb else "",
    }


def _rows_to_csv(rows: list[dict]) -> str:
    """Serialise a list of flat dicts to CSV string."""
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


@router.get("/jobs/{job_id}/result.csv")
async def get_extraction_result_csv(job_id: str) -> StreamingResponse:
    """Download extraction result as CSV (single row)."""
    result: ExtractionResult | None = None
    if job_id in _jobs:
        j = _jobs[job_id]
        if j["status"] != "completed":
            raise HTTPException(status_code=202, detail=f"Job not completed: {j['status']}")
        result = j["result"]
    elif job_id in _results_by_run:
        result = _results_by_run[job_id]
    if result is None:
        raise HTTPException(status_code=404, detail="Job or run not found")
    csv_content = _rows_to_csv([_result_to_row(result)])
    filename = result.document.technical_metadata.file_name.rsplit(".", 1)[0] + ".csv"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/results/export.csv")
async def export_results_csv(
    run_ids: str = Query(..., description="Comma-separated list of run_ids"),
) -> StreamingResponse:
    """Download multiple extraction results as a multi-row CSV."""
    ids = [r.strip() for r in run_ids.split(",") if r.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="No run_ids provided")
    rows = []
    for rid in ids:
        result: ExtractionResult | None = _results_by_run.get(rid)
        if result is None and rid in _jobs:
            result = _jobs[rid].get("result")
        if result:
            rows.append(_result_to_row(result))
    if not rows:
        raise HTTPException(status_code=404, detail="No results found for provided run_ids")
    csv_content = _rows_to_csv(rows)
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="export.csv"'},
    )


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
