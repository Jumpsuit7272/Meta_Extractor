un # RPD: Universal File Metadata & Extraction Comparison Service

A **Universal Extraction & Comparison Service** that extracts metadata and structured content from supported file types and compares outputs across runs, models, sources, or versions—with full audit trail (confidence + provenance + geometry).

## Features

- **Universal metadata extraction** from documents, images, emails, archives, Office files
- **Technical, embedded, and content metadata** extraction
- **Structured content extraction** (text, tables, KV pairs, OCR with geometry)
- **Run-to-run and source-to-source comparison** with scoring, diffs, conflict detection
- **Canonical JSON output** with provenance, confidence, and geometry
- **REST APIs** for sync/async extraction and comparison

## E2E Tests (Playwright)

```bash
pip install playwright pytest-playwright httpx
playwright install chromium

# Terminal 1: start the server
python run.py
# or: uvicorn rpd.main:app --port 8000

# Terminal 2: run E2E tests
pytest tests/e2e -v --base-url=http://localhost:8000
```

Core API tests always run; UI tests run when the server is up and the UI is available.

## Supported File Types

| Category | Formats |
|----------|---------|
| Documents | PDF, DOCX, XLSX, PPTX |
| Images | JPEG, PNG, TIFF, BMP, WebP |
| Email | EML, MSG |
| Archives | ZIP |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
uvicorn rpd.main:app --reload
```

## Server Installation (Intranet)

Use the install-and-run scripts to deploy on a server for intranet access:

**Linux/macOS:**
```bash
chmod +x scripts/install_and_run.sh
./scripts/install_and_run.sh 8000
# Binds to 0.0.0.0:8000 – accessible from other machines as http://<server-ip>:8000
```

**Windows:**
```cmd
scripts\install_and_run.bat 8000
```

The scripts create a virtual environment, install dependencies, and start the server. Access:
- **App UI:** http://localhost:8000
- **Intranet landing:** http://localhost:8000/intranet
- **API Docs:** http://localhost:8000/docs

## API Endpoints

### Extraction
- `POST /extract/sync` - Synchronous extraction (file upload)
- `POST /extract/async` - Asynchronous extraction (returns job ID)
- `GET /extract/jobs/{job_id}` - Job status
- `GET /extract/jobs/{job_id}/result` - Extraction result

### Ingestion
- `POST /ingest/uri` - Ingest from http/https or s3:// URI

### Comparison
- `POST /compare` - Synchronous comparison (by run_ids or inline results)
- `POST /compare/async` - Asynchronous comparison
- `GET /compare/jobs/{job_id}` - Job status
- `GET /compare/jobs/{job_id}/report` - Comparison report

### Example: Compare Two Extractions

```bash
# 1. Extract document (get run_id from response)
curl -X POST -F "file=@invoice.pdf" http://localhost:8000/extract/sync

# 2. Extract same document again (or different version)
curl -X POST -F "file=@invoice_v2.pdf" http://localhost:8000/extract/sync

# 3. Compare by run_id (from provenance.run_id in each result)
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{"left_run_id": "<run_id_1>", "right_run_id": "<run_id_2>"}'
```

## Schema & Rules

- `schemas/extraction_result.schema.json` - Canonical extraction output
- `schemas/comparison_report.schema.json` - Comparison report format
- `rule_packs/critical_fields.yaml` - Critical fields by document type (invoice, ID, contract, etc.)
