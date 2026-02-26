"""Comparison API endpoints."""

import csv
import io
import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from rpd.database import get_db
from rpd.db_service import (
    load_comparison_report,
    load_extraction_result,
    persist_comparison_report,
)
from rpd.models import ComparisonReport, ExtractionResult
from rpd.services.comparison_engine import compare

router = APIRouter(prefix="/compare", tags=["comparison"])

# In-memory job store (sync results stored here too, keyed by report_id)
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
async def compare_sync(
    body: CompareRequest = Body(...),
    response: Response = None,
    db: AsyncSession = Depends(get_db),
) -> ComparisonReport:
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
            left = await load_extraction_result(db, body.left_run_id)
        if not right:
            right = await load_extraction_result(db, body.right_run_id)
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
    _compare_jobs[report.id] = {"status": "completed", "report": report, "error": None}
    await persist_comparison_report(db, report)
    if response is not None:
        response.headers["X-Report-Id"] = report.id
    return report


@router.post("/async")
async def compare_async(
    body: CompareRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
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
            left = await load_extraction_result(db, body.left_run_id)
        if not right:
            right = await load_extraction_result(db, body.right_run_id)
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
            report_id=job_id,
        )
        _compare_jobs[job_id]["status"] = "completed"
        _compare_jobs[job_id]["report"] = report
        await persist_comparison_report(db, report)
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
async def get_compare_report(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> ComparisonReport:
    """Get comparison report for completed job."""
    if job_id in _compare_jobs:
        j = _compare_jobs[job_id]
        if j["status"] != "completed":
            raise HTTPException(status_code=202, detail=f"Job not completed: {j['status']}")
        if j.get("error"):
            raise HTTPException(status_code=500, detail=j["error"])
        return j["report"]
    report = await load_comparison_report(db, job_id)
    if report:
        return report
    raise HTTPException(status_code=404, detail="Job not found")


def _report_to_rows(report: ComparisonReport) -> list[dict]:
    """Flatten a ComparisonReport's diffs into CSV-friendly rows."""
    rows = []
    sections = {
        "metadata": report.metadata_diffs or [],
        "structure": report.structure_diffs or [],
        "content": report.content_diffs or [],
    }
    for section, diffs in sections.items():
        for d in diffs:
            rows.append({
                "section": section,
                "diff_type": d.diff_type or "",
                "path": d.path or "",
                "severity": d.severity or "",
                "left_value": str(d.left_value) if d.left_value is not None else "",
                "right_value": str(d.right_value) if d.right_value is not None else "",
                "confidence": d.confidence if d.confidence is not None else "",
            })
    return rows


def _rows_to_csv(rows: list[dict]) -> str:
    if not rows:
        return "section,diff_type,path,severity,left_value,right_value,confidence\r\n"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


@router.get("/jobs/{job_id}/report.csv")
async def get_compare_report_csv(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Download comparison report diffs as CSV."""
    report: ComparisonReport | None = None
    if job_id in _compare_jobs:
        j = _compare_jobs[job_id]
        if j["status"] != "completed":
            raise HTTPException(status_code=202, detail=f"Job not completed: {j['status']}")
        if j.get("error"):
            raise HTTPException(status_code=500, detail=j["error"])
        report = j["report"]
    if report is None:
        report = await load_comparison_report(db, job_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Job not found")
    csv_content = _rows_to_csv(_report_to_rows(report))
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="comparison_{job_id[:8]}.csv"'},
    )
