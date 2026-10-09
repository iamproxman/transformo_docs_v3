# 🏗️ TransformoDocs — Deep Technical Architecture & System Design Document

This document details the **engineering architecture, technical decisions, tech stack choices, data models, search algorithm, OCR pipeline, RAG design, and performance optimizations** of TransformoDocs.

---

## 🛠️ 1. Technology Stack & Technical Rationale

| Layer | Technology Selected | Technical Rationale & Architectural Choice |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI (Python 3.10+)** | High-performance asynchronous WSGI/ASGI framework built on Starlette and Pydantic. Selected for async I/O non-blocking execution, automatic OpenAPI schema generation, low memory footprint, and native Server-Sent Events (SSE) streaming. |
| **Database & ORM** | **SQLite + SQLAlchemy ORM** | Zero-configuration embedded relational SQL engine. SQLite provides ACID transaction guarantees, low-latency disk I/O, and structured indexing without external database process management. SQLAlchemy provides explicit eager loading (`joinedload`) to eliminate N+1 query problems. |
| **AI / LLM Core** | **Google Gemini 2.5 Flash / 3.5 Flash** | Multi-modal LLM API with native Vision processing, 1M+ token context window, and low latency response time. Selected for multi-modal OCR (reading stylized logo text), structured JSON response enforcement (`response_mime_type="application/json"`), and cost-effective RAG reasoning. |
| **OCR Pipeline** | **PyMuPDF + PyTesseract + Gemini Vision API** | Multi-tiered OCR fallback pipeline. `PyMuPDF (fitz)` handles native PDF text layer extraction; `PyTesseract` handles local CPU OCR for scanned image body text; `Gemini Vision API` handles stylized logo graphics, badges, headers, and stamps. |
| **Real-time Status** | **Server-Sent Events (SSE)** | Unidirectional HTTP streaming (`StreamingResponse`) using isolated SQLAlchemy session polling (`SessionLocal()`). Chosen over WebSockets to reduce protocol complexity and connection state management overhead. |
| **Frontend UI** | **Vanilla JavaScript (ES6+), HTML5, Vanilla CSS** | Zero build step framework (no React/Vue bundling complexity), instant DOM rendering speed, native Fetch API, CSS CSS custom properties design tokens, glassmorphic UI layout. |
| **Bot Integration** | **python-telegram-bot (v20+ Async) + httpx** | Asynchronous Telegram Bot API wrapper communicating with the FastAPI backend via `httpx`. Supports multi-modal image/file ingestion, automatic Q&A message routing, and HTML markup escaping. |

---

## 🏛️ 2. High-Level Architecture & Data Flow

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   Web Dashboard │       │  Telegram Bot   │       │   REST Clients  │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   │ HTTP / JSON / Multipart
                                   ▼
                   ┌───────────────────────────────┐
                   │     FastAPI Application       │
                   │      (app/api/router)         │
                   └───────────────┬───────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ DocumentProc    │       │ Search Engine   │       │ RAG Engine      │
│ State Machine   │       │ (SearchService) │       │ (LLMService)    │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         ├──► PyMuPDF / Tesseract  ├──► Tokenization &       ├──► Gemini Flash RAG
         ├──► Gemini Vision OCR    │    Synonym Expansion    │    Prompt Context
         └──► Typed DB Ingestion   └──► Multi-Score Ranking  └──► USED_SOURCES Filter
