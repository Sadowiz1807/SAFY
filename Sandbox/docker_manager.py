from __future__ import annotations

from pathlib import Path
import json
import os
import subprocess
import time


class DockerSandboxManager:
    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)

    def required(self) -> bool:
        return os.getenv("SAFY_SANDBOX_DOCKER_REQUIRED") == "1"

    def available(self) -> bool:
        try:
            return self._run(["docker", "info"], timeout=15, check=False).returncode == 0
        except Exception:
            return False

    def require_available(self) -> str:
        if not self.required():
            return "SKIPPED_DOCKER_NOT_REQUIRED"
        if not self.available():
            raise RuntimeError("BLOCKED_DOCKER_ENGINE_NOT_RUNNING")
        return "DOCKER_AVAILABLE"

    def runtime_names(self, sandbox_id: str, dbms: str) -> dict:
        safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in sandbox_id)
        return {
            "container": f"safy-sandbox-{safe}-{dbms}",
            "network": "safy-sandbox-network",
            "volume": f"safy-sandbox-{safe}-data",
        }

    def _run(self, args: list[str], timeout: int = 60, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess:
        result = subprocess.run(
            args,
            cwd=self.repo_root,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if check and result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "docker command failed").strip())
        return result

    def _ensure_network(self, network: str) -> None:
        if self._run(["docker", "network", "inspect", network], check=False).returncode != 0:
            self._run(["docker", "network", "create", network], timeout=60)

    def _ensure_volume(self, volume: str) -> None:
        if self._run(["docker", "volume", "inspect", volume], check=False).returncode != 0:
            self._run(["docker", "volume", "create", volume], timeout=60)

    def start_postgres(self, sandbox_id: str, owner_password: str, image: str = "postgres:16-alpine") -> dict:
        self.require_available()
        names = self.runtime_names(sandbox_id, "postgresql")
        self._ensure_network(names["network"])
        self._ensure_volume(names["volume"])
        inspect = self._run(["docker", "inspect", names["container"]], check=False)
        if inspect.returncode == 0:
            self._run(["docker", "start", names["container"]], timeout=60, check=False)
        else:
            self._run([
                "docker", "run", "-d",
                "--name", names["container"],
                "--network", names["network"],
                "-v", f"{names['volume']}:/var/lib/postgresql/data",
                "-e", "POSTGRES_DB=safy_sandbox",
                "-e", "POSTGRES_USER=safy_owner",
                "-e", f"POSTGRES_PASSWORD={owner_password}",
                image,
            ], timeout=120)
        self.wait_postgres_ready(names["container"], owner_password)
        return {"driver": "postgresql", "database": "safy_sandbox", "owner_user": "safy_owner", **names}

    def wait_postgres_ready(self, container: str, owner_password: str, timeout: int = 90) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self.exec_psql(container, "SELECT 1", user="safy_owner", password=owner_password, output_json=False, check=False)
            if result.returncode == 0:
                return
            time.sleep(2)
        raise RuntimeError("BLOCKED_DOCKER_ENGINE_NOT_RUNNING:postgres_not_ready")

    def stop(self, container: str) -> None:
        self._run(["docker", "stop", container], timeout=60, check=False)

    def delete(self, container: str, volume: str | None = None, delete_volume: bool = False) -> None:
        self._run(["docker", "rm", "-f", container], timeout=60, check=False)
        if delete_volume and volume:
            self._run(["docker", "volume", "rm", "-f", volume], timeout=60, check=False)

    def inspect_status(self, container: str) -> dict:
        result = self._run(["docker", "inspect", container], check=False)
        if result.returncode != 0:
            return {"exists": False}
        data = json.loads(result.stdout)[0]
        return {"exists": True, "running": bool(data.get("State", {}).get("Running")), "name": data.get("Name", "").lstrip("/")}

    def copy_to_container(self, source: Path, container: str, dest: str) -> None:
        self._run(["docker", "cp", str(source), f"{container}:{dest}"], timeout=120)

    def exec_psql(self, container: str, sql: str, user: str, password: str, output_json: bool = True, check: bool = True) -> subprocess.CompletedProcess:
        args = ["docker", "exec", "-i", "-e", f"PGPASSWORD={password}", container, "psql", "-U", user, "-d", "safy_sandbox", "-v", "ON_ERROR_STOP=1"]
        if output_json:
            args += ["-X", "-q", "-t", "-A", "-F", ",", "-c", sql]
        else:
            args += ["-c", sql]
        return self._run(args, timeout=120, check=check)

    def exec_psql_file(self, container: str, file_path: str, user: str, password: str, stop_on_error: bool = True) -> None:
        stop_flag = "ON_ERROR_STOP=1" if stop_on_error else "ON_ERROR_STOP=0"
        self._run(["docker", "exec", "-e", f"PGPASSWORD={password}", container, "psql", "-U", user, "-d", "safy_sandbox", "-v", stop_flag, "-f", file_path], timeout=180)

    def exec_pg_restore(self, container: str, file_path: str, user: str, password: str) -> None:
        self._run(["docker", "exec", "-e", f"PGPASSWORD={password}", container, "pg_restore", "-U", user, "-d", "safy_sandbox", "--clean", "--if-exists", file_path], timeout=300)
