# TransformoDocs — Execution-Ready Engineering & Architecture Plan

**Version:** 2.0 (Supersedes conceptual docs)  
**Scope:** Service boundaries, async pipeline contracts, PostgreSQL DDL schema, storage layout, state machine, and phased build order.  

---

## 0. Decisions Locked (Zero Confusion)

| Domain | Decision | Rationale |
| :--- | :--- | :--- |
| **Sync vs. Async** | **100% Async Pipeline** | File upload returns `202 Accepted` in <300ms. OCR and LLM extraction take 2–30s. Synchronous HTTP calls will time out under load. |
| **Tech Stack** | **Hybrid (Spring Boot + Python FastAPI)** | Spring Boot (`core-api`) handles API, auth, RBAC, state orchestration, SSE, and DB schema. Python FastAPI (`doc-ai`) handles OpenCV, PyTesseract, PyMuPDF, and LLM parsing. |
| **Queue Engine** | **RabbitMQ (Quorum Queues)** | RabbitMQ provides explicit ACKs, redelivery, and Dead-Letter Queues (DLQ). Redis queues lose messages on worker crash. |
| **Database vs. Storage** | **PostgreSQL + MinIO/S3 + Elasticsearch + Redis** | • **Postgres:** Primary source of truth for metadata, status, lifecycle, and typed extracted fields (`extracted_fields`). NEVER store raw file bytes in Postgres.  <br>• **S3 / MinIO:** Stores original PDFs/images, page PNGs, raw hOCR, full text > 1MB, and JSON/XML exports.<br>• **Elasticsearch:** Search index projection. Fully rebuildable from Postgres + S3 at any time.<br>• **Redis:** Ephemeral locks, SSE pub/sub, rate limiting, and JWT denylist. |
| **PDF Ingestion Routing** | **Text-Layer Probe First** | Probe PDF for native text layer using PyMuPDF. Native PDFs extract in ~100ms with zero OCR error. Scanned/image PDFs route to PyTesseract OCR. |
| **Status Delivery** | **SSE Primary + Polling Fallback** | Server-Sent Events (SSE) stream job events in real time. 3-second HTTP polling acts as bulletproof fallback behind strict corporate proxies. |

---

## 1. Service Topology & Architecture

TransformoDocs consists of three core deployable services plus the React frontend:
1. `core-api` **(Java / Spring Boot):** Single owner of the database schema. Handles Auth, REST endpoints, upload initiation, job dispatching, status SSE streams, and callback verification.
2. `doc-ai` **(Python / FastAPI):** Stateless processing worker. Consumes jobs from RabbitMQ, reads bytes from MinIO/S3, executes routing / OCR / NLP field extraction, writes artifacts back to S3, and POSTs the result envelope to `core-api`.
3. `indexer` **(Java / Outbox Poller):** Reads outbox events from PostgreSQL and maintains the Elasticsearch search index.

```
┌─────────────────────────────────────────────────────────┐
│                      React SPA                          │
└────────────┬──────────────────────────────────▲─────────┘
             │ REST (Presigned PUT)              │ SSE / Polling
┌────────────▼──────────────────────────────────┴─────────┐
│              Spring Boot ("core-api")                   │
│          Auth · Upload · Orchestration · SSE            │
└───┬─────────────┬─────────────────────────┬─────────────┘
    │ Presigned   │ Publish                 │ Write
    ▼             ▼                         ▼
┌─────────┐   ┌──────────────┐         ┌──────────────────┐
│ MinIO/S3│   │   RabbitMQ   │         │    PostgreSQL    │
└────▲────┘   └──────┬───────┘         └──────────────────┘
     │               │ Consume
     │        ┌──────▼──────────────────────────┐
     └────────┤   Python FastAPI ("doc-ai")     │
  Read/Write  │   Route · OCR · LLM Extraction  │
              └──────┬──────────────────────────┘
                     │ Internal REST Callback
                     ▼
             core-api ──► PostgreSQL ──► Outbox ──► Elasticsearch
```

---

## 2. Document Processing State Machine

Transitions are guarded strictly inside `DocumentStateService`. Every transition writes an immutable audit record to `job_events`.

```
UPLOADED ──► QUEUED ──► ROUTING ──► EXTRACTING ──► CLASSIFYING ──► PARSING ──► INDEXING ──► COMPLETED
   │           │           │            │              │             │          │
   └───────────┴───────────┴────────────┴──────────────┴─────────────┴──────────┴──► FAILED
                                                                                       │ (retries exhausted)
                                                                                       ▼
                                                                                   DEAD_LETTER
```

