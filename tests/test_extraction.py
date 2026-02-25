"""Tests for extraction pipeline."""

import pytest
from rpd.services.file_identifier import identify_file, compute_hashes
from rpd.services.extraction_pipeline import run_extraction


def test_identify_pdf():
    pdf_header = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n"
    ident = identify_file(pdf_header, "test.pdf")
    assert ident["mime_type"] == "application/pdf"
    assert ident["extension"] == ".pdf"
    assert ident["file_size_bytes"] == len(pdf_header)


def test_identify_jpeg():
    jpeg_sig = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    ident = identify_file(jpeg_sig, "photo.jpg")
    assert "image" in ident["mime_type"]
    assert ident["hash_sha256"]


def test_extract_pdf_empty():
    # Minimal PDF
    pdf = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids []\n/Count 0\n>>\nendobj\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF"
    result = run_extraction(pdf, "empty.pdf")
    assert result.document.technical_metadata.mime_type == "application/pdf"
    assert result.document.technical_metadata.hash_sha256
    assert result.provenance.run_id


def test_extract_txt_as_octet():
    txt = b"Hello world"
    ident = identify_file(txt, "readme.txt")
    assert ident["mime_type"] in ("application/octet-stream", "text/plain")
    assert ident["hash_sha256"]
