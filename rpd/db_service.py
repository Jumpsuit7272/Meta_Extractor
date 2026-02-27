"""DB persistence service: Pydantic ↔ ORM conversion."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rpd.db_models import (
    DBBlock,
    DBComparisonReport,
    DBContentMetadata,
    DBDiffItem,
    DBDocument,
    DBDocumentLink,
    DBEmbeddedMetadata,
    DBExtractionResult,
    DBPart,
    DBProvenance,
    DBRelationship,
    DBTechnicalMetadata,
)
from rpd.models import (
    Block,
    ComparisonReport,
    ConflictResolution,
    ContentMetadata,
    DiffItem,
    DocumentRoot,
    EmbeddedMetadata,
    ExtractionResult,
    Geometry,
    Part,
    Provenance,
    Relationship,
    SimilarityScores,
    TechnicalMetadata,
)

def _json_safe(v):
    """Recursively convert a value to something JSON-serializable (str fallback for unknown types)."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        return {k: _json_safe(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_json_safe(item) for item in v]
    return str(v)


# Known EmbeddedMetadata field names (by_alias=False)
_EMB_KNOWN = frozenset({
    "title", "author", "creator", "producer", "creation_date", "modified_date",
    "page_count", "exif", "last_modified_by", "revision",
    "from_addr", "to_addr", "cc", "bcc", "date", "subject", "message_id", "attachments",
})


async def persist_extraction_result(
    session: AsyncSession,
    result: ExtractionResult,
) -> None:
    """Persist a complete ExtractionResult to the database."""
    prov = result.provenance
    doc = result.document
    tech = doc.technical_metadata
    emb = doc.embedded_metadata
    content = doc.content_metadata

    session.add(DBProvenance(
        run_id=prov.run_id,
        extractor_version=prov.extractor_version,
        extractor_name=prov.extractor_name,
        source_uri=prov.source_uri,
        extraction_timestamp=prov.extraction_timestamp,
        settings=prov.settings,
    ))

    session.add(DBDocument(
        id=doc.id,
        confidence=doc.confidence,
    ))

    session.add(DBTechnicalMetadata(
        document_id=doc.id,
        file_name=tech.file_name,
        mime_type=tech.mime_type,
        extension=tech.extension,
        file_size_bytes=tech.file_size_bytes,
        hash_sha256=tech.hash_sha256,
        hash_md5=tech.hash_md5,
        created_at_ingested=tech.created_at_ingested,
        source_system=tech.source_system,
        source_uri=tech.source_uri,
        encryption_flag=tech.encryption_flag,
        password_protected_flag=tech.password_protected_flag,
        embedded_object_count=tech.embedded_object_count,
    ))

    if emb is not None:
        emb_dict = emb.model_dump(by_alias=False)
        extras = {k: v for k, v in emb_dict.items() if k not in _EMB_KNOWN}
        session.add(DBEmbeddedMetadata(
            document_id=doc.id,
            title=emb.title,
            author=emb.author,
            creator=emb.creator,
            producer=emb.producer,
            creation_date=emb.creation_date,
            modified_date=emb.modified_date,
            page_count=emb.page_count,
            exif=emb.exif,
            last_modified_by=emb.last_modified_by,
            revision=emb.revision,
            from_addr=emb.from_addr,
            to_addr=emb.to_addr,
            cc=emb.cc,
            bcc=emb.bcc,
            date=emb.date,
            subject=emb.subject,
            message_id=emb.message_id,
            attachments=emb.attachments,
            extras=extras or None,
        ))

    if content is not None:
        session.add(DBContentMetadata(
            document_id=doc.id,
            language=content.language,
            language_confidence=content.language_confidence,
            page_count=content.page_count,
            sheet_count=content.sheet_count,
            slide_count=content.slide_count,
            text_length=content.text_length,
            word_count=content.word_count,
            table_count=content.table_count,
            form_field_count=content.form_field_count,
            selection_count=content.selection_count,
            signature_count=content.signature_count,
            entity_counts=content.entity_counts,
        ))

    session.add(DBExtractionResult(run_id=prov.run_id, document_id=doc.id))

    for part in result.parts:
        session.add(DBPart(
            id=part.id,
            run_id=prov.run_id,
            part_type=part.part_type,
            index=part.index,
            metadata_=part.metadata,
            confidence=part.confidence,
            geometry=part.geometry.model_dump() if part.geometry else None,
            block_ids=part.block_ids,
        ))

    for block in result.blocks:
        session.add(DBBlock(
            id=block.id,
            run_id=prov.run_id,
            block_type=block.block_type,
            part_id=block.part_id,
            content=block.content,
            value=block.value,
            key=block.key,
            cells=block.cells,
            rows=block.rows,
            cols=block.cols,
            state=block.state,
            confidence=block.confidence,
            geometry=block.geometry.model_dump() if block.geometry else None,
            children=block.children,
        ))

    for rel in result.relationships:
        session.add(DBRelationship(
            run_id=prov.run_id,
            source_id=rel.source_id,
            target_id=rel.target_id,
            relation_type=rel.relation_type,
        ))

    await session.flush()


