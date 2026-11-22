# 261121 — Gỡ toàn bộ phần "tự học", chỉ chừa báo cáo

Ghi đè phạm vi của `261109-cleanup-and-ui-redo` theo chỉ đạo trực tiếp của user (2026-11-21).
Trạng thái: **ĐÃ THỰC THI MỘT PHẦN, CHƯA NGHIỆM THU.** P1-P3 backend CHƯA đạt nghiệm thu: pytest chưa kiểm chứng (exit 1, thiếu `shootingstar_test_db`), migration chưa chạy, chưa có review độc lập của omp (command-code chỉ là reviewer tạm, đọc `app.py` sau khi Lead sửa chồng). P4 frontend/docs: omp `VERDICT: PASS`, typecheck exit 0, `npm run build` không ổn định (exit 1 rồi 0), reveal chưa thử trên trình duyệt. Còn mở: 5 quyết định bên dưới, chưa commit.

## Goal
Gỡ mọi thứ liên quan "tự học" (lessons, Pattern Lab thống kê, research agent học từ tài liệu, model tự huấn luyện). Giữ: ingestion, snapshot, replay chiến thuật, trade plan/watch, và toàn bộ luồng báo cáo Gemini.

## Giữ (không đụng)
- Ingestion Binance + snapshots + trang Lịch sử giá.
- Replay `/replay/jobs` (strategy engine, `ai_prediction = NO_MODEL`).
- Báo cáo Gemini `/external-analysis/jobs`, kể cả `grounded_research` (nguồn tài liệu trong báo cáo) và `evaluate_pattern_diagnostics` (tiêu chí nến hiển thị ở `PatternChecks`).
- Trade plan/watch (`trade_watch`, `entry_strategy`, `barrier_evaluation`, routes). Không phải "tự học". Chờ user xác nhận ở Quyết định 5.
- `url_validator.py` (còn được `gemini_adapter` dùng).

## Gỡ
| Nhóm | Mục |
|---|---|
| Lessons | `lesson_routes.py`, `external_analysis/lessons.py`, 3 bảng `lessons*`/`lesson_*`, `lesson_ids` trong báo cáo, `extract_lessons_from_text`, `approved_lessons` |
| Research agent học | `orchestrate_research`, `search_catalogue`, `count_catalogue_documents`, `DocumentMatch`, `lesson_service` trong `ResearchAgent` |
| Pattern Lab | `PatternLabService`, các `*Rule`, `PatternHit/Report`, `/pattern-rules`, `/patterns`, bảng `pattern_rules`, `pattern_hits`, DTO, repository |
| UI | trang `patterns`, `lessons`, `signals`, `research`, mục menu tương ứng |
| CLI | `scan-patterns`, `research-pattern` |

## Đã làm trong phiên này (chưa commit, chưa kiểm chứng đủ)
- `read_routes.py`: bỏ 4 route pattern, import và helper chết.
- `app.py`: bỏ `lesson_router`. `cli/main.py`: bỏ 2 lệnh CLI.
- `patterns.py`: cắt còn phần diagnostics (từ 856 xuống khoảng 530 dòng).
- `repository.py`, `models.py`, `schemas.py`, `db/__init__.py`: bỏ repo, model (kể cả cột `lesson_ids_json`), DTO của lessons và pattern.
- Đã xoá file: `api/lesson_routes.py`, `external_analysis/lessons.py`, `tests/test_lessons.py`, `tests/test_pattern_lab.py`.
- Test đã xoá: 2 test `/pattern-rules`, `/patterns`; `test_research_admin_api_endpoint`, `test_cli_research_pattern_mock`.
- Frontend: bỏ 2 mục menu, trang và feature `lessons`, `patterns`, chip bài học trong `report-view.tsx`, `lesson_ids` ở `external-types.ts`. `tsc --noEmit` đã pass sau bước này, `pytest` 120 pass trước khi xoá đợt 2.

## Trạng thái hiện tại: **backend đang gãy**
Đã quan sát: `import shootingstar.api.app` lỗi `ModuleNotFoundError: ...external_analysis.lessons` vì `research_agent.py:16` còn import file đã xoá.
Chưa chạy nhưng thấy bằng grep, chắc chắn gãy khi chạy:
- `service.py:342,435,451` dùng `job.lesson_ids_json` (cột đã bỏ khỏi model), `service.py:55-63` còn `approved_lessons` và `ResearchAgent(lesson_service=None)`.
- `verifier.py` (`approved_lesson_ids`), `contracts.py:46` (`lesson_ids`), `gemini_adapter.py` (dòng 201-253, 301, 309-460, 977).
- `tests/test_api_and_ui.py:65-71` còn import `PatternHitModel`, `PatternRuleModel`, `PatternHitRepository`, `PatternRuleRepository`; `test_persistence.py`, `test_research_agent.py`, `test_external_analysis.py` còn tham chiếu lessons/pattern.

