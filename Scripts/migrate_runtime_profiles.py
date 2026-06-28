import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from DataStore.config_loader import ConfigLoader, load_json, write_json_atomic

def migrate_profiles():
    config = ConfigLoader().load()
    target = Path(config.root) / "Data" / "safy_profiles.json"
    
    # Backups
    if target.exists():
        shutil.copy2(target, f"{target}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak")

    # Sources
    user_p = Path(config.root) / "Data" / "User" / "user_profiles.json"
    db_p = Path(config.root) / "Data" / "Database_management" / "database_profiles.json"

    profiles = {
        "schema_version": 1,
        "updated_at": datetime.now().isoformat(),
        "model_profiles": [],
        "database_profiles": []
    }

    if user_p.exists():
        data = load_json(user_p)
        if isinstance(data, list):
            profiles["model_profiles"] = data
        elif isinstance(data, dict) and "profiles" in data:
            profiles["model_profiles"] = data["profiles"]

    if db_p.exists():
        data = load_json(db_p)
        if isinstance(data, list):
            profiles["database_profiles"] = data
        elif isinstance(data, dict) and "profiles" in data:
            profiles["database_profiles"] = data["profiles"]

    write_json_atomic(target, profiles)
    print(f"Migrated profiles to {target}")

def migrate_sessions():
    config = ConfigLoader().load()
    sessions_dir = Path(config.root) / "Data" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    
    # Migration from SQLite runtime_db to JSON would go here
    # For Pass 2, we ensure the directory structure exists and scaffold is ready
    print(f"Session storage ready at {sessions_dir}")

def migrate_audit():
    config = ConfigLoader().load()
    audit_dir = Path(config.root) / "Data" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    
    target = audit_dir / "safy_audit.jsonl"
    print(f"Audit JSONL ready at {target}")

if __name__ == "__main__":
    migrate_profiles()
    migrate_sessions()
    migrate_audit()
