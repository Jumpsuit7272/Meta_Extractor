"""Orchestrates full extraction: identification, metadata, content (FR-30 canonical output)."""

import uuid
from datetime import datetime
from typing import Any

from rpd.models import (
    Block,
    ContentMetadata,
    DocumentRoot,
    EmbeddedMetadata,
    ExtractionResult,
    Part,
    Provenance,
    Relationship,
    TechnicalMetadata,
)
from rpd.services.content_extractor import (
    extract_archive_children,
    extract_docx_content,
    extract_eml_content,
    extract_image_ocr,
    extract_msg_content,
    extract_pdf_content,
    extract_pdf_form_info,
    extract_xlsx_content,
)
from rpd.services.file_identifier import identify_file
from rpd.services.metadata_extractor import extract_content_metadata, extract_embedded_metadata


def run_extraction(
    data: bytes,
    filename: str = "",
    source_uri: str | None = None,
    run_id: str | None = None,
    extractor_name: str = "rpd-builtin",
    extractor_version: str = "0.1.0",
    source_system: str = "",
    ocr_enabled: bool = True,
    geolocation_lookup: bool | None = None,  # None = use settings
) -> ExtractionResult:
    """
    Full extraction pipeline: identify, extract metadata, extract content.
    Produces canonical ExtractionResult.
    """
    run_id = run_id or str(uuid.uuid4())
    now = datetime.utcnow()

    # 1. Identification (FR-01, FR-02, FR-03)
    ident = identify_file(data, filename, source_uri)
    doc_id = ident["hash_sha256"][:16] + "_" + str(uuid.uuid4())[:8]

    technical = TechnicalMetadata(
        file_name=ident["file_name"],
        mime_type=ident["mime_type"],
        extension=ident["extension"],
        file_size_bytes=ident["file_size_bytes"],
        hash_sha256=ident["hash_sha256"],
        hash_md5=ident.get("hash_md5"),
        created_at_ingested=now,
        source_system=source_system,
        source_uri=source_uri,
    )

    # 2. Embedded metadata (FR-11) - includes GPS/geolocation for images
    embedded = extract_embedded_metadata(
        data, ident["mime_type"], ident["extension"],
        geolocation_lookup=geolocation_lookup,
    )

    # 3. Content extraction (FR-20 to FR-23)
    mime = ident["mime_type"]
    ext = ident["extension"]
    parts: list[Part] = []
    blocks: list[Block] = []
    full_text = ""
    table_count = 0

    if "pdf" in mime:
        parts, blocks, full_text, table_count = extract_pdf_content(data)
    elif mime.startswith("image/"):
        if ocr_enabled:
            parts, blocks, full_text = extract_image_ocr(data, mime)
        else:
            parts = [Part(id="p_0", part_type="page", index=0)]
    elif "wordprocessingml" in mime or "msword" in mime:
        parts, blocks, full_text, table_count = extract_docx_content(data)
    elif "spreadsheetml" in mime or "ms-excel" in mime:
        parts, blocks, full_text, table_count = extract_xlsx_content(data)
    elif "presentationml" in mime:
        parts = [Part(id="p_0", part_type="slide", index=0)]
    elif "rfc822" in mime or ext == ".eml":
        parts, blocks, full_text = extract_eml_content(data)
    elif "outlook" in mime or ext == ".msg":
        parts, blocks, full_text = extract_msg_content(data)
    elif "text/plain" in mime or (mime == "application/octet-stream" and ext in (".txt",)):
        try:
            full_text = data.decode("utf-8", errors="replace")
        except Exception:
            full_text = ""
        if full_text:
            pid = f"p_{uuid.uuid4().hex[:8]}"
            parts = [Part(id=pid, part_type="page", index=0)]
            blocks = [Block(id=f"b_{uuid.uuid4().hex[:12]}", part_id=pid, block_type="text", content=full_text)]
    elif "zip" in mime:
        children = extract_archive_children(data)
        for i, ch in enumerate(children):
            parts.append(Part(id=f"att_{i}", part_type="attachment", index=i, metadata={"name": ch["name"]}))
        full_text = " ".join(c["name"] for c in children)

    # 4. Content metadata (FR-12)
    content_meta = extract_content_metadata(full_text, len(parts), table_count)
    if embedded and embedded.page_count is not None:
        content_meta.page_count = embedded.page_count
    if "pdf" in mime:
        content_meta.form_field_count, content_meta.signature_count = extract_pdf_form_info(data)

    # 5. Link blocks to parts
    relationships: list[Relationship] = []
    for b in blocks:
        if b.part_id:
            relationships.append(Relationship(source_id=b.part_id, target_id=b.id, relation_type="contains"))

    provenance = Provenance(
        run_id=run_id,
        extractor_version=extractor_version,
        extractor_name=extractor_name,
        source_uri=source_uri,
        extraction_timestamp=now,
    )

    document = DocumentRoot(
        id=doc_id,
        technical_metadata=technical,
        embedded_metadata=embedded,
        content_metadata=content_meta,
        confidence=0.9,
    )

    return ExtractionResult(
        document=document,
        parts=parts,
        blocks=blocks,
        relationships=relationships,
        provenance=provenance,
    )
