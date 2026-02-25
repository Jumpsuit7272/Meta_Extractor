"""Pydantic models for extraction and comparison."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- Geometry ---
class Bounds(BaseModel):
    x: float
    y: float
    width: float
    height: float


class Geometry(BaseModel):
    type: str = "box"  # box | polygon
    bounds: Bounds | None = None
    points: list[dict[str, float]] | None = None


# --- Technical Metadata (FR-10) ---
class TechnicalMetadata(BaseModel):
    file_name: str
    mime_type: str
    extension: str = ""
    file_size_bytes: int
    hash_sha256: str
    hash_md5: str | None = None
    created_at_ingested: datetime = Field(default_factory=datetime.utcnow)
    source_system: str = ""
    source_uri: str | None = None
    encryption_flag: bool = False
    password_protected_flag: bool = False
    embedded_object_count: int | None = None


# --- Embedded Metadata (FR-11) ---
class EmbeddedMetadata(BaseModel):
    model_config = {"extra": "allow", "populate_by_name": True}
    title: str | None = None
    author: str | None = None
    creator: str | None = None
    producer: str | None = None
    creation_date: str | None = None
    modified_date: str | None = None
    page_count: int | None = None
    exif: dict[str, Any] | None = None
    # Office
    last_modified_by: str | None = None
    revision: str | None = None
    # Email
    from_addr: str | None = Field(None, alias="from")
    to_addr: str | None = None
    cc: str | None = None
    bcc: str | None = None
    date: str | None = None
    subject: str | None = None
    message_id: str | None = None
    attachments: list[dict] | None = None


# --- Content Metadata (FR-12) ---
class ContentMetadata(BaseModel):
    language: str | None = None
    language_confidence: float | None = None
    page_count: int | None = None
    sheet_count: int | None = None
    slide_count: int | None = None
    text_length: int = 0
    word_count: int = 0
    table_count: int = 0
    form_field_count: int = 0
    selection_count: int = 0
    signature_count: int = 0
    entity_counts: dict[str, int] | None = None


# --- Document Root ---
class DocumentRoot(BaseModel):
    id: str
    technical_metadata: TechnicalMetadata
    embedded_metadata: EmbeddedMetadata | None = None
    content_metadata: ContentMetadata | None = None
    confidence: float | None = None


# --- Part ---
class Part(BaseModel):
    id: str
    part_type: str  # page, sheet, slide, attachment, embedded
    index: int = 0
    metadata: dict[str, Any] | None = None
    block_ids: list[str] = Field(default_factory=list, alias="blocks")
    confidence: float | None = None
    geometry: Geometry | None = None


# --- Block ---
class Block(BaseModel):
    id: str
    block_type: str  # text, line, word, kv, table, cell, selection, signature
    part_id: str | None = None
    content: str | None = None
    value: Any = None
    key: str | None = None
    cells: list[list[Any]] | None = None
    rows: int | None = None
    cols: int | None = None
    state: str | None = None
    confidence: float | None = None
    geometry: Geometry | None = None
    children: list[str] | None = None


# --- Relationship ---
class Relationship(BaseModel):
    source_id: str
    target_id: str
    relation_type: str = "contains"  # contains, references, child_of, derived_from


# --- Provenance ---
class Provenance(BaseModel):
    run_id: str
    extractor_version: str
    extractor_name: str = "rpd-builtin"
    source_uri: str | None = None
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    settings: dict[str, Any] | None = None


# --- Extraction Result ---
class ExtractionResult(BaseModel):
    document: DocumentRoot
    parts: list[Part] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    provenance: Provenance

    model_config = {"json_schema_extra": {"$schema": "extraction_result"}}


# --- Comparison models ---
class DiffItem(BaseModel):
    diff_type: str  # added, removed, changed, conflict
    path: str = ""
    left_value: Any = None
    right_value: Any = None
    severity: str  # low, medium, high, critical
    left_block_id: str | None = None
    right_block_id: str | None = None
    left_confidence: float | None = None
    right_confidence: float | None = None
    description: str = ""


class SimilarityScores(BaseModel):
    document_level: float = 1.0
    metadata_similarity: float | None = None
    structure_similarity: float | None = None
    content_similarity: float | None = None
    per_part: list[dict[str, Any]] = Field(default_factory=list)


class ConflictResolution(BaseModel):
    policy: str = ""
    chosen_values: list[dict[str, Any]] = Field(default_factory=list)


class ComparisonReport(BaseModel):
    id: str
    status: str  # match, partial_match, conflict, incompatible
    similarity_scores: SimilarityScores | None = None
    metadata_diffs: list[DiffItem] = Field(default_factory=list)
    structure_diffs: list[DiffItem] = Field(default_factory=list)
    content_diffs: list[DiffItem] = Field(default_factory=list)
    query_answer_diffs: list[DiffItem] = Field(default_factory=list)
    severity_summary: dict[str, int] | None = None
    narrative_summary: str = ""
    conflict_resolution: ConflictResolution | None = None
    left_provenance: Provenance | None = None
    right_provenance: Provenance | None = None
    left_run_id: str | None = None
    right_run_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
