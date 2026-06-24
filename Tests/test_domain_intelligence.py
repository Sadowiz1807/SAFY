from pathlib import Path
import json
import zipfile

from DomainIntelligence.compiler import DomainCompiler
from DomainIntelligence.context_builder import DomainContextBuilder
from DomainIntelligence.registry import DomainRegistry
from DomainIntelligence.router import DomainRouter
from DomainIntelligence.security import validate_pack_archive
from Core.context_pack import ContextPack


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_temp_domain_packs(tmp_path: Path) -> Path:
    repo_root = _repo_root()
    temp_root = tmp_path / "safy_temp"
    compiler = DomainCompiler(temp_root, source_root=repo_root / "Datasets" / "domain")
    report = compiler.build_all()
    assert len(report["domain_reports"]) == 10
    return temp_root


def test_compiler_builds_all_domain_packs(tmp_path):
    temp_root = _build_temp_domain_packs(tmp_path)
    registry = DomainRegistry(temp_root).load()
    assert len(registry["domains"]) == 10
    assert (temp_root / "DomainIntelligence" / "packs" / "registry.json").exists()
    assert not (temp_root / "DomainPacks" / "registry.json").exists()
    for entry in registry["domains"]:
        pack_path = Path(entry["path"])
        assert pack_path.exists()
        assert validate_pack_archive(pack_path)["valid"]
        with zipfile.ZipFile(pack_path) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            assert manifest["format"] == "safy-domain"
            assert manifest["domain_id"] == entry["domain_id"]
            assert manifest["content_counts"]["retrieval_documents"] > 0
            assert "retrieval_corpus.jsonl" in zf.namelist()


def test_router_uses_question_and_schema_signals(tmp_path):
    temp_root = _build_temp_domain_packs(tmp_path)
    registry = DomainRegistry(temp_root).load()
    result = DomainRouter(registry["domains"]).route(
        "Liệt kê đơn hàng và thanh toán theo khách hàng",
        "tables: customers, orders, order_items, payments, shipments",
    )
    assert result.selected_domain_id == "ecommerce"
    assert result.confidence > 0
    assert result.schema_fingerprint.startswith("sha256:")


def test_context_builder_returns_bounded_cited_context(tmp_path):
    temp_root = _build_temp_domain_packs(tmp_path)
    ctx = DomainContextBuilder(temp_root).build(
        "Liệt kê orders và payments chưa thanh toán",
        "tables: customers, orders, order_items, payments",
        database_type="sqlite",
        max_docs=4,
    )
    assert ctx.domain_id == "ecommerce"
    assert len(ctx.retrieved_doc_ids) <= 4
    assert ctx.citations
    assert "Domain intelligence context" in ctx.to_prompt_text()


def test_context_pack_includes_domain_context_in_prompt():
    pack = ContextPack(
        session_id="s1",
        user_message="show orders",
        target="connected_database",
        sandbox_id=None,
        database_profile_id="db1",
        schema_summary="tables: orders",
        domain_context={"domain_id": "ecommerce", "prompt_text": "Domain intelligence context: ecommerce"},
    )
    text = pack.to_prompt_text()
    assert "Schema context:" in text
    assert "Domain intelligence context: ecommerce" in text
    assert pack.to_dict()["domain_context"]["domain_id"] == "ecommerce"


def test_pack_archive_rejects_zip_slip(tmp_path):
    bad = tmp_path / "bad.safy-domain"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"format": "safy-domain"}))
        zf.writestr("../evil.json", "{}")
    result = validate_pack_archive(bad)
    assert not result["valid"]
    assert any("unsafe_path" in e for e in result["errors"])
