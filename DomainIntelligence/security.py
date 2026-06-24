from __future__ import annotations

import json
import os
import re
import zipfile
from pathlib import Path

ALLOWED_SUFFIXES = {".json", ".jsonl", ".md", ".txt", ".npz"}
SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
]

def has_secret(text: str) -> bool:
    return any(p.search(text or "") for p in SECRET_PATTERNS)

def safe_member_name(name: str) -> bool:
    p = Path(name)
    return not (p.is_absolute() or ".." in p.parts or name.startswith(("/", "\\")))

def validate_pack_archive(path: str | Path, *, max_files: int = 200, max_uncompressed: int = 50_000_000) -> dict:
    pack_path = Path(path)
    errors: list[str] = []
    total = 0
    try:
        with zipfile.ZipFile(pack_path) as zf:
            infos = zf.infolist()
            if len(infos) > max_files:
                errors.append("too_many_files")
            names = {i.filename for i in infos}
            if "manifest.json" not in names:
                errors.append("missing_manifest")
            for info in infos:
                total += info.file_size
                if not safe_member_name(info.filename):
                    errors.append(f"unsafe_path:{info.filename}")
                if info.filename.endswith("/"):
                    continue
                if Path(info.filename).suffix and Path(info.filename).suffix not in ALLOWED_SUFFIXES:
                    errors.append(f"disallowed_suffix:{info.filename}")
                mode = (info.external_attr >> 16) & 0o170000
                if mode in {0o120000, 0o10000}:
                    errors.append(f"unsafe_link:{info.filename}")
            if total > max_uncompressed:
                errors.append("uncompressed_size_limit")
            if "manifest.json" in names:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                if manifest.get("format") != "safy-domain":
                    errors.append("bad_format")
    except Exception as exc:
        errors.append(f"archive_error:{type(exc).__name__}:{exc}")
    return {"valid": not errors, "errors": errors, "uncompressed_size": total}
