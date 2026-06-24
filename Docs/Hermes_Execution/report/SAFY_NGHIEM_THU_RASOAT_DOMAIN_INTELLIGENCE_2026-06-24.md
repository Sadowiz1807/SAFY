> **SUPERSEDED / HISTORICAL**  
> Báo cáo này phản ánh trạng thái trước đợt sửa Domain Intelligence ngày 2026-06-24.  
> Trạng thái hiện hành nằm trong `DOMAIN_INTELLIGENCE_FIX_REPORT_2026-06-24.md` và `current_state.md`.

# SAFY — Báo cáo nghiệm thu rà soát Domain Intelligence

**Thời điểm rà soát:** 2026-06-24 20:10:39 SEAST  
**Repo:** `C:\Users\ASUS\SAFY`  
**Phạm vi:** rà soát bug, conflict, regression, artifact/handoff mismatch sau thay đổi `DomainIntelligence`.  
**Chế độ:** chỉ kiểm tra, không sửa code trong pass rà soát.

---

## 1. Kết luận nghiệm thu

**Trạng thái nghiệm thu hiện tại: `KHÔNG ĐẠT / CHƯA NÊN BÀN GIAO`**

Lý do chính:

1. `pytest -q` đang fail: `2 failed, 3 passed`.
2. 7 test cũ đang bị deleted khỏi working tree, làm mất regression coverage quan trọng.
3. ZIP handoff bắt buộc `SAFY_compiled_domain_intelligence_all_domains.zip` hiện không tồn tại.
4. Có conflict kiến trúc giữa prompt/docs/tests yêu cầu `DomainBuild/` + `DomainPacks/` và code hiện tại dùng `DomainIntelligence/work|reports|packs`.
5. Report handoff hiện tại stale: ghi test pass và có ZIP/package, nhưng trạng thái thực tế không khớp.
6. Cần xác minh lại CLI installed command `safy domain ...` sau `python -m pip install -e .`.

---

## 2. Lệnh kiểm tra đã chạy

```bash
git status --short
git diff --name-status
git diff --stat
python -m compileall DomainIntelligence Core Agent Apps/Api/safy_api Tests
python -m pytest -q
python -m pytest --collect-only -q
python -m Apps.Api.safy_api.cli domain validate --all
python -m Apps.Api.safy_api.cli domain benchmark --all
python -m Apps.Api.safy_api.cli domain list
```

Security scan cơ bản trên added lines:

```bash
git diff | grep '^+' | grep -iE "(api_key|secret|password|token|passwd)\s*=\s*['\"][^'\"]{6,}['\"]|os\.system\(|subprocess.*shell=True|\beval\(|\bexec\(|pickle\.loads?\(|execute\(f\"|\.format\(.*SELECT|\.format\(.*INSERT" || true
```

---

## 3. Kết quả kiểm tra nhanh

| Hạng mục | Kết quả | Ghi chú |
|---|---:|---|
| Python compileall | PASS | `DomainIntelligence`, `Core`, `Agent`, `Apps/Api/safy_api`, `Tests` compile được |
| Pytest | FAIL | `2 failed, 3 passed` |
| Pytest collect | WARNING | Chỉ còn `5 tests collected` |
| Domain validate | PASS | 10/10 packs valid qua module CLI |
| Domain benchmark | PASS | Có benchmark lexical router/retriever |
| Source dataset integrity | PASS | `Datasets/domain` tree hash không đổi |
| Handoff ZIP | FAIL | `SAFY_compiled_domain_intelligence_all_domains.zip` không tồn tại |
| Security grep cơ bản | PASS/WARNING | Không thấy secret pattern rõ ràng; chỉ có Git line-ending warnings |

---

## 4. P0 — Blocker nghiêm trọng

### P0.1 — Không phát hiện P0 kiểu phá source dataset hoặc pack hỏng toàn bộ

Không thấy bằng chứng cho các lỗi P0 sau:

- `Datasets/domain/` bị sửa trực tiếp.
- Domain pack không validate được toàn bộ.
- Archive validation fail hàng loạt.
- Hardcoded secret rõ ràng trong diff.

Bằng chứng dataset:

```text
dataset_file_count: 727
dataset_tree_hash: 0201fb53c4f62cf10edded0eb28494eeb257795fa634f1474bd67a581238e463
```

Bằng chứng validate:

```text
python -m Apps.Api.safy_api.cli domain validate --all
10/10 valid
```

**Nhận định:** Không có P0 ngay lập tức, nhưng các P1 bên dưới vẫn đủ để chặn nghiệm thu.

---

## 5. P1 — Phải xử lý trước khi bàn giao / commit

### P1.1 — Test suite đang fail

Lệnh:

```bash
python -m pytest -q
```

Kết quả:

```text
2 failed, 3 passed
```

Failing tests:

```text
Tests/test_domain_intelligence.py::test_compiler_builds_all_domain_packs
Tests/test_domain_intelligence.py::test_router_uses_question_and_schema_signals
```

Nguyên nhân trực tiếp:

- Test đang đọc registry cũ:

```python
root / "DomainPacks" / "registry.json"
```

ở:

