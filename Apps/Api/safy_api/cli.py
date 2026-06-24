from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn


def get_repo_root() -> Path:
    env_root = os.environ.get("SAFY_HOME")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[3]


def _wait_for_health(health_url: str, timeout_seconds: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1.0) as response:
                if response.status == 200:
                    return True
        except (OSError, urllib.error.URLError):
            time.sleep(0.25)
    return False


def _open_browser_when_ready(url: str, health_url: str) -> None:
    if _wait_for_health(health_url):
        webbrowser.open(url)
    else:
        print(f"Dashboard not ready before browser timeout: {url}", file=sys.stderr)


def _port_available(host: str, port: int) -> bool:
    try:
        with socket.create_server((host, port), reuse_port=False):
            return True
    except OSError:
        return False


def _existing_safy_health(health_url: str) -> bool:
    try:
        with urllib.request.urlopen(health_url, timeout=1.0) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return False
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    return data.get("name") == "SAFY" and data.get("status") == "ok"


def main() -> None:
    parser = argparse.ArgumentParser(description="SAFY command line launcher")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Start SAFY")
    run_parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    run_parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    run_parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    run_parser.add_argument("--browser", dest="browser", action="store_true", default=True, help="Open dashboard browser")
    run_parser.add_argument("--no-browser", dest="browser", action="store_false", help="Do not open browser")

    subparsers.add_parser("info", help="Show SAFY info")
    domain_parser = subparsers.add_parser("domain", help="Manage SAFY compiled domain packs")
    domain_parser.add_argument("domain_args", nargs=argparse.REMAINDER)
    test_parser = subparsers.add_parser("test", help="Run SAFY tests")
    test_parser.add_argument("--stage", help="Run a specific stage test directory, for example stage9")

    args = parser.parse_args()
    root = get_repo_root()
    os.environ["SAFY_HOME"] = str(root)

    if args.command == "run":
        url = f"http://{args.host}:{args.port}/"
        health_url = f"http://{args.host}:{args.port}/health"
        if not _port_available(args.host, args.port):
            if _existing_safy_health(health_url):
                print(f"SAFY is already running at {url}")
                print(f"Dashboard URL: {url}")
                return
            print(
                f"Port {args.port} is already in use. Stop the existing SAFY process or use --port <other>.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Starting SAFY at {url}")
        print(f"Dashboard URL: {url}")
        if args.browser:
            threading.Thread(target=_open_browser_when_ready, args=(url, health_url), daemon=True).start()
        uvicorn.run(
            "Apps.Api.safy_api.main:app",
            host=args.host,
            port=args.port,
            reload=not args.no_reload,
            app_dir=str(root),
        )
    elif args.command == "info":
        print("SAFY Version: 1.1.0")
        print(f"Home: {root}")
        print("Dashboard: http://127.0.0.1:8000/")
    elif args.command == "domain":
        from DomainIntelligence.cli import main as domain_main
        sys.exit(domain_main(args.domain_args, root=root))
    elif args.command == "test":
        import pytest

        target = root / "Tests" / args.stage if args.stage else root / "Tests"
        sys.exit(pytest.main([str(target)]))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