## Quyết định cần user chốt trước khi dispatch
1. Giữ `evaluate_pattern_diagnostics` và `grounded_research` trong báo cáo? Khuyến nghị: giữ (là bằng chứng của báo cáo, không phải tự học).
2. Drop bảng DB bằng migration Alembic mới: 5 bảng (`lesson_review_events`, `lesson_revisions`, `lessons`, `pattern_hits`, `pattern_rules`) và cột `external_analysis_jobs.lesson_ids_json`. Việc này trái ghi chú "schema locked" và plan 261109 ("không drop"). Cần user đồng ý rõ. Khuyến nghị: viết migration có `downgrade`, **không chạy** cho tới khi bật Postgres và `pg_dump`.
3. Hướng xử lý trạng thái gãy: tiến tiếp (khuyến nghị, đã gỡ quá nửa) hay `git stash` để quay lại? 86+ thay đổi chưa commit, nên không `git checkout` bừa.
4. Báo cáo cũ trong DB có `lesson_ids_json` khác rỗng: bỏ mất dữ liệu đó có chấp nhận không? Chưa kiểm tra DB (Postgres đang tắt).
5. Trade plan/watch: giữ như plan 261109, hay gỡ luôn?

## Phases
Phân quyền file tách rời (branch `dev` dùng chung).

### P1 — Tách lessons khỏi pipeline báo cáo (worker: omp terra, backend)
Files sở hữu: `application/external_analysis/{research_agent,service,verifier,contracts}.py`, `adapters/model_api/gemini_adapter.py`, `api/external_routes.py` (chỉ nếu trả `lesson_ids`).
- `ResearchAgent`: giữ `conduct_job_research` + `research_contract_to_dict`, bỏ phần lessons và catalogue.
- `service.py`: bỏ `approved_lessons`, `lesson_ids_json`; bỏ truyền `lesson_service`.
- `verifier.py`, `contracts.py`: bỏ `lesson_ids`.
- `gemini_adapter.py`: bỏ tham số/prompt lessons, `extract_lessons_from_text`, mock tương ứng; bỏ `lesson_ids` khỏi schema JSON yêu cầu model.
- Acceptance: `import shootingstar.api.app` ok; `grep -rniE "lesson" backend/shootingstar` không còn kết quả ngoài migration cũ.

### P2 — Test (worker: command-code flash; chạy sau P1)
Files sở hữu: `backend/tests/*` (4 file nêu trên + `conftest.py` nếu cần).
- Xoá test cho thứ đã gỡ, sửa import. Không viết test mới trừ khi mất coverage luồng báo cáo.
- Acceptance: `pytest backend/tests` xanh, báo số test và exit code.

### P3 — Migration + DBML (worker: omp terra; chỉ sau khi user chốt Quyết định 2)
Files: `backend/alembic/versions/<rev>_drop_self_learning_tables.py` (down_revision `6a7b8c9d0e1f`), `docs/database-schema.dbml`.
- `upgrade`: drop theo thứ tự `lesson_review_events`, `lesson_revisions`, `lessons`, `pattern_hits`, `pattern_rules`; drop cột `lesson_ids_json`. `downgrade`: tạo lại đúng schema cũ.
- Không chạy lên DB thật trong phase này. Acceptance: `alembic upgrade head` rồi `downgrade -1` trên DB test sạch (cần `SHOOTINGSTAR_TEST_DATABASE_URL`).

### P4 — Frontend + docs (worker: command-code flash; song song P1)
Files: `frontend/src/**`, `README.md`, `docs/**` (trừ `docs/plans/261109-*` chỉ ghi chú superseded), `backend/shootingstar/api/app.py` (văn bản "Pattern Lab" ở trang `/`).
- Rà dấu vết còn sót; sửa text; cập nhật `docs/DESIGN.md`/README nếu nhắc trang đã bỏ.
- Acceptance: `npm run typecheck` và `npm run build` exit 0. Ghi rõ lỗi bảo mật Next 16.4.0 nếu còn.

### P5 — Verify (orchestrator tự làm, không tin báo cáo của thợ)
- `git diff` đối chiếu từng acceptance; grep symbol đã xoá; chạy `pytest`, `typecheck`, `build`.
- Bật Postgres (user chạy `Start-Service postgresql-x64-18` quyền admin), `GET /health` phải `connected`, gọi thử `/external-analysis/jobs` ở mock mode.
- Quét chính tả phần text mới sửa. Không commit; chỉ commit khi user bảo.

## Rủi ro
- Dọn bảng không hoàn tác được; luôn `pg_dump` trước.
- Báo cáo đã lưu có thể tham chiếu `lesson_ids` cũ; UI không còn hiển thị nên an toàn, nhưng `GET /external-analysis/jobs/{id}` cần được kiểm tra không lỗi khi cột biến mất.
- Chưa chạy gì với Postgres thật; mọi nhận định về dữ liệu trong DB là chưa xác minh.
