from __future__ import annotations

from dataclasses import dataclass, field

from .sql_guard import BLOCK_PERMISSION, GuardDecision

READ_ONLY = "read_only"
DISABLED = "disabled"
CREDENTIAL_PERMISSIONS = "credential_permissions"
SANDBOX_TEST_SUPPORT = "sandbox_test_support"


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    decision: str | None = None
    permission_mode: str = READ_ONLY
    reasons: list[str] = field(default_factory=list)


def evaluate_permission(guard: GuardDecision, is_read_only: bool, permission_mode: str = READ_ONLY, execution_path: str = "user_query") -> PermissionDecision:
    if execution_path == "agent" and not is_read_only:
        return PermissionDecision(False, BLOCK_PERMISSION, permission_mode, ["agent_path_read_only"])
    if permission_mode == DISABLED:
        return PermissionDecision(False, BLOCK_PERMISSION, permission_mode, ["database_profile_disabled"])
    if permission_mode == READ_ONLY and not is_read_only:
        return PermissionDecision(False, BLOCK_PERMISSION, permission_mode, ["read_only_blocks_mutation"])
    if permission_mode == CREDENTIAL_PERMISSIONS and not is_read_only:
        return PermissionDecision(False, BLOCK_PERMISSION, permission_mode, ["credential_permissions_not_live_probed"])
    if permission_mode == SANDBOX_TEST_SUPPORT:
        return PermissionDecision(True, guard.decision, permission_mode, ["credential_permissions_not_live_probed"])
    if permission_mode == CREDENTIAL_PERMISSIONS:
        return PermissionDecision(True, guard.decision, permission_mode, ["credential_permissions_read_only"])
    if permission_mode not in {READ_ONLY, DISABLED, CREDENTIAL_PERMISSIONS, SANDBOX_TEST_SUPPORT}:
        return PermissionDecision(False, BLOCK_PERMISSION, permission_mode, ["unknown_permission_mode"])
    return PermissionDecision(True, guard.decision, permission_mode, [])
