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
    table_list = r"([A-Za-z0-9_\.\"`\[\]]+(?:\s*,\s*[A-Za-z0-9_\.\"`\[\]]+)*)"
    list_patterns = [
        rf"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?{table_list}",
        rf"\bTRUNCATE\s+TABLE\s+{table_list}",
    ]
    for pattern in list_patterns:
        for match in re.finditer(pattern, sql, re.IGNORECASE):
            for raw_name in match.group(1).split(","):
                name = _clean_identifier(raw_name)
                if name and name not in targets:
                    targets.append(name)
    patterns = [
        # CREATE TABLE IF NOT EXISTS previously captured the token "IF" as the
        # affected table. Keep the optional clause inside the pattern so the
        # actual object name is returned.
        r"\b(?:CREATE|ALTER)\s+TABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?[A-Za-z0-9_\.\"`\[\]]+\s+ON\s+([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bFROM\s+([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bJOIN\s+([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bINTO\s+([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bUPDATE\s+([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bDELETE\s+FROM\s+([A-Za-z0-9_\.\"`\[\]]+)",
        r"\bTABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?([A-Za-z0-9_\.\"`\[\]]+)",
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
