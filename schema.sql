-- RPD Metadata Extractor — PostgreSQL Schema
-- Generated from rpd/models.py

-- ============================================================
-- PROVENANCE
-- ============================================================
CREATE TABLE provenance (
    run_id              TEXT        PRIMARY KEY,
    extractor_version   TEXT        NOT NULL,
    extractor_name      TEXT        NOT NULL DEFAULT 'rpd-builtin',
    source_uri          TEXT,
    extraction_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    settings            JSONB
);

-- ============================================================
-- DOCUMENTS  (DocumentRoot)
-- ============================================================
CREATE TABLE documents (
    id          TEXT    PRIMARY KEY,
    confidence  REAL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- TECHNICAL METADATA  (FR-10)  — 1:1 with documents
-- ============================================================
CREATE TABLE technical_metadata (
    document_id             TEXT        PRIMARY KEY
                                        REFERENCES documents(id) ON DELETE CASCADE,
    file_name               TEXT        NOT NULL,
    mime_type               TEXT        NOT NULL,
    extension               TEXT        NOT NULL DEFAULT '',
    file_size_bytes         BIGINT      NOT NULL,
    hash_sha256             TEXT        NOT NULL,
    hash_md5                TEXT,
    created_at_ingested     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_system           TEXT        NOT NULL DEFAULT '',
    source_uri              TEXT,
    encryption_flag         BOOLEAN     NOT NULL DEFAULT FALSE,
    password_protected_flag BOOLEAN     NOT NULL DEFAULT FALSE,
    embedded_object_count   INTEGER
);

-- ============================================================
-- EMBEDDED METADATA  (FR-11)  — 1:1 with documents
-- ============================================================
CREATE TABLE embedded_metadata (
    document_id     TEXT    PRIMARY KEY
                            REFERENCES documents(id) ON DELETE CASCADE,
    -- General
    title           TEXT,
    author          TEXT,
    creator         TEXT,
    producer        TEXT,
    creation_date   TEXT,
    modified_date   TEXT,
    page_count      INTEGER,
    exif            JSONB,
    -- Office
    last_modified_by TEXT,
    revision        TEXT,
    -- Email
    from_addr       TEXT,
    to_addr         TEXT,
    cc              TEXT,
    bcc             TEXT,
    date            TEXT,
    subject         TEXT,
    message_id      TEXT,
    attachments     JSONB       -- list[dict]
);

-- ============================================================
-- CONTENT METADATA  (FR-12)  — 1:1 with documents
-- ============================================================
CREATE TABLE content_metadata (
    document_id         TEXT    PRIMARY KEY
                                REFERENCES documents(id) ON DELETE CASCADE,
    language            TEXT,
    language_confidence REAL,
    page_count          INTEGER,
    sheet_count         INTEGER,
    slide_count         INTEGER,
    text_length         INTEGER NOT NULL DEFAULT 0,
    word_count          INTEGER NOT NULL DEFAULT 0,
    table_count         INTEGER NOT NULL DEFAULT 0,
    form_field_count    INTEGER NOT NULL DEFAULT 0,
    selection_count     INTEGER NOT NULL DEFAULT 0,
    signature_count     INTEGER NOT NULL DEFAULT 0,
    entity_counts       JSONB       -- dict[str, int]
);

-- ============================================================
-- EXTRACTION RESULTS  — ties a provenance run to a document
-- ============================================================
CREATE TABLE extraction_results (
    run_id      TEXT    PRIMARY KEY REFERENCES provenance(run_id)  ON DELETE CASCADE,
    document_id TEXT    NOT NULL    REFERENCES documents(id)        ON DELETE CASCADE
);

CREATE INDEX idx_extraction_results_document ON extraction_results(document_id);

-- ============================================================
-- PARTS
-- ============================================================
CREATE TABLE parts (
    id          TEXT    PRIMARY KEY,
    run_id      TEXT    NOT NULL REFERENCES extraction_results(run_id) ON DELETE CASCADE,
    part_type   TEXT    NOT NULL,   -- page | sheet | slide | attachment | embedded
    index       INTEGER NOT NULL DEFAULT 0,
    metadata    JSONB,
    confidence  REAL,
    geometry    JSONB               -- Geometry (type + bounds/points)
);

CREATE INDEX idx_parts_run ON parts(run_id);

-- ============================================================
-- BLOCKS
-- ============================================================
CREATE TABLE blocks (
    id          TEXT    PRIMARY KEY,
    run_id      TEXT    NOT NULL REFERENCES extraction_results(run_id) ON DELETE CASCADE,
    block_type  TEXT    NOT NULL,   -- text | line | word | kv | table | cell | selection | signature
    part_id     TEXT    REFERENCES parts(id) ON DELETE SET NULL,
    content     TEXT,
    value       JSONB,
    key         TEXT,
    cells       JSONB,              -- list[list[Any]]
    rows        INTEGER,
    cols        INTEGER,
    state       TEXT,
    confidence  REAL,
    geometry    JSONB
);

CREATE INDEX idx_blocks_run     ON blocks(run_id);
CREATE INDEX idx_blocks_part    ON blocks(part_id);
CREATE INDEX idx_blocks_type    ON blocks(block_type);

-- Part → Block ordered mapping (alias="blocks" list in Part)
CREATE TABLE part_blocks (
    part_id     TEXT    NOT NULL REFERENCES parts(id)  ON DELETE CASCADE,
    block_id    TEXT    NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (part_id, block_id)
);

-- Block → child Block mapping (children: list[str])
CREATE TABLE block_children (
    parent_id   TEXT    NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
    child_id    TEXT    NOT NULL REFERENCES blocks(id) ON DELETE CASCADE,
    PRIMARY KEY (parent_id, child_id)
);

-- ============================================================
-- RELATIONSHIPS
-- ============================================================
CREATE TABLE relationships (
    id              SERIAL  PRIMARY KEY,
    run_id          TEXT    NOT NULL REFERENCES extraction_results(run_id) ON DELETE CASCADE,
    source_id       TEXT    NOT NULL,
    target_id       TEXT    NOT NULL,
    relation_type   TEXT    NOT NULL DEFAULT 'contains'
                                     -- contains | references | child_of | derived_from
);

CREATE INDEX idx_relationships_run    ON relationships(run_id);
CREATE INDEX idx_relationships_source ON relationships(source_id);
CREATE INDEX idx_relationships_target ON relationships(target_id);

-- ============================================================
-- COMPARISON REPORTS
-- ============================================================
CREATE TABLE comparison_reports (
    id                              TEXT        PRIMARY KEY,
    status                          TEXT        NOT NULL,
                                    -- match | partial_match | conflict | incompatible
    -- SimilarityScores (inlined)
    similarity_document_level       REAL        NOT NULL DEFAULT 1.0,
    similarity_metadata             REAL,
    similarity_structure            REAL,
    similarity_content              REAL,
    similarity_per_part             JSONB,      -- list[dict]
    -- Summary
    severity_summary                JSONB,      -- dict[str, int]
    narrative_summary               TEXT        NOT NULL DEFAULT '',
    -- ConflictResolution (inlined)
    conflict_policy                 TEXT,
    conflict_chosen_values          JSONB,      -- list[dict]
    -- Provenance links
    left_run_id                     TEXT        REFERENCES provenance(run_id),
    right_run_id                    TEXT        REFERENCES provenance(run_id),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- DIFF ITEMS  (metadata / structure / content / query_answer)
-- ============================================================
CREATE TABLE diff_items (
    id              SERIAL  PRIMARY KEY,
    report_id       TEXT    NOT NULL REFERENCES comparison_reports(id) ON DELETE CASCADE,
    category        TEXT    NOT NULL,
                    -- metadata | structure | content | query_answer
    diff_type       TEXT    NOT NULL,   -- added | removed | changed | conflict
    path            TEXT    NOT NULL DEFAULT '',
    left_value      JSONB,
    right_value     JSONB,
    severity        TEXT    NOT NULL,   -- low | medium | high | critical
    left_block_id   TEXT,
    right_block_id  TEXT,
    left_confidence REAL,
    right_confidence REAL,
    description     TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX idx_diff_items_report   ON diff_items(report_id);
CREATE INDEX idx_diff_items_category ON diff_items(category);
CREATE INDEX idx_diff_items_severity ON diff_items(severity);
