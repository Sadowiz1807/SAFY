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
    request_timeout_seconds: int = 180

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
    request_timeout_seconds: int | None = None

    model_config = ConfigDict(extra="forbid")


class DatabaseProfilePayload(BaseModel):
    """Unified database connection payload used by every supported DB type.

    The browser always sends this complete shape. The backend treats
    ``database_type`` plus structured fields as authoritative and keeps URL
    inference only for backward compatibility.
    """

    schema_version: str = "1.0"
    profile_id: str | None = "main_database"
    profile_name: str | None = None
    connection_name: str | None = None
    display_name: str | None = "Main database"
    database_type: Literal["postgresql", "supabase_rpc", "mysql", "mariadb", "sqlite", "sqlserver", "oracle"] | None = None
    provider: str | None = None
    driver: str | None = None
    dbms: str | None = None
    engine: str | None = None
    connection_kind: str | None = None
    execution_transport: str | None = None
    base_url: str | None = None
    host: str | None = None
    port: int | None = None
    instance: str | None = None
    database: str | None = None
    database_schema: str | None = Field(default=None, alias="schema")
    sqlite_path: str | None = None
    allowed_root: str | None = None
    service_name: str | None = None
    sid: str | None = None
    authentication: Literal["password", "api_key", "none", "sql_server", "windows"] | None = None
    trusted_connection: bool = False
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    raw_secret: str | None = None
    secret_kind: Literal["password", "api_key", "none"] | None = None
    preserve_secret: bool = False
    secret_mode: Literal["none", "env", "raw_secret"] = "none"
    password_mode: Literal["none", "env", "raw_secret"] = "none"
    password_env: str | None = None
    api_key_env: str | None = None
    secret_env: str | None = None
    ssl_mode: str | None = "preferred"
    encrypt: bool = True
    trust_server_certificate: bool = False
    odbc_driver: str | None = None
    sql_rpc_function: str | None = "safy_execute_sql"
    sql_rpc_argument: str | None = "sql"
    timeout_seconds: int = Field(default=15, ge=1, le=300)
    user_query_access_mode: Literal["credential_permissions", "read_only", "disabled"] = "credential_permissions"
    read_only: bool = True
    active: bool = True
    real_db_readonly: bool = True

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DatabaseLegacySaveRequest(BaseModel):
    profile_id: str | None = "main_database"
    display_name: str | None = "Main database"
    provider: Literal["unified", "self_hosted", "supabase", "google_cloud_sql", "aws_aurora"] = "self_hosted"
    base_url: str | None = None
    driver: Literal["mysql", "mariadb", "postgresql", "postgres", "sqlite", "sqlserver", "oracle", "aurora_mysql", "aurora_postgresql", "supabase_rpc", "supabase_rest"] = "sqlite"
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
    context_file_ids: list[str] = Field(default_factory=list)
    model_profile_id: str | None = None
    database_profile_id: str | None = None
    sandbox_id: str | None = None
    target: Literal["auto", "sandbox", "connected_database"] = "auto"
    auto_execute: bool = True
    options: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ContextUrlFetchRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)

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
    context_generation: int | None = None
    schema_generation: str | None = None
    driver: str | None = None
    dialect: str | None = None

    model_config = ConfigDict(extra="forbid")


class QueryExecuteRequest(BaseModel):
    sql: str | None = None
    check_id: str | None = None
    sql_hash: str | None = None
    chat_id: str | None = None
    session_id: str | None = None
    target: str = "connected_database"
    sandbox_id: str | None = None
    database_profile_id: str | None = None
    user_query_access_mode: Literal["credential_permissions", "read_only", "disabled"] | None = None
    user_decision: Literal["yes", "no"] | None = None
    confirmation_code: str | None = Field(default=None, pattern=r"^\d{4}$")
    real_db_mode: bool = False
    row_limit: int = Field(default=100, ge=1, le=1000)
    context_generation: int | None = None
    schema_generation: str | None = None
    driver: str | None = None
    dialect: str | None = None

    model_config = ConfigDict(extra="forbid")


class SandboxRuleDraftRequest(BaseModel):
    database_profile_id: str
    sandbox_id: str = "sandbox_default"
    raw_text: str
    rule_id: str | None = None
    connection_name: str | None = None
    source_type: str = "manual_text"
    source_filename: str | None = None
    severity: Literal["block", "warn"] = "block"

    model_config = ConfigDict(extra="forbid")


class SandboxRuleActionRequest(BaseModel):
    database_profile_id: str
    sandbox_id: str = "sandbox_default"
    rule_id: str
    decision: str | None = None

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
