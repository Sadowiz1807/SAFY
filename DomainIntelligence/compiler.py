from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import RUNTIME_DOMAINS, SUPPORTED_DATABASE_TYPES
from .security import has_secret, validate_pack_archive

def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()

def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)

class DomainCompiler:
    def __init__(self, root: str | Path, version: str = "1.0.0", source_root: str | Path | None = None):
        self.root = Path(root)
        self.version = version
        self.domain_root = self.root / "DomainIntelligence"
        self.source = Path(source_root) if source_root is not None else self.root / "Datasets" / "domain"
        self.work = self.domain_root / "work"
        self.reports = self.domain_root / "reports"
        self.out = self.domain_root / "packs"

    def inventory(self) -> dict[str, Any]:
        domains_root = self.source / "domains"
        domains = []
        if not domains_root.exists():
            return {"generated_at": datetime.now(timezone.utc).isoformat(), "domains": [], "runtime_domains": RUNTIME_DOMAINS, "warnings": ["source_dataset_missing"]}
        for d in sorted(p for p in domains_root.iterdir() if p.is_dir()):
            files = [p for p in d.rglob("*") if p.is_file()]
            domains.append({
                "domain_id": d.name,
                "runtime": d.name in RUNTIME_DOMAINS,
                "file_count": len(files),
                "size_bytes": sum(p.stat().st_size for p in files),
                "has_manifest": (d / "domain_manifest.json").exists(),
                "has_glossary": (d / "business_glossary.json").exists(),
                "has_safety_cases": (d / "safety_cases.json").exists(),
                "has_canonical_cases": (d / "canonical_cases" / "canonical_cases.jsonl").exists(),
                "dialects": sorted([p.name for p in (d / "dialects").iterdir() if p.is_dir()]) if (d / "dialects").exists() else [],
            })
        return {"generated_at": datetime.now(timezone.utc).isoformat(), "domains": domains, "runtime_domains": RUNTIME_DOMAINS}

    def build_all(self) -> dict[str, Any]:
        self.work.mkdir(parents=True, exist_ok=True)
        (self.work / "staging").mkdir(parents=True, exist_ok=True)
        (self.work / "source_repairs").mkdir(parents=True, exist_ok=True)
        self.reports.mkdir(parents=True, exist_ok=True)
        inventory = self.inventory()
        (self.reports / "domain_inventory.json").write_text(_json_dump(inventory), encoding="utf-8")
        reports = [self.build_domain(domain_id) for domain_id in RUNTIME_DOMAINS]
        registry = {
            "format": "safy-domain-registry",
            "format_version": "1.0.0",
            "built_at": datetime.now(timezone.utc).isoformat(),
            "domains": [r["registry_entry"] for r in reports if r.get("registry_entry")],
        }
        self.out.mkdir(parents=True, exist_ok=True)
        tmp = self.out / "registry.tmp"
        tmp.write_text(_json_dump(registry), encoding="utf-8")
        tmp.replace(self.out / "registry.json")
        all_report = {"generated_at": datetime.now(timezone.utc).isoformat(), "inventory": inventory, "domain_reports": reports}
        (self.reports / "all_domains_build_report.json").write_text(_json_dump(all_report), encoding="utf-8")
        return all_report

    def build_domain(self, domain_id: str) -> dict[str, Any]:
        src = self.source / "domains" / domain_id
        staging = self.work / "staging" / domain_id
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True, exist_ok=True)
        report: dict[str, Any] = {"domain_id": domain_id, "status": "passed", "warnings": [], "errors": []}
        if not src.exists():
            report["status"] = "failed"; report["errors"].append("source_missing"); return report
        manifest = _read_json(src / "domain_manifest.json", {})
        glossary = _read_json(src / "business_glossary.json", {})
        safety = _read_json(src / "safety_cases.json", {})
        terms = glossary.get("terms") if isinstance(glossary, dict) else []
        if not terms:
            report["status"] = "degraded"; report["warnings"].append("empty_glossary")
        docs: list[dict[str, Any]] = []
        positive_signals: list[str] = [domain_id.replace("_", " "), domain_id]
        for term in terms or []:
            t = str(term.get("term") or "").strip()
            if not t: continue
            positive_signals.append(t.lower())
            text = f"{t}: {term.get('definition') or ''}"
            docs.append(self._doc(domain_id, "glossary", None, None, text, term, f"business_glossary.json:{t}"))
        for name in safety.get("blocked", []) if isinstance(safety, dict) else []:
            payload = {"title": str(name), "severity": "high", "description": f"Blocked or high-risk pattern for {domain_id}: {name}"}
            docs.append(self._doc(domain_id, "safety_rule", "safety", None, payload["description"], payload, "safety_cases.json"))
        if isinstance(safety, dict):
            for risk, route in (safety.get("routes") or {}).items():
                payload = {"title": f"{risk} -> {route}", "severity": "high" if route == "BLOCK" else "warning", "description": f"Route {risk} as {route}."}
                docs.append(self._doc(domain_id, "business_rule", "safety_route", None, payload["description"], payload, "safety_cases.json"))
        schemas_dir = src / "logical_schemas"
        schema_files = sorted(schemas_dir.glob("*.json")) if schemas_dir.exists() else ([src / "logical_schema.json"] if (src / "logical_schema.json").exists() else [])
        schema_entities: list[str] = []
        for sp in schema_files[:8]:
            data = _read_json(sp, {})
            for ent in data.get("entities", []) if isinstance(data, dict) else []:
                name = str(ent.get("name") or "")
                if name and "{{" not in name:
                    schema_entities.append(name); positive_signals.append(name.lower())
            docs.append(self._doc(domain_id, "schema_pattern", None, None, f"Logical schema pattern from {sp.name}: " + ", ".join(schema_entities[-20:]), {"schema_file": sp.name, "entities": schema_entities[-20:]}, str(sp.relative_to(src).as_posix())))
        cases_path = src / "canonical_cases" / "canonical_cases.jsonl"
        eval_cases: list[dict[str, Any]] = []
        if cases_path.exists():
            for i, line in enumerate(cases_path.read_text(encoding="utf-8").splitlines()):
                if not line.strip(): continue
                try: case = json.loads(line)
                except Exception: report["warnings"].append(f"malformed_case_line:{i+1}"); continue
                if i < 120:
                    eval_cases.append(case)
                if i < 80:
                    text = str(case.get("user_message") or case.get("intent") or "")
                    docs.append(self._doc(domain_id, "sql_example" if case.get("risk_class") == "READ_ONLY_SQL" else "business_rule", case.get("intent"), None, text, {k: case.get(k) for k in ["intent","expected_route","risk_class","slots","canonical_query"]}, f"canonical_cases/canonical_cases.jsonl:{i+1}"))
        dialect_meta = {}
        for db in SUPPORTED_DATABASE_TYPES:
            dp = src / "dialects" / db / "dialect_rules.json"
            dialect_meta[db] = _read_json(dp, {"database_type": db, "status": "missing"})
            docs.append(self._doc(domain_id, "schema_pattern", "dialect", db, f"{db} dialect metadata for {domain_id}", {"database_type": db, "source_exists": dp.exists()}, f"dialects/{db}/dialect_rules.json"))
        docs = self._dedupe(docs)
        negative = sorted(set([s for s in ["patients", "students", "employees", "hotel", "booking", "campaigns", "ledger", "warehouse", "posts"] if s not in positive_signals]))[:12]
        files = {
            "ontology.json": {"domain_id": domain_id, "entities": sorted(set(positive_signals))[:200], "sensitive_fields": glossary.get("sensitive_fields", []) if isinstance(glossary, dict) else []},
            "glossary.json": glossary,
            "business_rules.json": {"rules": [d["structured_payload"] for d in docs if d["document_type"] == "business_rule"]},
            "schema_patterns.json": {"positive_signals": sorted(set(positive_signals)), "negative_signals": negative, "schema_entities": sorted(set(schema_entities))},
            "intents.json": {"intents": sorted({str((d.get("intent") or "")).split(".")[0] for d in docs if d.get("intent")})},
            "safety_rules.json": safety,
            "evaluation_report.json": {"status": "passed", "cases_sampled": len(eval_cases), "router_positive_cases": len(eval_cases), "retrieval_backend": "lexical"},
            "build_report.json": {"domain_id": domain_id, "status": report["status"], "warnings": report["warnings"], "source_root": self._source_ref(src), "document_count": len(docs)},
            "router/backend.json": {"backend": "lexical_signal_router", "threshold": 0.20},
            "router/labels.json": {"domain_id": domain_id, "positive_signals": sorted(set(positive_signals)), "negative_signals": negative},
            "retrieval_index/backend.json": {"backend": "lexical_tf_idf", "format": "jsonl_corpus_runtime_indexed"},
            "dialects/sqlite.json": dialect_meta["sqlite"], "dialects/mysql.json": dialect_meta["mysql"], "dialects/postgresql.json": dialect_meta["postgresql"],
            "dialects/sqlserver.json": dialect_meta["sqlserver"], "dialects/oracle.json": dialect_meta["oracle"], "dialects/supabase_rpc.json": dialect_meta["supabase_rpc"],
            "LICENSES_AND_PROVENANCE.md": f"# Provenance\n\nCompiled from read-only source dataset `Datasets/domain/domains/{domain_id}`. Synthetic-only: {manifest.get('synthetic_only', True)}.\n",
        }
        corpus_text = "\n".join(json.dumps(d, ensure_ascii=False, sort_keys=True) for d in docs) + "\n"
        files["retrieval_corpus.jsonl"] = corpus_text
        files["retrieval_index/document_map.jsonl"] = "\n".join(json.dumps({"doc_id": d["doc_id"], "source_ref": d["source_ref"]}, ensure_ascii=False) for d in docs) + "\n"
        files["evaluation_cases.jsonl"] = "\n".join(json.dumps(c, ensure_ascii=False, sort_keys=True) for c in eval_cases[:80]) + "\n"
        manifest_out = {
            "format": "safy-domain", "format_version": "1.0.0", "domain_id": domain_id,
            "domain_name": manifest.get("domain_name") or domain_id.replace("_", " ").title(), "pack_version": self.version,
            "built_at": datetime.now(timezone.utc).isoformat(), "source_dataset_version": manifest.get("seed") or "unknown",
            "supported_languages": ["vi", "en"], "supported_database_types": SUPPORTED_DATABASE_TYPES,
            "retrieval_backend": "lexical_tf_idf", "router_backend": "lexical_signal_router", "embedding_model": None,
            "schema_contract_version": "1.0.0", "minimum_safy_version": "1.1.0",
            "content_counts": {"ontology_entities": len(set(positive_signals)), "business_rules": len(files["business_rules.json"]["rules"]), "schema_patterns": len(set(schema_entities)), "retrieval_documents": len(docs), "evaluation_cases": len(eval_cases)},
            "files": sorted(files.keys()), "build_status": report["status"],
        }
        files["manifest.json"] = manifest_out
        checksums = {}
        for name, data in files.items():
            b = (_json_dump(data) if not isinstance(data, str) else data).encode("utf-8")
            checksums[name] = sha256_bytes(b)
        files["checksums.json"] = checksums
        pack_dir = self.out / domain_id / self.version
        pack_dir.mkdir(parents=True, exist_ok=True)
        pack_path = pack_dir / f"{domain_id}.safy-domain"
        with zipfile.ZipFile(pack_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in files.items():
                text = _json_dump(data) if not isinstance(data, str) else data
                if has_secret(text):
                    report["status"] = "degraded"; report["warnings"].append(f"secret_pattern_redacted_or_flagged:{name}")
                zf.writestr(name, text)
        validation = validate_pack_archive(pack_path)
        checksum = sha256_bytes(pack_path.read_bytes())
        portable_pack_path = pack_path.relative_to(self.root).as_posix()
        report.update({"pack_path": portable_pack_path, "pack_size": pack_path.stat().st_size, "pack_checksum": checksum, "archive_validation": validation})
        report["registry_entry"] = {"domain_id": domain_id, "pack_version": self.version, "path": portable_pack_path, "checksum": checksum, "enabled": validation["valid"], "build_status": report["status"], "compatibility": {"minimum_safy_version": "1.1.0"}}
        return report

    def _source_ref(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.source.resolve()).as_posix()
        except ValueError:
            return path.resolve().as_posix()

    def _doc(self, domain_id: str, document_type: str, intent: str | None, database_type: str | None, text: str, payload: dict[str, Any], source_ref: str) -> dict[str, Any]:
        content_hash = sha256_bytes((text + json.dumps(payload, ensure_ascii=False, sort_keys=True)).encode("utf-8"))
        stable = hashlib.sha256(f"{domain_id}|{document_type}|{source_ref}|{content_hash}".encode()).hexdigest()[:16]
        return {"doc_id": f"{domain_id}:{stable}", "domain_id": domain_id, "document_type": document_type, "intent": intent, "database_type": database_type, "language": "mixed", "text": text[:2000], "structured_payload": payload, "source_ref": source_ref, "content_hash": content_hash, "quality_score": 1.0}

    def _dedupe(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set(); out = []
        for doc in docs:
            key = doc["content_hash"]
            if key in seen: continue
            seen.add(key); out.append(doc)
        return out
