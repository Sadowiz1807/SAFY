from __future__ import annotations

from pathlib import Path
import json
import os
import sqlite3
import subprocess
import shutil

from Gateway.db_drivers import execute_readonly
from Gateway.db_drivers.errors import DriverError
from Gateway.sql_normalizer import normalize_sql

from .audit import SandboxAudit
from .docker_manager import DockerSandboxManager
from .restore_manager import RestoreManager
from .sandbox_state import SandboxRecord, assert_transition, now_iso
from .sandbox_store import SandboxStore, safe_id
from .schema_cache import SchemaCache
from .secret_store import LocalSecretStore

class SandboxError(Exception):
    def __init__(self, code: str, message: str | None = None, details: dict | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message or code)

class SandboxManager:
    def __init__(self, repo_root: Path | str | None = None):
        resolved_root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
        self.repo_root = resolved_root
        self.data_root = resolved_root / "Data"
        self.store = SandboxStore(self.data_root)
        self.secrets = LocalSecretStore(self.data_root)
        self.docker = DockerSandboxManager(resolved_root)

    def _audit(self, sandbox_id: str) -> SandboxAudit:
        return SandboxAudit(self.store.sandbox_dir(sandbox_id))

    def _public(self, record: SandboxRecord) -> dict:
        data = record.to_dict()
        data.pop("runtime_handle", None)
        data["id"] = record.sandbox_id
        data["engine"] = record.dbms
        data["status"] = record.state
        data["network_disabled"] = True
        return data

    def _legacy_workspace_root(self) -> Path:
        return self.repo_root / "Sandbox" / "workspaces"

    def create_workspace(self, chat_id: str, workflow_id: str) -> dict:
        workspace_id = safe_id(f"ws_{workflow_id}")
        workspace_dir = self._legacy_workspace_root() / workspace_id
        workspace_dir.mkdir(parents=True, exist_ok=True)
        db_path = workspace_dir / "sandbox.sqlite3"
        manifest = {
            "workspace_id": workspace_id,
            "chat_id": chat_id,
            "workflow_id": workflow_id,
            "db_path": str(db_path),
            "target": "sandbox",
        }
        (workspace_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        return manifest

    def manifest_for_path(self, db_path: Path) -> dict:
        resolved = Path(db_path).resolve()
        managed_roots = [self._legacy_workspace_root().resolve(), self.store.root.resolve()]
        if not any(resolved == root or root in resolved.parents for root in managed_roots):
            raise ValueError("db_path_outside_managed_sandbox")
        manifest_path = resolved.parent / "manifest.json"
        if manifest_path.exists():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        return {"db_path": str(resolved), "target": "sandbox"}

    def create(self, payload: dict) -> dict:
        try:
            sandbox_id = safe_id(payload.get("sandbox_id") or payload.get("id") or "sandbox_default")
        except ValueError as exc:
            raise SandboxError("SANDBOX_INVALID_ID", str(exc)) from exc
        project_id = payload.get("project_id") or "project_default"
        workspace_id = payload.get("workspace_id") or "workspace_default"
        active = bool(payload.get("active", True))
        current = self.store.active_for_scope(project_id, workspace_id)
        if active and current and current.sandbox_id != sandbox_id and not payload.get("deactivate_existing"):
            raise SandboxError("ACTIVE_SANDBOX_CONFLICT", "An active sandbox already exists for this project/workspace.")
        if active and current and current.sandbox_id != sandbox_id:
            current.active = False
            current.updated_at = now_iso()
            self.store.save(current)
        if self.store.metadata_path(sandbox_id).exists():
            raise SandboxError("SANDBOX_ALREADY_EXISTS")
        dbms = (payload.get("dbms") or payload.get("engine") or "sqlite").lower()
        record = SandboxRecord(
            sandbox_id=sandbox_id,
            name=payload.get("name") or "Default sandbox",
            project_id=project_id,
            workspace_id=workspace_id,
            dbms=dbms,
            provider_compatibility=payload.get("provider_compatibility") or "self_hosted",
            source_kind=payload.get("source_kind"),
            source_ref=payload.get("source_ref"),
            active=active,
            created_by=payload.get("created_by"),
        )
        d = self.store.sandbox_dir(sandbox_id)
        record.schema_cache_path = str(d / "schema_cache.json")
        record.restore_job_path = str(d / "restore_job.json")
        record.readonly_credential_ref = self.secrets.create_password(sandbox_id, "readonly_credential")
        if dbms in {"postgresql", "postgres", "supabase_postgres"}:
            record.container_ref = self.docker.runtime_names(sandbox_id, "postgresql")["container"]
            record.runtime_handle = {"owner_credential_ref": self.secrets.create_password(sandbox_id, "owner_credential")}
        self.store.save(record)
        self._audit(sandbox_id).write("sandbox_create", sandbox_id, project_id=project_id, workspace_id=workspace_id, dbms=dbms)
        SchemaCache(d).write_empty(dbms)
        return self._public(record)

    def list(self) -> list[dict]:
        return [self._public(r) for r in self.store.list() if r.state != "deleted"]

    def get(self, sandbox_id: str) -> dict:
        return self._public(self.store.get(sandbox_id))

    def transition(self, sandbox_id: str, state: str) -> SandboxRecord:
        record = self.store.get(sandbox_id)
        try:
            assert_transition(record.state, state)
        except ValueError as exc:
            self._audit(sandbox_id).write("sandbox_transition", sandbox_id, status="failed", error_code="INVALID_SANDBOX_TRANSITION")
            raise SandboxError("INVALID_SANDBOX_TRANSITION", str(exc)) from exc
        record.state = state
        record.updated_at = now_iso()
        record.last_error_code = None
        self.store.save(record)
        self._audit(sandbox_id).write("sandbox_transition", sandbox_id, state=state)
        return record


    def missing_runtime_secret_refs(self, sandbox_id: str) -> list[str]:
        """Return missing internal sandbox credential references.

        These are NOT the user's real database/API keys from .env. They are
        SAFY-generated local credentials stored under Data/secrets and used to
        operate the isolated sandbox runtime. Full-project exports intentionally
        exclude Data/secrets, so old sandbox metadata can point at refs that no
        longer exist after applying a clean project package.
        """
        record = self.store.get(sandbox_id)
        missing: list[str] = []
        readonly_ref = record.readonly_credential_ref or ""
        if not readonly_ref or not self.secrets.get(readonly_ref):
            missing.append("readonly_credential_ref")
        if self._is_postgres(record):
            owner_ref = (record.runtime_handle or {}).get("owner_credential_ref") or ""
            if not owner_ref or not self.secrets.get(owner_ref):
                missing.append("owner_credential_ref")
        return missing

    def runtime_secrets_ready(self, sandbox_id: str) -> bool:
        return not self.missing_runtime_secret_refs(sandbox_id)

    def recreate_existing(self, sandbox_id: str, delete_volume: bool = True) -> dict:
        """Recreate an existing sandbox and regenerate internal credentials.

        This is used when metadata survived but Data/secrets did not. In that
        situation the real database profile can still be valid, but the local
        sandbox cannot be controlled because its SAFY-generated owner/readonly
        credentials are gone.
        """
        try:
            old = self.store.get(sandbox_id)
        except KeyError as exc:
            raise SandboxError("SANDBOX_NOT_FOUND", f"Sandbox not found: {sandbox_id}") from exc

        if self._is_postgres(old):
            names = self.docker.runtime_names(old.sandbox_id, "postgresql")
            container = old.container_ref or names["container"]
            try:
                self.docker.delete(container, names.get("volume"), delete_volume=delete_volume)
            except Exception as exc:
                if self.docker.required():
                    raise SandboxError("SANDBOX_RECREATE_FAILED", str(exc), {"sandbox_id": sandbox_id}) from exc

        for ref in [old.readonly_credential_ref, (old.runtime_handle or {}).get("owner_credential_ref")]:
            self.secrets.delete(ref)
        self.store.delete_files(sandbox_id)

        payload = {
            "id": old.sandbox_id,
            "name": old.name,
            "project_id": old.project_id,
            "workspace_id": old.workspace_id,
            "engine": old.dbms,
            "provider_compatibility": old.provider_compatibility,
            "source_kind": old.source_kind,
            "source_ref": old.source_ref,
            "active": old.active,
            "created_by": old.created_by or "sandbox_secret_repair",
            "deactivate_existing": True,
        }
        self.create(payload)
        return self.start(sandbox_id)

    def _owner_password(self, record: SandboxRecord) -> str:
        ref = record.runtime_handle.get("owner_credential_ref")
        password = self.secrets.get(ref or "")
        if not password:
            raise SandboxError("SANDBOX_SECRET_MISSING")
        return password

    def _readonly_password(self, record: SandboxRecord) -> str:
        password = self.secrets.get(record.readonly_credential_ref or "")
        if not password:
            raise SandboxError("SANDBOX_SECRET_MISSING")
        return password

    def _postgres_container(self, record: SandboxRecord) -> str:
        container = record.container_ref or self.docker.runtime_names(record.sandbox_id, "postgresql")["container"]
        return container

    def _is_postgres(self, record: SandboxRecord) -> bool:
        return record.dbms in {"postgresql", "postgres", "supabase_postgres"}

    def _setup_postgres_readonly(self, record: SandboxRecord) -> None:
        owner_password = self._owner_password(record)
        readonly_password = self._readonly_password(record)
        escaped = readonly_password.replace("'", "''")
        sql = f"""
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'safy_readonly') THEN
    CREATE ROLE safy_readonly LOGIN PASSWORD '{escaped}';
  ELSE
    ALTER ROLE safy_readonly LOGIN PASSWORD '{escaped}';
  END IF;
END $$;
GRANT CONNECT ON DATABASE safy_sandbox TO safy_readonly;
GRANT USAGE ON SCHEMA public TO safy_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO safy_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO safy_readonly;
"""
        self.docker.exec_psql(self._postgres_container(record), sql, user="safy_owner", password=owner_password, output_json=False)

    def _generate_postgres_schema_cache(self, record: SandboxRecord) -> dict:
        owner_password = self._owner_password(record)
        sql = """
SELECT table_name || '|' || column_name || '|' || data_type || '|' || is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
"""
        result = self.docker.exec_psql(self._postgres_container(record), sql, user="safy_owner", password=owner_password)
        grouped: dict[str, list[dict]] = {}
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            table, column, data_type, nullable = (line.split("|", 3) + [""] * 4)[:4]
            grouped.setdefault(table, []).append({"name": column, "type": data_type, "nullable": nullable == "YES"})
        tables = [{"name": name, "columns": cols} for name, cols in grouped.items()]
        return SchemaCache(self.store.sandbox_dir(record.sandbox_id)).write_postgres(tables)

    def start(self, sandbox_id: str) -> dict:
        record = self.transition(sandbox_id, "starting")
        if self._is_postgres(record):
            try:
                docker_status = self.docker.require_available()
                if docker_status != "DOCKER_AVAILABLE":
                    raise RuntimeError("SANDBOX_DOCKER_REQUIRED_FOR_POSTGRES")
                runtime = self.docker.start_postgres(record.sandbox_id, self._owner_password(record))
                record.container_ref = runtime["container"]
                record.runtime_handle = {**record.runtime_handle, **runtime, "docker_status": "DOCKER_AVAILABLE"}
                self._setup_postgres_readonly(record)
                self._generate_postgres_schema_cache(record)
                record.state = "ready"
            except RuntimeError as exc:
                record.state = "failed"
                record.last_error_code = str(exc).split(":", 1)[0] or "SANDBOX_START_FAILED"
            except SandboxError as exc:
                record.state = "failed"
                record.last_error_code = exc.code
        else:
            record.state = "ready"
            if record.dbms == "sqlite":
                record.runtime_handle = {"driver": "sqlite", "database": str(self.store.sandbox_dir(sandbox_id) / "runtime.sqlite3")}
        record.updated_at = now_iso()
        self.store.save(record)
        self._audit(sandbox_id).write("sandbox_start", sandbox_id, status="success" if record.state == "ready" else "failed", error_code=record.last_error_code)
        if record.state == "failed":
            raise SandboxError(record.last_error_code or "SANDBOX_START_FAILED")
        return self._public(record)

    def stop(self, sandbox_id: str) -> dict:
        record = self.transition(sandbox_id, "stopping")
        if self._is_postgres(record):
            self.docker.stop(self._postgres_container(record))
        record.state = "stopped"
        record.updated_at = now_iso()
        self.store.save(record)
        self._audit(sandbox_id).write("sandbox_stop", sandbox_id)
        return self._public(record)

    def delete(self, sandbox_id: str, delete_volume: bool = False) -> dict:
        record = self.store.get(sandbox_id)
        if record.state != "deleting":
            try:
                assert_transition(record.state, "deleting")
            except ValueError as exc:
                raise SandboxError("INVALID_SANDBOX_TRANSITION", str(exc)) from exc
        if self._is_postgres(record):
            names = self.docker.runtime_names(record.sandbox_id, "postgresql")
            self.docker.delete(record.container_ref or names["container"], names["volume"], delete_volume=delete_volume)
            self.secrets.delete(record.runtime_handle.get("owner_credential_ref"))
        self._audit(sandbox_id).write("sandbox_delete", sandbox_id, volume_deleted=bool(delete_volume))
        self.secrets.delete(record.readonly_credential_ref)
        record.state = "deleted"
        record.active = False
        record.updated_at = now_iso()
        self.store.save(record)
        return {"sandbox_id": sandbox_id, "state": "deleted", "active": False}

    def _safe_restore_source(self, source_path: str | None) -> Path:
        if not source_path:
            raise SandboxError("BLOCKED_BACKUP_MISSING")
        source = Path(source_path).expanduser().resolve()
        if not source.exists() or not source.is_file():
            raise SandboxError("BLOCKED_BACKUP_MISSING")
        repo = self.repo_root.resolve()
        allowed_roots = [repo / "Data" / "TestFixtures", self.store.root.resolve(), Path(os.getenv("SAFY_SANDBOX_ALLOWED_RESTORE_ROOT", str(repo / "Data" / "TestFixtures"))).expanduser().resolve()]
        if not any(source == root or root in source.parents for root in allowed_roots):
            raise SandboxError("BLOCKED_UNMANAGED_RESTORE_SOURCE")
        return source

    def _prepare_supabase_roles(self, record: SandboxRecord) -> None:
        sql = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='supabase_admin') THEN CREATE ROLE supabase_admin LOGIN SUPERUSER; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role NOLOGIN; END IF;