### Transition Rules:
- **`COMPLETED` -> `PROCESSING`** is illegal and throws an exception.
- **`FAILED`** is recoverable via retry policy (3 attempts, exponential backoff: 30s -> 2m -> 8m with +/-20% jitter).
- **`DEAD_LETTER`** is terminal and requires admin manual intervention.
- The retry counter lives on `processing_jobs`, not on the document record.

---

## 3. Async Pipeline Contracts & Ingestion Flow

### 3.1 Two-Phase Presigned Upload Flow
1. **Initiate:** `POST /api/v1/documents/init` with `{ filename, sizeBytes, mimeType, sha256 }`.
   - If `sha256` exists in org, returns `200 OK` with `{ documentId, status: "COMPLETED", deduped: true }` (Instant 5ms deduplication).
   - Otherwise returns `201 Created` with `{ documentId, uploadUrl, expiresIn: 900 }`.
2. **Upload:** Browser executes `PUT <uploadUrl>` directly to MinIO/S3. Backend server never touches binary upload streams.
3. **Commit:** Browser sends `POST /api/v1/documents/{id}/commit`. Backend enqueues RabbitMQ message and returns `202 Accepted` with `{ status: "QUEUED", statusUrl }`.

### 3.2 RabbitMQ Message Contract (`docs.process`)
```json
{
  "jobId": "018f3a2b-1234-7000-8000-000000000001",
  "documentId": "018f3a2b-1234-7000-8000-000000000002",
  "orgId": "018f3a2b-1234-7000-8000-000000000003",
  "jobType": "PROCESS_DOCUMENT",
  "bucket": "transformo-docs",
  "key": "org/018f.../raw/018f.../original.pdf",
  "mimeType": "application/pdf",
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "attempt": 1,
  "idempotencyKey": "018f...:PROCESS_DOCUMENT:v1",
  "enqueuedAt": "2026-09-16T10:00:00Z"
}
```

---

## 4. PostgreSQL DDL Schema

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "citext";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 1. Organizations & Tenancy
CREATE TABLE organizations (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                TEXT NOT NULL,
  storage_quota_bytes BIGINT DEFAULT 10737418240, -- 10 GB
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Users & Auth
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  email         CITEXT NOT NULL,
  password_hash TEXT NOT NULL,
  full_name     TEXT,
  role          TEXT NOT NULL DEFAULT 'USER' CHECK (role IN ('ADMIN','USER','VIEWER')),
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (org_id, email)
);

-- 3. Document Status & Types
CREATE TYPE doc_status AS ENUM (
  'UPLOADED','QUEUED','ROUTING','EXTRACTING','CLASSIFYING',
  'PARSING','INDEXING','COMPLETED','FAILED','DEAD_LETTER','QUARANTINED'
);

CREATE TYPE source_kind AS ENUM (
  'NATIVE_PDF','SCANNED_PDF','HYBRID_PDF','IMAGE','OFFICE','UNKNOWN'
);

-- 4. Documents Spine
CREATE TABLE documents (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  uploaded_by         UUID NOT NULL REFERENCES users(id),
  original_filename   TEXT NOT NULL,
  mime_type           TEXT NOT NULL,
  size_bytes          BIGINT NOT NULL CHECK (size_bytes > 0),
  sha256              CHAR(64) NOT NULL,
  storage_bucket      TEXT NOT NULL,
  storage_key         TEXT NOT NULL,
  source_kind         source_kind NOT NULL DEFAULT 'UNKNOWN',
  page_count          INTEGER,
  detected_languages  TEXT[],
  doc_type            TEXT,                  -- e.g. INVOICE, KYC, RESUME
  doc_type_confidence NUMERIC(4,3) CHECK (doc_type_confidence BETWEEN 0 AND 1),
  structured_data     JSONB,                 -- Whole extracted payload
  ocr_mean_confidence NUMERIC(5,2),
  status              doc_status NOT NULL DEFAULT 'UPLOADED',
  status_message      TEXT,
  processing_ms       INTEGER,
  indexed_at          TIMESTAMPTZ,
  completed_at        TIMESTAMPTZ,
  deleted_at          TIMESTAMPTZ,           -- Soft delete
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_org_sha UNIQUE (org_id, sha256) -- Deduplication index
);

