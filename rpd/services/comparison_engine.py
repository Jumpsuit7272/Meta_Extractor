"""Comparison engine: alignment, normalization, diffs (FR-40 to FR-61)."""

import json
import re
import uuid
from datetime import datetime
from typing import Any

from rpd.models import ComparisonReport, DiffItem, ExtractionResult, Provenance, SimilarityScores


def _normalize(value: Any, normalize_dates: bool = True, normalize_currency: bool = True) -> Any:
    """Normalize values for comparison."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    s = str(value).strip().lower()
    # Whitespace
    s = re.sub(r"\s+", " ", s)
    # Dates -> ISO-like
    if normalize_dates and re.search(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", s):
        s = re.sub(r"(\d{1,4})[-/](\d{1,2})[-/](\d{1,4})", r"\1-\2-\3", s)
    # Currency
    if normalize_currency:
        s = re.sub(r"[$€£]\s*", "", s)
        s = re.sub(r",(?=\d{3})", "", s)
    return s


def _get_nested(obj: dict, path: str) -> Any:
    """Get value at JSON path like 'embedded_metadata.creator'."""
    parts = path.replace("]", "").split(".")
    cur = obj
    for p in parts:
        if p.isdigit():
            cur = cur[int(p)] if isinstance(cur, list) else None
        else:
            cur = cur.get(p) if isinstance(cur, dict) else None
        if cur is None:
            break
    return cur


def _metadata_diffs(
    left: ExtractionResult,
    right: ExtractionResult,
    normalize: bool = True,
) -> list[DiffItem]:
    """Compare technical and embedded metadata (FR-40)."""
    diffs: list[DiffItem] = []
    left_doc = left.document.model_dump()
    right_doc = right.document.model_dump()

    def collect_fields(d: dict, prefix: str = "") -> dict[str, Any]:
        out = {}
        for k, v in d.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict) and not any(x in str(v) for x in ["x", "y", "width", "height"]):
                out.update(collect_fields(v, path))
            elif v is not None:
                out[path] = v
        return out

    left_flat = collect_fields(left_doc)
    right_flat = collect_fields(right_doc)

    all_keys = set(left_flat) | set(right_flat)
    for key in all_keys:
        lv = left_flat.get(key)
        rv = right_flat.get(key)
        if lv is None and rv is not None:
            diffs.append(DiffItem(diff_type="added", path=key, right_value=rv, severity="low"))
        elif lv is not None and rv is None:
            diffs.append(DiffItem(diff_type="removed", path=key, left_value=lv, severity="low"))
        elif lv != rv:
            ln = _normalize(lv) if normalize else lv
            rn = _normalize(rv) if normalize else rv
            if ln != rn:
                sev = "high" if "creator" in key or "producer" in key or "modified" in key or "hash" in key else "medium"
                diffs.append(DiffItem(diff_type="changed", path=key, left_value=lv, right_value=rv, severity=sev))

    return diffs


def _structure_diffs(left: ExtractionResult, right: ExtractionResult) -> list[DiffItem]:
    """Compare derived structure (FR-41)."""
    diffs: list[DiffItem] = []
    lc = left.document.content_metadata
    rc = right.document.content_metadata

    def _get(obj: Any, name: str, default: int = 0) -> int:
        if obj is None:
            return default
        return getattr(obj, name, default) or default

    def check(name: str, lv: Any, rv: Any, severity: str = "high"):
        if lv != rv:
            diffs.append(DiffItem(diff_type="changed", path=f"content_metadata.{name}", left_value=lv, right_value=rv, severity=severity))

    check("page_count", _get(lc, "page_count"), _get(rc, "page_count"))
    check("table_count", _get(lc, "table_count"), _get(rc, "table_count"))
    check("form_field_count", _get(lc, "form_field_count"), _get(rc, "form_field_count"), "medium")
    check("signature_count", _get(lc, "signature_count"), _get(rc, "signature_count"))

    if len(left.parts) != len(right.parts):
        diffs.append(DiffItem(
            diff_type="changed",
            path="parts.length",
            left_value=len(left.parts),
            right_value=len(right.parts),
            severity="high",
        ))
    return diffs


def _text_similarity(a: str, b: str) -> float:
    """Simple Jaccard-like text similarity."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    aa = set(a.lower().split())
    bb = set(b.lower().split())
    inter = len(aa & bb)
    union = len(aa | bb) or 1
    return inter / union


