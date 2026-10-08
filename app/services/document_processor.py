import os
import time
import datetime
from sqlalchemy.orm import Session
from app.models.models import (
    Document, DocumentText, ExtractedField, DocStatus, SourceKind, JobEvent, ProcessingJob
)
from app.services.storage_service import storage_service
from app.services.ocr_service import ocr_service
from app.services.llm_service import llm_service

class DocumentProcessor:

    def record_event(self, db: Session, doc_id: str, from_status: str, to_status: str, message: str, payload: dict = None):
        """Writes an immutable audit log record to job_events."""
        event = JobEvent(
            document_id=doc_id,
            from_status=from_status,
            to_status=to_status,
            message=message,
            payload=payload
        )
        db.add(event)
        db.commit()

    def process_document_by_id(self, doc_id: str):
        """Helper for background tasks to create and close its own fresh DB session."""
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            self.process_document(db, doc_id)
        finally:
            db.close()

    def process_document(self, db: Session, doc_id: str):
        """
        Executes the async document processing state machine:
        UPLOADED -> QUEUED -> ROUTING -> EXTRACTING -> CLASSIFYING -> PARSING -> INDEXING -> COMPLETED
        """
        start_time = time.time()
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return

        try:
            # 1. QUEUED -> ROUTING
            self.record_event(db, doc_id, doc.status.value, DocStatus.ROUTING.value, "Starting layout probe & routing")
            doc.status = DocStatus.ROUTING
            db.commit()

            file_full_path = storage_service.get_full_path(doc.storage_key)
            if not os.path.exists(file_full_path):
                raise FileNotFoundError(f"Physical document file missing on disk: {doc.original_filename}")

            pages_dir = storage_service.get_pages_dir(doc.org_id, doc.id)

            extracted_text = ""
            source_kind = SourceKind.UNKNOWN
            ocr_conf = 0.95

            if doc.mime_type == "application/pdf":
                source_kind, page_count, native_text, conf = ocr_service.probe_pdf(file_full_path)
                doc.page_count = page_count
                doc.source_kind = source_kind

                if source_kind == SourceKind.NATIVE_PDF:
                    extracted_text = native_text
                    ocr_conf = conf
                else:
                    # 2. ROUTING -> EXTRACTING (Scanned PDF OCR)
                    self.record_event(db, doc_id, DocStatus.ROUTING.value, DocStatus.EXTRACTING.value, "Running Tesseract OCR on scanned PDF")
                    doc.status = DocStatus.EXTRACTING
                    db.commit()

                    extracted_text, ocr_conf = ocr_service.extract_scanned_pdf(file_full_path, pages_dir)
            else:
                # Image file (PNG / JPG / WEBP)
                doc.source_kind = SourceKind.IMAGE
                doc.page_count = 1
                self.record_event(db, doc_id, DocStatus.ROUTING.value, DocStatus.EXTRACTING.value, "Running Tesseract OCR on document image")
                doc.status = DocStatus.EXTRACTING
                db.commit()

                extracted_text, ocr_conf = ocr_service.extract_text_from_image(file_full_path)

            doc.ocr_mean_confidence = ocr_conf

            # Save full text record
            doc_text_entry = db.query(DocumentText).filter(DocumentText.document_id == doc_id).first()
            if not doc_text_entry:
                doc_text_entry = DocumentText(
                    document_id=doc_id,
                    full_text=extracted_text,
                    char_count=len(extracted_text),
                    word_count=len(extracted_text.split())
                )
                db.add(doc_text_entry)
            else:
                doc_text_entry.full_text = extracted_text
                doc_text_entry.char_count = len(extracted_text)
                doc_text_entry.word_count = len(extracted_text.split())

            # 3. EXTRACTING -> CLASSIFYING & PARSING
            self.record_event(db, doc_id, DocStatus.EXTRACTING.value, DocStatus.CLASSIFYING.value, "Extracting structured JSON fields with LLM Engine")
            doc.status = DocStatus.CLASSIFYING
            db.commit()

            # Call Gemini AI / Heuristic Extraction engine
            ai_payload = llm_service.extract_structured_fields(extracted_text, doc.original_filename)

            doc.doc_type = ai_payload.get("doc_type", "OTHER")
            doc.doc_type_confidence = ai_payload.get("doc_type_confidence", 0.90)
            doc.structured_data = ai_payload

            # 4. Save Extracted Fields into typed product table
            db.query(ExtractedField).filter(ExtractedField.document_id == doc_id).delete()
            for field in ai_payload.get("extracted_fields", []):
                field_obj = ExtractedField(
                    document_id=doc_id,
                    field_key=field.get("field_key"),
                    field_label=field.get("field_label"),
                    data_type=field.get("data_type", "STRING"),
                    value_text=field.get("value_text"),
                    value_number=field.get("value_number"),
                    value_date=field.get("value_date"),
                    value_bool=field.get("value_bool"),
                    currency_code=field.get("currency_code"),
                    confidence=field.get("confidence", 0.90),
                    page_no=field.get("page_no", 1),
                    extractor="GEMINI_AI"
                )
                db.add(field_obj)

            # 5. INDEXING -> COMPLETED
            doc.status = DocStatus.INDEXING
            db.commit()

            doc.status = DocStatus.COMPLETED
            doc.processing_ms = int((time.time() - start_time) * 1000)
            doc.completed_at = datetime.datetime.utcnow()
            doc.indexed_at = datetime.datetime.utcnow()

            self.record_event(db, doc_id, DocStatus.INDEXING.value, DocStatus.COMPLETED.value, "Document processing completed successfully")
            db.commit()

        except Exception as e:
            db.rollback()
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.status = DocStatus.FAILED
                doc.status_message = str(e)
                self.record_event(db, doc_id, "PROCESSING", DocStatus.FAILED.value, f"Processing failed: {str(e)}")
                db.commit()

document_processor = DocumentProcessor()