END $$;
GRANT anon, authenticated, service_role TO supabase_admin WITH ADMIN OPTION;
"""
        self.docker.exec_psql(self._postgres_container(record), sql, user="safy_owner", password=self._owner_password(record), output_json=False)

    def _restore_postgres_source(self, record: SandboxRecord, source: Path) -> None:
        d = self.store.sandbox_dir(record.sandbox_id)
        if record.provider_compatibility == "supabase":
            self._prepare_supabase_roles(record)
        working = source
        if source.name.lower().endswith(".backup.gz"):
            working = RestoreManager(d).decompress_gzip_to_tmp(str(source))
        name = working.name.lower()
        container_path = f"/tmp/{working.name}"
        self.docker.copy_to_container(working, self._postgres_container(record), container_path)
        owner_password = self._owner_password(record)
        if name.endswith(".sql"):
            self.docker.exec_psql_file(self._postgres_container(record), container_path, user="safy_owner", password=owner_password)
        elif name.endswith((".backup", ".dump")):
            try:
                self.docker.exec_pg_restore(self._postgres_container(record), container_path, user="safy_owner", password=owner_password)
            except RuntimeError as exc:
                if "appears to be a text format dump" not in str(exc):
                    raise
                self.docker.exec_psql_file(self._postgres_container(record), container_path, user="safy_owner", password=owner_password, stop_on_error=record.provider_compatibility != "supabase")
        else:
            raise SandboxError("UNSUPPORTED_BACKUP_FORMAT")

    def restore(self, sandbox_id: str, payload: dict) -> dict:
        record = self.store.get(sandbox_id)
        if record.state in {"created", "stopped"}:
            record.state = "starting"
            self.store.save(record)
            self.start(sandbox_id)
            record = self.store.get(sandbox_id)
        if record.state != "ready":
            raise SandboxError("SANDBOX_NOT_READY")
        record.state = "restoring"
        self.store.save(record)
        d = self.store.sandbox_dir(sandbox_id)
        job = {"status": "running", "started_at": now_iso(), "source_type": payload.get("source_type"), "source_path_persisted": False}
        Path(record.restore_job_path or d / "restore_job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
        try:
            if record.dbms == "sqlite":
                raw_source = payload.get("source_path")
                safe_source = str(self._safe_restore_source(raw_source)) if raw_source else None
                db_path = RestoreManager(d).restore_sqlite(safe_source)
                SchemaCache(d).generate_sqlite(db_path)
                record.runtime_handle = {"driver": "sqlite", "database": str(db_path)}
            elif self._is_postgres(record):
                source = payload.get("source_path")
                if os.getenv("SAFY_SANDBOX_SUPABASE_BACKUP_RESTORE_REQUIRED") == "1" and not source:
                    source = str(self.repo_root / "Data" / "TestFixtures" / "supabase" / "db_cluster-27-01-2026@16-06-46.backup.gz")
                self._restore_postgres_source(record, self._safe_restore_source(source))
                self._setup_postgres_readonly(record)
                self._generate_postgres_schema_cache(record)
            else:
                SchemaCache(d).write_empty(record.dbms)
            record.state = "ready"
            record.last_error_code = None
            job.update({"status": "success", "finished_at": now_iso()})
        except SandboxError as exc:
            record.state = "failed"
            record.last_error_code = exc.code
            job.update({"status": "failed", "error_code": exc.code, "finished_at": now_iso()})
        except (FileNotFoundError, ValueError) as exc:
            known_code = str(exc)
            if known_code not in {
                "BLOCKED_BACKUP_MISSING",
                "UNSUPPORTED_BACKUP_FORMAT",
                "INVALID_SQLITE_BACKUP",
                "BACKUP_TOO_LARGE",
            }:
                known_code = "BLOCKED_BACKUP_RESTORE_FAILED"
            record.state = "failed"
            record.last_error_code = known_code
            job.update({"status": "failed", "error_code": known_code, "finished_at": now_iso()})
        except Exception as exc:
            record.state = "failed"
            record.last_error_code = "BLOCKED_BACKUP_RESTORE_FAILED"
            safe_message = str(exc)
            owner_ref = record.runtime_handle.get("owner_credential_ref", "") if record.runtime_handle else ""
            readonly_ref = record.readonly_credential_ref or ""
            for secret in (self.secrets.get(owner_ref), self.secrets.get(readonly_ref)):
                if secret:
                    safe_message = safe_message.replace(secret, "[REDACTED]")
            job.update({"status": "failed", "error_code": record.last_error_code, "error_message": safe_message, "finished_at": now_iso()})
        record.updated_at = now_iso()
        self.store.save(record)
        Path(record.restore_job_path or d / "restore_job.json").write_text(json.dumps(job, indent=2, sort_keys=True), encoding="utf-8")
        self._audit(sandbox_id).write("sandbox_restore", sandbox_id, status=job["status"], error_code=record.last_error_code)
        if record.state == "failed":
            raise SandboxError(record.last_error_code or "BLOCKED_BACKUP_RESTORE_FAILED")
        return {"sandbox": self._public(record), "restore_job": job}

    def schema(self, sandbox_id: str) -> dict:
        return SchemaCache(self.store.sandbox_dir(sandbox_id)).read()

    def audit(self, sandbox_id: str, limit: int = 100) -> list[dict]:
        return self._audit(sandbox_id).read(limit)

    def profile_for_execute(self, sandbox_id: str) -> dict:
        record = self.store.get(sandbox_id)
        if record.state != "ready":
            raise SandboxError("SANDBOX_NOT_READY")
        password = self.secrets.get(record.readonly_credential_ref or "")
        if not password:
            raise SandboxError("SANDBOX_SECRET_MISSING")
        if record.dbms == "sqlite":
            database = record.runtime_handle.get("database") or str(self.store.sandbox_dir(sandbox_id) / "runtime.sqlite3")
            return {"driver": "sqlite", "dbms": "sqlite", "database": database, "read_only": True, "allowed_root": str(self.store.sandbox_dir(sandbox_id))}
        if self._is_postgres(record):
            return {"driver": "postgresql", "dbms": "postgresql", "container": self._postgres_container(record), "database": "safy_sandbox", "username": "safy_readonly", "read_only": True}
        raise SandboxError("SANDBOX_DBMS_ADAPTER_STAGED", f"{record.dbms} sandbox query execution is staged follow-up.")

    def _execute_postgres_readonly(self, record: SandboxRecord, sql: str, row_limit: int) -> dict:
        limited_sql = f"SELECT row_to_json(q) FROM ({sql.rstrip().rstrip(';')}) q LIMIT {max(1, min(int(row_limit), 1000))}"
        result = self.docker.exec_psql(self._postgres_container(record), limited_sql, user="safy_readonly", password=self._readonly_password(record))
        rows = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        columns = list(rows[0].keys()) if rows else []
        return {"columns": columns, "rows": rows, "metadata": {"row_count": len(rows), "sandbox_id": record.sandbox_id, "result_rows_persisted": False}}

    def execute_readonly(self, sandbox_id: str, sql: str, row_limit: int = 100) -> dict:
        record = self.store.get(sandbox_id)
        profile = self.profile_for_execute(sandbox_id)
        try:
            if self._is_postgres(record):
                payload = self._execute_postgres_readonly(record, sql, row_limit)
            else:
                payload = execute_readonly(sql, profile, options={"row_limit": row_limit})
            row_count = payload.get("metadata", {}).get("row_count")
            self._audit(sandbox_id).write("sandbox_query_execute", sandbox_id, check_id=None, sql_hash=None, row_count=row_count, result_rows_persisted=False)
            return payload
        except (DriverError, RuntimeError, json.JSONDecodeError) as exc:
            code = getattr(exc, "error_code", "SANDBOX_QUERY_FAILED")
            self._audit(sandbox_id).write("sandbox_query_execute", sandbox_id, status="failed", error_code=code)
            details = getattr(exc, "details", None)
            raise SandboxError(code, str(exc), details) from exc

    def execute_validation(self, sandbox_id: str, sql: str, row_limit: int = 100) -> dict:
        """Run user-controlled Check Safety SQL inside the sandbox.

        This is intentionally different from execute_readonly(). It is used by
        the Execute Box Check Safety flow to validate DDL/DML/SELECT in the
        isolated sandbox before the user is allowed to execute against the real
        connected database.
        """
        record = self.store.get(sandbox_id)
        if self.missing_runtime_secret_refs(sandbox_id):
            try:
                self.recreate_existing(sandbox_id, delete_volume=True)
                record = self.store.get(sandbox_id)
            except SandboxError:
                record = self.store.get(sandbox_id)
        if record.state in {"created", "stopped", "failed"}:
            try:
                self.start(sandbox_id)
                record = self.store.get(sandbox_id)
            except SandboxError:
                record = self.store.get(sandbox_id)
        if record.state != "ready":
            raise SandboxError("SANDBOX_NOT_READY", f"Sandbox status is {record.state}.", {"sandbox_id": sandbox_id, "status": record.state})

        try:
            if self._is_postgres(record):
                owner_password = self._owner_password(record)
                # Transaction rollback validates syntax/object access for most DDL/DML
                # without permanently mutating the sandbox.
                validation_sql = "BEGIN;\n" + sql.strip().rstrip(";") + ";\nROLLBACK;"
                result = self.docker.exec_psql(self._postgres_container(record), validation_sql, user="safy_owner", password=owner_password, output_json=False)
                payload = {
                    "success": True,
                    "status": "sandbox_passed",
                    "sandbox_id": sandbox_id,
                    "metadata": {
                        "row_count": 0,
                        "sandbox_id": sandbox_id,
                        "validated_in_transaction": True,
                        "rolled_back": True,
                        "stdout": (result.stdout or "").strip()[-2000:],
                    },
                }
            else:
                # SQLite validation uses a transaction and rollback as well.
                if record.dbms != "sqlite":
                    raise SandboxError("SANDBOX_DBMS_ADAPTER_STAGED", f"{record.dbms} sandbox validation is not implemented yet.")
                db_path = record.runtime_handle.get("database") if record.runtime_handle else None
                if not db_path:
                    db_path = str(self.store.sandbox_dir(sandbox_id) / "runtime.sqlite3")
                statements = normalize_sql(sql).statements
                if not statements:
                    raise SandboxError("SANDBOX_VALIDATION_FAILED", "SQL is empty.", {"sandbox_id": sandbox_id})
                conn = sqlite3.connect(db_path, timeout=5)
                cursor = None
                try:
                    conn.execute("BEGIN")
                    # Execute statements one by one. sqlite3.executescript()
                    # performs an implicit COMMIT and would defeat rollback-only
                    # validation, so it must not be used here.
                    for statement in statements:
                        cursor = conn.execute(statement)
                        cursor.close()
                        cursor = None
                finally:
                    if cursor is not None:
                        cursor.close()
                    conn.rollback()
                    conn.close()
                payload = {
                    "success": True,
                    "status": "sandbox_passed",
                    "sandbox_id": sandbox_id,
                    "metadata": {
                        "row_count": 0,
                        "sandbox_id": sandbox_id,
                        "validated_in_transaction": True,
                        "rolled_back": True,
                    },
                }
            self._audit(sandbox_id).write("sandbox_query_validate", sandbox_id, status="success", result_rows_persisted=False)
            return payload
        except (DriverError, RuntimeError, json.JSONDecodeError, sqlite3.Error) as exc:
            code = getattr(exc, "error_code", "SANDBOX_VALIDATION_FAILED")
            self._audit(sandbox_id).write("sandbox_query_validate", sandbox_id, status="failed", error_code=code)
            details = getattr(exc, "details", None) or {"sandbox_id": sandbox_id}
            raise SandboxError(code, str(exc), details) from exc
