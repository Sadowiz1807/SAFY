from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from .cache import DomainCache
from .contracts import DomainContext
from .registry import DomainRegistry
from .retriever import LexicalRetriever
from .router import DomainRouter

class DomainContextBuilder:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.registry = DomainRegistry(self.root)
        self.cache = DomainCache(self.root)

    def build(self, question: str, schema_summary: str = "", database_profile_id: str | None = None, database_type: str | None = None, max_docs: int = 6) -> DomainContext:
        packs = self.registry.enabled_packs()
        if not packs:
            return DomainContext(None, None, 0.0, None, warnings=["domain_registry_empty"])
        router = DomainRouter(packs)
        route = router.route(question, schema_summary, database_profile_id)
        if route.decision == "none" or not route.selected_domain_id:
            return DomainContext(None, route.pack_version, route.confidence, route.schema_fingerprint, warnings=route.warnings, router=route.to_dict())
        pack = self.registry.get(route.selected_domain_id)
        if not pack:
            return DomainContext(None, None, route.confidence, route.schema_fingerprint, warnings=["selected_pack_missing"], router=route.to_dict())
        with zipfile.ZipFile(Path(pack["path"])) as zf:
            corpus = [json.loads(line) for line in zf.read("retrieval_corpus.jsonl").decode("utf-8").splitlines() if line.strip()]
        result = LexicalRetriever(corpus).search(question + "\n" + schema_summary, domain_id=route.selected_domain_id, top_k=max_docs, database_type=database_type)
        docs = [d.to_dict() for d in result.documents]
        ctx = DomainContext(
            domain_id=route.selected_domain_id,
            domain_pack_version=route.pack_version,
            router_confidence=route.confidence,
            schema_fingerprint=route.schema_fingerprint,
            warnings=route.warnings + result.warnings,
            router=route.to_dict(),
            retrieved_doc_ids=[d["doc_id"] for d in docs],
        )
        for doc in docs:
            payload = doc.get("structured_payload") or {}
            dtype = doc.get("document_type")
            item = {**payload, "source_ref": doc.get("source_ref"), "doc_id": doc.get("doc_id"), "text": doc.get("text")}
            if dtype == "business_rule":
                ctx.business_rules.append(item)
            elif dtype == "glossary":
                ctx.glossary_terms.append(item)
            elif dtype == "schema_pattern":
                ctx.schema_guidance.append(item)
            elif dtype == "sql_example":
                ctx.sql_examples.append(item)
            elif dtype == "safety_rule":
                ctx.safety_rules.append(item)
            ctx.citations.append({"doc_id": doc.get("doc_id"), "source_ref": doc.get("source_ref"), "content_hash": doc.get("content_hash")})
        ctx.selected_intents = sorted({str((d.get("intent") or "")).split(".")[0] for d in docs if d.get("intent")})
        ctx.token_estimate = max(1, len(ctx.to_prompt_text()) // 4)
        self.cache.put({
            "database_profile_id": database_profile_id,
            "schema_fingerprint": route.schema_fingerprint,
            "domain_id": ctx.domain_id,
            "domain_pack_version": ctx.domain_pack_version,
            "confidence": ctx.router_confidence,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolution_source": "router",
        })
        return ctx