def _content_diffs(
    left: ExtractionResult,
    right: ExtractionResult,
    normalize: bool = True,
) -> list[DiffItem]:
    """Compare extracted text and structured content (FR-42)."""
    diffs: list[DiffItem] = []

    # Document-level text
    l_text = " ".join(b.content or "" for b in left.blocks if b.content)
    r_text = " ".join(b.content or "" for b in right.blocks if b.content)
    sim = _text_similarity(l_text, r_text)
    if sim < 0.95:
        diffs.append(DiffItem(
            diff_type="changed",
            path="blocks.text",
            description=f"Text similarity: {sim:.2f}",
            severity="medium" if sim > 0.8 else "high",
        ))

    # KV comparison: blocks with key+value
    l_kv = {(b.key or "").lower(): b.value or b.content for b in left.blocks if b.block_type == "kv" and b.key}
    r_kv = {(b.key or "").lower(): b.value or b.content for b in right.blocks if b.block_type == "kv" and b.key}
    for k in set(l_kv) | set(r_kv):
        lv = l_kv.get(k)
        rv = r_kv.get(k)
        if lv is None:
            diffs.append(DiffItem(diff_type="added", path=f"kv.{k}", right_value=rv, severity="medium"))
        elif rv is None:
            diffs.append(DiffItem(diff_type="removed", path=f"kv.{k}", left_value=lv, severity="medium"))
        else:
            ln = _normalize(lv) if normalize else lv
            rn = _normalize(rv) if normalize else rv
            if ln != rn:
                diffs.append(DiffItem(diff_type="changed", path=f"kv.{k}", left_value=lv, right_value=rv, severity="high"))

    # Table count drift
    l_tables = [b for b in left.blocks if b.block_type == "table"]
    r_tables = [b for b in right.blocks if b.block_type == "table"]
    if len(l_tables) != len(r_tables):
        diffs.append(DiffItem(
            diff_type="changed",
            path="blocks.table_count",
            left_value=len(l_tables),
            right_value=len(r_tables),
            severity="high",
        ))

    return diffs


def _compute_status(diffs: list[DiffItem], threshold: float) -> str:
    """Determine overall status from diffs and similarity."""
    critical = sum(1 for d in diffs if d.severity == "critical")
    high = sum(1 for d in diffs if d.severity == "high")
    if critical > 0:
        return "conflict"
    if high > 2:
        return "partial_match"
    if high > 0 or any(d.severity == "medium" for d in diffs):
        return "partial_match"
    return "match"


def _severity_summary(diffs: list[DiffItem]) -> dict[str, int]:
    s = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for d in diffs:
        if d.severity in s:
            s[d.severity] += 1
    return s


def _narrative(diffs: list[DiffItem]) -> str:
    """Generate machine-readable summary of changes."""
    parts = []
    for d in diffs[:10]:
        if d.diff_type == "added":
            parts.append(f"Added: {d.path}")
        elif d.diff_type == "removed":
            parts.append(f"Removed: {d.path}")
        else:
            parts.append(f"Changed: {d.path}")
    if len(diffs) > 10:
        parts.append(f"... and {len(diffs) - 10} more")
    return "; ".join(parts) if parts else "No significant differences"


def compare(
    left: ExtractionResult,
    right: ExtractionResult,
    normalization_rules: dict[str, bool] | None = None,
    similarity_threshold: float = 0.95,
    document_type: str | None = None,
    report_id: str | None = None,
) -> ComparisonReport:
    """
    Compare two extraction results (FR-40 to FR-61).
    Returns canonical ComparisonReport.
    """
    norms = normalization_rules or {"dates": True, "currency": True}
    normalize = norms.get("dates", True) or norms.get("currency", True)

    metadata_diffs = _metadata_diffs(left, right, normalize)
    structure_diffs = _structure_diffs(left, right)
    content_diffs = _content_diffs(left, right, normalize)

    all_diffs = metadata_diffs + structure_diffs + content_diffs
    severity_summary = _severity_summary(all_diffs)
    status = _compute_status(all_diffs, similarity_threshold)

    l_text = " ".join(b.content or "" for b in left.blocks if b.content)
    r_text = " ".join(b.content or "" for b in right.blocks if b.content)
    doc_sim = _text_similarity(l_text, r_text)

    scores = SimilarityScores(
        document_level=doc_sim,
        metadata_similarity=max(0.0, 1.0 - len(metadata_diffs) / 20) if metadata_diffs else 1.0,
        structure_similarity=max(0.0, 1.0 - len(structure_diffs) / 5) if structure_diffs else 1.0,
        content_similarity=doc_sim,
    )

    return ComparisonReport(
        id=report_id or str(uuid.uuid4()),
        status=status,
        similarity_scores=scores,
        metadata_diffs=metadata_diffs,
        structure_diffs=structure_diffs,
        content_diffs=content_diffs,
        severity_summary=severity_summary,
        narrative_summary=_narrative(all_diffs),
        left_provenance=left.provenance,
        right_provenance=right.provenance,
        left_run_id=left.provenance.run_id,
        right_run_id=right.provenance.run_id,
        created_at=datetime.utcnow(),
    )
