from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class NormalizedSQL:
    original_sql: str
    sql_without_comments: str
    normalized_sql: str
    statements: list[str]
    is_multi_statement: bool


_SQL_FENCE_RE = re.compile(
    r"^\s*```(?:sql|postgresql|postgres|mysql|sqlite|tsql|plsql)?[ \t]*\r?\n?(?P<body>[\s\S]*?)\r?\n?```\s*$",
    re.IGNORECASE,
)


def sanitize_sql_input(sql: str | None) -> str:
    """Return a safe SQL candidate without weakening fail-closed parsing.

    SAFY accepts a single Markdown SQL code block because model providers often
    return SQL in that format. Prose around a fence, multiple fences, and other
    mixed content are intentionally left untouched so the classifier can reject
    them as UNKNOWN/MULTI_STATEMENT instead of extracting executable text.
    """
    text = "" if sql is None else str(sql)
    match = _SQL_FENCE_RE.fullmatch(text)
    return match.group("body").strip() if match else text.strip()


def strip_comments(sql: str) -> str:
    # Keeps string literals intact while removing line/block comments.
    out: list[str] = []
    i = 0
    quote: str | None = None
    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""
        if quote:
            out.append(ch)
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    out.append(sql[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "-" and nxt == "-":
            i += 2
            while i < len(sql) and sql[i] not in "\r\n":
                i += 1
            out.append(" ")
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < len(sql) and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i = min(i + 2, len(sql))
            out.append(" ")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def split_statements(sql: str) -> list[str]:
    statements: list[str] = []
    start = 0
    quote: str | None = None
    i = 0
    while i < len(sql):
        ch = sql[i]
        if quote:
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == ";":
            part = sql[start:i].strip()
            if part:
                statements.append(part)
            start = i + 1
        i += 1
    tail = sql[start:].strip()
    if tail:
        statements.append(tail)
    return statements


def normalize_sql(sql: str) -> NormalizedSQL:
    original_sql = "" if sql is None else str(sql)
    candidate = sanitize_sql_input(original_sql)
    stripped = strip_comments(candidate)
    statements = [re.sub(r"\s+", " ", s).strip() for s in split_statements(stripped)]
    normalized = "; ".join(statements)
    return NormalizedSQL(
        original_sql=original_sql,
        sql_without_comments=stripped,
        normalized_sql=normalized,
        statements=statements,
        is_multi_statement=len(statements) > 1,
    )
