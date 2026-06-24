from __future__ import annotations

import argparse
from pathlib import Path
import re
import zipfile


EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    ".pytest_tmp",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "build",
    "dist",
    "logs",
}
EXCLUDED_EXACT = {
    ".env",
    ".env.local",
    "Data/safy_profiles.json",
    "Data/safy_profiles.local.json",
    "Data/Database_management/database_profiles.json",
    "Data/model_profiles/model_profiles.json",
    "Data/User/user_profiles.json",
}
EXCLUDED_PREFIXES = {
    "Data/secrets/",
    "Data/sessions/",
    "Data/sandboxes/",
    "Data/SchemaGraph/",
    "Sandbox/workspaces/",
    "DomainIntelligence/work/",
    "DomainIntelligence/packs/cache/",
}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".backup",
    ".dump",
}
SAFE_ENV_NAMES = {".env.template", ".env.example", ".env.local.example"}
SECRET_NAME_RE = re.compile(r"(^|/)(secret|secrets|credential|credentials)(/|$)", re.I)


def should_include(root: Path, path: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    parts = set(path.relative_to(root).parts)
    if parts & EXCLUDED_DIRS:
        return False
    if rel in EXCLUDED_EXACT:
        return False
    if any(rel.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.name.endswith(".egg-info") or any(part.endswith(".egg-info") for part in path.parts):
        return False
    if path.name.startswith(".env") and path.name not in SAFE_ENV_NAMES:
        return False
    if SECRET_NAME_RE.search(rel) and rel not in {"Data/secrets/.gitkeep"}:
        return False
    return True


def build_archive(root: Path, output: Path) -> tuple[int, int]:
    included = 0
    excluded = 0
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.resolve() == output:
                continue
            if should_include(root, path):
                archive.write(path, (Path(root.name) / path.relative_to(root)).as_posix())
                included += 1
            else:
                excluded += 1
    return included, excluded


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a secret-safe SAFY handoff ZIP")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    output = (args.output or root.parent / "SAFY_clean_handoff.zip").resolve()
    included, excluded = build_archive(root, output)
    print(f"Created: {output}")
    print(f"Included files: {included}")
    print(f"Excluded files: {excluded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
