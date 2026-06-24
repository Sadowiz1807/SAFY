from __future__ import annotations

from pathlib import Path

import pytest

from Core.skill_loader import discover_skills, load_skill_document, SkillDocumentError, build_skill_context
from Core.skill_registry import SkillRegistry
from Core.skill_router import route_skill


def write_skill(root: Path, name: str, body: str = "ok", refs: list[str] | None = None, enabled: bool = True, risk: str = "medium") -> Path:
    d = root / name
    d.mkdir()
    refs = refs or []
    (d / "SKILL.md").write_text(f"""---
name: {name}
version: 1.0.0
description: Test skill
enabled: {str(enabled).lower()}
risk_level: {risk}
references: {refs!r}
---
# {name}
## Purpose
{body}
## When to use
Use in tests.
## Required context
Context.
## Procedure
Procedure.
## Safety rules
Safe.
## Expected output
Output.
## Failure behavior
Fail closed.
""", encoding="utf-8")
    return d


def test_valid_and_disabled_skill_discovery(tmp_path: Path):
    write_skill(tmp_path, "valid_skill")
    write_skill(tmp_path, "disabled_skill", enabled=False)
    descriptors, invalid = discover_skills(tmp_path)
    assert "valid_skill" in descriptors
    assert descriptors["disabled_skill"].enabled is False
    assert invalid == {}


def test_malformed_skill_isolated(tmp_path: Path):
    write_skill(tmp_path, "valid_skill")
    bad = tmp_path / "bad_skill"; bad.mkdir(); (bad / "SKILL.md").write_text("not yaml", encoding="utf-8")
    descriptors, invalid = discover_skills(tmp_path)
    assert "valid_skill" in descriptors
    assert "bad_skill" in invalid


def test_reference_security_and_lazy_load(tmp_path: Path):
    d = write_skill(tmp_path, "ref_skill", refs=["references/a.md"])
    (d / "references").mkdir(); (d / "references" / "a.md").write_text("reference body", encoding="utf-8")
    descriptors, _ = discover_skills(tmp_path)
    desc = descriptors["ref_skill"]
    loaded = load_skill_document(desc)
    assert loaded.references["references/a.md"] == "reference body"
    assert "reference body" in build_skill_context(loaded)


def test_missing_and_traversal_references_fail(tmp_path: Path):
    write_skill(tmp_path, "missing_ref", refs=["references/nope.md"])
    descriptors, invalid = discover_skills(tmp_path)
    assert "missing_ref" in invalid
    write_skill(tmp_path, "bad_ref", refs=["../escape.md"])
    descriptors, invalid = discover_skills(tmp_path)
    assert "bad_ref" in invalid


def test_registry_and_router(tmp_path: Path):
    write_skill(tmp_path, "text_to_sql")
    registry = SkillRegistry(skills_root=tmp_path)
    assert "text_to_sql" in registry.active_names()
    assert route_skill("connected_read_only_query", registry) == "text_to_sql"
