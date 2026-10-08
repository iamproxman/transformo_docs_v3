import re
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from app.models.models import Document, DocumentText, ExtractedField, DocStatus
from typing import List, Dict, Any, Optional

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "in", "on", "at", "for", "to",
    "of", "with", "by", "from", "and", "or", "what", "who", "where", "which",
    "how", "show", "me", "find", "get", "give", "tell", "list", "all", "doc", "docs", "document"
}

class SearchService:
    def search_documents(
        self,
        db: Session,
        query: str = "",
        doc_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Deterministic, multi-keyword relevance search engine.
        Tokenizes query, strips conversational stopwords, matches against:
         - original_filename
         - DocumentText.full_text
         - ExtractedField (value_text, field_label, field_key)
         - Document.doc_type & structured_data summary
        Returns results ranked strictly by relevance score.
        """
        clean_query = query.strip()

        # Extract search tokens
        raw_tokens = re.findall(r'[a-zA-Z0-9\-\_]+', clean_query.lower())
        meaningful_tokens = [t for t in raw_tokens if t not in STOPWORDS]
        if not meaningful_tokens and raw_tokens:
            meaningful_tokens = raw_tokens

        # Base document query
        q = db.query(Document).options(
            joinedload(Document.extracted_fields),
            joinedload(Document.text_entry)
        )
        if status:
            try:
                q = q.filter(Document.status == DocStatus(status))
            except ValueError:
                pass
        if doc_type:
            q = q.filter(Document.doc_type == doc_type)

        all_docs = q.all()

        # Case 1: Empty search query -> Return recent documents
        if not clean_query or not raw_tokens:
            recent_docs = sorted(all_docs, key=lambda d: d.created_at, reverse=True)[:limit]
            output = []
            for doc in recent_docs:
                full_text = doc.text_entry.full_text if doc.text_entry and doc.text_entry.full_text else ""
                output.append({
                    "document_id": doc.id,
                    "filename": doc.original_filename,
                    "doc_type": doc.doc_type,
                    "snippet": self._extract_snippet(full_text, ""),
                    "score": 1.0,
                    "created_at": doc.created_at,
                    "extracted_summary": doc.structured_data,
                })
            return output

        # Case 2: Query provided -> Strictly match tokens & rank by score
        output = []

        for doc in all_docs:
            full_text = doc.text_entry.full_text if doc.text_entry and doc.text_entry.full_text else ""
            fields = doc.extracted_fields or []

            full_text_lower = full_text.lower()
            fn_lower = (doc.original_filename or "").lower()
            dt_lower = (doc.doc_type or "").lower()
            json_str = str(doc.structured_data or {}).lower()

            matched_field_str = ""
            score = 0.0
            matched_token_count = 0

            # 1. Full query string exact match bonus (+0.40)
            if clean_query.lower() in full_text_lower or clean_query.lower() in fn_lower:
                score += 0.40

            # 2. Match each token across all document attributes
            for token in meaningful_tokens:
                token_matched = False

                # Extracted Fields match (+0.35)
                for f in fields:
                    val_str = (f.value_text or "").lower()
                    lbl_str = (f.field_label or "").lower()
                    key_str = (f.field_key or "").lower()
                    if token in val_str or token in lbl_str or token in key_str:
                        score += 0.35
                        if not matched_field_str and f.field_label and f.value_text:
                            matched_field_str = f"Matched '{f.field_label}': {f.value_text}"
                        token_matched = True
                        break

                if not token_matched:
                    # Doc Type match (+0.30)
                    if token in dt_lower or (token == "hospital" and dt_lower in ["medical_record", "hospital_bill"]):
                        score += 0.30
                        token_matched = True

                if not token_matched:
                    # Full Text match (+0.25 + frequency bonus)
                    if token in full_text_lower:
                        freq = full_text_lower.count(token)
                        score += 0.25 + min(freq * 0.03, 0.15)
                        token_matched = True

                if not token_matched:
                    # Filename match (+0.20)
                    if token in fn_lower:
                        score += 0.20
                        token_matched = True

                if not token_matched:
                    # Structured JSON match (+0.20)
                    if token in json_str:
                        score += 0.20
                        token_matched = True

                if token_matched:
                    matched_token_count += 1

            # IF NO TOKENS MATCHED, EXCLUDE THIS DOCUMENT ENTIRELY
            if matched_token_count == 0:
                continue

            # Token coverage ratio boost (+0.30)
            score += (matched_token_count / len(meaningful_tokens)) * 0.30

            # Normalize score to [0, 1] range to prevent overflow
            max_possible = 0.40 + len(meaningful_tokens) * 0.35 + 0.30
            score = min(round(score / max(max_possible, 1.0), 4), 0.99)

            snippet = matched_field_str if matched_field_str else self._extract_snippet(full_text, clean_query, meaningful_tokens)

            output.append({
                "document_id": doc.id,
                "filename": doc.original_filename,
                "doc_type": doc.doc_type,
                "snippet": snippet,
                "score": score,
                "created_at": doc.created_at,
                "extracted_summary": doc.structured_data,
            })

        # Sort strictly by relevance score DESCENDING
        output.sort(key=lambda x: x["score"], reverse=True)
        return output[:limit]

    @staticmethod
    def _extract_snippet(full_text: str, query: str, tokens: List[str] = None, context: int = 180) -> str:
        """Extract a relevant snippet around matching search terms."""
        if not full_text:
            return ""
        text = full_text.strip()
        if not query and not tokens:
            return text[:context] + ("…" if len(text) > context else "")

        search_terms = (tokens or []) + [query.lower()]
        idx = -1
        for term in search_terms:
            if not term or len(term) < 2:
                continue
            pos = text.lower().find(term)
            if pos != -1:
                idx = pos
                break

        if idx == -1:
            return text[:context] + ("…" if len(text) > context else "")

        start = max(0, idx - 60)
        end = min(len(text), idx + context)
        snippet = ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")
        return snippet


search_service = SearchService()


