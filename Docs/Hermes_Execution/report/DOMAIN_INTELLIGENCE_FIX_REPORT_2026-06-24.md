# DOMAIN INTELLIGENCE FIX REPORT — 2026-06-24

**Repo:** `C:\Users\ASUS\SAFY`  
**Thời điểm hoàn tất:** 2026-06-24 20:25:41 SEAST  
**Phạm vi:** sửa trực tiếp SAFY Domain Intelligence theo prompt `HERMES_PROMPT_FIX_DOMAIN_INTELLIGENCE_IN_PLACE.md`.  
**Kết luận:** `PASS`

---

## 1. Executive summary

Đã sửa trực tiếp trong repository hiện tại, không tạo project mới, không tạo ZIP, không phục hồi 7 test đã xóa chủ đích.

Kết quả chính:

- `Tests/test_domain_intelligence.py` không còn hard-code `DomainPacks`.
- Domain Intelligence test build được cô lập vào `tmp_path`, không mutate artifact production.
- `python -m pytest -q`: `5 passed`.
- `python -m compileall DomainIntelligence Core Agent Apps/Api/safy_api Tests`: PASS.
- Module CLI và installed CLI đều chạy được sau `python -m pip install -e .`.
- 10/10 domain pack validate được.
- `Datasets/domain/` không đổi: before/after tree hash giống nhau.
- Không tạo lại root-level `DomainBuild/`, `DomainPacks/`, hoặc ZIP cũ.

---

## 2. Kiến trúc authoritative sau sửa

Kiến trúc Domain Intelligence chính thức hiện tại:

```text
DomainIntelligence/
├── *.py
├── packs/
│   ├── registry.json
│   ├── cache/                         # runtime/generated cache; gitignored
│   └── <domain_id>/<version>/<domain_id>.safy-domain
├── reports/
└── work/                              # build-time staging/temp; gitignored
```

Luồng runtime/build hiện tại:

```text
Datasets/domain/                       # read-only canonical source
        ↓
DomainIntelligence/work/               # build-time staging/temp root
        ↓
DomainIntelligence/packs/registry.json # runtime registry
DomainIntelligence/packs/<domain>/<version>/<domain>.safy-domain
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

Không dùng lại / không tạo lại:

```text
DomainBuild/
DomainPacks/
SAFY_compiled_domain_intelligence_all_domains.zip
```

`SAFY_compiled_domain_intelligence_all_domains.zip` là artifact handoff lịch sử, không phải runtime requirement trong task này.

---

## 3. Danh sách file thực tế đã sửa trong task này

Các file trong allowlist đã được sửa:

1. `.gitignore`
2. `Tests/test_domain_intelligence.py`
3. `DomainIntelligence/compiler.py`
4. `DomainIntelligence/registry.py`
5. `SAFY_source.md`
6. `current_state.md`
7. `Docs/Hermes_Execution/report/COMPILED_DOMAIN_INTELLIGENCE_REPORT.md`
8. `Docs/Hermes_Execution/report/DOMAIN_INTELLIGENCE_FIX_REPORT_2026-06-24.md` — file báo cáo cuối được phép tạo.

Các file allowlist đã kiểm tra nhưng không cần sửa trong task này:

- `DomainIntelligence/cli.py`
- `DomainIntelligence/cache.py`
- `Apps/Api/safy_api/cli.py`
- `pyproject.toml`

---

## 4. File ngoài phạm vi có vấn đề nhưng không sửa

Theo prompt, không sửa ngoài allowlist. Các mục dưới đây được ghi nhận nhưng không chỉnh trong pass này:

| File / nhóm file | Tình trạng | Tác động | Lý do chưa sửa |
|---|---|---|---|
| `Apps/Web/dashboard.js` | Modified từ trước | UI diff vẫn nằm trong working tree | Ngoài allowlist của task này |
| `Apps/Web/schema-graph.js` | Modified từ trước | UI diff vẫn nằm trong working tree | Ngoài allowlist của task này |
| `Apps/Web/styles.css` | Modified từ trước | UI diff vẫn nằm trong working tree | Ngoài allowlist của task này |
| `Agent/agent_runtime.py` | Modified từ trước | Runtime integration diff vẫn nằm trong working tree | Ngoài allowlist sửa của task này theo prompt |
| `Core/context_pack.py` | Modified từ trước | Context pack diff vẫn nằm trong working tree | Ngoài allowlist sửa của task này theo prompt |
| 7 historical tests dưới `Tests/` | Deleted chủ đích bởi user | Không còn active test coverage cũ | Prompt cấm restore/tạo lại |
| `Docs/Hermes_Execution/report/SAFY_NGHIEM_THU_RASOAT_DOMAIN_INTELLIGENCE_2026-06-24.md` | Untracked, đã tồn tại trước prompt fix | Báo cáo rà soát lịch sử | Không thuộc file báo cáo cuối của task này; không động vào |

7 test deleted được giữ nguyên theo quyết định user:

```text
Tests/test_audit_privacy.py
Tests/test_driver_routing.py
Tests/test_runtime_state_privacy.py
Tests/test_sandbox_validation.py
Tests/test_schema_graph_store.py
Tests/test_skill_documents.py
Tests/test_sql_safety_workflow.py
```

---

## 5. Root cause của hai test fail

Hai test fail ban đầu:

```text
Tests/test_domain_intelligence.py::test_compiler_builds_all_domain_packs
Tests/test_domain_intelligence.py::test_router_uses_question_and_schema_signals
```

Root cause:

- Test cũ hard-code registry path:

```python
root / "DomainPacks" / "registry.json"
```

- Nhưng kiến trúc user phê duyệt hiện tại dùng:

```text
DomainIntelligence/packs/registry.json
```

- Test cũng gọi `DomainCompiler(root).build_all()` trực tiếp trên project root, có thể mutate production artifacts.

Fix đã thực hiện:

- Test chuyển sang API chính thức:

```python
DomainRegistry(temp_root).load()
```

- Test build vào temp root:

```python
DomainCompiler(temp_root, source_root=repo_root / "Datasets" / "domain")
```

- Compiler hỗ trợ `source_root` optional để đọc dataset thật nhưng ghi output vào temporary root.

---

## 6. Cách test build được cô lập khỏi production artifacts

Test helper mới:

```python
def _build_temp_domain_packs(tmp_path: Path) -> Path:
    repo_root = _repo_root()
    temp_root = tmp_path / "safy_temp"
    compiler = DomainCompiler(temp_root, source_root=repo_root / "Datasets" / "domain")
    report = compiler.build_all()
    assert len(report["domain_reports"]) == 10
    return temp_root
