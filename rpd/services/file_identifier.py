"""File identification, type detection, and integrity (FR-01, FR-02, FR-03)."""

import hashlib
import re
from pathlib import Path
from typing import BinaryIO

import filetype


# Magic bytes for container formats not always detected by filetype
SIGNATURES: dict[bytes, tuple[str, str]] = {
    b"PK\x03\x04": ("application/zip", ".zip"),
    b"PK\x05\x06": ("application/zip", ".zip"),
    b"%PDF": ("application/pdf", ".pdf"),
    b"\xd0\xcf\x11\xe0": ("application/vnd.ms-office", ".doc"),  # OLE/Office
    b"\xff\xd8\xff": ("image/jpeg", ".jpg"),
    b"\x89PNG": ("image/png", ".png"),
    b"GIF87a": ("image/gif", ".gif"),
    b"GIF89a": ("image/gif", ".gif"),
    b"RIFF": ("image/webp", ".webp"),  # Can also be WAV
    b"MM\x00\x2a": ("image/tiff", ".tiff"),
    b"II\x2a\x00": ("image/tiff", ".tiff"),
    b"From ": ("message/rfc822", ".eml"),  # EML
}

# OOXML (DOCX, XLSX, PPTX) - ZIP with specific structure
OOXML_MIMES = {
    "word/document.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xl/workbook.xml": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt/presentation.xml": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

EXT_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".eml": "message/rfc822",
    ".msg": "application/vnd.ms-outlook",
    ".zip": "application/zip",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}


def _read_head(data: bytes, n: int = 16) -> bytes:
    return data[:n] if len(data) >= n else data


def detect_mime_and_extension(data: bytes, filename: str = "") -> tuple[str, str]:
    """Detect MIME type and extension via signature (magic bytes)."""
    head = _read_head(data, 32)

    # Check known signatures (longest first for specificity)
    for sig, (mime, ext) in sorted(SIGNATURES.items(), key=lambda x: -len(x[0])):
        if head.startswith(sig):
            # OOXML: ZIP containing Office docs
            if mime == "application/zip" and filename:
                ext_lower = Path(filename).suffix.lower()
                if ext_lower in (".docx", ".xlsx", ".pptx"):
                    mime = EXT_TO_MIME.get(ext_lower, mime)
                    ext = ext_lower
            return mime, ext

    # Fallback to filetype library
    kind = filetype.guess(data)
    if kind:
        return kind.mime, f".{kind.extension}"

    # Fallback to extension
    if filename:
        ext = Path(filename).suffix.lower()
        if ext in EXT_TO_MIME:
            return EXT_TO_MIME[ext], ext

    return "application/octet-stream", ""


def compute_hashes(data: bytes) -> tuple[str, str | None]:
    """Compute SHA-256 (required) and MD5 (optional)."""
    sha256 = hashlib.sha256(data).hexdigest()
    md5 = hashlib.md5(data).hexdigest()
    return sha256, md5


def validate_eml_header(data: bytes) -> bool:
    """Check if data starts with EML-like header."""
    try:
        text = data[:500].decode("utf-8", errors="ignore")
        return text.startswith("From ") or "Content-Type:" in text or "Subject:" in text
    except Exception:
        return False


def identify_file(data: bytes, filename: str = "", source_uri: str | None = None) -> dict:
    """
    Identify file: type, MIME, extension, size, hashes.
    Returns dict for use in TechnicalMetadata.
    """
    mime, ext = detect_mime_and_extension(data, filename)
    sha256, md5 = compute_hashes(data)
    size = len(data)

    # EML heuristic: often starts with "From "
    if not ext and validate_eml_header(data):
        mime, ext = "message/rfc822", ".eml"

    name = Path(filename).name if filename else f"unknown{ext}"

    return {
        "file_name": name,
        "mime_type": mime,
        "extension": ext,
        "file_size_bytes": size,
        "hash_sha256": sha256,
        "hash_md5": md5,
    }
