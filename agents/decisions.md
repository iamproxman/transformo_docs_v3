# Architectural Decisions Log

| Decision | Choice | Rationale |
| :--- | :--- | :--- |
| **Pipeline Mode** | Asynchronous / Background Tasks | File upload immediately returns `202 Accepted`. Heavy OCR & LLM processing run via background tasks with real-time SSE stream updates. |
| **OCR & PDF Parser** | PyMuPDF + PyTesseract | Native PDF text layer probe gives 100ms instant extraction; scanned PDFs/images fall back to Tesseract OCR. |
| **AI Processing** | Google Gemini API (gemini-1.5-flash / gemini-2.0-flash) | Generates structured JSON schema, confidence scores, auto-classification, and document RAG Q&A with zero hosting cost. |
| **Storage** | Local Filesystem / R2 / S3 Ready | Clean storage interface (`StorageService`) supporting local directory out-of-the-box and S3/Cloudflare R2 seamlessly. |
| **Multi-Channel Access** | Web SPA + Telegram Bot | Users can interact via modern web dashboard or directly inside Telegram (upload, search, ask questions). |
