from __future__ import annotations

from Logging.redact import redact_text


def build_provider_prompt(message: str, domain: str, assumptions: list[str]) -> str:
    safe_message = redact_text(message or "") or ""
    return "\n".join([
        "Task: propose a sandbox-only database schema plan.",
        f"Domain: {domain}",
        "Target: sandbox only",
        "Do not include secrets or raw data samples.",
        f"User request: {safe_message[:500]}",
        "Assumptions: " + "; ".join(assumptions),
    ])
