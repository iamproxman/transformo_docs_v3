# TransformoDocs 🚀
> **Intelligent Document Processing (IDP) & Retrieval-Augmented Generation (RAG) Platform**

TransformoDocs is an Intelligent Document Processing (IDP) system that ingests PDFs, scanned images, invoices, resumes, and medical records, extracts structured JSON data via **PyMuPDF native text probing + Tesseract OCR + Google Gemini AI**, and provides hybrid keyword search and RAG Q&A via a **Web Dashboard** and **Telegram Bot**.

---

## 📊 Feature Audit & Gap Analysis

Below is an honest breakdown comparing the **current codebase state** against the enterprise reference specification (`Reference_docs/TransformoDocs_Execution_Plan.md`).

---

### ✅ 1. What IS Implemented & Working

| Component | Status | Details |
| :--- | :---: | :--- |
| **PDF Text-Layer Probing** | ✅ **Done** | PyMuPDF probes PDFs for native text layers in <100ms. Native PDFs bypass OCR. |
| **Image & Scanned PDF OCR** | ✅ **Done** | PyTesseract OCR with auto-downloaded `eng.traineddata` + Gemini Vision fallback for scanned images. |
| **AI Structured Field Extraction** | ✅ **Done** | Google Gemini LLM with candidate model fallbacks (`gemini-1.5-flash-latest`, `gemini-1.5-pro-latest`, `gemini-2.0-flash`) + heuristic regex backup. |
| **Document State Machine** | ✅ **Done** | Complete state machine transitions (`QUEUED` → `ROUTING` → `EXTRACTING` → `CLASSIFYING` → `INDEXING` → `COMPLETED`/`FAILED`) logged in `job_events`. |
| **Storage Auto-Healing** | ✅ **Done** | Automatic resolution and healing for document storage paths on disk. |
| **Multi-Token Search Engine** | ✅ **Done** | Case-insensitive token relevance scoring across filename, full text, document type, extracted fields, and JSON metadata. |
| **RAG Q&A Assistant API** | ✅ **Done** | Answers user queries using relevant score-ranked document context via Gemini AI. |
| **Telegram Bot Integration** | ✅ **Done** | Telegram bot supporting document upload, document status, `/search`, and `/ask`. |
| **Web SPA Dashboard** | ✅ **Done** | Dark glassmorphism UI with upload progress, live document preview, field inspector, search interface, and RAG bot drawer. |

---

### ⚠️ 2. What IS NOT Implemented (Current Gaps)

| Component | Current State | Target Specification (`Reference_docs`) |
| :--- | :--- | :--- |
| **Vector Database & Embeddings** | Token matching & score ranking in Python | **Dense Vector Search** using `pgvector`, ChromaDB, or Qdrant for semantic query understanding. |
| **Async Message Queue** | FastAPI `BackgroundTasks` (in-memory threads) | **RabbitMQ Quorum Queues / Celery** with Dead-Letter Queues (DLQ) for worker isolation. |
| **Search Engine Scale** | SQLite / Python in-memory scoring | **Elasticsearch / OpenSearch** projection index driven by PostgreSQL Transactional Outbox. |
| **Cloud Object Storage** | Local disk directory (`./storage`) | **AWS S3 / MinIO** presigned PUT/GET upload URLs. |
| **Auth & Multi-Tenancy** | Default single org ID (`00000000-...`) | **JWT Authentication**, bcrypt password hashing, and org-level RBAC (`ADMIN`, `USER`, `VIEWER`). |

---

### 🚀 3. Remaining Roadmap & Improvements

1. **Semantic Vector Search (High Priority):**
   - Replace pure token matching with dense vector embeddings (`sentence-transformers/all-MiniLM-L6-v2` or `text-embedding-3-small` / Gemini embeddings).
   - Enables semantic matches (e.g. searching for *"physician billing"* matches *"Hospital Medical Invoice"* even if exact words differ).

2. **Queue Resilience (Medium Priority):**
   - Migrate background document processing to Celery / Redis or RabbitMQ workers to prevent worker crashes from affecting web server threads.

3. **Elasticsearch / PostgreSQL Migration (Medium Priority):**
   - Upgrade SQLite database to PostgreSQL + Flyway migrations for high-concurrency enterprise workloads.

---

## 🛠️ Quick Start Guide

### 1. Local Setup

```bash
# Navigate to project root
cd Transformo_docs

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Run FastAPI backend server
uvicorn app.main:app --reload --port 8000
```
Open `http://localhost:8000` in your web browser.

---

### 2. Environment Variables (`.env`)

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_google_gemini_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=sqlite:///./transformo_docs.db
UPLOAD_DIR=./storage
```

---

### 3. Running Telegram Bot

```bash
cd telegram_bot
pip install -r requirements.txt
python bot.py
```