```text
Tests/test_domain_intelligence.py:16
Tests/test_domain_intelligence.py:33
```

- Compiler hiện tại ghi registry mới tại:

```text
DomainIntelligence/packs/registry.json
```

Code liên quan:

```text
DomainIntelligence/compiler.py:30-34
DomainIntelligence/compiler.py:70-73
```

**Đánh giá:** Đây là conflict giữa test và implementation path. Chưa đạt regression gate.

---

### P1.2 — 7 test cũ bị deleted khỏi working tree

`git status --short` báo:

```text
D Tests/test_audit_privacy.py
D Tests/test_driver_routing.py
D Tests/test_runtime_state_privacy.py
D Tests/test_sandbox_validation.py
D Tests/test_schema_graph_store.py
D Tests/test_skill_documents.py
D Tests/test_sql_safety_workflow.py
```

Các test bị mất coverage cho những boundary quan trọng:

- audit/privacy
- driver routing
- runtime state privacy
- sandbox validation
- schema graph store
- skill documents
- SQL safety workflow

Bằng chứng thêm:

```bash
python -m pytest --collect-only -q
```

Kết quả:

```text
5 tests collected
```

**Đánh giá:** Báo cáo `5 passed` nếu có không đại diện cho full regression suite cũ. Đây là regression nghiệm thu nghiêm trọng.

---

### P1.3 — Handoff ZIP bắt buộc không tồn tại

Kiểm tra artifact:

```text
SAFY_compiled_domain_intelligence_all_domains.zip
```

Kết quả:

```text
zip_exists False
```

Prompt yêu cầu deliverable cuối:

```text
SAFY_compiled_domain_intelligence_all_domains.zip
```

**Đánh giá:** Chưa đạt tiêu chí bàn giao artifact.

---

### P1.4 — Report/handoff hiện tại stale so với trạng thái thực tế

Report hiện có:

```text
Docs/Hermes_Execution/report/COMPILED_DOMAIN_INTELLIGENCE_REPORT.md
```

Mismatch phát hiện:

- Report ghi `python -m pytest -q` pass.
- Thực tế hiện tại `pytest -q` fail `2 failed, 3 passed`.
- Report nói có handoff ZIP/package.
- Thực tế ZIP không tồn tại.
- Report mô tả flow `DomainBuild -> DomainPacks`, nhưng implementation hiện tại dùng `DomainIntelligence/work`, `DomainIntelligence/reports`, `DomainIntelligence/packs`.

**Đánh giá:** Không nên dùng report hiện tại làm bằng chứng nghiệm thu cuối.

---

### P1.5 — Conflict kiến trúc artifact: Prompt/docs/tests vs code hiện tại

Prompt v2 yêu cầu:

```text
DomainBuild/
DomainPacks/
DomainPacks/registry.json
DomainPacks/packs/<domain>/<version>/<domain>.safy-domain
```

Thực tế hiện tại:

```text
DomainBuild exists False
DomainPacks exists False
DomainIntelligence/packs exists True
DomainIntelligence/reports exists True
DomainIntelligence/work exists True
```

Code hiện tại:

```python
self.domain_root = self.root / "DomainIntelligence"
self.work = self.domain_root / "work"
self.reports = self.domain_root / "reports"
self.out = self.domain_root / "packs"
```

Vị trí:

```text
DomainIntelligence/compiler.py:30-34
```

**Đánh giá:** Đây là conflict trực tiếp với prompt v2 và với test đang tồn tại.

---

### P1.6 — CLI installed command cần verify lại sau reinstall

Dạng module chạy được:

```bash
python -m Apps.Api.safy_api.cli domain list
```

Nhưng cần kiểm tra command installed:

```bash
safy domain list
```

Sub-review độc lập ghi nhận rủi ro:

```text
ModuleNotFoundError: No module named 'DomainIntelligence'
```

Nguyên nhân khả dĩ:

- `pyproject.toml` đã thêm `DomainIntelligence*`.
- Nhưng editable install / console script hiện tại có thể chưa refresh mapping.
- Handoff docs lại hướng dẫn dùng `safy domain ...`.

**Cần chạy xác minh trước nghiệm thu:**

```bash
python -m pip install -e .
safy domain list
safy domain validate --all
safy domain benchmark --all
```

---

### P1.7 — Pack checksum/report dễ stale sau mỗi build

Compiler ghi timestamp build trong manifest:

```text
DomainIntelligence/compiler.py:160
```

Mỗi lần build lại có thể đổi checksum pack. Vì test hiện tại gọi:

```python
DomainCompiler(root).build_all()
```

nên chạy test cũng regenerate artifact và có thể làm checksum/report stale.

**Đánh giá:** Cần chốt build cuối, sau đó mới generate report/checksum/ZIP cuối. Không nên chạy test build-mutating sau khi đóng report nếu report chứa checksum cố định.

---

## 6. P2 — Vấn đề vừa / cần dọn để tránh nhầm lẫn

### P2.1 — Documentation conflict trong `current_state.md`

`current_state.md` đã nói compiled domain intelligence, nhưng vẫn mô tả flow:

```text
DomainBuild/staging
DomainPacks/
```

