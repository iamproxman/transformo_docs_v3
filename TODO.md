# 📋 TransformoDocs — Team Engineering TODO & Agent Task Board

> **Instructions for AI Agents & Teammates:**  
> This file contains actionable, prioritized tasks for extending TransformoDocs. When starting a task, claim it by marking your name/agent ID in the checklist and refer to `Reference_docs/TransformoDocs_Execution_Plan.md` for architectural context.

---

## 🚀 Priority 1: Vector Embeddings & Hybrid Semantic Search

### 🎯 Task 1.1: Dense Vector Embedding & Vector Database Integration
- **Target Component:** `backend/app/services/search_service.py`, `backend/app/models/models.py`
- **Objective:** Upgrade search from token matching to **Hybrid Semantic Vector Search**.
- **Implementation Plan:**
  1. Generate text embeddings for document chunks using `sentence-transformers` (`all-MiniLM-L6-v2`) or Google Gemini Embeddings API (`models/text-embedding-004`).
  2. Store vector embeddings in SQLite (`sqlite-vss`) or PostgreSQL (`pgvector`).
  3. Combine dense vector similarity scores with BM25 keyword matching for hybrid ranking:
     $$\text{Final Score} = 0.6 \times \text{Vector Cosine Sim} + 0.4 \times \text{Keyword Score}$$
- **Acceptance Criteria:**
  - Searching for *"hospitalization charges"* returns *"Medical Patient Invoice"* even if exact words differ.
  - Sub-100ms vector retrieval on 10,000 document chunks.

---

## ⚡ Priority 2: Async Queue & Worker Isolation

### 🎯 Task 2.1: Migrate Background Tasks to Celery / RabbitMQ
- **Target Component:** `backend/app/services/document_processor.py`, `backend/app/api/documents.py`
- **Objective:** Replace FastAPI `BackgroundTasks` with Celery + Redis or RabbitMQ worker processes.
- **Implementation Plan:**
  1. Add Celery application instance in `backend/app/core/celery_app.py`.
  2. Decorate `process_document_by_id` as `@celery_app.task(bind=True, max_retries=3)`.
  3. Update `documents.py` endpoints to call `.delay(doc_id)`.
  4. Implement Dead-Letter Queue (DLQ) logging for unrecoverable errors.
- **Acceptance Criteria:**
  - Heavy OCR or LLM extractions execute in standalone worker containers without blocking web server event loops.
  - Failed tasks automatically retry 3 times with exponential backoff (30s → 2m → 8m).

---

## 🔐 Priority 3: Authentication & Multi-Tenant Security

### 🎯 Task 3.1: JWT Auth & RBAC Guard Implementation
- **Target Component:** `backend/app/api/auth.py`, `backend/app/api/documents.py`, `backend/app/models/models.py`
- **Objective:** Eliminate hardcoded default org ID (`00000000-...`) and enforce organization-level data isolation.
- **Implementation Plan:**
  1. Implement `/api/v1/auth/register` and `/api/v1/auth/login` using `passlib[bcrypt]` and `python-jose`.
  2. Create a FastAPI dependency `get_current_user` to extract JWT user claims.
  3. Enforce `org_id` filtering on all document database queries and file access routes.
  4. Add RBAC role checks (`ADMIN`, `USER`, `VIEWER`).
- **Acceptance Criteria:**
  - Unauthorized requests return `401 Unauthorized`.
  - Users can only view, search, and preview documents belonging to their authenticated `org_id`.

---

## ☁️ Priority 4: Object Storage & Two-Phase Upload

### 🎯 Task 4.1: MinIO / S3 Presigned Upload Pipeline
- **Target Component:** `backend/app/services/storage_service.py`, `backend/app/api/documents.py`
- **Objective:** Offload binary upload streams from the FastAPI web server directly to S3 / MinIO object storage.
- **Implementation Plan:**
  1. Add `boto3` MinIO/S3 storage client wrapper to `storage_service.py`.
  2. Implement `POST /api/v1/documents/init` returning presigned `PUT` upload URLs.
  3. Implement `POST /api/v1/documents/{id}/commit` to trigger processing after S3 upload completes.
- **Acceptance Criteria:**
  - File upload returns `201 Created` with `uploadUrl` in <300ms.
  - Server does not hold binary upload streams in memory.

---

## 📊 Summary Checklist for Incoming Agents

- [ ] **Task 1.1:** Vector Embeddings & Hybrid Search
- [ ] **Task 2.1:** Celery / RabbitMQ Worker Isolation
- [ ] **Task 3.1:** JWT Auth & RBAC Security
- [ ] **Task 4.1:** S3 Presigned Upload Pipeline
