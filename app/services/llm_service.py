import os
import json
import re
from typing import Dict, Any, List

try:
    from google import genai as new_genai
    from google.genai import types as genai_types
    USING_NEW_SDK = True
except ImportError:
    import google.generativeai as old_genai
    USING_NEW_SDK = False

from app.config import settings


class LLMService:
    MODEL_CANDIDATES = [
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro-latest",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-pro",
    ]

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key and USING_NEW_SDK:
            self._client = new_genai.Client(api_key=self.api_key)
        elif self.api_key and not USING_NEW_SDK:
            old_genai.configure(api_key=self.api_key)
            self._client = None
        else:
            self._client = None

    # ------------------------------------------------------------------ #
    #  Internal: try each model candidate until one succeeds              #
    # ------------------------------------------------------------------ #
    def _generate(self, prompt: str, json_mode: bool = False) -> str:
        """Try each model candidate; return raw text or raise on all failures."""
        for model_name in self.MODEL_CANDIDATES:
            try:
                if USING_NEW_SDK and self._client:
                    kwargs = {"model": model_name, "contents": prompt}
                    if json_mode:
                        kwargs["config"] = new_genai.types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                    response = self._client.models.generate_content(**kwargs)
                    return response.text
                elif not USING_NEW_SDK:
                    model = old_genai.GenerativeModel(model_name)
                    gen_cfg = {"response_mime_type": "application/json"} if json_mode else {}
                    response = model.generate_content(prompt, generation_config=gen_cfg or None)
                    return response.text
            except Exception:
                continue
        raise RuntimeError("All Gemini model candidates failed.")

    def ocr_image_with_gemini(self, image_path: str) -> str:
        """Performs multi-modal Vision OCR using Gemini on an image file."""
        if not self.api_key:
            return ""

        prompt = "Perform complete OCR on this image. Extract all text verbatim line by line, maintaining structure, table headers, and key-value fields."

        for model_name in self.MODEL_CANDIDATES:
            try:
                if USING_NEW_SDK and self._client:
                    with open(image_path, "rb") as f:
                        image_bytes = f.read()
                    mime_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
                    part = new_genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                    response = self._client.models.generate_content(
                        model=model_name,
                        contents=[part, prompt]
                    )
                    if response and response.text:
                        return response.text
                elif not USING_NEW_SDK:
                    from PIL import Image
                    img = Image.open(image_path)
                    model = old_genai.GenerativeModel(model_name)
                    response = model.generate_content([img, prompt])
                    if response and response.text:
                        return response.text
            except Exception:
                continue
        return ""

    @staticmethod
    def _strip_json_fences(text: str) -> str:
        """Remove markdown ``` code fences if Gemini wraps JSON in them."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\n?```$", "", text)
        return text.strip()

    # ------------------------------------------------------------------ #
    #  Public: structured field extraction                                #
    # ------------------------------------------------------------------ #
    def extract_structured_fields(self, document_text: str, filename: str) -> Dict[str, Any]:
        if self.api_key:
            prompt = f"""
You are an enterprise document intelligence engine.
Analyze the document content below (Filename: {filename}) and return ONLY valid JSON.

Required structure:
{{
  "doc_type": "MEDICAL_RECORD | HOSPITAL_BILL | INVOICE | RECEIPT | RESUME | CONTRACT | KYC | FINANCIAL_REPORT | TECHNICAL_DOC | OTHER",
  "doc_type_confidence": 0.95,
  "summary": "1–2 sentence summary detailing what this document is about",
  "extracted_fields": [
    {{
      "field_key": "hospitalName | patientName | doctorName | medicalRecordNumber | invoiceNumber | vendorName | billedTo | totalAmount | documentDate | contactEmail",
      "field_label": "Human Readable Label",
      "data_type": "STRING | NUMBER | DATE",
      "value_text": "extracted value",
      "value_number": null,
      "value_date": null,
      "currency_code": "USD | INR | EUR | null",
      "confidence": 0.95,
      "page_no": 1
    }}
  ]
}}

