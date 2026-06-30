from __future__ import annotations

import fnmatch
import hashlib
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "Reports" / "packages" / "SAFY_CLEAN_SOURCE_PACKAGE.zip"

EXCLUDE_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules",
    ".venv", "venv", "Sandbox/workspaces", "Reports/packages", "Reports/audit_tmp", "Reports/audits", "Reports/e2e_tests", "Reports/verification", "Reports/fixes",
}
EXCLUDE_PATTERNS = [
    ".env", ".env.*", "*.pyc", "*.pyo", "*.log", "*.sqlite", "*.sqlite3", "*.db",
    "Data/secrets/*", "Data/sessions/*", "Data/sandboxes/*", "Data/context_files/files/*",
    "Data/context_files/metadata/*.json", "Data/context_files/metadata/legacy/*",
    "Data/sandbox_rules/databases/*", "Data/sandbox_rules/*.json", "Reports/audit_tmp/*",
    "Data/Database_management/database_profiles.json", "Data/model_profiles/model_profiles.json", "Data/safy_profiles.json", "Reports/audits/*",
    "Reports/e2e_tests/*", "Reports/verification/*", "Reports/fixes/*",
    "Data/User/user_profiles.json", "Data/SchemaGraph/*", "Datasets/*",
]
ALLOW_KEEP = {"Data/context_files/.gitkeep", "Data/context_files/files/.gitkeep", "Data/context_files/metadata/.gitkeep", "Data/context_files/metadata/legacy/.gitkeep", "Data/SchemaGraph/.gitkeep"}
SECRET_PATTERNS = ("sk-", "Bearer ", "service_role", "api_key=", "password=", "postgres://", "mysql://")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def excluded(path: Path) -> bool:
    r = rel(path)
    if r in ALLOW_KEEP:
        return False
    parts = set(r.split("/"))
    if parts & EXCLUDE_DIRS:
        return True
    return any(fnmatch.fnmatch(r, pat) for pat in EXCLUDE_PATTERNS)


def file_has_secret(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:200000]
    except Exception:
        return False
    lower = text.lower()
    return any(p.lower() in lower for p in SECRET_PATTERNS)


def build(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    included = []
    secret_hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path == output:
            continue
        if excluded(path):
            continue
        if file_has_secret(path) and path.suffix.lower() in {".env", ".json", ".txt", ".md", ".yml", ".yaml"}:
            secret_hits.append(rel(path))
            continue
        included.append(path)
    if secret_hits:
        raise SystemExit("Refusing to package possible secret files: " + ", ".join(secret_hits[:20]))
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(included, key=rel):
            zf.write(path, rel(path))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(digest + "\n", encoding="utf-8")
    print(output)
    print(digest)
    return output


if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUTPUT
    build(target)
