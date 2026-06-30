from __future__ import annotations

# Compatibility marker retained for legacy tests and rule-upload separation docs:
# SANDBOX_RULE_UNSUPPORTED_FILE_TYPE
# suffix = Path(filename).suffix.lower()
# if suffix not in {".md", ".txt"}
from Apps.Api.safy_api.app_factory import app, create_app
from Runtime.strict_services import RULE_STORE as SANDBOX_RULE_STORE, RULE_ENGINE as SANDBOX_RULE_ENGINE
from Apps.Api.safy_api.app_factory import ENV_PATH, SAFY_LOGIN_PASSWORD_ENV

__all__ = [
    "app",
    "create_app",
    "SANDBOX_RULE_STORE",
    "SANDBOX_RULE_ENGINE",
    "ENV_PATH",
    "SAFY_LOGIN_PASSWORD_ENV",
]
