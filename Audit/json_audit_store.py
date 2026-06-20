from __future__ import annotations
from pathlib import Path
from typing import Any
import json, uuid
from Audit.audit_store import AuditStoreError, now_iso
from Logging.redact import redact_obj, redact_text

class JsonAuditStore:
    def __init__(self, path: str | Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
    def init(self):
        self.path.parent.mkdir(parents=True, exist_ok=True); self.path.touch(exist_ok=True)
    def _records(self):
        self.init(); out=[]
        for line in self.path.read_text(encoding='utf-8').splitlines():
            if line.strip(): out.append(json.loads(line))
        return out
    def _append(self, rec):
        self.init()
        with self.path.open('a', encoding='utf-8') as f: f.write(json.dumps(rec, sort_keys=True, ensure_ascii=True)+'\n')
    def write_event(self, **event: Any) -> dict[str, Any]:
        ts=now_iso(); rec={
            'audit_id': event.get('audit_id') or f"audit_{uuid.uuid4().hex}", 'event_type': event.get('event_type') or 'generic',
            'actor_type': event.get('actor_type'), 'actor_id': event.get('actor_id'), 'action': event.get('action') or 'unknown',
            'target_type': event.get('target_type'), 'target_id': event.get('target_id'), 'risk_level': event.get('risk_level'),
            'status': event.get('status') or 'created', 'created_at': event.get('created_at') or ts, 'updated_at': event.get('updated_at') or ts,
            'request_id': event.get('request_id'), 'check_id': event.get('check_id'), 'sql_hash': event.get('sql_hash'),
            'error_code': event.get('error_code'), 'error_message': redact_text(event.get('error_message')),
            'repair_status': event.get('repair_status'), 'repair_reason': event.get('repair_reason'), 'repair_attempt_count': event.get('repair_attempt_count',0),
            'repair_last_error': redact_text(event.get('repair_last_error')), 'metadata': redact_obj(event.get('metadata') or {})}
        self._append(rec); return rec
    def update_event(self, audit_id: str, **updates: Any) -> dict[str, Any]:
        rec=self.get_event(audit_id); rec.update({k:(redact_text(v) if 'error' in k else v) for k,v in updates.items()}); rec['updated_at']=now_iso(); rec['audit_update']=True; self._append(rec); return rec
    def get_event(self, audit_id: str) -> dict[str, Any]:
        for rec in reversed(self._records()):
            if rec.get('audit_id') == audit_id: return rec
        raise AuditStoreError('PROFILE_NOT_FOUND', f'Audit event not found: {audit_id}')
    def list_events(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(reversed(self._records()))[:limit]
