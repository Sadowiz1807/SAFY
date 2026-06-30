from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import re
import uuid
from typing import Any

VALID_STATUSES = {
    "draft", "validating", "active", "conflict_rule", "conflict_schema",
    "pending_user_decision", "active_future_only", "warning_only", "disabled", "archived",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_id(value: str | None, fallback: str) -> str:
    raw = str(value or fallback).strip() or fallback
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)[:120]


class SandboxRuleStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / ".gitkeep").touch(exist_ok=True)
        self.index_path = self.root / "rules_index.json"
        if not self.index_path.exists():
            self._write_json(self.index_path, {"schema_version": 1, "rules": {}})

    def scope_dir(self, database_profile_id: str, sandbox_id: str) -> Path:
        path = self.root / "databases" / safe_id(database_profile_id, "db_default") / safe_id(sandbox_id, "sandbox_default")
        (path / "drafts").mkdir(parents=True, exist_ok=True)
        (path / "versions").mkdir(parents=True, exist_ok=True)
        (path / "validation_reports").mkdir(parents=True, exist_ok=True)
        active = path / "active_rules.json"
        if not active.exists():
            self._write_json(active, {"schema_version": 1, "rules": []})
        return path

    def create_draft(self, *, database_profile_id: str, sandbox_id: str, raw_text: str, connection_name: str | None = None, source_type: str = "manual_text", source_filename: str | None = None, severity: str = "block") -> dict[str, Any]:
        now = utc_now()
        rule_id = f"rule_{uuid.uuid4().hex}"
        rule = {
            "schema_version": 1,
            "rule_id": rule_id,
            "database_profile_id": database_profile_id,
            "sandbox_id": sandbox_id,
            "connection_name": connection_name,
            "source_type": source_type,
            "source_filename": source_filename,
            "raw_text": raw_text or "",
            "parsed_rules": [],
            "status": "draft",
            "severity": severity or "block",
            "schema_fingerprint": None,
            "validated_at": None,
            "activated_at": None,
            "created_at": now,
            "updated_at": now,
            "version": 1,
        }
        self.save_rule(rule)
        return rule

    def save_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        status = rule.get("status") or "draft"
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid sandbox rule status: {status}")
        rule["updated_at"] = utc_now()
        scope = self.scope_dir(rule["database_profile_id"], rule["sandbox_id"])
        rid = safe_id(rule["rule_id"], "rule")
        if status == "active":
            active_path = scope / "active_rules.json"
            active = self._read_json(active_path, {"schema_version": 1, "rules": []})
            rules = [r for r in active.get("rules", []) if r.get("rule_id") != rule.get("rule_id")]
            rules.append(rule)
            active["rules"] = rules
            self._write_json(active_path, active)
            self._write_json(scope / "versions" / f"{rid}_v{rule.get('version', 1)}.json", rule)
            draft_path = scope / "drafts" / f"{rid}.json"
            if draft_path.exists():
                draft_path.unlink()
        else:
            self._write_json(scope / "drafts" / f"{rid}.json", rule)
        self._update_index(rule)
        return rule

    def get_rule(self, database_profile_id: str, sandbox_id: str, rule_id: str) -> dict[str, Any] | None:
        scope = self.scope_dir(database_profile_id, sandbox_id)
        for p in [scope / "drafts" / f"{safe_id(rule_id, 'rule')}.json", scope / "versions" / f"{safe_id(rule_id, 'rule')}_v1.json"]:
            if p.exists():
                return self._read_json(p, None)
        for r in self.list_rules(database_profile_id, sandbox_id).get("active_rules", []):
            if r.get("rule_id") == rule_id:
                return r
        return None

    def list_rules(self, database_profile_id: str, sandbox_id: str) -> dict[str, Any]:
        scope = self.scope_dir(database_profile_id, sandbox_id)
        raw_active = self._read_json(scope / "active_rules.json", {"rules": []}).get("rules", [])
        # Defensive cleanup at read boundary: older builds could leave disabled or
        # draft records inside active_rules.json. Do not return them as active.
        active = [r for r in raw_active if r.get("status") == "active"]
        drafts = [self._read_json(p, {}) for p in sorted((scope / "drafts").glob("*.json"))]
        drafts = [r for r in drafts if r and r.get("status") != "active"]
        return {"database_profile_id": database_profile_id, "sandbox_id": sandbox_id, "active_rules": active, "draft_rules": drafts, "rules": active + drafts}

    def write_validation_report(self, rule: dict[str, Any], report: dict[str, Any]) -> Path:
        scope = self.scope_dir(rule["database_profile_id"], rule["sandbox_id"])
        stamp = utc_now().replace(":", "").replace(".", "_")
        path = scope / "validation_reports" / f"{safe_id(rule['rule_id'], 'rule')}_{stamp}.json"
        self._write_json(path, report)
        return path

    def disable(self, database_profile_id: str, sandbox_id: str, rule_id: str) -> dict[str, Any] | None:
        scope = self.scope_dir(database_profile_id, sandbox_id)
        active_path = scope / "active_rules.json"
        active = self._read_json(active_path, {"rules": []})
        kept, disabled = [], None
        for rule in active.get("rules", []):
            if rule.get("rule_id") == rule_id:
                rule = {**rule, "status": "disabled", "updated_at": utc_now()}
                disabled = rule
                self.save_rule(rule)
            else:
                kept.append(rule)
        active["rules"] = kept
        self._write_json(active_path, active)
        return disabled

    def _update_index(self, rule: dict[str, Any]) -> None:
        index = self._read_json(self.index_path, {"schema_version": 1, "rules": {}})
        index.setdefault("rules", {})[rule["rule_id"]] = {
            "database_profile_id": rule["database_profile_id"],
            "sandbox_id": rule["sandbox_id"],
            "status": rule["status"],
            "updated_at": rule.get("updated_at"),
        }
        self._write_json(self.index_path, index)

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