CREATE INDEX ON documents (org_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX ON documents (status) WHERE status NOT IN ('COMPLETED','DEAD_LETTER');
CREATE INDEX idx_documents_structured ON documents USING GIN (structured_data jsonb_path_ops);

-- 5. Document Text Store
CREATE TABLE document_text (
  document_id   UUID PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  full_text     TEXT,                   -- Populated when < 1MB
  full_text_key TEXT,                   -- S3 key when >= 1MB
  char_count    INTEGER NOT NULL DEFAULT 0,
  word_count    INTEGER NOT NULL DEFAULT 0,
  tsv           TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', coalesce(full_text, ''))) STORED,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_document_text_tsv ON document_text USING GIN (tsv);

-- 6. Typed Extracted Fields (Product Table)
CREATE TABLE extracted_fields (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id    UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  field_key      TEXT NOT NULL,          -- e.g. invoiceNumber, totalAmount
  field_label    TEXT,
  data_type      TEXT NOT NULL CHECK (data_type IN ('STRING','NUMBER','DATE','BOOL')),
  value_text     TEXT,
  value_number   NUMERIC(20,4),
  value_date     DATE,
  value_bool     BOOLEAN,
  currency_code  CHAR(3),
  confidence     NUMERIC(4,3) CHECK (confidence BETWEEN 0 AND 1),
  page_no        INTEGER,
  bbox           JSONB,                  -- Normalized {"x":0.1,"y":0.2,"w":0.3,"h":0.1}
  extractor      TEXT NOT NULL,          -- e.g. 'TESSERACT_OCR' | 'LLM_GPT35'
  is_verified    BOOLEAN NOT NULL DEFAULT FALSE,
  verified_by    UUID REFERENCES users(id),
  original_value TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_id, field_key)
);

CREATE INDEX ON extracted_fields (field_key, value_number) WHERE value_number IS NOT NULL;
CREATE INDEX ON extracted_fields (field_key, value_date) WHERE value_date IS NOT NULL;

-- 7. Processing Jobs & Audit Events
CREATE TABLE processing_jobs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  job_type        TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'PENDING',
  attempt         INTEGER NOT NULL DEFAULT 0,
  max_attempts    INTEGER NOT NULL DEFAULT 3,
  idempotency_key TEXT NOT NULL UNIQUE,
  error_code      TEXT,
  error_message   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE job_events (
  id          BIGSERIAL PRIMARY KEY,
  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  job_id      UUID REFERENCES processing_jobs(id) ON DELETE SET NULL,
  from_status TEXT,
  to_status   TEXT NOT NULL,
  message     TEXT,
  payload     JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON job_events (document_id, created_at);

-- 8. Transactional Outbox for Search Indexing
CREATE TABLE search_outbox (
  id           BIGSERIAL PRIMARY KEY,
  document_id  UUID NOT NULL,
  operation    TEXT NOT NULL CHECK (operation IN ('UPSERT','DELETE')),
  payload      JSONB,
  published_at TIMESTAMPTZ,
  attempts     INTEGER NOT NULL DEFAULT 0,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON search_outbox (created_at) WHERE published_at IS NULL;
```

---

## 5. Storage Layout (S3 / MinIO)

```
transformo-docs/
└── org/{orgId}/
    └── raw/{documentId}/
        ├── original.pdf              <-- Immutable raw upload
        ├── pages/
        │   ├── page-0001.png         <-- Preprocessed page images
        │   └── page-0002.png
        ├── ocr/
        │   ├── page-0001.hocr        <-- Bounding boxes & token layouts
        │   └── full.txt              <-- Stored here if > 1MB
        └── exports/
            ├── structured.json       <-- Extracted JSON
            └── structured.xml        <-- Extracted XML
```

---

## 6. Phased Implementation Build Order

1. **Phase 0 — Infrastructure Skeleton (Week 1):** Bring up Docker Compose (Postgres, MinIO, RabbitMQ, Elasticsearch, Redis). Run Flyway DDL migrations. Set up `/health` on all services.
2. **Phase 1 — Auth & Storage (Week 2):** JWT registration/login, presigned upload URLs, `sha256` deduplication.
3. **Phase 2 — Async Plumbing & State Machine (Week 3):** RabbitMQ consumers, `doc-ai` mock worker, state machine transitions, `job_events` logging, SSE status streaming.
4. **Phase 3 — Ingestion Routing & OCR (Week 4):** Native PDF text-layer probe vs. scanned PDF OpenCV + PyTesseract OCR routing.
5. **Phase 4 — AI Parsing & Field Extraction (Week 5):** LLM prompt extraction for JSON/XML schema generation, writing to `extracted_fields`.
6. **Phase 5 — Search Indexing (Week 6):** Transactional Outbox poller, Elasticsearch mapping & nested field queries (`amount > 50000`).
7. **Phase 6 — Frontend UI (Week 7):** React SPA dashboard, upload progress, bounding box highlight document viewer, field editor.
8. **Phase 7 — Security & Hardening (Week 8):** Service-to-service secret headers (`X-Internal-Service-Key`), poison pill exception guards, rate limits, ClamAV virus scanning.
