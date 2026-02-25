"""API integration tests - extract, compare."""

import pytest
import httpx

BASE = "http://127.0.0.1:8000"

# Minimal valid PDF
MINIMAL_PDF = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 700 Td
(Hello World) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000226 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
317
%%EOF"""


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE, timeout=30)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root_serves_ui(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "uploadZone" in r.text or "RPD" in r.text


def test_extract_sync_pdf(client):
    r = client.post("/extract/sync", files={"file": ("test.pdf", MINIMAL_PDF, "application/pdf")})
    assert r.status_code == 200
    data = r.json()
    assert "document" in data
    assert "provenance" in data
    assert data["document"]["technical_metadata"]["mime_type"] == "application/pdf"
    assert data["provenance"]["run_id"]


def test_extract_and_compare(client):
    # Extract same PDF twice (simulate two runs)
    r1 = client.post("/extract/sync", files={"file": ("doc1.pdf", MINIMAL_PDF, "application/pdf")})
    r2 = client.post("/extract/sync", files={"file": ("doc2.pdf", MINIMAL_PDF, "application/pdf")})
    assert r1.status_code == 200 and r2.status_code == 200

    left = r1.json()
    right = r2.json()

    # Compare
    r = client.post("/compare", json={
        "left_result": left,
        "right_result": right,
    })
    assert r.status_code == 200
    report = r.json()
    assert report["status"] in ("match", "partial_match", "conflict", "incompatible")
    assert "similarity_scores" in report
    assert "left_provenance" in report
    assert "right_provenance" in report


def test_compare_by_run_id(client):
    r1 = client.post("/extract/sync", files={"file": ("a.pdf", MINIMAL_PDF, "application/pdf")})
    r2 = client.post("/extract/sync", files={"file": ("b.pdf", MINIMAL_PDF, "application/pdf")})
    assert r1.status_code == 200 and r2.status_code == 200
    run_a = r1.json()["provenance"]["run_id"]
    run_b = r2.json()["provenance"]["run_id"]

    r = client.post("/compare", json={"left_run_id": run_a, "right_run_id": run_b})
    assert r.status_code == 200
    assert r.json()["status"]
