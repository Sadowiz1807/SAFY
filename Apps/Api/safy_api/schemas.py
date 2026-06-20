from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class ModelLegacySaveRequest(BaseModel):
    provider: str
    base_url: str
    api_key_env: str = ""
    model_name: str

    model_config = ConfigDict(extra="forbid")


class ModelProviderProfileRequest(BaseModel):
    profile_id: str | None = None
    display_name: str | None = None
    provider_type: str = "openai_compatible"
    provider: str | None = None
    base_url: str = "http://localhost:1234/v1"
    model: str
    model_name: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None
    auth_mode: Literal["local_no_auth", "env_api_key"] = "local_no_auth"
    is_active: bool = False
    capabilities: dict = Field(default_factory=dict)
    context_window: int | None = None

    model_config = ConfigDict(extra="forbid")


class ModelProviderPatchRequest(BaseModel):
    display_name: str | None = None
    provider_type: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key_env: str | None = None
    auth_mode: Literal["local_no_auth", "env_api_key"] | None = None
    is_active: bool | None = None
    capabilities: dict | None = None
    context_window: int | None = None

    model_config = ConfigDict(extra="forbid")


class DatabaseLegacySaveRequest(BaseModel):
    profile_id: str | None = "main_database"
    display_name: str | None = "Main database"
    provider: Literal["unified", "self_hosted", "supabase", "google_cloud_sql", "aws_aurora"] = "self_hosted"
    base_url: str | None = None
    driver: Literal["mysql", "postgresql", "postgres", "sqlite", "sqlserver", "oracle", "aurora_mysql", "aurora_postgresql", "supabase_rpc", "supabase_rest"] = "sqlite"
    dbms: str | None = None
    engine: str | None = None
    host: str = "127.0.0.1"
    port: int = 0
    database: str
    username: str = ""
    api_key: str = ""
    raw_secret: str = ""
    secret_mode: Literal["none", "env", "raw_secret"] = "env"
    password_mode: Literal["none", "env", "raw_secret"] = "env"
    password_env: str = ""
    ssl_mode: str = "preferred"
    user_query_access_mode: Literal["credential_permissions", "read_only", "disabled"] = "credential_permissions"
    read_only: bool = True
    active: bool = True
    real_db_readonly: bool = True
    allowed_root: str | None = None

    model_config = ConfigDict(extra="forbid")


class AgentChatRequest(BaseModel):
    chat_id: str | None = None
    session_id: str | None = None
    message: str
    model_profile_id: str | None = None
    database_profile_id: str | None = None
    sandbox_id: str | None = None
    target: Literal["auto", "sandbox", "connected_database"] = "auto"
    auto_execute: bool = True
    options: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class SessionCreateRequest(BaseModel):
    chat_id: str | None = None
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class SessionMessageRequest(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str
    audit_id: str | None = None
    workspace_id: str | None = None
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class QueryCheckRequest(BaseModel):
    sql: str
    chat_id: str | None = None
    session_id: str | None = None
    target: str = "connected_database"
    sandbox_id: str | None = None
    database_profile_id: str | None = None
    user_query_access_mode: Literal["credential_permissions", "read_only", "disabled"] = "credential_permissions"
    real_db_mode: bool = False

    model_config = ConfigDict(extra="forbid")


class QueryExecuteRequest(BaseModel):
    check_id: str | None = None
    sql_hash: str | None = None
    chat_id: str | None = None
    session_id: str | None = None
    target: str = "connected_database"
    sandbox_id: str | None = None
    database_profile_id: str | None = None
    user_decision: Literal["yes", "no"] | None = None
    confirmation_code: str | None = Field(default=None, pattern=r"^\d{4}$")
    real_db_mode: bool = False
    row_limit: int = 100

    model_config = ConfigDict(extra="forbid")


class SandboxCreateRequest(BaseModel):
    sandbox_id: str | None = None
    id: str | None = None
    name: str | None = "Default sandbox"
    project_id: str | None = "project_default"
    workspace_id: str | None = "workspace_default"
    dbms: str | None = None
    engine: str | None = "sqlite"
    provider_compatibility: str | None = "self_hosted"
    source_kind: str | None = None
    source_ref: str | None = None
    read_only: bool = True
    network_disabled: bool = True
    active: bool = True
    deactivate_existing: bool = False
    created_by: str | None = None

    model_config = ConfigDict(extra="forbid")


class SandboxRestoreRequest(BaseModel):
    source_type: str | None = None
    source_kind: str | None = None
    source_path: str | None = None

    model_config = ConfigDict(extra="forbid")


class RecoveryResolveRequest(BaseModel):
    recovery_id: str
    action: Literal["cleanup", "restore", "abandon"]

    model_config = ConfigDict(extra="forbid")


class DatabaseTestRequest(BaseModel):
    database_profile_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class UserLoginRequest(BaseModel):
    username: str = ""
    password: str = ""
    use_saved_password: bool = False

    model_config = ConfigDict(extra="forbid")
