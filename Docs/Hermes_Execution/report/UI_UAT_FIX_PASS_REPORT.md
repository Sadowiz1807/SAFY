# UI_UAT_FIX_PASS_REPORT

1. File đã đọc.
- `Apps/Web/index.html`
- `Apps/Web/mock-ui.js`
- `Apps/Web/styles.css`
- `Apps/Api/safy_api/main.py`
- `Apps/Api/safy_api/schemas.py`
- `Data/model_profiles/model_profiles.json`
- `Data/Database_management/database_profiles.json`
- `DataStore/profile_store.py`
- `State/json_runtime_db.py`

2. File đã sửa.
- `Apps/Web/index.html`
- `Apps/Web/mock-ui.js`
- `Apps/Api/safy_api/main.py`
- `Apps/Api/safy_api/schemas.py`
- `State/json_runtime_db.py`

3. Model API Key field đã khôi phục ở đâu.
- Khôi phục field `API Key` trong model form ở `Apps/Web/index.html`.
- `mock-ui.js` cập nhật `syncModelFields()` để LM Studio/Ollama không bắt buộc API Key, còn provider remote hiển thị/đòi API Key.
- UI dùng field đơn giản `API Key`, không bắt user thao tác trực tiếp với `api_key_env` technical field.

4. Save/Test model đã sửa gì.
- Giữ route model hiện có: `POST /model-profiles`, `POST /model-profiles/{profile_id}/activate`, `POST /model-profiles/{profile_id}/test`, `GET /model-profiles/active`.
- `saveModelConfig()` save rồi activate, sau đó refresh active profile và update topbar/model status.
- `testModelConnection()` ưu tiên test profile đã active/saved; nếu chưa có thì save trước rồi test.
- Lỗi model được render ở model card / normalized error area, không đẩy sang Execute Error.
- Lưu ý backend hiện tại không có secret store cho raw API key; codebase hiện thiên về `api_key_env`. Workflow UI đã được đơn giản hóa, nhưng save/test live cho remote provider vẫn phụ thuộc backend secret handling hiện có.

5. Session delete endpoint/UI đã thêm gì.
- Thêm backend `DELETE /sessions/{chat_id}` trong `Apps/Api/safy_api/main.py`.
- Thêm `delete_session(chat_id)` trong `State/json_runtime_db.py`.
- UI `loadSessions()` thêm delete bằng right-click context menu + confirm.
- Sau khi xóa: remove session, reload list, và nếu đang mở session đó thì clear/create session mới.

6. Database mock/real status được xác định ở đâu.
- `GET /database-profiles/active` trong `Apps/Api/safy_api/main.py` trả thêm trạng thái chuẩn hóa gồm `mode`, `connection_status`, `read_only`.
- `mock-ui.js` thêm logic parse/summarize để hiển thị rõ:
  - `Database: Not connected`
  - `Database: Mock/Fake`
  - `Database: Real connected`
  - `Database: Real connection failed`

7. Database form simple đã sửa gì.
- `Apps/Web/index.html` chuyển phần chính của DB form về simple fields:
  - Connection Name
  - Base URL
  - API Key
  - Username
  - Save Database
  - Test Connection
- Các field kỹ thuật vẫn giữ trong `Advanced Settings` và mặc định ẩn/collapsed.
- `mock-ui.js` cập nhật build payload từ simple fields trước, rồi mới map nội bộ sang format backend.

8. Verification commands/results.
- `python -m py_compile Apps/Api/safy_api/main.py Apps/Api/safy_api/schemas.py Agent/agent_runtime.py` → PASS
- `node --check Apps/Web/mock-ui.js` → PASS
- Code inspection grep/search đã dùng để kiểm tra các vùng liên quan `api_key`, `api_key_env`, session delete, database status.

9. Manual UI checklist result.
- 1. Model form có API Key field. → VERIFIED BY CODE
- 2. LM Studio không bắt API Key. → VERIFIED BY CODE
- 3. OpenAI/OpenRouter có API Key field. → VERIFIED BY CODE
- 4. Save Model thành công. → NOT LIVE-VERIFIED IN THIS PASS
- 5. Test Connection thành công hoặc lỗi hiện đúng trong Model card. → VERIFIED BY CODE, NOT LIVE-VERIFIED
- 6. Lỗi model không hiện ở Execute Error. → VERIFIED BY CODE
- 7. Có nút xóa session. → VERIFIED BY CODE (right-click delete behavior)
- 8. Xóa session hoạt động. → NOT LIVE-VERIFIED IN BROWSER, BACKEND/API CODE ADDED
- 9. Database status nói rõ Mock/Fake/Real/Not connected. → VERIFIED BY CODE
- 10. Database form simple chỉ hiện Connection Name, Base URL, API Key, Username. → VERIFIED BY CODE
- 11. Advanced database fields bị ẩn. → VERIFIED BY CODE
- 12. Save/Test Database cập nhật status đúng. → VERIFIED BY CODE, NOT LIVE-VERIFIED

10. Remaining issues.
- Backend hiện tại chưa thể hiện rõ cơ chế secret store cho raw API key/password; codebase hiện vẫn nghiêng về env-based secret reference (`api_key_env`, `password_env`).
- Vì vậy workflow UI đã đơn giản hơn cho user, nhưng save/test live với remote provider / real DB có thể vẫn cần backend decision nếu muốn hỗ trợ raw secret input thực sự.
- Chưa chạy live browser UAT trong pass này, nên các flow save/test/delete/status mới chỉ được verify bằng compile + code inspection.

11. Final status.
- `BLOCKED_UI_UAT_FIX_REQUIRES_BACKEND_DECISION`
