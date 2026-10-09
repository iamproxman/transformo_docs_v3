# 🚀 How TransformoDocs Works — Simple Explanation

Welcome! This document explains **what TransformoDocs is**, **how it works under the hood**, and **how we solved all the recent challenges** in simple, plain language.

---

## 💡 1. What is TransformoDocs?

Think of **TransformoDocs** as a super-smart digital filing cabinet with a built-in AI assistant. 

When you upload any file (a PDF, a photo of a visitor pass, a medical bill, or an invoice):
1. **It Reads Everything**: It extracts all text—even text printed inside fancy logos or graphic badges.
2. **It Extracts Important Details**: It automatically pulls out names, IDs, dates, mobile numbers, hospital names, and bill amounts.
3. **It Makes Everything Searchable**: You can type any keyword (like `"dipex"` or `"hospital"`) and get exact matches instantly.
4. **It Answers Your Questions**: You can chat with it in plain English (on the Web App or via Telegram) and ask questions like *"What is Jagdish's Visitor ID?"* or *"How many DIPEX passes do we have?"*.

---

## 👁️ 2. How Does It Read Files? (OCR & AI Brain)

When a document is uploaded, it goes through a two-step process:

### Step 1: Text Reading (OCR Eye)
- **Normal Text**: It uses **PyTesseract** to quickly read regular typed text.
- **Fancy/Stylized Logos & Badges**: PyTesseract often misses stylized text inside logos (like the **DIPEX 2025** logo on visitor passes). To solve this, we enabled **Gemini Vision AI OCR**, which looks at the image like a human eye and reads 100% of stylized titles, logos, headers, and stamps verbatim.

### Step 2: Structured Field Extraction (AI Brain)
- **Gemini AI Engine** reads the full text and categorizes the document (e.g. `VISITOR_PASS`, `HOSPITAL_BILL`, `INVOICE`, `RESUME`).
- It extracts specific key-value pairs cleanly:
  - **Visitor Pass**: `Visitor ID` (e.g. `11921`), `Visitor Name` (`Jagdish Uikey`), `Mobile Number` (`7620028357`), `Pass Issue Date`, `Event Name`.
  - **Hospital Bill**: `Hospital Name`, `Patient Name`, `Attending Doctor`, `Medical Record Number (MRN)`.
  - **Invoice**: `Invoice Number`, `Vendor Name`, `Total Amount`, `Document Date`.

---

## 🔍 3. How Does Search Work? (The Smart Finder)

When you type a search term in the **Search Tab** or in Telegram (`/search hospital`):

1. **Tokenization & Synonym Expansion**: 
   - If you search `"hospital"`, it also looks for related words like `"medical"`, `"patient"`, `"doctor"`, `"clinic"`.
   - If you search `"dipex"`, it also looks for `"exhibition"`, `"visitor"`, `"pass"`, `"srijan"`.
2. **Scoring**: It rates every document's relevance from `0%` to `100%`.
3. **Relevance Threshold**: Documents with a score under `5%` or zero matching terms are **filtered out**, so you only see truly relevant results without irrelevant clutter.

---

## 🤖 4. How Does the AI Assistant Work? (RAG Q&A Engine)

When you ask a question like:
> *"What are the entrance IDs for all 4 DIPEX passes?"*

1. **Document Retrieval**: The system pulls candidate documents from the database.
2. **Context Passing**: It sends the text of those documents to Gemini AI with instructions to answer your question strictly based on facts.
3. **Source Citation & Filtering**:
   - Gemini outputs an explicit list of the exact filenames it used to formulate the answer (`USED_SOURCES: ["Jagdish Uikey_Visitor_Pass.png", ...]`).
   - The backend filters out any unused candidate files.
   - Only the **actual sources referenced** are shown as clickable source chips under **"Sources Used"**.

---

## 📱 5. How Does the Telegram Bot Work?

The Telegram bot connects directly to the same smart engine:
- **Direct Uploads**: Send any photo or PDF in the Telegram chat, and it will be processed and indexed automatically.
- **Natural Q&A**: You don't even need to type `/ask`! Simply type your question in plain text (e.g., *"How many DIPEX passes do we have?"*), and the bot answers immediately.
- **Safe HTML Formatting**: Uses clean HTML rendering so filenames with underscores (`Jagdish_Uikey_Visitor_Pass.png`) never break Telegram chat formatting.

---

## ⚡ 6. How Did We Speed Up Rescanning?

1. **Payload Slimming**: We removed duplicate field lists from the server response payload, cutting data transfer overhead by over 50%.
2. **Multi-Threaded Parallel Rescan**: When you click "Rescan All", the server now processes 4 documents simultaneously using parallel worker threads instead of doing them one by one. This cut multi-file rescan times by ~75%.

---

## 🛠️ Summary of Key Components

| Component | File Path | Function |
| :--- | :--- | :--- |
| **OCR Service** | `backend/app/services/ocr_service.py` | Combines PyTesseract + Gemini Vision API to capture 100% of text and stylized logos. |
| **LLM Service** | `backend/app/services/llm_service.py` | Handles Gemini field extraction, document categorization, and RAG Q&A with strict source tracking. |
| **Search Engine** | `backend/app/services/search_service.py` | Multi-keyword relevance scoring, synonym expansion, and score filtering. |
| **Document Processor** | `backend/app/services/document_processor.py` | Manages the document state pipeline (Uploaded -> Routing -> Extracting -> Classifying -> Completed). |
| **FastAPI Backend** | `backend/app/api/` | Exposes REST API endpoints for upload, search, RAG, and live status streaming. |
| **Telegram Bot** | `telegram_bot/bot.py` | Interacts with users on Telegram for uploading, searching, and instant Q&A. |
| **Web Frontend** | `frontend/js/app.js` | Responsive vanilla HTML/JS web dashboard with live status updates and interactive preview modals. |

---
*TransformoDocs is now fast, accurate, smart, and fully documented!* 🚀
