from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.models import DocStatus, SourceKind

class DocumentInitRequest(BaseModel):
    filename: str
    size_bytes: int
    mime_type: str
    sha256: str

class DocumentInitResponse(BaseModel):
    document_id: str
    status: DocStatus
    deduped: bool = False
    upload_url: Optional[str] = None
    expires_in: int = 900

class ExtractedFieldSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    field_key: str
    field_label: Optional[str] = None
    data_type: str
    value_text: Optional[str] = None
    value_number: Optional[float] = None
    value_date: Optional[str] = None
    value_bool: Optional[str] = None
    currency_code: Optional[str] = None
    confidence: Optional[float] = None
    page_no: Optional[int] = None
    bbox: Optional[Dict[str, Any]] = None
    extractor: str
    is_verified: bool

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    source_kind: SourceKind
    page_count: Optional[int] = None
    doc_type: Optional[str] = None
    doc_type_confidence: Optional[float] = None
    ocr_mean_confidence: Optional[float] = None
    status: DocStatus
    status_message: Optional[str] = None
    processing_ms: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    extracted_fields: List[ExtractedFieldSchema] = []
    structured_data: Optional[Dict[str, Any]] = None
    full_text: Optional[str] = None

class SearchRequest(BaseModel):
    query: str
    doc_type: Optional[str] = None
    status: Optional[DocStatus] = None
    page: int = 1
    limit: int = 20

class SearchResultItem(BaseModel):
    document_id: str
    filename: str
    doc_type: Optional[str] = None
    snippet: str
    score: float
    created_at: datetime
    extracted_summary: Optional[Dict[str, Any]] = None

class RAGAskRequest(BaseModel):
    question: str
    document_ids: Optional[List[str]] = None

class RAGAskResponse(BaseModel):
    question: str
    answer: str
    sources: List[Dict[str, Any]] = []
    confidence: float = 0.95
