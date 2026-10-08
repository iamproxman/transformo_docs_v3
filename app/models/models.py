import uuid
import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum, JSON, Table
)
from sqlalchemy.orm import relationship
import enum
from app.database import Base

class DocStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    ROUTING = "ROUTING"
    EXTRACTING = "EXTRACTING"
    CLASSIFYING = "CLASSIFYING"
    PARSING = "PARSING"
    INDEXING = "INDEXING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"

class SourceKind(str, enum.Enum):
    NATIVE_PDF = "NATIVE_PDF"
    SCANNED_PDF = "SCANNED_PDF"
    HYBRID_PDF = "HYBRID_PDF"
    IMAGE = "IMAGE"
    OFFICE = "OFFICE"
    UNKNOWN = "UNKNOWN"

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    storage_quota_bytes = Column(Integer, default=10737418240) # 10 GB
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="USER")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    storage_bucket = Column(String(255), default="transformo-docs")
    storage_key = Column(String(512), nullable=False)
    source_kind = Column(SQLEnum(SourceKind), default=SourceKind.UNKNOWN)
    page_count = Column(Integer, nullable=True)
    detected_languages = Column(JSON, nullable=True)
    doc_type = Column(String(100), nullable=True) # e.g., INVOICE, KYC, RESUME, CONTRACT
    doc_type_confidence = Column(Float, nullable=True)
    structured_data = Column(JSON, nullable=True) # Whole extracted JSON payload
    ocr_mean_confidence = Column(Float, nullable=True)
    status = Column(SQLEnum(DocStatus), default=DocStatus.UPLOADED, nullable=False)
    status_message = Column(Text, nullable=True)
    processing_ms = Column(Integer, nullable=True)
    indexed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    text_entry = relationship("DocumentText", back_populates="document", uselist=False, cascade="all, delete-orphan")
    extracted_fields = relationship("ExtractedField", back_populates="document", cascade="all, delete-orphan")
    job_events = relationship("JobEvent", back_populates="document", cascade="all, delete-orphan")

    @property
    def full_text(self):
        """Provides access to extracted full text via the text_entry relationship."""
        return self.text_entry.full_text if self.text_entry else None

class DocumentText(Base):
    __tablename__ = "document_text"

    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    full_text = Column(Text, nullable=True)
    full_text_key = Column(String(512), nullable=True)
    char_count = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    document = relationship("Document", back_populates="text_entry")

class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    field_key = Column(String(100), nullable=False)
    field_label = Column(String(255), nullable=True)
    data_type = Column(String(50), nullable=False, default="STRING") # STRING, NUMBER, DATE, BOOL
    value_text = Column(Text, nullable=True)
    value_number = Column(Float, nullable=True)
    value_date = Column(String(50), nullable=True)
    value_bool = Column(Boolean, nullable=True)
    currency_code = Column(String(10), nullable=True)
    confidence = Column(Float, nullable=True)
    page_no = Column(Integer, nullable=True)
    bbox = Column(JSON, nullable=True)
    extractor = Column(String(100), default="GEMINI_AI")
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    document = relationship("Document", back_populates="extracted_fields")

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    job_type = Column(String(100), nullable=False, default="PROCESS_DOCUMENT")
    status = Column(String(50), default="PENDING")
    attempt = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    idempotency_key = Column(String(255), unique=True, nullable=False)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class JobEvent(Base):
    __tablename__ = "job_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(String(36), ForeignKey("processing_jobs.id", ondelete="SET NULL"), nullable=True)
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    document = relationship("Document", back_populates="job_events")
