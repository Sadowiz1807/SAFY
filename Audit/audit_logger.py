from __future__ import annotations

from .audit_store import AuditStore


def write_audit_log(audit_db_path, **event):
    """Backward-compatible audit writer for legacy imports."""
    store = AuditStore(audit_db_path)
    event_type = event.pop("event_type", event.pop("action", "audit_log"))
    return store.write_event(event_type=event_type, **event)


def write_pre_execution(audit_db_path, **event):
    store = AuditStore(audit_db_path)
    return store.write_event(event_type="pre_execution", status="prewrite_success", **event)


def update_post_execution(audit_db_path, audit_id: str, **updates):
    store = AuditStore(audit_db_path)
    return store.update_event(audit_id, **updates)


def write_high_risk_prewrite(audit_db_path, **event):
    return write_pre_execution(audit_db_path, risk_level="high", **event)
