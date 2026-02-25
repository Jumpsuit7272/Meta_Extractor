"""Universal metadata extraction: technical, embedded, content (FR-10, FR-11, FR-12)."""

from datetime import datetime
from pathlib import Path
from typing import Any

from rpd.models import ContentMetadata, EmbeddedMetadata, TechnicalMetadata
from rpd.services.file_identifier import identify_file


def _extract_pdf_embedded(data: bytes) -> dict[str, Any]:
    """Extract embedded metadata from PDF."""
    try:
        from PyPDF2 import PdfReader
        from io import BytesIO
        reader = PdfReader(BytesIO(data))
        meta = reader.metadata
        if not meta:
            return {}
        info = {}
        if meta.get("/Title"):
            info["title"] = meta["/Title"]
        if meta.get("/Author"):
            info["author"] = meta["/Author"]
        if meta.get("/Creator"):
            info["creator"] = meta["/Creator"]
        if meta.get("/Producer"):
            info["producer"] = meta["/Producer"]
        if meta.get("/CreationDate"):
            info["creation_date"] = str(meta["/CreationDate"])
        if meta.get("/ModDate"):
            info["modified_date"] = str(meta["/ModDate"])
        info["page_count"] = len(reader.pages)
        return info
    except Exception:
        return {}


def _extract_image_embedded(
    data: bytes, mime: str, *, geolocation_lookup: bool | None = None
) -> dict[str, Any]:
    """Extract EXIF and other embedded metadata from images, including GPS geolocation."""
    try:
        from PIL import Image
        from io import BytesIO

        img = Image.open(BytesIO(data))
        info: dict[str, Any] = {}
        exif_data = img.getexif()
        if exif_data:
            info["exif"] = {str(k): str(v) for k, v in exif_data.items() if v is not None}
        if hasattr(img, "info") and img.info and "icc_profile" in img.info:
            info["icc_profile"] = "present"

        # GPS extraction and reverse geocoding
        from rpd.services.geolocation import extract_image_geolocation

        geo = extract_image_geolocation(data, geolocation_lookup=geolocation_lookup)
        info.update(geo)
        return info
    except Exception:
        return {}


def _extract_office_embedded(data: bytes, mime: str, ext: str) -> dict[str, Any]:
    """Extract embedded metadata from Office (OOXML) files."""
    try:
        from zipfile import ZipFile
        from xml.etree import ElementTree as ET
        from io import BytesIO
        z = ZipFile(BytesIO(data), "r")
        info: dict[str, Any] = {}
        core_path = "docProps/core.xml"
        app_path = "docProps/app.xml"
        if core_path in z.namelist():
            core = ET.fromstring(z.read(core_path))
            ns = {"dc": "http://purl.org/dc/elements/1.1/", "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
                  "dcterms": "http://purl.org/dc/terms/"}
            for child in core:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if child.text and tag in ("creator", "lastModifiedBy", "created", "modified", "revision"):
                    info[tag.replace("lastModifiedBy", "last_modified_by")] = child.text
        return info
    except Exception:
        return {}


def _extract_email_embedded(data: bytes, mime: str, ext: str) -> dict[str, Any]:
    """Extract embedded metadata from EML/MSG."""
    info: dict[str, Any] = {}
    try:
        if ext.lower() == ".msg":
            import extract_msg
            msg = extract_msg.Message(data)
            info["from_addr"] = msg.sender
            info["to_addr"] = msg.to
            info["cc"] = msg.cc
            info["bcc"] = msg.bcc
            info["date"] = str(msg.date) if msg.date else None
            info["subject"] = msg.subject
            info["message_id"] = msg.messageId
            info["attachments"] = [{"name": a.longFilename, "size": a.size} for a in msg.attachments] if msg.attachments else []
            msg.close()
        else:
            # EML: parse headers
            text = data.decode("utf-8", errors="replace")
            for line in text.split("\n")[:50]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k == "from":
                        info["from_addr"] = v
                    elif k == "to":
                        info["to_addr"] = v
                    elif k == "cc":
                        info["cc"] = v
                    elif k == "bcc":
                        info["bcc"] = v
                    elif k == "date":
                        info["date"] = v
                    elif k == "subject":
                        info["subject"] = v
                    elif k == "message-id":
                        info["message_id"] = v
    except Exception:
        pass
    return info


def _extract_archive_embedded(data: bytes) -> dict[str, Any]:
    """Extract manifest from ZIP archives."""
    try:
        from zipfile import ZipFile
        from io import BytesIO
        z = ZipFile(BytesIO(data), "r")
        manifest = []
        for zi in z.infolist():
            manifest.append({"name": zi.filename, "size": zi.file_size, "compress_size": zi.compress_size})
        return {"manifest": manifest}
    except Exception:
        return {}


def extract_embedded_metadata(
    data: bytes, mime: str, ext: str, *, geolocation_lookup: bool | None = None
) -> EmbeddedMetadata | None:
    """Extract type-specific embedded metadata."""
    info: dict[str, Any] = {}

    if "pdf" in mime:
        info = _extract_pdf_embedded(data)
    elif mime.startswith("image/"):
        info = _extract_image_embedded(data, mime, geolocation_lookup=geolocation_lookup)
    elif "openxmlformats" in mime or "ms-office" in mime:
        info = _extract_office_embedded(data, mime, ext)
    elif "rfc822" in mime or "outlook" in mime or ext in (".eml", ".msg"):
        info = _extract_email_embedded(data, mime, ext)
    elif "zip" in mime:
        info = _extract_archive_embedded(data)

    if not info:
        return None
    return EmbeddedMetadata(**{k: v for k, v in info.items() if v is not None})


def extract_content_metadata(text: str, parts_count: int = 0, table_count: int = 0) -> ContentMetadata:
    """Derive content metadata from extracted text and structure."""
    words = text.split() if text else []
    word_count = len(words)
    text_length = len(text) if text else 0

    return ContentMetadata(
        language=None,
        language_confidence=None,
        page_count=parts_count if parts_count else None,
        text_length=text_length,
        word_count=word_count,
        table_count=table_count,
    )