async def load_extraction_result(
    session: AsyncSession,
    run_id: str,
) -> ExtractionResult | None:
    """Reconstruct ExtractionResult from DB by run_id."""
    db_er = (await session.execute(
        select(DBExtractionResult).where(DBExtractionResult.run_id == run_id)
    )).scalar_one_or_none()
    if db_er is None:
        return None

    prov_row = await session.get(DBProvenance, run_id)
    doc_row = await session.get(DBDocument, db_er.document_id)
    tech_row = await session.get(DBTechnicalMetadata, db_er.document_id)
    emb_row = await session.get(DBEmbeddedMetadata, db_er.document_id)
    content_row = await session.get(DBContentMetadata, db_er.document_id)

    parts_rows = (await session.execute(
        select(DBPart).where(DBPart.run_id == run_id)
    )).scalars().all()
    blocks_rows = (await session.execute(
        select(DBBlock).where(DBBlock.run_id == run_id)
    )).scalars().all()
    rels_rows = (await session.execute(
        select(DBRelationship).where(DBRelationship.run_id == run_id)
    )).scalars().all()

    tech = TechnicalMetadata(
        file_name=tech_row.file_name,
        mime_type=tech_row.mime_type,
        extension=tech_row.extension,
        file_size_bytes=tech_row.file_size_bytes,
        hash_sha256=tech_row.hash_sha256,
        hash_md5=tech_row.hash_md5,
        created_at_ingested=tech_row.created_at_ingested,
        source_system=tech_row.source_system,
        source_uri=tech_row.source_uri,
        encryption_flag=tech_row.encryption_flag,
        password_protected_flag=tech_row.password_protected_flag,
        embedded_object_count=tech_row.embedded_object_count,
    )

    emb = None
    if emb_row:
        known = {
            "title": emb_row.title, "author": emb_row.author,
            "creator": emb_row.creator, "producer": emb_row.producer,
            "creation_date": emb_row.creation_date, "modified_date": emb_row.modified_date,
            "page_count": emb_row.page_count, "exif": emb_row.exif,
            "last_modified_by": emb_row.last_modified_by, "revision": emb_row.revision,
            "from": emb_row.from_addr,  # alias
            "to_addr": emb_row.to_addr, "cc": emb_row.cc, "bcc": emb_row.bcc,
            "date": emb_row.date, "subject": emb_row.subject,
            "message_id": emb_row.message_id, "attachments": emb_row.attachments,
        }
        extras = emb_row.extras or {}
        emb = EmbeddedMetadata(**{**known, **extras})

    content = None
    if content_row:
        content = ContentMetadata(
            language=content_row.language,
            language_confidence=content_row.language_confidence,
            page_count=content_row.page_count,
            sheet_count=content_row.sheet_count,
            slide_count=content_row.slide_count,
            text_length=content_row.text_length,
            word_count=content_row.word_count,
            table_count=content_row.table_count,
            form_field_count=content_row.form_field_count,
            selection_count=content_row.selection_count,
            signature_count=content_row.signature_count,
            entity_counts=content_row.entity_counts,
        )

    document = DocumentRoot(
        id=doc_row.id,
        technical_metadata=tech,
        embedded_metadata=emb,
        content_metadata=content,
        confidence=doc_row.confidence,
    )
    provenance = Provenance(
        run_id=prov_row.run_id,
        extractor_version=prov_row.extractor_version,
        extractor_name=prov_row.extractor_name,
        source_uri=prov_row.source_uri,
        extraction_timestamp=prov_row.extraction_timestamp,
        settings=prov_row.settings,
    )
    parts = [
        Part(
            id=r.id,
            part_type=r.part_type,
            index=r.index,
            metadata=r.metadata_,
            confidence=r.confidence,
            geometry=Geometry(**r.geometry) if r.geometry else None,
            blocks=r.block_ids or [],
        )
        for r in parts_rows
    ]
    blocks = [
        Block(
            id=r.id,
            block_type=r.block_type,
            part_id=r.part_id,
            content=r.content,
            value=r.value,
            key=r.key,
            cells=r.cells,
            rows=r.rows,
            cols=r.cols,
            state=r.state,
            confidence=r.confidence,
            geometry=Geometry(**r.geometry) if r.geometry else None,
            children=r.children,
        )
        for r in blocks_rows
    ]
    relationships = [
        Relationship(
            source_id=r.source_id,
            target_id=r.target_id,
            relation_type=r.relation_type,
        )
        for r in rels_rows
    ]
    return ExtractionResult(
        document=document,
        parts=parts,
        blocks=blocks,
        relationships=relationships,
        provenance=provenance,
    )