```

Cơ chế cô lập:

```text
repo/Datasets/domain/                  # chỉ đọc
        ↓
tmp_path/safy_temp/DomainIntelligence/work/
tmp_path/safy_temp/DomainIntelligence/packs/
tmp_path/safy_temp/DomainIntelligence/reports/
```

Bằng chứng không mutate production artifact khi chạy pytest:

```text
PRODUCTION_ARTIFACTS_CHANGED []
```

---

## 7. Kết quả từng lệnh

### 7.1 Compileall

Command:

```bash
python -m compileall DomainIntelligence Core Agent Apps/Api/safy_api Tests
```

Result:

```text
EXIT 0
PASS
```

---

### 7.2 Pytest collect

Command:

```bash
python -m pytest --collect-only -q
```

Result:

```text
Tests/test_domain_intelligence.py::test_compiler_builds_all_domain_packs
Tests/test_domain_intelligence.py::test_router_uses_question_and_schema_signals
Tests/test_domain_intelligence.py::test_context_builder_returns_bounded_cited_context
Tests/test_domain_intelligence.py::test_context_pack_includes_domain_context_in_prompt
Tests/test_domain_intelligence.py::test_pack_archive_rejects_zip_slip

5 tests collected in 0.02s
EXIT 0
```

---

### 7.3 Pytest

Command:

```bash
python -m pytest -q
```

Result:

```text
.....                                                                    [100%]
5 passed in 1.66s
EXIT 0
```

---

### 7.4 Editable install

Command:

```bash
python -m pip install -e .
```

Result:

```text
Successfully built safy
Successfully installed safy-1.1.0
EXIT 0
```

Ghi chú: `pip install -e .` sinh `safy.egg-info/` tạm trong repo; file này đã được xóa sau xác minh để không để lại artifact ngoài allowlist.

---

### 7.5 Module CLI list

Command:

```bash
python -m Apps.Api.safy_api.cli domain list
```

Result:

```text
banking_finance 1.0.0 passed
crm_sales 1.0.0 passed
ecommerce 1.0.0 passed
education 1.0.0 passed
healthcare 1.0.0 passed
hotel_booking 1.0.0 passed
human_resources 1.0.0 passed
inventory_logistics 1.0.0 passed
saas_analytics 1.0.0 passed
social_content 1.0.0 passed
EXIT 0
```

---

### 7.6 Module CLI validate

Command:

```bash
python -m Apps.Api.safy_api.cli domain validate --all
```

Result:

```text
10/10 valid
EXIT 0
```

---

### 7.7 Module CLI benchmark

Command:

```bash
python -m Apps.Api.safy_api.cli domain benchmark --all
```

Result:

```text
EXIT 0
```

Benchmark là local/synthetic lexical benchmark, không phải production certification.

---

### 7.8 Installed CLI list

Command:

```bash
safy domain list
```

Result:

```text
banking_finance 1.0.0 passed
crm_sales 1.0.0 passed
ecommerce 1.0.0 passed
education 1.0.0 passed
healthcare 1.0.0 passed
hotel_booking 1.0.0 passed
human_resources 1.0.0 passed
inventory_logistics 1.0.0 passed
saas_analytics 1.0.0 passed
social_content 1.0.0 passed
EXIT 0
```

---

### 7.9 Installed CLI validate

Command:

```bash
safy domain validate --all
```

Result:

```text
10/10 valid
EXIT 0
```

---

### 7.10 Installed CLI benchmark

Command:

```bash
safy domain benchmark --all
```

Result:

```text
EXIT 0
```

Benchmark là local/synthetic lexical benchmark, không phải production certification.

---

## 8. Domain validation

Registry path:

```text
DomainIntelligence/packs/registry.json
```

Validated domains:

| Domain | Version | Status |
|---|---:|---:|
| banking_finance | 1.0.0 | passed / valid |
| crm_sales | 1.0.0 | passed / valid |
| ecommerce | 1.0.0 | passed / valid |
| education | 1.0.0 | passed / valid |
| healthcare | 1.0.0 | passed / valid |
| hotel_booking | 1.0.0 | passed / valid |
| human_resources | 1.0.0 | passed / valid |
| inventory_logistics | 1.0.0 | passed / valid |
| saas_analytics | 1.0.0 | passed / valid |
| social_content | 1.0.0 | passed / valid |

Summary:

```text
10/10 pack valid
```

---

## 9. Dataset integrity

Dataset path:

```text
Datasets/domain/
```

Integrity:

```text
file_count_before: 727
file_count_after: 727
before_hash: 0201fb53c4f62cf10edded0eb28494eeb257795fa634f1474bd67a581238e463
after_hash:  0201fb53c4f62cf10edded0eb28494eeb257795fa634f1474bd67a581238e463
changed_source_files: 0
```

Conclusion:

```text
Datasets/domain/ unchanged: PASS
```

---

## 10. Artifact integrity

Production artifacts checked before/after test/CLI verification:

| Artifact | Before SHA-256 | After SHA-256 | Changed |
|---|---|---|---:|
| `DomainIntelligence/packs/registry.json` | `700d2f5e5b09d581d1531e25dbcf388a2407f4978d70e40a57997cd5e4bb3a26` | `700d2f5e5b09d581d1531e25dbcf388a2407f4978d70e40a57997cd5e4bb3a26` | No |
| `banking_finance.safy-domain` | `27e4b4f43dc357d1dd18a483d1f85b95ff12d9b2b32dd8f86e2f7c3c43b48960` | same | No |
| `crm_sales.safy-domain` | `c000f6a8f43acf4f3153a7db0e0ad1046cf98acc8a042a9c325588898ca079df` | same | No |
| `ecommerce.safy-domain` | `526018a4853de28bfa4f962d6b21a0c3b4eda8bfd176b51ba83e0a78932a5a93` | same | No |
| `education.safy-domain` | `7f76e311efcc954fceda1724cd8e1d4a1fa7f5fc408d99aea04d28d95ab1eaa7` | same | No |
| `healthcare.safy-domain` | `7995ad4600aa84e6e2a18503b97cf20dd5f547b998a291af0bdaf6830673d5fd` | same | No |
| `hotel_booking.safy-domain` | `52727d0a81d1888cdf218c9684dd5c52b43b30fa7116435bd06a58dd5498eccf` | same | No |
| `human_resources.safy-domain` | `027dbd44d79627d9b489b7a2a0c1756128f0e85bb7183ef0dc8140373d13a95a` | same | No |
| `inventory_logistics.safy-domain` | `c175f5606b04d6da2138c724fc8fb7da1ac32c473849ccc099896227ef549969` | same | No |
| `saas_analytics.safy-domain` | `50c246cc5cc8b17f346be0e44de0f86fff9ee40a234dcfa674bc167a38fabff1` | same | No |
| `social_content.safy-domain` | `421a047e364ff117341542e4abe1343188548e0171c55b2f525ac990b375cbb5` | same | No |

Summary:

```text
ARTIFACTS_CHANGED []
pytest mutated production artifacts: No
CLI validation/benchmark mutated production artifacts: No
```

---

## 11. Git diff summary

Final `git diff --stat` summary:

```text
.gitignore                          |   8 +
Agent/agent_runtime.py              |  33 ++++
Apps/Api/safy_api/cli.py            |   5 +
Apps/Web/dashboard.js               |  53 ++++++
Apps/Web/schema-graph.js            | 102 +++++++++-
Apps/Web/styles.css                 |  75 ++++++++
Core/context_pack.py                |   8 +-
SAFY_source.md                      |   5 +-
Tests/test_audit_privacy.py         |  51 -----
Tests/test_driver_routing.py        |  87 ---------
Tests/test_runtime_state_privacy.py | 141 --------------
Tests/test_sandbox_validation.py    | 122 ------------
Tests/test_schema_graph_store.py    |  29 ---
Tests/test_skill_documents.py       |  83 ---------
Tests/test_sql_safety_workflow.py   | 362 ------------------------------------
pyproject.toml                      |   1 +
16 files changed, 286 insertions(+), 879 deletions(-)
```

Important interpretation:

- Several modified files and the 7 deleted tests were already present before this fix prompt.
- The 7 deleted tests are intentional per user prompt and were not restored.
- `current_state.md` is ignored by `.gitignore`, so it may not show in normal `git status`, but it was updated as required.
- Generated `.pyc` / `__pycache__` files are ignored and not in tracked diff.
- No root-level `DomainBuild/`, `DomainPacks/`, or ZIP was created.

---

## 12. Security / hard-coded path check

Security grep over added diff lines did not find a direct match for:

- obvious hardcoded `api_key`, `secret`, `password`, `token` assignment;
- `os.system(`;
- `subprocess` with `shell=True`;
- `eval(` / `exec(`;
- `pickle.loads`;
- basic SQL string-format injection patterns.

No hard-coded `C:\Users\ASUS\SAFY` path was introduced in code changes. Test helper resolves repo root dynamically with `Path(__file__).resolve().parents[1]` and writes build output to `tmp_path`.

---

## 13. Những giới hạn chưa xác nhận

- Benchmark hiện tại là local/synthetic lexical benchmark, không phải production certification.
- Không chạy live database integration test.
- Không khôi phục hoặc thay thế 7 historical tests đã bị user xóa chủ đích.
- Existing UI diffs trong `Apps/Web/*` không thuộc phạm vi sửa của task này.
- Domain router/retriever vẫn là offline lexical implementation, không phải embedding hoặc trained ML model.

---

## 14. Tiêu chí nghiệm thu theo prompt

| Tiêu chí | Kết quả |
|---|---:|
| Không sửa `Datasets/domain/` | PASS |
| Không restore 7 test user đã xóa | PASS |
| `Tests/test_domain_intelligence.py` không hard-code `DomainPacks` | PASS |
| Test compiler build vào temp root | PASS |
| Pytest không mutate artifact production | PASS |
| Toàn bộ test hiện có pass | PASS |
| `python -m compileall ...` pass | PASS |
| 10/10 pack validate | PASS |
| Module CLI chạy | PASS |
| Installed `safy domain ...` chạy sau editable install | PASS |
| `current_state.md` khớp kiến trúc mới | PASS |
| `SAFY_source.md` khớp kiến trúc mới | PASS |
| Existing compiled-domain report không còn claim sai | PASS |
| Packaging rule là mốc 20 file | PASS |
| Không có hard-coded path theo máy | PASS |
| Không tạo lại `DomainBuild/` hoặc `DomainPacks/` | PASS |
| Không tạo ZIP/patch/project copy | PASS |
| Chỉ sửa allowlist và tạo report cuối | PASS, với ghi chú có báo cáo rà soát cũ tồn tại sẵn từ trước task |
| Git diff được rà soát trước khi kết luận | PASS |

---

## 15. Kết luận cuối

```text
PASS
```

SAFY Domain Intelligence đã được sửa in-place theo kiến trúc `DomainIntelligence/` hiện tại. Test còn tồn tại pass, CLI module và installed CLI pass, 10/10 pack validate, dataset source không đổi, và production artifacts không bị mutate bởi pytest.
