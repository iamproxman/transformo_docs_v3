import os
import io
import pymupdf as fitz
from PIL import Image

# Auto-configure TESSDATA_PREFIX and download eng.traineddata if missing
import urllib.request

custom_tessdata = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tessdata"))
os.makedirs(custom_tessdata, exist_ok=True)

eng_traineddata_path = os.path.join(custom_tessdata, "eng.traineddata")
if not os.path.exists(eng_traineddata_path):
    print("Downloading Tesseract eng.traineddata...")
    try:
        urllib.request.urlretrieve(
            "https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata",
            eng_traineddata_path
        )
        print("Tesseract eng.traineddata downloaded successfully.")
    except Exception as e:
        print(f"Failed to download eng.traineddata: {e}")

os.environ["TESSDATA_PREFIX"] = custom_tessdata

import pytesseract
from typing import Tuple, List, Dict, Any
from app.models.models import SourceKind


class OCRService:
    """
    Handles PDF text layer probing, PyMuPDF native extraction, 
    and PyTesseract / Gemini Vision OCR for scanned images/PDFs with graceful fallbacks.
    """

    def probe_pdf(self, pdf_path: str) -> Tuple[SourceKind, int, str, float]:
        """
        Probes a PDF to check if it has a native text layer or requires OCR.
        Returns (SourceKind, page_count, extracted_text, mean_confidence).
        """
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        full_text_list = []
        total_chars = 0
        total_alphanumeric = 0

        for page in doc:
            text = page.get_text("text")
            full_text_list.append(text)
            total_chars += len(text)
            total_alphanumeric += sum(1 for c in text if c.isalnum())

        full_text = "\n".join(full_text_list).strip()

        # If average alphanumeric characters per page > 15, it's native text
        if page_count > 0 and (total_alphanumeric / page_count) > 15:
            return SourceKind.NATIVE_PDF, page_count, full_text, 0.99
        else:
            return SourceKind.SCANNED_PDF, page_count, full_text, 0.85

    def extract_text_from_image(self, image_path: str) -> Tuple[str, float]:
        """
        Runs PyTesseract OCR on an image file with fallback to Gemini Vision OCR and PIL analysis.
        """
        tesseract_text = ""
        mean_conf = 0.80

        # Attempt 1: PyTesseract
        try:
            img = Image.open(image_path)
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            text_tokens = []
            confidences = []

            for i in range(len(data['text'])):
                token = data['text'][i].strip()
                conf = int(data['conf'][i])
                if token:
                    text_tokens.append(token)
                    if conf > 0:
                        confidences.append(conf)

            tesseract_text = " ".join(text_tokens)
            if confidences:
                mean_conf = (sum(confidences) / len(confidences)) / 100.0
        except Exception:
            tesseract_text = ""

        if len(tesseract_text.strip()) >= 15:
            return tesseract_text, mean_conf

        # Attempt 2: Gemini Vision API OCR
        try:
            from app.services.llm_service import llm_service
            gemini_ocr_text = llm_service.ocr_image_with_gemini(image_path)
            if gemini_ocr_text and len(gemini_ocr_text.strip()) >= 10:
                return gemini_ocr_text, 0.95
        except Exception:
            pass

        # Attempt 3: If tesseract yielded any tokens (even short), return them
        if tesseract_text.strip():
            return tesseract_text, mean_conf

        filename = os.path.basename(image_path)
        return f"Document Image: {filename}", 0.70

    def extract_scanned_pdf(self, pdf_path: str, pages_dir: str) -> Tuple[str, float]:
        """
        Renders PDF pages as images and runs multi-level OCR on each page.
        """
        doc = fitz.open(pdf_path)
        page_texts = []
        confidences = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            native_text = page.get_text("text")
            if len(native_text.strip()) > 10:
                page_texts.append(f"--- Page {page_num+1} ---\n{native_text.strip()}")
                confidences.append(0.95)
            else:
                pix = page.get_pixmap(dpi=200)
                img_path = os.path.join(pages_dir, f"page-{page_num+1:04d}.png")
                pix.save(img_path)

                text, conf = self.extract_text_from_image(img_path)
                if text:
                    page_texts.append(f"--- Page {page_num+1} ---\n{text}")
                    confidences.append(conf)

        full_text = "\n\n".join(page_texts)
        mean_conf = (sum(confidences) / len(confidences)) if confidences else 0.80
        return full_text, mean_conf


ocr_service = OCRService()

