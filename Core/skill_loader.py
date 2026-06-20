from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def _parse_scalar(value: str):
    value = value.strip()
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [part.strip().strip("\"'") for part in inner.split(",")]
    try:
        return int(value)
    except ValueError:
        return value.strip("\"'")


def load_skill(skill_name: str) -> dict:
    path = ROOT / "Skills" / skill_name / "Skill.md"
    if not path.exists():
        raise FileNotFoundError("SKILL_NOT_FOUND")
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not match:
        raise ValueError("SKILL_POLICY_INVALID")
    fm_text, body = match.groups()
    data: dict = {}
    current: str | None = None
    for line in fm_text.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            if value.strip():
                data[key.strip()] = _parse_scalar(value)
                current = None
            else:
                data[key.strip()] = {}
                current = key.strip()
        elif current and ":" in line:
            key, value = line.strip().split(":", 1)
            data[current][key.strip()] = _parse_scalar(value)
    return {"name": skill_name, "frontmatter": data, "body": body}
