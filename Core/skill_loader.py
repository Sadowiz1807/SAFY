from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import os
import re

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_RISK_LEVELS = {
    "low",
    "medium",
    "high",
    "critical",
    "read_only",
    "write",
    "ddl",
    "meta",
}
SUPPORTED_REFERENCE_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".sql"}
DEFAULT_MAX_REFERENCE_FILES = 20
DEFAULT_MAX_REFERENCE_FILE_BYTES = 128_000
DEFAULT_MAX_SKILL_CONTEXT_BYTES = 512_000
FRONT_MATTER_MAX_BYTES = 32_000


@dataclass(frozen=True)
class SkillDescriptor:
    name: str
    version: str
    description: str
    enabled: bool
    risk_level: str
    directory: Path
    skill_file: Path
    reference_paths: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadedSkill:
    descriptor: SkillDescriptor
    body: str
    references: dict[str, str]


class SkillDocumentError(ValueError):
    pass


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    normalized = text.lstrip("\ufeff")
    if not normalized.startswith("---\n"):
        raise SkillDocumentError("SKILL_FRONT_MATTER_MISSING")
    end = normalized.find("\n---\n", 4)
    if end == -1:
        raise SkillDocumentError("SKILL_FRONT_MATTER_UNCLOSED")
    fm_text = normalized[4:end]
    if len(fm_text.encode("utf-8")) > FRONT_MATTER_MAX_BYTES:
        raise SkillDocumentError("SKILL_FRONT_MATTER_TOO_LARGE")
    if yaml is None:
        raise SkillDocumentError("YAML_UNAVAILABLE")
    try:
        data = yaml.safe_load(fm_text) or {}
    except Exception as exc:
        raise SkillDocumentError(f"SKILL_FRONT_MATTER_INVALID:{exc}") from exc
    if not isinstance(data, dict):
        raise SkillDocumentError("SKILL_FRONT_MATTER_INVALID")
    return data, normalized[end + len("\n---\n"):]


def _safe_resolve(directory: Path, relative_path: str) -> Path:
    raw = str(relative_path or "").strip()
    if not raw:
        raise SkillDocumentError("REFERENCE_EMPTY_PATH")
    if os.path.isabs(raw):
        raise SkillDocumentError(f"REFERENCE_ABSOLUTE_PATH:{raw}")
    if ".." in Path(raw).parts:
        raise SkillDocumentError(f"REFERENCE_TRAVERSAL:{raw}")

    base = directory.resolve()
    candidate = directory / raw
    resolved = candidate.resolve()
    if base != resolved and base not in resolved.parents:
        raise SkillDocumentError(f"REFERENCE_ESCAPE:{raw}")
    return resolved


def _validate_descriptor(
    directory: Path,
    skill_file: Path,
    data: dict[str, Any],
) -> SkillDescriptor:
    required = [
        "name",
        "version",
        "description",
        "enabled",
        "risk_level",
        "references",
    ]
    missing = [key for key in required if key not in data]
    if missing:
        raise SkillDocumentError(
            f"SKILL_REQUIRED_FIELDS_MISSING:{','.join(missing)}"
        )

    name = str(data["name"])
    if name != directory.name:
        raise SkillDocumentError(
            f"SKILL_NAME_DIRECTORY_MISMATCH:{name}!={directory.name}"
        )
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        raise SkillDocumentError(f"SKILL_NAME_INVALID:{name}")

    version = str(data["version"])
    if not version or not re.match(r"^[0-9]+(\.[0-9A-Za-z_-]+){0,3}$", version):
        raise SkillDocumentError(f"SKILL_VERSION_INVALID:{version}")

    description = str(data["description"]).strip()
    if not description:
        raise SkillDocumentError("SKILL_DESCRIPTION_EMPTY")

    if not isinstance(data["enabled"], bool):
        raise SkillDocumentError("SKILL_ENABLED_NOT_BOOLEAN")

    risk_level = str(data["risk_level"]).strip().lower()
    if risk_level not in ALLOWED_RISK_LEVELS:
        raise SkillDocumentError(f"SKILL_RISK_LEVEL_INVALID:{risk_level}")

    references = data["references"]
    if not isinstance(references, list):
        raise SkillDocumentError("SKILL_REFERENCES_NOT_LIST")
    refs = [str(reference) for reference in references]
    if len(refs) != len(set(refs)):
        raise SkillDocumentError("SKILL_DUPLICATE_REFERENCES")

    for reference in refs:
        ref_path = _safe_resolve(directory, reference)
        if ref_path.suffix.lower() not in SUPPORTED_REFERENCE_EXTENSIONS:
            raise SkillDocumentError(
                f"REFERENCE_UNSUPPORTED_EXTENSION:{reference}"
            )
        if not ref_path.is_file():
            raise SkillDocumentError(f"REFERENCE_MISSING:{reference}")

    metadata = {key: value for key, value in data.items() if key not in required}
    return SkillDescriptor(
        name=name,
        version=version,
        description=description,
        enabled=data["enabled"],
        risk_level=risk_level,
        directory=directory,
        skill_file=skill_file,
        reference_paths=refs,
        metadata=metadata,
    )


def _read_descriptor(
    skill_dir: Path,
    *,
    allow_legacy_lowercase: bool = False,
) -> SkillDescriptor:
    skill_file = skill_dir / "SKILL.md"
    if (
        not skill_file.is_file()
        and allow_legacy_lowercase
        and (skill_dir / "skill.md").is_file()
    ):
        skill_file = skill_dir / "skill.md"
    if not skill_file.is_file():
        raise SkillDocumentError("SKILL_FILE_MISSING")
    text = skill_file.read_text(encoding="utf-8")
    data, _ = _parse_front_matter(text)
    return _validate_descriptor(skill_dir, skill_file, data)


