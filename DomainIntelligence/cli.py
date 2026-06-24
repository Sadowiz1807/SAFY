from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compiler import DomainCompiler
from .pack_reader import DomainPackReader
from .registry import DomainRegistry
from .security import validate_pack_archive


def main(argv: list[str] | None = None, root: str | Path | None = None) -> int:
    root_path = Path(root or Path.cwd()).resolve()
    parser = argparse.ArgumentParser(prog="safy domain")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    inspect_p = sub.add_parser("inspect"); inspect_p.add_argument("domain_id")
    validate_p = sub.add_parser("validate"); validate_p.add_argument("target", nargs="?", default="all"); validate_p.add_argument("--all", action="store_true")
    build_p = sub.add_parser("build"); build_p.add_argument("target", nargs="?", default="all"); build_p.add_argument("--all", action="store_true")
    install_p = sub.add_parser("install"); install_p.add_argument("path")
    remove_p = sub.add_parser("remove"); remove_p.add_argument("domain_id"); remove_p.add_argument("--version")
    bench_p = sub.add_parser("benchmark"); bench_p.add_argument("target", nargs="?", default="all"); bench_p.add_argument("--all", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    registry = DomainRegistry(root_path)
    if args.command == "list":
        payload = registry.load()
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else "\n".join(f"{p.get('domain_id')} {p.get('pack_version')} {p.get('build_status')}" for p in payload.get("domains", [])))
        return 0
    if args.command == "inspect":
        pack = registry.get(args.domain_id)
        if not pack:
            print(f"domain not installed: {args.domain_id}", file=sys.stderr); return 2
        reader = DomainPackReader(pack["path"])
        print(json.dumps(reader.manifest, ensure_ascii=False, indent=2)); reader.close(); return 0
    if args.command == "validate":
        packs = registry.enabled_packs()
        if not getattr(args, "all", False) and args.target not in {"--all", "all"}:
            packs = [p for p in packs if p.get("domain_id") == args.target]
        results = [{"domain_id": p.get("domain_id"), **validate_pack_archive(p["path"])} for p in packs]
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2)); return 0 if all(r["valid"] for r in results) and results else 1
    if args.command == "build":
        compiler = DomainCompiler(root_path)
        if getattr(args, "all", False) or args.target in {"--all", "all"}:
            result = compiler.build_all()
        else:
            result = compiler.build_domain(args.target)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    if args.command == "install":
        validation = validate_pack_archive(args.path)
        if not validation["valid"]:
            print(json.dumps(validation, ensure_ascii=False, indent=2), file=sys.stderr); return 1
        reader = DomainPackReader(args.path)
        manifest = reader.manifest; reader.close()
        import shutil, hashlib
        dest = root_path / "DomainIntelligence" / "packs" / manifest["domain_id"] / manifest["pack_version"] / Path(args.path).name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(args.path, dest)
        data = registry.load(); domains = [p for p in data.get("domains", []) if not (p.get("domain_id") == manifest["domain_id"] and p.get("pack_version") == manifest["pack_version"])]
        domains.append({"domain_id": manifest["domain_id"], "pack_version": manifest["pack_version"], "path": str(dest), "checksum": "sha256:" + hashlib.sha256(dest.read_bytes()).hexdigest(), "enabled": True, "build_status": manifest.get("build_status"), "compatibility": {"minimum_safy_version": manifest.get("minimum_safy_version")}})
        data["domains"] = domains; registry.write(data); print(str(dest)); return 0
    if args.command == "remove":
        data = registry.load(); before = len(data.get("domains", []))
        data["domains"] = [p for p in data.get("domains", []) if not (p.get("domain_id") == args.domain_id and (args.version is None or p.get("pack_version") == args.version))]
        registry.write(data); print(f"removed {before-len(data['domains'])}"); return 0
    if args.command == "benchmark":
        import time, zipfile
        from .router import DomainRouter
        from .retriever import LexicalRetriever
        packs = registry.enabled_packs(); rows=[]
        router = DomainRouter(packs)
        for p in packs:
            if not getattr(args, "all", False) and args.target not in {"--all", "all", p.get("domain_id")}: continue
            query = f"show important records for {p.get('domain_id')}"
            schema = "tables: " + p.get("domain_id", "").replace("_", " ")
            t0 = time.perf_counter(); route = router.route(query, schema, threshold=0.0); t1 = time.perf_counter()
            with zipfile.ZipFile(Path(p["path"])) as zf:
                corpus = [json.loads(line) for line in zf.read("retrieval_corpus.jsonl").decode("utf-8").splitlines() if line.strip()]
            retriever = LexicalRetriever(corpus)
            t2 = time.perf_counter(); result = retriever.search(query, domain_id=p.get("domain_id"), top_k=5); t3 = time.perf_counter()
            rows.append({
                "domain_id": p.get("domain_id"),
                "router_latency_ms": round((t1 - t0) * 1000, 3),
                "retrieval_latency_ms": round((t3 - t2) * 1000, 3),
                "retrieved_docs": len(result.documents),
                "router_decision": route.decision,
                "pack_size_bytes": Path(p["path"]).stat().st_size,
            })
        print(json.dumps({"backend": "lexical", "results": rows}, ensure_ascii=False, indent=2)); return 0 if rows else 1
    return 2
