"""SQLAlchemy 2.0 ORM models (SQLite-adapted from schema.sql)."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from rpd.database import Base


# ── Provenance ───────────────────────────────────────────────────────────────

class DBProvenance(Base):
    __tablename__ = "provenance"

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    extractor_version: Mapped[str] = mapped_column(Text, nullable=False)
    extractor_name: Mapped[str] = mapped_column(Text, nullable=False, default="rpd-builtin")
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    extraction_result: Mapped["DBExtractionResult | None"] = relationship(
        back_populates="provenance", uselist=False, cascade="all, delete-orphan"
    )


# ── Document ─────────────────────────────────────────────────────────────────

class DBDocument(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    technical_metadata: Mapped["DBTechnicalMetadata | None"] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    embedded_metadata: Mapped["DBEmbeddedMetadata | None"] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    content_metadata: Mapped["DBContentMetadata | None"] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    extraction_result: Mapped["DBExtractionResult | None"] = relationship(
        back_populates="document", uselist=False
    )


# ── Technical Metadata ───────────────────────────────────────────────────────

class DBTechnicalMetadata(Base):
    __tablename__ = "technical_metadata"

    document_id: Mapped[str] = mapped_column(
        Text, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    extension: Mapped[str] = mapped_column(Text, nullable=False, default="")
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hash_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    hash_md5: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_ingested: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source_system: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    encryption_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    password_protected_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    embedded_object_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    document: Mapped[DBDocument] = relationship(back_populates="technical_metadata")


# ── Embedded Metadata ────────────────────────────────────────────────────────

class DBEmbeddedMetadata(Base):
    __tablename__ = "embedded_metadata"

    document_id: Mapped[str] = mapped_column(
        Text, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    creator: Mapped[str | None] = mapped_column(Text, nullable=True)
    producer: Mapped[str | None] = mapped_column(Text, nullable=True)
    creation_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    modified_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exif: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_modified_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_addr: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_addr: Mapped[str | None] = mapped_column(Text, nullable=True)
    cc: Mapped[str | None] = mapped_column(Text, nullable=True)
    bcc: Mapped[str | None] = mapped_column(Text, nullable=True)
    date: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[list | None] = mapped_column(JSON, nullable=True)
    extras: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    document: Mapped[DBDocument] = relationship(back_populates="embedded_metadata")


# ── Content Metadata ─────────────────────────────────────────────────────────

class DBContentMetadata(Base):
    __tablename__ = "content_metadata"

    document_id: Mapped[str] = mapped_column(
        Text, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sheet_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slide_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    table_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    form_field_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signature_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    entity_counts: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    document: Mapped[DBDocument] = relationship(back_populates="content_metadata")


# ── Extraction Result ────────────────────────────────────────────────────────

class DBExtractionResult(Base):
    __tablename__ = "extraction_results"

    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("provenance.run_id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[str] = mapped_column(
        Text, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    provenance: Mapped[DBProvenance] = relationship(back_populates="extraction_result")
    document: Mapped[DBDocument] = relationship(back_populates="extraction_result")
    parts: Mapped[list["DBPart"]] = relationship(
        back_populates="extraction_result", cascade="all, delete-orphan"
    )
    blocks: Mapped[list["DBBlock"]] = relationship(
        back_populates="extraction_result", cascade="all, delete-orphan"
    )
    relationships: Mapped[list["DBRelationship"]] = relationship(
        back_populates="extraction_result", cascade="all, delete-orphan"
    )


# ── Parts ────────────────────────────────────────────────────────────────────

class DBPart(Base):
    __tablename__ = "parts"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("extraction_results.run_id", ondelete="CASCADE"), nullable=False
    )
    part_type: Mapped[str] = mapped_column(Text, nullable=False)
    index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    block_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)

    extraction_result: Mapped[DBExtractionResult] = relationship(back_populates="parts")


# ── Blocks ───────────────────────────────────────────────────────────────────

class DBBlock(Base):
    __tablename__ = "blocks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("extraction_results.run_id", ondelete="CASCADE"), nullable=False
    )
    block_type: Mapped[str] = mapped_column(Text, nullable=False)
    part_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("parts.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=True)
    key: Mapped[str | None] = mapped_column(Text, nullable=True)
    cells: Mapped[list | None] = mapped_column(JSON, nullable=True)
    rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cols: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    children: Mapped[list | None] = mapped_column(JSON, nullable=True)

    extraction_result: Mapped[DBExtractionResult] = relationship(back_populates="blocks")


# ── Relationships ────────────────────────────────────────────────────────────

class DBRelationship(Base):
    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("extraction_results.run_id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    relation_type: Mapped[str] = mapped_column(Text, nullable=False, default="contains")

    extraction_result: Mapped[DBExtractionResult] = relationship(back_populates="relationships")


# ── Comparison Report ────────────────────────────────────────────────────────

class DBComparisonReport(Base):
    __tablename__ = "comparison_reports"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    similarity_document_level: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    similarity_metadata: Mapped[float | None] = mapped_column(Float, nullable=True)
    similarity_structure: Mapped[float | None] = mapped_column(Float, nullable=True)
    similarity_content: Mapped[float | None] = mapped_column(Float, nullable=True)
    similarity_per_part: Mapped[list | None] = mapped_column(JSON, nullable=True)
    severity_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    narrative_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conflict_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflict_chosen_values: Mapped[list | None] = mapped_column(JSON, nullable=True)
    left_run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("provenance.run_id"), nullable=True
    )
    right_run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("provenance.run_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    diff_items: Mapped[list["DBDiffItem"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


# ── Diff Items ───────────────────────────────────────────────────────────────

class DBDiffItem(Base):
    __tablename__ = "diff_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(
        Text, ForeignKey("comparison_reports.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    diff_type: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    left_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    right_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    left_block_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    right_block_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    left_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    report: Mapped[DBComparisonReport] = relationship(back_populates="diff_items")
