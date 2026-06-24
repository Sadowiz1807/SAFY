from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .contracts import RetrievalDocument, RetrievalResult

def tokenize(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ỹ]+", (text or "").lower(), re.UNICODE)

class LexicalRetriever:
    def __init__(self, documents: list[dict[str, Any]]):
        self.documents = documents
        self.doc_tokens = [Counter(tokenize(d.get("text", ""))) for d in documents]
        self.df = Counter()
        for counts in self.doc_tokens:
            self.df.update(counts.keys())
        self.n = max(1, len(documents))

    def search(self, query: str, *, domain_id: str, top_k: int = 6, document_types: set[str] | None = None, database_type: str | None = None) -> RetrievalResult:
        q = Counter(tokenize(query))
        scored: list[tuple[float, dict[str, Any]]] = []
        for doc, counts in zip(self.documents, self.doc_tokens):
            if doc.get("domain_id") != domain_id:
                continue
            if document_types and doc.get("document_type") not in document_types:
                continue
            if database_type and doc.get("database_type") not in {None, database_type, "null"}:
                continue
            score = 0.0
            for term, qtf in q.items():
                tf = counts.get(term, 0)
                if not tf:
                    continue
                idf = math.log((self.n + 1) / (self.df.get(term, 0) + 0.5)) + 1
                score += (1 + math.log(tf)) * idf * qtf
            if score:
                scored.append((score + float(doc.get("quality_score") or 0), doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        docs = [RetrievalDocument(**d) for _, d in scored[:top_k]]
        return RetrievalResult(domain_id=domain_id, query=query, documents=docs)