async def persist_comparison_report(
    session: AsyncSession,
    report: ComparisonReport,
) -> None:
    """Persist a ComparisonReport and all its diff items to the database."""
    scores = report.similarity_scores
    cr = report.conflict_resolution

    session.add(DBComparisonReport(
        id=report.id,
        status=report.status,
        similarity_document_level=scores.document_level if scores else 1.0,
        similarity_metadata=scores.metadata_similarity if scores else None,
        similarity_structure=scores.structure_similarity if scores else None,
        similarity_content=scores.content_similarity if scores else None,
        similarity_per_part=scores.per_part if scores else None,
        severity_summary=report.severity_summary,
        narrative_summary=report.narrative_summary,
        conflict_policy=cr.policy if cr else None,
        conflict_chosen_values=cr.chosen_values if cr else None,
        left_run_id=report.left_run_id,
        right_run_id=report.right_run_id,
        created_at=report.created_at,
    ))

    diff_map = {
        "metadata": report.metadata_diffs,
        "structure": report.structure_diffs,
        "content": report.content_diffs,
        "query_answer": report.query_answer_diffs,
    }
    for category, diffs in diff_map.items():
        for d in diffs:
            session.add(DBDiffItem(
                report_id=report.id,
                category=category,
                diff_type=d.diff_type,
                path=d.path,
                left_value=_json_safe(d.left_value),
                right_value=_json_safe(d.right_value),
                severity=d.severity,
                left_block_id=d.left_block_id,
                right_block_id=d.right_block_id,
                left_confidence=d.left_confidence,
                right_confidence=d.right_confidence,
                description=d.description,
            ))

    await session.flush()


