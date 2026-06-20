from __future__ import annotations

from dataclasses import dataclass
import re

from .sql_classifier import SQLClassification


@dataclass(frozen=True)
class TargetExtraction:
    targets: list[str]
    warnings: list[str]


def _clean_identifier(value: str) -> str:
    return value.strip().strip('"`[]')


def extract_targets(classification: SQLClassification) -> TargetExtraction:
    sql = classification.normalized.normalized_sql
    targets: list[str] = []
    warnings: list[str] = []
    patterns = [
        r"\bFROM\s+([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bJOIN\s+([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bINTO\s+([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bUPDATE\s+([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bDELETE\s+FROM\s+([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bTABLE\s+([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bDATABASE\s+([A-Za-z0-9_\.\"`\[\]]+)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, sql, re.IGNORECASE):
            name = _clean_identifier(match.group(1))
            if name and name not in targets:
                targets.append(name)
    if not targets:
        warnings.append("target_extraction_best_effort_no_targets")
    return TargetExtraction(targets=targets, warnings=warnings)
