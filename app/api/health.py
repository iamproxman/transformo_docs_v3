import shutil
import pytesseract
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.config import settings

router = APIRouter(tags=["health"])

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    # Check DB connection
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    # Check Tesseract binary
    tesseract_installed = shutil.which("tesseract") is not None

    return {
        "status": "healthy" if db_ok else "unhealthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "connected" if db_ok else "disconnected",
        "ocr_engine": "tesseract_ready" if tesseract_installed else "tesseract_missing",
        "gemini_ai": "configured" if bool(settings.GEMINI_API_KEY) else "free_heuristic_fallback",
        "telegram_bot": "configured" if bool(settings.TELEGRAM_BOT_TOKEN) else "disabled"
    }