Document:
\"\"\"
{document_text[:8000]}
\"\"\"
"""
            try:
                raw = self._generate(prompt, json_mode=True)
                raw = self._strip_json_fences(raw)
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and "doc_type" in parsed:
                    return parsed
            except Exception:
                pass  # fall through to heuristic

        return self._heuristic_extraction(document_text, filename)

    # ------------------------------------------------------------------ #
    #  Public: RAG Q&A                                                    #
    # ------------------------------------------------------------------ #
    def answer_rag_question(self, question: str, documents_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        context_str = ""
        sources = []
        for idx, doc in enumerate(documents_context):
            fn = doc.get("filename", f"Doc-{idx+1}")
            doc_id = doc.get("id", "")
            snippet = doc.get("full_text", "")[:3000]
            context_str += f"\n--- DOCUMENT {idx+1}: {fn} (ID: {doc_id}) ---\n{snippet}\n"
            sources.append({"document_id": doc_id, "filename": fn})

        if self.api_key:
            prompt = f"""
You are TransformoDocs RAG Assistant.
Answer the user's question ONLY from the document context below.
If the answer is not in the context, say so explicitly.

Context:
{context_str}

Question: {question}

Respond concisely in markdown.
"""
            try:
                answer = self._generate(prompt, json_mode=False)
                return {"question": question, "answer": answer, "sources": sources, "confidence": 0.95}
            except Exception:
                pass

        # Keyword-match fallback
        answer = f"Found {len(documents_context)} document(s):\n\n"
        for doc in documents_context:
            fn = doc.get("filename", "Document")
            text = doc.get("full_text", "")
            matches = [l for l in text.split("\n") if any(w.lower() in l.lower() for w in question.split())]
            if matches:
                answer += f"**{fn}:**\n> " + "\n> ".join(matches[:3]) + "\n\n"
            else:
                answer += f"**{fn}:** {text[:200]}...\n\n"
        answer += "\n*(Add your Gemini API key in `.env` to enable deep AI answers.)*"
        return {"question": question, "answer": answer, "sources": sources, "confidence": 0.75}

    # ------------------------------------------------------------------ #
    #  Internal: rule-based heuristic extraction                         #
    # ------------------------------------------------------------------ #
    def _heuristic_extraction(self, text: str, filename: str) -> Dict[str, Any]:
        lower = (text + " " + filename).lower()
        doc_type = "OTHER"
        fields = []

        # 1. Classification
        if any(w in lower for w in ["hospital", "patient", "discharge summary", "mrn-", "attending physician", "medical center", "clinic", "cardiology", "icu room"]):
            if "bill" in lower or "charge" in lower or "invoice" in lower:
                doc_type = "HOSPITAL_BILL"
            else:
                doc_type = "MEDICAL_RECORD"
        elif "invoice" in lower or "bill to" in lower or "subtotal" in lower or "tax invoice" in lower:
            doc_type = "INVOICE"
        elif "receipt" in lower or "payment received" in lower or "transaction id" in lower:
            doc_type = "RECEIPT"
        elif "resume" in lower or "curriculum vitae" in lower or ("education" in lower and "experience" in lower):
            doc_type = "RESUME"
        elif "agreement" in lower or "contract" in lower or "nda" in lower:
            doc_type = "CONTRACT"
        elif "algorithm" in lower or "specification" in lower or "pseudocode" in lower or "technical" in lower:
            doc_type = "TECHNICAL_DOC"

        # 2. Medical / Hospital Field Extraction
        if doc_type in ["MEDICAL_RECORD", "HOSPITAL_BILL"] or "hospital" in lower or "clinic" in lower:
            hosp_match = re.search(r'([A-Za-z0-9\s\.\&\-]{3,50}(?:Hospital|Clinic|Medical Center|Care Center|Health System))', text, re.IGNORECASE)
            if hosp_match:
                h_name = hosp_match.group(1).strip()
                fields.append({
                    "field_key": "hospitalName", "field_label": "Hospital / Clinic Name",
                    "data_type": "STRING", "value_text": h_name, "confidence": 0.95, "page_no": 1
                })

            pat_match = re.search(r'(?:Patient Name|Patient|Name):\s*([A-Za-z\s\.]+)', text, re.IGNORECASE)
            if pat_match:
                p_name = pat_match.group(1).strip().split('\n')[0]
                if len(p_name) > 2 and len(p_name) < 50:
                    fields.append({
                        "field_key": "patientName", "field_label": "Patient Name",
                        "data_type": "STRING", "value_text": p_name, "confidence": 0.92, "page_no": 1
                    })

            doc_match = re.search(r'(?:Attending Physician|Physician|Doctor|Dr\.):\s*([A-Za-z\s\.,]+)', text, re.IGNORECASE)
            if doc_match:
                d_name = doc_match.group(1).strip().split('\n')[0]
                fields.append({
                    "field_key": "doctorName", "field_label": "Attending Doctor / Physician",
                    "data_type": "STRING", "value_text": d_name, "confidence": 0.90, "page_no": 1
                })

            mrn_match = re.search(r'(?:MRN|Patient ID|Record #|Registration No):\s*([A-Za-z0-9\-]+)', text, re.IGNORECASE)
            if mrn_match:
                fields.append({
                    "field_key": "medicalRecordNumber", "field_label": "Medical Record Number (MRN)",
                    "data_type": "STRING", "value_text": mrn_match.group(1).strip(), "confidence": 0.95, "page_no": 1
                })

        # 3. Invoice / Vendor Extraction
        inv_match = re.search(r'(?:Invoice No|Invoice #|Bill No|Bill #):\s*([A-Za-z0-9\-]+)', text, re.IGNORECASE)
        if inv_match:
            fields.append({
                "field_key": "invoiceNumber", "field_label": "Invoice Number",
                "data_type": "STRING", "value_text": inv_match.group(1).strip(), "confidence": 0.95, "page_no": 1
            })

        vendor_match = re.search(r'([A-Za-z0-9\s]{3,40}(?:Inc|LLC|Solutions|Corp|Enterprises|Technologies|Center))', text)
        if vendor_match:
            fields.append({
                "field_key": "vendorName", "field_label": "Vendor / Organization Name",
                "data_type": "STRING", "value_text": vendor_match.group(1).strip(), "confidence": 0.88, "page_no": 1
            })

        # 4. General Extractors (Email, Amounts, Dates)
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        if emails:
            fields.append({
                "field_key": "contactEmail", "field_label": "Contact Email",
                "data_type": "STRING", "value_text": emails[0], "confidence": 0.95, "page_no": 1
            })

        amounts = re.findall(r'\$\s*([0-9,]+\.?[0-9]{0,2})|₹\s*([0-9,]+\.?[0-9]{0,2})', text)
        if amounts:
            flat = next((a for tup in amounts for a in tup if a), None)
            if flat:
                try:
                    num = float(flat.replace(",", ""))
                    fields.append({
                        "field_key": "totalAmount", "field_label": "Total Amount",
                        "data_type": "NUMBER", "value_text": f"${num:,.2f}", "value_number": num,
                        "currency_code": "USD", "confidence": 0.90, "page_no": 1
                    })
                except ValueError:
                    pass

        dates = re.findall(r'\b\d{4}[-/]\d{2}[-/]\d{2}\b|\b\d{2}[-/]\d{2}[-/]\d{4}\b', text)
        if dates:
            fields.append({
                "field_key": "documentDate", "field_label": "Document Date",
                "data_type": "DATE", "value_text": dates[0], "value_date": dates[0],
                "confidence": 0.88, "page_no": 1
            })

        # Summary
        if text.strip():
            first_line = text.strip().split("\n")[0][:100]
            summary = f"{doc_type.replace('_', ' ').title()} document ({filename}). Content header: '{first_line}'"
        else:
            summary = f"{doc_type.replace('_', ' ').title()} document ({filename})."

        return {"doc_type": doc_type, "doc_type_confidence": 0.88, "summary": summary, "extracted_fields": fields}


llm_service = LLMService()