```

---

## 🔬 3. Deep Dive into Technical Decisions

### Decision 3.1: Hybrid Multi-Tiered OCR Pipeline
- **Problem**: Traditional local OCR (`PyTesseract`) relies on standard font glyph recognition. On stylized graphic banners (e.g. the stylized **DIPEX 2025** logo on visitor passes), Tesseract fails to detect characters, omitting critical keywords from document indexation.
- **Solution**: We built a 3-tier hybrid OCR pipeline in `ocr_service.py`:
  1. **Tier 1 (Native PDF Probe)**: Uses `pymupdf` to check if a PDF contains native vector text (`alphanumeric_count / pages > 15`). If true, extracts vector text with 99% confidence in milliseconds.
  2. **Tier 2 (Local CPU OCR)**: Uses `pytesseract` to extract standard body text from images.
  3. **Tier 3 (Multi-Modal Vision OCR)**: When `GEMINI_API_KEY` is configured, executes `llm_service.ocr_image_with_gemini()`. Gemini's multi-modal vision transformer analyzes the full image layout and extracts stylized logo text, banners, watermarks, badges, and key-value fields verbatim.
  4. **Text Merging & Deduplication**: Tokens extracted from Tesseract and Gemini Vision are merged to guarantee near 100% recall.

### Decision 3.2: Deterministic + Semantic Hybrid Search Engine
- **Problem**: Pure vector embeddings search often misses exact string lookups (e.g., Visitor ID `11921` or Part Number `GG1000460BX`). Pure keyword matching fails on semantic intent (searching `"hospital"` fails to find a document with `"medical clinic"`).
- **Solution**: Engineered a deterministic multi-attribute scoring engine with synonym expansion in `search_service.py`:
  - **Token Normalization**: Query is sanitized and tokenized (`re.findall(r'[a-zA-Z0-9\-\_]+')`), stripping conversational stopwords.
  - **Synonym & Alias Expansion**: Maps terms like `"hospital"` -> `["medical", "patient", "clinic", "doctor"]` and `"dipex"` -> `["exhibition", "visitor", "pass", "srijan"]`.
  - **Multi-Attribute Relevance Scoring**:
    $$\text{Score} = w_{\text{alias}} S_{\text{doc\_type}} + w_{\text{exact}} S_{\text{exact}} + w_{\text{field}} S_{\text{field}} + w_{\text{text}} S_{\text{full\_text}} + w_{\text{syn}} S_{\text{synonym}}$$
    - Exact Query Match: `+0.40`
    - Extracted Field Match (`field_label`, `value_text`): `+0.35`
    - Document Type Alias Match: `+0.45`
    - Full Text Match: `+0.25` (+ frequency boost)
    - Filename Match: `+0.20`
  - **Score Cutoff**: Results are normalized to `[0, 1]` and filtered at `score >= 0.05` to eliminate irrelevant documents.

### Decision 3.3: RAG Citation & Source Manifesting (`USED_SOURCES`)
- **Problem**: Standard RAG approaches return all candidate context documents as "sources", resulting in inaccurate citations for documents that weren't actually used in the LLM's response.
- **Solution**: Implemented a two-stage source filtering system in `llm_service.py`:
  1. **LLM Output Protocol**: The RAG prompt enforces a strict protocol instructing Gemini to append a JSON source manifest:
     ```text
     USED_SOURCES: ["filename1.png", "filename2.pdf"]
     ```
  2. **Backend Parsing & Filtering**: The backend extracts `USED_SOURCES`, filters the candidate documents down to only the files explicitly listed/cited in the response text, and strips out the metadata block before serving the response to the user.

### Decision 3.4: Asynchronous Processing & ThreadPool Execution
- **Problem**: Synchronous document processing blocks worker threads during heavy OCR rendering and LLM API calls. Sequential batch rescanning of multiple documents caused noticeable latency.
- **Solution**: 
  - FastAPI `BackgroundTasks` offloads state machine execution from the request-response thread.
  - In `api/documents.py`, batch rescanning is wrapped in a `ThreadPoolExecutor(max_workers=4)`, allowing 4 documents to process concurrently in parallel, reducing rescan times by ~75%.

### Decision 3.5: JSON Payload Slimming & Data Normalization
- **Problem**: `doc.structured_data` previously contained a duplicate copy of the entire `extracted_fields` array, which was serialized twice in every `DocumentResponse`, bloating JSON responses by >50%.
- **Solution**: Refactored `doc.structured_data` to store concise document summary metadata (`doc_type`, `doc_type_confidence`, `summary`), while housing typed fields cleanly in the `ExtractedField` relational model table.

---

## 🗄️ 4. Relational Database Schema (`models.py`)

```sql
-- Documents Master Table
CREATE TABLE documents (
    id VARCHAR PRIMARY KEY,
    org_id VARCHAR NOT NULL,
    original_filename VARCHAR NOT NULL,
    mime_type VARCHAR NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 VARCHAR NOT NULL,
    storage_bucket VARCHAR,
    storage_key VARCHAR,
    source_kind VARCHAR, -- NATIVE_PDF, SCANNED_PDF, IMAGE
    page_count INTEGER,
    doc_type VARCHAR,   -- VISITOR_PASS, HOSPITAL_BILL, INVOICE, RESUME, etc.
    doc_type_confidence FLOAT,
    ocr_mean_confidence FLOAT,
    status VARCHAR NOT NULL, -- QUEUED, ROUTING, EXTRACTING, CLASSIFYING, COMPLETED, FAILED
    status_message TEXT,
    processing_ms INTEGER,
    structured_data JSON,
    created_at TIMESTAMP,
    completed_at TIMESTAMP,
    indexed_at TIMESTAMP
);

-- Full-Text Entry Table (1:1 with Document)
CREATE TABLE document_texts (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
    full_text TEXT NOT NULL,
    char_count INTEGER,
    word_count INTEGER,
    created_at TIMESTAMP
);

-- Extracted Fields Table (1:N with Document)
CREATE TABLE extracted_fields (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR REFERENCES documents(id) ON DELETE CASCADE,
    field_key VARCHAR NOT NULL,  -- e.g. visitorId, patientName, totalAmount
    field_label VARCHAR,
    data_type VARCHAR NOT NULL, -- STRING, NUMBER, DATE
    value_text TEXT,
    value_number FLOAT,
    value_date VARCHAR,
    value_bool BOOLEAN,
    currency_code VARCHAR,
    confidence FLOAT,
    page_no INTEGER,
    extractor VARCHAR NOT NULL   -- GEMINI_AI / HEURISTIC
);
```

---

## 🔄 5. State Machine Lifecycle

```
 ┌──────────────┐
 │   UPLOADED   │  File received & hash generated
 └──────┬───────┘
        ▼
 ┌──────────────┐
 │    QUEUED    │  Enqueued into processing queue
 └──────┬───────┘
        ▼
 ┌──────────────┐
 │   ROUTING    │  Probes layout (PDF text layer vs Scanned Image)
 └──────┬───────┘
        ▼
 ┌──────────────┐
 │  EXTRACTING  │  Runs Tesseract OCR & Gemini Vision OCR
 └──────┬───────┘
        ▼
 ┌──────────────┐
 │ CLASSIFYING  │  Gemini AI extracts typed fields & document classification
 └──────┬───────┘
        ▼
 ┌──────────────┐
 │   INDEXING   │  Indexes text & fields into search storage
 └──────┬───────┘
        ▼
 ┌──────────────┐
 │  COMPLETED   │  Ready for search, inspection, and RAG Q&A
 └──────────────┘
```

---
*TransformoDocs Technical Design & Architecture Documentation*
