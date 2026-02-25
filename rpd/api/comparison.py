"""Comparison API endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from rpd.models import ComparisonReport, ExtractionResult
from rpd.services.comparison_engine import compare

router = APIRouter(prefix="/compare", tags=["comparison"])

# In-memory job store
_compare_jobs: dict[str, dict[str, Any]] = {}


class CompareRequest(BaseModel):
    left_run_id: str | None = None
    right_run_id: str | None = None
    left_result: ExtractionResult | dict | None = None
    right_result: ExtractionResult | dict | None = None
    normalization_rules: dict[str, bool] | None = None
    similarity_threshold: float = 0.95
    document_type: str | None = None


@router.post("")
async def compare_sync(body: CompareRequest = Body(...)) -> ComparisonReport:
    """
    Synchronous comparison. Provide either run_ids (from stored results)
    or left_result + right_result directly.
    """
    left: ExtractionResult | None = None
    right: ExtractionResult | None = None

    if body.left_result and body.right_result:
        left = ExtractionResult(**body.left_result) if isinstance(body.left_result, dict) else body.left_result
        right = ExtractionResult(**body.right_result) if isinstance(body.right_result, dict) else body.right_result
    elif body.left_run_id and body.right_run_id:
        from rpd.api.extraction import _results_by_run
        left = _results_by_run.get(body.left_run_id)
        right = _results_by_run.get(body.right_run_id)
        if not left:
            raise HTTPException(status_code=404, detail=f"Extraction result not found: {body.left_run_id}")
        if not right:
            raise HTTPException(status_code=404, detail=f"Extraction result not found: {body.right_run_id}")
    else:
        raise HTTPException(status_code=400, detail="Provide left_result and right_result, or left_run_id and right_run_id")

    report = compare(
        left=left,
        right=right,
        normalization_rules=body.normalization_rules,
        similarity_threshold=body.similarity_threshold,
        document_type=body.document_type,
    )
    return report


@router.post("/async")
async def compare_async(body: CompareRequest = Body(...)) -> dict:
    """Asynchronous comparison. Returns job_id."""
    job_id = str(uuid.uuid4())
    left: ExtractionResult | None = None
    right: ExtractionResult | None = None

    if body.left_result and body.right_result:
        left = ExtractionResult(**body.left_result) if isinstance(body.left_result, dict) else body.left_result
        right = ExtractionResult(**body.right_result) if isinstance(body.right_result, dict) else body.right_result
    elif body.left_run_id and body.right_run_id:
        from rpd.api.extraction import _results_by_run
        left = _results_by_run.get(body.left_run_id)
        right = _results_by_run.get(body.right_run_id)
        if not left:
            raise HTTPException(status_code=404, detail=f"Extraction result not found: {body.left_run_id}")
        if not right:
            raise HTTPException(status_code=404, detail=f"Extraction result not found: {body.right_run_id}")
    else:
        raise HTTPException(status_code=400, detail="Provide left_result and right_result, or left_run_id and right_run_id")

    _compare_jobs[job_id] = {"status": "running", "report": None, "error": None}

    try:
        report = compare(
            left=left,
            right=right,
            normalization_rules=body.normalization_rules,
            similarity_threshold=body.similarity_threshold,
            document_type=body.document_type,
        )
        _compare_jobs[job_id]["status"] = "completed"
        _compare_jobs[job_id]["report"] = report
    except Exception as e:
        _compare_jobs[job_id]["status"] = "failed"
        _compare_jobs[job_id]["error"] = str(e)

    return {"job_id": job_id, "status": "submitted"}


@router.get("/jobs/{job_id}")
async def get_compare_job(job_id: str) -> dict:
    """Get comparison job status."""
    if job_id not in _compare_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    j = _compare_jobs[job_id]
    return {"job_id": job_id, "status": j["status"], "error": j.get("error")}


@router.get("/jobs/{job_id}/report")
async def get_compare_report(job_id: str) -> ComparisonReport:
    """Get comparison report for completed job."""
    if job_id not in _compare_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    j = _compare_jobs[job_id]
    if j["status"] != "completed":
        raise HTTPException(status_code=202, detail=f"Job not completed: {j['status']}")
    if j.get("error"):
        raise HTTPException(status_code=500, detail=j["error"])
    return j["report"]
