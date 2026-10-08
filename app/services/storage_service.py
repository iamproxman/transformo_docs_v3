import os
import shutil
from typing import BinaryIO
from app.config import settings

class StorageService:
    def __init__(self, base_dir: str = settings.UPLOAD_DIR):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def get_document_path(self, org_id: str, document_id: str, filename: str) -> str:
        doc_dir = os.path.join(self.base_dir, "org", org_id, "raw", document_id)
        os.makedirs(doc_dir, exist_ok=True)
        return os.path.join(doc_dir, filename)

    def get_pages_dir(self, org_id: str, document_id: str) -> str:
        pages_dir = os.path.join(self.base_dir, "org", org_id, "raw", document_id, "pages")
        os.makedirs(pages_dir, exist_ok=True)
        return pages_dir

    def save_file(self, file_obj: BinaryIO, relative_key: str) -> str:
        full_path = os.path.join(self.base_dir, relative_key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as buffer:
            shutil.copyfileobj(file_obj, buffer)
        return full_path

    def read_file(self, relative_key: str) -> bytes:
        full_path = os.path.join(self.base_dir, relative_key)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {relative_key}")
        with open(full_path, "rb") as f:
            return f.read()

    def get_full_path(self, relative_key: str) -> str:
        full_path = os.path.join(self.base_dir, relative_key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        return full_path


storage_service = StorageService()
