# Compiled Domain Intelligence Report

## Status

Implemented compiled domain intelligence for SAFY with read-only source dataset handling, `.safy-domain` pack build, registry, secure pack loading, lexical router, lexical retriever, bounded `DomainContext`, runtime `ContextPack` integration, CLI commands, tests, and reports.

This report has been corrected for the in-place architecture approved on 2026-06-24. The current runtime architecture does **not** use root-level `DomainBuild/` or `DomainPacks/`, and the old handoff ZIP is not a runtime requirement.

## Inventory and dataset integrity

- Runtime domains required: 10.
- Source dataset file count: 727.
- Source dataset tree hash: `sha256:0201fb53c4f62cf10edded0eb28494eeb257795fa634f1474bd67a581238e463`.
- Source files changed under `Datasets/domain/`: 0.
- Source dataset policy: read-only canonical input.

## Authoritative architecture

```text
Datasets/domain/                         # read-only canonical source
        ↓
DomainIntelligence/work/                 # build-time staging/temp work
        ↓
DomainIntelligence/packs/registry.json   # runtime registry
DomainIntelligence/packs/<domain_id>/<version>/<domain_id>.safy-domain
        ↓
DomainIntelligence registry/router/retriever/context builder
        ↓
Agent/agent_runtime.py
        ↓
Core/context_pack.py
        ↓
text_to_sql skill prompt path
        ↓
existing SQL Guard / sandbox / Execute Box boundaries
```

## Files changed or created for Domain Intelligence

- `DomainIntelligence/__init__.py`
- `DomainIntelligence/cache.py`
- `DomainIntelligence/cli.py`
- `DomainIntelligence/compiler.py`
- `DomainIntelligence/context_builder.py`
- `DomainIntelligence/contracts.py`
- `DomainIntelligence/pack_reader.py`
- `DomainIntelligence/registry.py`
- `DomainIntelligence/retriever.py`
- `DomainIntelligence/router.py`
- `DomainIntelligence/schema_fingerprint.py`
- `DomainIntelligence/security.py`
- `DomainIntelligence/packs/registry.json`
- `DomainIntelligence/packs/<domain_id>/1.0.0/*.safy-domain`
- `DomainIntelligence/reports/`
- `Agent/agent_runtime.py`
- `Apps/Api/safy_api/cli.py`
- `Core/context_pack.py`
- `Tests/test_domain_intelligence.py`
- `.gitignore`
- `pyproject.toml`
- `SAFY_source.md`
- `current_state.md`

## Domain pack results

| Domain | Build status | Pack size bytes | SHA-256 |
|---|---:|---:|---|
| banking_finance | passed | 28647 | `sha256:27e4b4f43dc357d1dd18a483d1f85b95ff12d9b2b32dd8f86e2f7c3c43b48960` |
| crm_sales | passed | 28360 | `sha256:c000f6a8f43acf4f3153a7db0e0ad1046cf98acc8a042a9c325588898ca079df` |
| ecommerce | passed | 30581 | `sha256:526018a4853de28bfa4f962d6b21a0c3b4eda8bfd176b51ba83e0a78932a5a93` |
| education | passed | 28362 | `sha256:7f76e311efcc954fceda1724cd8e1d4a1fa7f5fc408d99aea04d28d95ab1eaa7` |
| healthcare | passed | 28405 | `sha256:7995ad4600aa84e6e2a18503b97cf20dd5f547b998a291af0bdaf6830673d5fd` |
| hotel_booking | passed | 28369 | `sha256:52727d0a81d1888cdf218c9684dd5c52b43b30fa7116435bd06a58dd5498eccf` |
| human_resources | passed | 28805 | `sha256:027dbd44d79627d9b489b7a2a0c1756128f0e85bb7183ef0dc8140373d13a95a` |
| inventory_logistics | passed | 28613 | `sha256:c175f5606b04d6da2138c724fc8fb7da1ac32c473849ccc099896227ef549969` |
| saas_analytics | passed | 28662 | `sha256:50c246cc5cc8b17f346be0e44de0f86fff9ee40a234dcfa674bc167a38fabff1` |
| social_content | passed | 28332 | `sha256:421a047e364ff117341542e4abe1343188548e0171c55b2f525ac990b375cbb5` |

## Verified commands

```text
python -m compileall DomainIntelligence Core Agent Apps/Api/safy_api Tests
PASS

python -m pytest --collect-only -q
5 tests collected

python -m pytest -q
5 passed

python -m pip install -e .
PASS

python -m Apps.Api.safy_api.cli domain list
PASS; 10 domains listed

python -m Apps.Api.safy_api.cli domain validate --all
PASS; 10/10 archives valid

python -m Apps.Api.safy_api.cli domain benchmark --all
PASS; lexical local benchmark recorded

safy domain list
PASS; 10 domains listed

safy domain validate --all
PASS; 10/10 archives valid

safy domain benchmark --all
PASS; lexical local benchmark recorded
```

## Test isolation note

`Tests/test_domain_intelligence.py` now builds packs into a temporary SAFY root using `tmp_path` and `DomainCompiler(temp_root, source_root=<repo>/Datasets/domain)`. The tests read the real source dataset but write `DomainIntelligence/work`, `DomainIntelligence/packs`, and `DomainIntelligence/reports` only under the temporary root.

Production artifact hashes were checked before and after `pytest`; no production pack or registry hash changed.

## Security review

- `Datasets/domain/` was not modified.
- Pack loading validates Zip Slip/path traversal, unusual link modes, allowed suffixes, uncompressed size, file count, and manifest format.
- Runtime treats pack content as data only; no pickle/joblib/code execution is used.
- Domain context is bounded and includes citations/doc IDs rather than raw whole datasets.
- Existing SQL Guard, sandbox validation, one-time check binding, and Execute Box confirmation remain authoritative.

## Current decisions captured

- The 7 historical test files deleted from `Tests/` are intentionally not restored.
- Packaging rule is now `>20 files modified -> full project`, `<=20 files modified -> modified files only`.
- `SAFY_compiled_domain_intelligence_all_domains.zip` is not a runtime requirement and was not created in this in-place fix pass.
- Root-level `DomainBuild/` and `DomainPacks/` must not be recreated for this implementation.

## Known limitations / not certified

- Router and retriever are offline lexical implementations, not embedding or trained ML models.
- Benchmarks are local deterministic CLI measurements, not live multi-user production load tests.
- Domain datasets are synthetic/reference assets; pack quality follows available source evidence and is not a compliance certification.
- Current automated test scope is the 5 remaining Domain Intelligence tests; deleted historical tests are not active in this working tree.

## Rollback guidance

Rollback by reverting the modified files listed above and removing the `DomainIntelligence/` package/artifacts only if the product decision is to remove compiled Domain Intelligence entirely. Do not restore root-level `DomainBuild/` or `DomainPacks/` for the current architecture.
