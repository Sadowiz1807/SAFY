from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Core.skill_loader import discover_skills, load_skill_document  # noqa: E402
from Core.skill_policy import SkillPolicy  # noqa: E402

FORBIDDEN_NAMES = {
    "runtime.py",
    "runner.py",
    "worker.py",
    "server.py",
    "service.py",
    "bootstrap.py",
    "requirements.txt",
}
FORBIDDEN_SUFFIXES = {".exe", ".dll", ".bat", ".cmd", ".ps1"}
PLACEHOLDERS = [
    "{{DOMAIN_ID}}",
    "{{DOMAIN_NAME}}",
    "{{ENTITY_NAME}}",
    "{{TABLE_NAME}}",
    "{{COLUMN_NAME}}",
    "{{OWNER}}",
]
SECRET_PATTERNS = [
    re.compile(r"password\s*=", re.I),
    re.compile(r"api[_-]?key\s*=", re.I),
    re.compile(r"service[_-]?role\s*=", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
]
REQUIRED_SECTIONS = [
    "## Purpose",
    "## When to use",
    "## Required context",
    "## Procedure",
    "## Safety rules",
    "## Expected output",
    "## Failure behavior",
]


def main() -> int:
    errors: list[str] = []
    skills_root = ROOT / "Skills"
    descriptors, invalid = discover_skills(
        skills_root,
        allow_legacy_lowercase=False,
    )

    for name, reason in invalid.items():
        errors.append(f"invalid skill {name}: {reason}")

    for path in skills_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(skills_root)
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden executable/runtime file: {relative}")
        if path.name in {"Skill.md", "skill.md"}:
            errors.append(f"legacy skill filename: {relative}")

        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(placeholder in text for placeholder in PLACEHOLDERS):
            errors.append(f"unresolved placeholder in {relative}")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"secret-like marker in {relative}: {pattern.pattern}")

    for name, descriptor in descriptors.items():
        if not (descriptor.directory / "SKILL.md").is_file():
            errors.append(f"missing canonical SKILL.md: {name}")
        try:
            loaded = load_skill_document(descriptor)
            for section in REQUIRED_SECTIONS:
                if section.lower() not in loaded.body.lower():
                    errors.append(f"missing section {section}: {name}")
        except Exception as exc:
            errors.append(f"load failed {name}: {exc}")

    if "text_to_sql" not in descriptors:
        errors.append("text_to_sql skill missing")
    if "text_to_query" in descriptors or (skills_root / "text_to_query").exists():
        errors.append("obsolete text_to_query skill remains")

    create_database = descriptors.get("create_database")
    if create_database is not None:
        try:
            loaded = load_skill_document(create_database)
            frontmatter = {
                "name": create_database.name,
                "version": create_database.version,
                "description": create_database.description,
                "enabled": create_database.enabled,
                "risk_level": create_database.risk_level,
                "references": create_database.reference_paths,
                **create_database.metadata,
            }
            SkillPolicy.compile(frontmatter)
        except Exception as exc:
            errors.append(f"create_database policy invalid: {exc}")

    if not descriptors:
        errors.append("no skills discovered")

    if errors:
        print("FAIL")
        for error in errors:
            print(" -", error)
        return 1

    print("PASS")
    print(f"skills={len(descriptors)}")
    print("canonical_text_skill=text_to_sql")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