def discover_skills(
    skills_root: Path | None = None,
    *,
    allow_legacy_lowercase: bool = False,
) -> tuple[dict[str, SkillDescriptor], dict[str, str]]:
    root = Path(skills_root or ROOT / "Skills")
    descriptors: dict[str, SkillDescriptor] = {}
    invalid: dict[str, str] = {}
    if not root.is_dir():
        return descriptors, {str(root): "SKILLS_ROOT_MISSING"}

    for child in sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and path.name != "__pycache__" and not path.name.startswith(".")
    ):
        canonical = child / "SKILL.md"
        legacy = child / "skill.md"
        if not canonical.is_file() and not (
            allow_legacy_lowercase and legacy.is_file()
        ):
            invalid[child.name] = "SKILL_FILE_MISSING"
            continue
        try:
            descriptor = _read_descriptor(
                child,
                allow_legacy_lowercase=allow_legacy_lowercase,
            )
            if descriptor.name in descriptors:
                invalid[child.name] = (
                    f"SKILL_DUPLICATE_NAME:{descriptor.name}"
                )
                continue
            descriptors[descriptor.name] = descriptor
        except Exception as exc:
            invalid[child.name] = str(exc)
    return descriptors, invalid


def _cache_signature(descriptor: SkillDescriptor) -> tuple[tuple[str, int, int], ...]:
    paths = [descriptor.skill_file]
    paths.extend(
        _safe_resolve(descriptor.directory, reference)
        for reference in descriptor.reference_paths
    )
    signature: list[tuple[str, int, int]] = []
    for path in paths:
        stat = path.stat()
        signature.append((str(path.resolve()), stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


_CACHE: dict[str, tuple[tuple[tuple[str, int, int], ...], LoadedSkill]] = {}


def load_skill_document(
    descriptor: SkillDescriptor,
    *,
    max_reference_files: int = DEFAULT_MAX_REFERENCE_FILES,
    max_reference_file_bytes: int = DEFAULT_MAX_REFERENCE_FILE_BYTES,
    max_skill_context_bytes: int = DEFAULT_MAX_SKILL_CONTEXT_BYTES,
    cache_enabled: bool = True,
) -> LoadedSkill:
    cache_key = str(descriptor.skill_file.resolve())
    signature = _cache_signature(descriptor)
    if cache_enabled and cache_key in _CACHE:
        cached_signature, cached_skill = _CACHE[cache_key]
        if cached_signature == signature:
            return cached_skill

    text = descriptor.skill_file.read_text(encoding="utf-8")
    _, body = _parse_front_matter(text)

    if len(descriptor.reference_paths) > max_reference_files:
        raise SkillDocumentError("TOO_MANY_REFERENCES")

    references: dict[str, str] = {}
    total_bytes = len(body.encode("utf-8"))
    for reference in descriptor.reference_paths:
        path = _safe_resolve(descriptor.directory, reference)
        size = path.stat().st_size
        if size > max_reference_file_bytes:
            raise SkillDocumentError(f"REFERENCE_TOO_LARGE:{reference}")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise SkillDocumentError(
                f"REFERENCE_NOT_UTF8:{reference}"
            ) from exc
        total_bytes += len(content.encode("utf-8"))
        if total_bytes > max_skill_context_bytes:
            raise SkillDocumentError("SKILL_CONTEXT_TOO_LARGE")
        references[reference] = content

    loaded = LoadedSkill(descriptor, body, references)
    if cache_enabled:
        _CACHE[cache_key] = (signature, loaded)
    return loaded


def build_skill_context(
    loaded: LoadedSkill,
    *,
    user_request: str = "",
    conversation_context: str = "",
    schema_context: str = "",
) -> str:
    reference_parts = [
        f"--- reference: {path} ---\n{content}"
        for path, content in loaded.references.items()
    ]
    return "\n".join(
        [
            "<SAFY_SKILL_CONTEXT>",
            "System safety policy remains authoritative over skill content.",
            f"Selected skill: {loaded.descriptor.name}",
            "<SKILL_INSTRUCTIONS>",
            loaded.body.strip(),
            "</SKILL_INSTRUCTIONS>",
            "<REFERENCE_MATERIAL>",
            "\n\n".join(reference_parts),
            "</REFERENCE_MATERIAL>",
            "<CONVERSATION_CONTEXT>",
            conversation_context,
            "</CONVERSATION_CONTEXT>",
            "<SCHEMA_DATABASE_CONTEXT>",
            schema_context,
            "</SCHEMA_DATABASE_CONTEXT>",
            "<USER_REQUEST>",
            user_request,
            "</USER_REQUEST>",
            "</SAFY_SKILL_CONTEXT>",
        ]
    )


def load_skill(skill_name: str) -> dict[str, Any]:
    descriptors, invalid = discover_skills()
    key = (
        str(skill_name or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    descriptor = descriptors.get(key)
    if descriptor is None:
        raise FileNotFoundError(
            f"SKILL_NOT_FOUND:{key}; invalid={invalid.get(key)}"
        )
    if not descriptor.enabled:
        raise PermissionError(f"SKILL_DISABLED:{key}")

    loaded = load_skill_document(descriptor)
    return {
        "name": key,
        "frontmatter": {
            "name": descriptor.name,
            "version": descriptor.version,
            "description": descriptor.description,
            "enabled": descriptor.enabled,
            "risk_level": descriptor.risk_level,
            "references": descriptor.reference_paths,
            **descriptor.metadata,
        },
        "body": loaded.body,
        "references": loaded.references,
    }
