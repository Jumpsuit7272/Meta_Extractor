"""History browser and document link endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from rpd.database import get_db
from rpd.db_service import (
    create_document_link,
    list_document_links,
    list_extractions,
    load_comparison_report,
    load_extraction_result,
    persist_comparison_report,
)
from rpd.models import ComparisonReport
from rpd.services.comparison_engine import compare

router = APIRouter(tags=["links"])


class CreateLinkRequest(BaseModel):
    source_run_id: str
    target_run_id: str
    label: str = "related"


@router.get("/history")
async def get_history(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Return all past extractions as a lightweight summary list, newest first."""
    return await list_extractions(db)


@router.post("/links")
async def create_link(
    body: CreateLinkRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Create a named link between two extraction records and run a comparison.
    Returns the new link id and the full ComparisonReport.
    """
    if body.source_run_id == body.target_run_id:
        raise HTTPException(status_code=400, detail="source_run_id and target_run_id must differ")

    source = await load_extraction_result(db, body.source_run_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Extraction not found: {body.source_run_id}")

    target = await load_extraction_result(db, body.target_run_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Extraction not found: {body.target_run_id}")

    report: ComparisonReport = compare(left=source, right=target)
    await persist_comparison_report(db, report)

    link = await create_document_link(
        db,
        source_run_id=body.source_run_id,
        target_run_id=body.target_run_id,
        label=body.label,
        comparison_report_id=report.id,
    )

    return {
        "link_id": link.id,
        "source_run_id": body.source_run_id,
        "target_run_id": body.target_run_id,
        "label": body.label,
        "comparison_report": report.model_dump(),
    }


@router.get("/links")
async def get_links(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Return all document links with file names and comparison status."""
    return await list_document_links(db)


@router.get("/links/{link_id}")
async def get_link(
    link_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a single document link with its full comparison report."""
    from rpd.db_models import DBDocumentLink
    link = await db.get(DBDocumentLink, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    report = None
    if link.comparison_report_id:
        r = await load_comparison_report(db, link.comparison_report_id)
        report = r.model_dump() if r else None

    return {
        "link_id": link.id,
        "source_run_id": link.source_run_id,
        "target_run_id": link.target_run_id,
        "label": link.label,
        "comparison_report_id": link.comparison_report_id,
        "created_at": link.created_at.isoformat() if link.created_at else None,
        "comparison_report": report,
    }
