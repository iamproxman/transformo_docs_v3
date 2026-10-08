from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.models import Document, DocumentText, DocStatus
from app.schemas.schemas import SearchResultItem, RAGAskRequest, RAGAskResponse
from app.services.search_service import search_service
from app.services.llm_service import llm_service

router = APIRouter(prefix="/search", tags=["search"])

@router.get("", response_model=List[SearchResultItem])
def search_documents(
    q: str = Query("", description="Search term or query"),
    doc_type: Optional[str] = Query(None, description="Filter by document type (e.g. INVOICE)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Deterministic hybrid text & field search across ingested documents.
    """
    results = search_service.search_documents(db, query=q, doc_type=doc_type, status=status, limit=limit)
    return results

@router.post("/ask", response_model=RAGAskResponse)
def ask_rag_question(req: RAGAskRequest, db: Session = Depends(get_db)):
    """
    RAG Chatbot Q&A endpoint. 
    Retrieves matching documents in strict relevance score order and uses AI/NLP to answer questions grounded in context.
    """
    if not req.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    docs = []
    if req.document_ids:
        docs_db = db.query(Document).filter(Document.id.in_(req.document_ids)).all()
        doc_map = {d.id: d for d in docs_db}
        for doc_id in req.document_ids:
            if doc_id in doc_map:
                doc = doc_map[doc_id]
                docs.append({
                    "id": doc.id,
                    "filename": doc.original_filename,
                    "full_text": doc.text_entry.full_text if doc.text_entry else ""
                })
    else:
        # Search relevant documents ranked by relevance score
        search_results = search_service.search_documents(db, query=req.question, limit=10)
        doc_ids = [r["document_id"] for r in search_results]
        
        if doc_ids:
            docs_db = db.query(Document).filter(Document.id.in_(doc_ids)).all()
            doc_map = {d.id: d for d in docs_db}
            # Maintain exact score-ranked order
            for r in search_results:
                did = r["document_id"]
                if did in doc_map:
                    doc = doc_map[did]
                    docs.append({
                        "id": doc.id,
                        "filename": doc.original_filename,
                        "full_text": doc.text_entry.full_text if doc.text_entry else ""
                    })
        else:
            # Fallback to recent documents if no direct query match
            docs_db = db.query(Document).order_by(Document.created_at.desc()).limit(10).all()
            for doc in docs_db:
                docs.append({
                    "id": doc.id,
                    "filename": doc.original_filename,
                    "full_text": doc.text_entry.full_text if doc.text_entry else ""
                })

    if not docs:
        return RAGAskResponse(
            question=req.question,
            answer="No documents found in your library yet. Upload a document to start asking questions!",
            sources=[],
            confidence=1.0
        )

    response = llm_service.answer_rag_question(req.question, docs)
    return RAGAskResponse(**response)

