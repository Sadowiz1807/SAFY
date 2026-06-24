from __future__ import annotations

import importlib.util
from pathlib import Path
import tomllib

from Scripts.validate_skills import main as validate_skills


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_packager_module():
    path = _root() / "Scripts" / "package_clean_handoff.py"
    spec = importlib.util.spec_from_file_location("safy_clean_packager", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skill_tree_is_canonical_and_contract_valid():
    root = _root()
    legacy = []
    for path in (root / "Skills").iterdir():
        if path.is_dir() and path.name != path.name.lower():
            legacy.append(path.name)
    assert not legacy
    assert not list((root / "Skills").rglob("Skill.md"))
    assert not list((root / "Skills").rglob("skill.md"))
    assert validate_skills() == 0


def test_wheel_resource_contract_declares_runtime_assets():
    data = tomllib.loads((_root() / "pyproject.toml").read_text(encoding="utf-8"))
    include = set(data["tool"]["setuptools"]["packages"]["find"]["include"])
    package_data = data["tool"]["setuptools"]["package-data"]

    assert "Apps*" in include
    assert "Configs*" in include
    assert "Skills*" in include
    assert "DomainIntelligence*" in include
    assert "Web/*.html" in package_data["Apps"]
    assert "*/SKILL.md" in package_data["Skills"]
    assert "packs/registry.json" in package_data["DomainIntelligence"]
    assert "packs/*/*/*.safy-domain" in package_data["DomainIntelligence"]


def test_clean_handoff_excludes_secrets_and_runtime(tmp_path):
    module = _load_packager_module()
    root = tmp_path / "SAFY"
    files = {
        ".env": False,
        ".env.template": True,
        ".git/config": False,
        "Data/secrets/sandbox_secrets.json": False,
        "Data/sessions/audit.sqlite3": False,
        "Data/Database_management/database_profiles.json": False,
        "Data/model_profiles/model_profiles.json": False,
        "Data/User/user_profiles.json": False,
        "DomainIntelligence/packs/registry.json": True,
        "DomainIntelligence/packs/ecommerce/1.0.0/ecommerce.safy-domain": True,
        "DomainIntelligence/packs/cache/schema_domain_cache.json": False,
        "current_state.md": True,
    }
    for relative in files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test", encoding="utf-8")

    for relative, expected in files.items():
        assert module.should_include(root, root / relative) is expected, relative
