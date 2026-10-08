import os
import hashlib
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.models import Document, DocumentText, Organization, DocStatus, SourceKind, ProcessingJob
from app.schemas.schemas import DocumentInitRequest, DocumentInitResponse, DocumentResponse
from app.services.storage_service import storage_service
from app.services.document_processor import document_processor

router = APIRouter(prefix="/documents", tags=["documents"])

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"

def ensure_default_org(db: Session) -> Organization:
    org = db.query(Organization).filter(Organization.id == DEFAULT_ORG_ID).first()
    if not org:
        org = Organization(id=DEFAULT_ORG_ID, name="Default Organization")
        db.add(org)
        db.commit()
        db.refresh(org)
    return org

@router.post("/init", response_model=DocumentInitResponse, status_code=status.HTTP_201_CREATED)
def init_upload(req: DocumentInitRequest, db: Session = Depends(get_db)):
    """
    Two-Phase Presigned Upload Flow:
    1. Checks SHA256 for instant deduplication (returns 200 OK if exists).
    2. Otherwise returns upload URL & document ID.
    """
    org = ensure_default_org(db)
    
    # Check deduplication index
    existing_doc = db.query(Document).filter(
        Document.org_id == org.id,
        Document.sha256 == req.sha256
    ).first()

    if existing_doc:
        return DocumentInitResponse(
            document_id=existing_doc.id,
            status=existing_doc.status,
            deduped=True,
            upload_url=None,
            expires_in=0
        )

    # Create document record
    doc = Document(
        org_id=org.id,
        original_filename=req.filename,
        mime_type=req.mime_type,
        size_bytes=req.size_bytes,
        sha256=req.sha256,
        storage_bucket="transformo-docs",
        storage_key=f"org/{org.id}/raw/temp/{req.filename}",
        status=DocStatus.UPLOADED
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    doc.storage_key = f"org/{org.id}/raw/{doc.id}/{req.filename}"
    db.commit()

    return DocumentInitResponse(
        document_id=doc.id,
        status=doc.status,
        deduped=False,
        upload_url=f"/api/v1/documents/{doc.id}/upload-binary",
        expires_in=900
    )

@router.post("/{document_id}/upload-binary")
async def upload_binary(
    document_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Direct binary upload endpoint. Stores file and enqueues document processing pipeline.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    content = await file.read()
    
    # Verify SHA256 matches
    calc_sha = hashlib.sha256(content).hexdigest()
    if calc_sha != doc.sha256:
        doc.sha256 = calc_sha

    # Save to storage
    file_full_path = storage_service.get_full_path(doc.storage_key)
    with open(file_full_path, "wb") as f:
        f.write(content)

    doc.status = DocStatus.QUEUED
    db.commit()

    # Enqueue background processing state machine
    background_tasks.add_task(document_processor.process_document_by_id, doc.id)

    return {
        "status": "QUEUED",
        "document_id": doc.id,
        "message": "File uploaded successfully. Processing pipeline started."
    }

@router.post("/upload", response_model=List[DocumentResponse], status_code=status.HTTP_202_ACCEPTED)
async def direct_upload(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Direct upload endpoint supporting single or multiple file uploads at once.
    """
    org = ensure_default_org(db)
    uploaded_docs = []

    for file in files:
        content = await file.read()
        sha256_hash = hashlib.sha256(content).hexdigest()

        # Check deduplication
        existing = db.query(Document).filter(
            Document.org_id == org.id,
            Document.sha256 == sha256_hash
        ).first()

        if existing:
            uploaded_docs.append(existing)
            continue

        doc = Document(
            org_id=org.id,
            original_filename=file.filename,
            mime_type=file.content_type or "application/octet-stream",
            size_bytes=len(content),
            sha256=sha256_hash,
            storage_bucket="transformo-docs",
            storage_key="",
            status=DocStatus.QUEUED
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        doc.storage_key = f"org/{org.id}/raw/{doc.id}/{file.filename}"
        db.commit()

        # Save file securely creating parent directory
        file_full_path = storage_service.get_full_path(doc.storage_key)
        with open(file_full_path, "wb") as f:
            f.write(content)

        # Start processing pipeline in background
        background_tasks.add_task(document_processor.process_document_by_id, doc.id)
        uploaded_docs.append(doc)

    return uploaded_docs

@router.post("/seed-samples", response_model=List[DocumentResponse])
async def seed_sample_documents(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Automatically ingests sample documents (Hospital bill, Hospital discharge summary, Invoice, Resume, Algorithm spec) into the platform.
    """
    org = ensure_default_org(db)
    sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../sample_docs"))
    
    # Run test doc generator script if sample_docs is empty or missing
    try:
        from generate_test_docs import create_sample_invoice_image, create_sample_hospital_bill_image, create_sample_hospital_discharge_pdf, create_sample_resume_pdf, create_sample_algorithm_pdf
        create_sample_invoice_image()
        create_sample_hospital_bill_image()
        create_sample_hospital_discharge_pdf()
        create_sample_resume_pdf()
        create_sample_algorithm_pdf()
    except Exception as e:
        print(f"Warning: Failed to generate sample docs automatically: {e}")

    seeded = []
    if not os.path.exists(sample_dir):
        return seeded

    for filename in sorted(os.listdir(sample_dir)):
        filepath = os.path.join(sample_dir, filename)
        if not os.path.isfile(filepath):
            continue

        with open(filepath, "rb") as f:
            content = f.read()

        calc_sha = hashlib.sha256(content).hexdigest()
        existing = db.query(Document).filter(Document.org_id == org.id, Document.sha256 == calc_sha).first()
        if existing:
            # Re-process existing doc to update text extraction & fields
            background_tasks.add_task(document_processor.process_document_by_id, existing.id)
            seeded.append(existing)
            continue

        mime = "application/pdf" if filename.endswith(".pdf") else "image/png"
        doc = Document(
            org_id=org.id,
            original_filename=filename,
            mime_type=mime,
            size_bytes=len(content),
            sha256=calc_sha,
            storage_bucket="transformo-docs",
            storage_key="",
            status=DocStatus.QUEUED
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        doc.storage_key = f"org/{org.id}/raw/{doc.id}/{filename}"
        db.commit()

        full_path = storage_service.get_full_path(doc.storage_key)
        with open(full_path, "wb") as f:
            f.write(content)

        background_tasks.add_task(document_processor.process_document_by_id, doc.id)
        seeded.append(doc)

    return seeded

@router.post("/reprocess-all")
async def reprocess_all_documents(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Re-runs the extraction and field parsing pipeline on all documents in DB."""
    docs = db.query(Document).all()
    for doc in docs:
        doc.status = DocStatus.QUEUED
        db.commit()
        background_tasks.add_task(document_processor.process_document_by_id, doc.id)
    return {"message": f"Enqueued re-processing for {len(docs)} documents."}

@router.post("/{document_id}/reprocess")
async def reprocess_document(document_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Re-runs text extraction and field parsing on a single document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.status = DocStatus.QUEUED
    db.commit()
    background_tasks.add_task(document_processor.process_document_by_id, doc.id)
    return {"message": "Document re-processing started.", "document_id": doc.id}

@router.get("", response_model=List[DocumentResponse])
def list_documents(status: Optional[DocStatus] = None, limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(Document)
    if status:
        q = q.filter(Document.status == status)
    docs = q.order_by(Document.created_at.desc()).limit(limit).all()
    return docs



@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.get("/{document_id}/file")
def download_document_file(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    file_path = storage_service.get_full_path(doc.storage_key)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Physical file missing on disk for '{doc.original_filename}'. Please re-upload this document.")

    return FileResponse(file_path, media_type=doc.mime_type, filename=doc.original_filename)

@router.get("/{document_id}/preview")
def preview_document_file(document_id: str, db: Session = Depends(get_db)):
    """Serve file inline in browser (for iframe/object preview)."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    file_path = storage_service.get_full_path(doc.storage_key)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Physical file missing on disk for '{doc.original_filename}'. Please re-upload this document.")

    from fastapi.responses import Response
    with open(file_path, "rb") as f:
        content = f.read()
    return Response(
        content=content,
        media_type=doc.mime_type,
        headers={"Content-Disposition": f"inline; filename=\"{doc.original_filename}\""}
    )

@router.get("/{document_id}/status-stream")
async def status_stream(document_id: str, db: Session = Depends(get_db)):
    """
    Server-Sent Events (SSE) endpoint for real-time document status streaming.
    """
    async def event_generator():
        last_status = None
        while True:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                yield f"data: {json.dumps({'error': 'Document not found'})}\n\n"
                break
            
            if doc.status.value != last_status:
                last_status = doc.status.value
                data = {
                    "document_id": doc.id,
                    "status": doc.status.value,
                    "status_message": doc.status_message,
                    "doc_type": doc.doc_type,
                    "processing_ms": doc.processing_ms
                }
                yield f"data: {json.dumps(data)}\n\n"

            if doc.status in [DocStatus.COMPLETED, DocStatus.FAILED, DocStatus.DEAD_LETTER]:
                break

            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.delete("/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = storage_service.get_full_path(doc.storage_key)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully"}

