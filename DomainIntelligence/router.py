from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from .contracts import RouterCandidate, RouterResult
from .schema_fingerprint import schema_fingerprint

def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\wÀ-ỹ]+", (text or "").lower(), re.UNICODE))

class DomainRouter:
    def __init__(self, registry_packs: list[dict[str, Any]]):
        self.packs = registry_packs
        self.features: dict[str, dict[str, Any]] = {}
        for pack in registry_packs:
            try:
                with zipfile.ZipFile(Path(pack["path"])) as zf:
                    self.features[pack["domain_id"]] = json.loads(zf.read("router/labels.json").decode("utf-8"))
            except Exception:
                self.features[pack.get("domain_id", "")] = {"positive_signals": [], "negative_signals": []}

    def route(self, question: str, schema_summary: str = "", database_profile_id: str | None = None, threshold: float = 0.20) -> RouterResult:
        q_tokens = _tokens(question)
        s_text = (schema_summary or "").lower()
        fp = schema_fingerprint(schema_summary)
        candidates: list[RouterCandidate] = []
        for pack in self.packs:
            domain_id = pack.get("domain_id")
            features = self.features.get(domain_id, {})
            positives = [str(x).lower() for x in features.get("positive_signals") or []]
            negatives = [str(x).lower() for x in features.get("negative_signals") or []]
            matched_q = [sig for sig in positives if sig and (sig in q_tokens or sig in (question or "").lower())]
            matched_schema = [sig for sig in positives if sig and sig in s_text]
            neg = [sig for sig in negatives if sig and (sig in q_tokens or sig in s_text)]
            q_score = min(1.0, len(matched_q) / 5.0)
            s_score = min(1.0, len(matched_schema) / 8.0)
            score = max(0.0, (0.62 * q_score + 0.38 * s_score) - (0.08 * len(neg)))
            candidates.append(RouterCandidate(domain_id, round(score, 4), round(q_score, 4), round(s_score, 4), matched_q + matched_schema[:8], neg[:8]))
        candidates.sort(key=lambda c: c.score, reverse=True)
        if not candidates or candidates[0].score <= 0:
            return RouterResult(None, 0.0, "none", candidates[:5], None, fp, ["no_domain_signals"])
        top = candidates[0]
        second = candidates[1].score if len(candidates) > 1 else 0.0
        if top.score < threshold:
            return RouterResult(None, top.score, "none", candidates[:5], None, fp, ["confidence_below_threshold"])
        if second and top.score - second < 0.05:
            return RouterResult(top.domain_id, top.score, "ambiguous", candidates[:5], self._version(top.domain_id), fp, ["close_domain_candidates"])
        return RouterResult(top.domain_id, top.score, "selected", candidates[:5], self._version(top.domain_id), fp, [])

    def _version(self, domain_id: str) -> str | None:
        for pack in self.packs:
            if pack.get("domain_id") == domain_id:
                return pack.get("pack_version")
        return None