async def load_comparison_report(
    session: AsyncSession,
    report_id: str,
) -> ComparisonReport | None:
    """Reconstruct ComparisonReport from DB by report_id."""
    db_report = await session.get(DBComparisonReport, report_id)
    if db_report is None:
        return None

    diffs_rows = (await session.execute(
        select(DBDiffItem).where(DBDiffItem.report_id == report_id)
    )).scalars().all()

    def _build_diffs(category: str) -> list[DiffItem]:
        return [
            DiffItem(
                diff_type=r.diff_type,
                path=r.path,
                left_value=r.left_value,
                right_value=r.right_value,
                severity=r.severity,
                left_block_id=r.left_block_id,
                right_block_id=r.right_block_id,
                left_confidence=r.left_confidence,
                right_confidence=r.right_confidence,
                description=r.description,
            )
            for r in diffs_rows if r.category == category
        ]

    scores = SimilarityScores(
        document_level=db_report.similarity_document_level,
        metadata_similarity=db_report.similarity_metadata,
        structure_similarity=db_report.similarity_structure,
        content_similarity=db_report.similarity_content,
        per_part=db_report.similarity_per_part or [],
    )
    cr = ConflictResolution(
        policy=db_report.conflict_policy or "",
        chosen_values=db_report.conflict_chosen_values or [],
    ) if db_report.conflict_policy else None

    return ComparisonReport(
        id=db_report.id,
        status=db_report.status,
        similarity_scores=scores,
        metadata_diffs=_build_diffs("metadata"),
        structure_diffs=_build_diffs("structure"),
        content_diffs=_build_diffs("content"),
        query_answer_diffs=_build_diffs("query_answer"),
        severity_summary=db_report.severity_summary,
        narrative_summary=db_report.narrative_summary,
        conflict_resolution=cr,
        left_run_id=db_report.left_run_id,
        right_run_id=db_report.right_run_id,
        created_at=db_report.created_at,
    )


async def list_extractions(session: AsyncSession) -> list[dict]:
    """Return lightweight summary of all past extractions, newest first."""
    stmt = (
        select(
            DBProvenance.run_id,
            DBProvenance.extraction_timestamp,
            DBTechnicalMetadata.file_name,
            DBTechnicalMetadata.mime_type,
            DBTechnicalMetadata.file_size_bytes,
            DBTechnicalMetadata.extension,
        )
        .join(DBExtractionResult, DBExtractionResult.run_id == DBProvenance.run_id)
        .join(DBTechnicalMetadata, DBTechnicalMetadata.document_id == DBExtractionResult.document_id)
        .order_by(DBProvenance.extraction_timestamp.desc())
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "run_id": r.run_id,
            "file_name": r.file_name,
            "mime_type": r.mime_type,
            "file_size_bytes": r.file_size_bytes,
            "extension": r.extension,
            "extraction_timestamp": r.extraction_timestamp.isoformat() if r.extraction_timestamp else None,
        }
        for r in rows
    ]


async def create_document_link(
    session: AsyncSession,
    source_run_id: str,
    target_run_id: str,
    label: str,
    comparison_report_id: str | None = None,
) -> DBDocumentLink:
    """Insert a document link and flush."""
    link = DBDocumentLink(
        source_run_id=source_run_id,
        target_run_id=target_run_id,
        label=label,
        comparison_report_id=comparison_report_id,
        created_at=datetime.utcnow(),
    )
    session.add(link)
    await session.flush()
    return link


async def list_document_links(session: AsyncSession) -> list[dict]:
    """Return all document links with file names for both sides, newest first."""
    src_tech = DBTechnicalMetadata.__table__.alias("src_tech")
    tgt_tech = DBTechnicalMetadata.__table__.alias("tgt_tech")
    src_er = DBExtractionResult.__table__.alias("src_er")
    tgt_er = DBExtractionResult.__table__.alias("tgt_er")

    stmt = (
        select(
            DBDocumentLink.id,
            DBDocumentLink.source_run_id,
            DBDocumentLink.target_run_id,
            DBDocumentLink.label,
            DBDocumentLink.comparison_report_id,
            DBDocumentLink.created_at,
            src_tech.c.file_name.label("source_file"),
            tgt_tech.c.file_name.label("target_file"),
        )
        .join(src_er, src_er.c.run_id == DBDocumentLink.source_run_id)
        .join(src_tech, src_tech.c.document_id == src_er.c.document_id)
        .join(tgt_er, tgt_er.c.run_id == DBDocumentLink.target_run_id)
        .join(tgt_tech, tgt_tech.c.document_id == tgt_er.c.document_id)
        .order_by(DBDocumentLink.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "source_run_id": r.source_run_id,
            "source_file": r.source_file,
            "target_run_id": r.target_run_id,
            "target_file": r.target_file,
            "label": r.label,
            "comparison_report_id": r.comparison_report_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