Trong khi code thực tế dùng:

```text
DomainIntelligence/work
DomainIntelligence/packs
```

**Đánh giá:** Cần thống nhất docs theo kiến trúc đã chọn.

---

### P2.2 — Packaging rule conflict: 12 file vs 20 file

Trong `current_state.md`/quy ước cũ:

```text
>12 files modified → full project
<=12 files → modified files only
```

Trong prompt v2:

```text
>20 files source/project modified → full project
<=20 files → patch
```

Hiện thay đổi domain-intelligence khoảng 19 file source/project.

- Theo prompt v2: có thể gửi patch.
- Theo current_state cũ: phải gửi full project.

**Đánh giá:** Cần chọn một rule authoritative cho handoff lần này.

---

### P2.3 — Generated artifacts nằm trong source module

Hiện artifact runtime/build nằm dưới:

```text
DomainIntelligence/packs/
DomainIntelligence/reports/
DomainIntelligence/work/
```

Rủi ro:

- Lẫn code source với generated artifacts.
- `compileall` đi qua `DomainIntelligence/packs`.
- Dễ package nhầm cache/report/pack vào source tree.
- Mâu thuẫn với prompt yêu cầu `DomainPacks/` riêng và `DomainBuild/` build-time only.

---

### P2.4 — `__pycache__` / `.pyc` sinh ra sau kiểm tra

Do chạy `compileall` / `pytest`, có thể có artifact:

```text
DomainIntelligence/__pycache__/
Tests/__pycache__/
```

Nếu đóng ZIP bằng cách quét tree không lọc kỹ, file rác có thể lọt vào handoff.

---

### P2.5 — Git line-ending warnings trên Windows

`git diff/status` báo nhiều warning:

```text
LF will be replaced by CRLF the next time Git touches it
```

Các file bị ảnh hưởng gồm:

```text
Agent/agent_runtime.py
Apps/Web/dashboard.js
Apps/Web/schema-graph.js
Apps/Web/styles.css
Core/context_pack.py
SAFY_source.md
pyproject.toml
```

**Đánh giá:** Không phải runtime bug ngay, nhưng làm diff nhiễu và có thể gây churn khi Git touch file.

---

### P2.6 — Security scan cơ bản không thấy secret rõ ràng

Đã scan added lines cho các pattern:

- `api_key`
- `secret`
- `password`
- `token`
- `os.system`
- `subprocess shell=True`
- `eval`
- `exec`
- `pickle.loads`
- SQL injection pattern cơ bản

Không thấy hit rõ ràng ngoài warning line-ending của Git.

---

## 7. Domain pack validation hiện tại

Dù có conflict artifact path, module CLI hiện validate 10/10 pack:

```text
banking_finance: valid
crm_sales: valid
ecommerce: valid
education: valid
healthcare: valid
hotel_booking: valid
human_resources: valid
inventory_logistics: valid
saas_analytics: valid
social_content: valid
```

Benchmark lexical hiện chạy được, ví dụ average từ lần rà soát trước:

```text
Avg router latency: khoảng 0.1 ms
Avg retrieval latency: khoảng 0.08–0.09 ms
```

**Lưu ý:** Đây là benchmark local synthetic/CLI, không phải certification production workload.

---

## 8. Danh sách việc cần làm để đạt nghiệm thu

Thứ tự đề xuất:

1. **Khôi phục 7 test cũ bị deleted**.
2. Quyết định kiến trúc artifact cuối:
   - Theo prompt: `DomainBuild/` + `DomainPacks/`; hoặc
   - Theo code mới: `DomainIntelligence/work|reports|packs`.
3. Sửa test, docs, report theo kiến trúc đã chọn.
4. Đảm bảo `python -m pytest -q` pass trên toàn bộ test suite.
5. Xác minh installed CLI:
   ```bash
   python -m pip install -e .
   safy domain list
   safy domain validate --all
   safy domain benchmark --all
   ```
6. Regenerate report sau build cuối.
7. Regenerate `SAFY_compiled_domain_intelligence_all_domains.zip`.
8. Verify ZIP thật sự tồn tại và chứa:
   - 10 `.safy-domain`
   - registry
   - report
   - README_INSTALL.md
   - checksums
9. Chạy lại dataset tree hash để chứng minh `Datasets/domain/` không đổi.
10. Dọn generated junk: `__pycache__`, `.pyc`, cache runtime không cần bàn giao.

---

## 9. Quyết định nghiệm thu

| Tiêu chí | Trạng thái |
|---|---:|
| Không sửa `Datasets/domain/` | PASS |
| 10 packs validate được | PASS |
| Runtime/code compile được | PASS |
| Full tests pass | FAIL |
| Test coverage cũ còn nguyên | FAIL |
| Artifact ZIP cuối tồn tại | FAIL |
| Docs/report khớp thực tế | FAIL |
| CLI handoff command verified | CHƯA XÁC NHẬN |

**Kết luận cuối:** `KHÔNG ĐẠT NGHIỆM THU Ở TRẠNG THÁI HIỆN TẠI`.

Cần xử lý các P1 trước khi tạo ZIP bàn giao lại.
