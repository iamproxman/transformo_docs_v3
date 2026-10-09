# TransformoDocs — Agent Context & Architecture Blueprint

## System Overview
TransformoDocs is an Intelligent Document Processing (IDP) and Retrieval-Augmented Generation (RAG) platform. It ingests PDFs, scanned documents, and images; performs layout/text analysis (probe native text vs Tesseract OCR); extracts structured JSON key-value fields using Google Gemini AI; and enables multi-modal search & Q&A via Web UI and Telegram Bot.

## Stack Architecture
- **Backend API**: Python FastAPI (`app/main.py`)
- **Database**: SQLAlchemy ORM (SQLite for zero-cost local / PostgreSQL compatible DDL)
- **Document Pipeline**: PyMuPDF (native PDF probe) + Tesseract OCR (scanned images/PDFs) + Gemini 1.5/2.0 Flash (LLM extraction & RAG)
- **Storage**: Local filesystem storage with S3/Cloudflare R2 abstraction
- **Bot Integration**: Telegram Bot API integration (file upload, document search, RAG Q&A)
- **Frontend**: Vanilla HTML5, CSS3 (Glassmorphism Dark Mode), JavaScript (ES Modules, SSE)

## Key Directories
- `agents/`: Agent context switch files and state tracking
- `backend/`: FastAPI application code & services
- `frontend/`: Web UI dashboard & document viewer
- `telegram_bot/`: Telegram bot integration service
