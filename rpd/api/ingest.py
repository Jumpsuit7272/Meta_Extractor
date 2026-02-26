"""Ingestion: file bytes or storage URI (FR-01)."""

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from rpd.api.extraction import _results_by_run
from rpd.database import get_db
from rpd.db_service import persist_extraction_result
from rpd.models import ExtractionResult
from rpd.services.extraction_pipeline import run_extraction

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/uri")
async def ingest_by_uri(
    source_uri: str = Body(..., embed=True),
    source_system: str = Body("", embed=True),
    run_id: str | None = Body(None, embed=True),
    ocr_enabled: bool = Body(True, embed=True),
    db: AsyncSession = Depends(get_db),
) -> ExtractionResult:
    """
    Ingest file from storage URI (http/https or s3). Returns ExtractionResult.
    """
    if source_uri.startswith("http://") or source_uri.startswith("https://"):
        async with httpx.AsyncClient() as client:
            resp = await client.get(source_uri)
            resp.raise_for_status()
            data = resp.content
        filename = source_uri.split("/")[-1].split("?")[0] or "unknown"
    elif source_uri.startswith("s3://"):
        try:
            import boto3
            from urllib.parse import urlparse
            parsed = urlparse(source_uri)
            bucket = parsed.netloc
            key = parsed.path.lstrip("/")
            s3 = boto3.client("s3")
            obj = s3.get_object(Bucket=bucket, Key=key)
            data = obj["Body"].read()
            filename = key.split("/")[-1]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"S3 fetch failed: {e}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported URI scheme. Use http/https or s3://")

    result = run_extraction(
        data=data,
        filename=filename,
        source_uri=source_uri,
        run_id=run_id,
        source_system=source_system,
        ocr_enabled=ocr_enabled,
    )
    _results_by_run[result.provenance.run_id] = result
    await persist_extraction_result(db, result)
    return result
