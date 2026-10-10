# Phase 02 — Watcher, lịch sử và lifecycle

## Context
[Plan](plan.md), sau [Phase 01](phase-01-entry-barriers-risk.md). P1; Pending. Hai clock: wait expiry từ candidate creation; holding expiry = confirmed entry time + 1_800_000ms. Theo dõi chạy dài hơn cả hai nhưng không gia hạn candidate/position.

## Files
Root: `D:/AShiroru/ProgramCode/Project/Team/ShootingStar/`.
- Create `backend/shootingstar/adapters/binance_market_events.py`: REST/public WS trade events và quotes/depth đủ phục vụ evidence; tái dùng transport/rate handling ingestion sau đọc implementation, không duplicate secrets.
- Create `backend/shootingstar/application/trade_watch.py`: một lifecycle/watch service, deterministic reducer và orchestration nhỏ; không scheduler framework/service thứ hai.
- Modify `backend/shootingstar/adapters/db/models.py`, `repository.py`: plan/candidate, entry/exit observation, watch lease/cursor, prediction artifact refs; append-only events với unique idempotency keys. Không dùng bảng directional signal như triple-barrier schema.
- Create migration mới dưới `backend/alembic/versions/` sau xác minh head thật; không sửa revision đã phát hành.
- Create `backend/shootingstar/api/trade_plan_routes.py`; modify `api/app.py`, `api/schemas.py`, `cli/main.py` cho đăng ký route/worker CLI.
- Add `backend/tests/test_trade_watch.py` và contract tests theo existing API test patterns.

## Runtime và API
- CLI public watcher `shootingstar watch-entry --symbol BTCUSDT --config <file>` chạy đến operator stop, không gắn tuổi worker với 30m. CLI replay/research dùng snapshot/cursor chronological riêng, không xem outcome tương lai để chọn điểm vào.
- FastAPI nhận cấu hình/start/stop bằng protected admin endpoint, ghi durable command để worker xử lý; không chạy endless watcher trong request/BackgroundTasks. Worker unique lease, bounded heartbeat và clear owner để chống hai terminal cùng mở position.
- Routes dự kiến: POST `/trade-watches`, GET `/trade-watches/{id}`, POST `/trade-watches/{id}/stop`; GET `/trade-plans/{id}`; POST `/trade-plans/{id}/entry-observations`, POST `/trade-plans/{id}/exit-observations`; POST `/trade-plans/{id}/cancel` chỉ FLAT. All write auth, limit và idempotency; không POST `/api/v3/order` hoặc signed trade tools.
- Observation mode tường minh `PAPER | MANUAL_REPORTED`. PAPER là giả định execution model có evidence, không masquerade real fill; MANUAL_REPORTED lưu giá/quantity/time/fees người xác nhận, không chứng minh exchange fill. Không hỗ trợ leverage/short.
- `RESEARCH_ONLY` shadow run riêng: unapproved frozen strategy/artifact được tạo hypothetical episodes tự động theo occupancy policy cố định; không emit BUY_ELIGIBLE, không tạo MANUAL_REPORTED position, không lẫn real/manual reservation. Entry/exit/quote evidence riêng dùng để hoàn thành approval Phase 03.
- UI chỉ poll DTO/durable state. Polling không tạo candidate mới, không Gemini call, không đổi clock.
- Auth dùng server-admin convention hiện có (`X-Admin-Key`/`SHOOTINGSTAR_ADMIN_KEY`), không coi CORS/localhost là auth; operator identity fixed server-side cho local single-operator, không nhận `operator_id` body để bypass reservation. Strategy enable gate riêng, không buộc public watcher dùng external-model enabled flag; shared helper nếu tách phải migrate refs external/lesson routes, không fork authorization semantics. GET strategy state cũng protected.
- Next mutation proxy kiểm same-origin/CSRF trước tự gắn admin header; không expose admin key qua browser/env public. Worker CLI commands chỉ local authorized operator; approval audit ghi identity/time/report hashes.

## Lifecycle
`WATCHING → WAIT_CONFIRMATION → ENTRY_ELIGIBLE → OPEN → EXIT_REQUIRED → CLOSED`; candidate có nhánh `SKIPPED | INVALIDATED | EXPIRED | CANCELLED`. Data health độc lập `FRESH | DEGRADED | DISCONNECTED | RECOVERING`.

- Trigger entry chỉ sau nến confirmation đã đóng và available tại decision. Freeze candidate/barriers khi bắt đầu wait. Waiting reanalysis tạo version mới và invalidates predecessor, không sửa history; chưa có entry không chạy clock giữ lệnh.
- Entry eligibility recheck ngay transaction tại receipt: confirmation/current price/freshness/cost/expiry còn đúng, candidate version chưa superseded, no active exposure. Proposed/paper expired reject; actual manual off-plan chỉ nhận đường observation recovery riêng, không BUY promotion. Worker concurrency dùng sequence/CAS để confirmation vs expiry/invalidation không commit hai terminal states.
- Atomic reservation `(operator_id, symbol)` giữ trong cả `OPEN | EXIT_REQUIRED` và mọi remaining quantity > 0, xuyên watch replacement/restart. Entry/start/stop guard dùng active exposure, không chỉ OPEN hoặc session ID. Idempotency/constraint và lease có fencing token để worker cũ không commit sau mất lease.
- Execution mode khóa trên position tại entry: PAPER chỉ paper-model outcomes đóng được; MANUAL_REPORTED phải operator ghi exit cùng mode. Paper exit không đóng manual, mode-switch reject. Partial exits giảm remaining net BTC nhưng không giải phóng reservation đến hết lượng; handling dust/fee ghi rõ, không silently CLOSED.
- Delayed manual entry: lưu event occurrence và receipt riêng, reconcile atomic path từ entry boundary đến current cursor trước mở monitoring; hit trước receipt/deadline elapsed → EXIT_REQUIRED ngay, không nói alert đã gửi lúc event. Thiếu path → DEGRADED/UNSCORABLE, giữ active exposure. Manual off-plan vẫn ghi giữ vị thế, không nâng eligibility.
- OPEN/EXIT_REQUIRED: monitor ordered touches, TP/SL và deadline immutable, không LLM. Timeout instruction theo clock ngay cả disconnect, chưa quote/fill không tạo exit price. Strategy-resolved label và filled/manual position outcome riêng.
- Stop khi FLAT dừng discovery; active exposure chỉ stop-new-entries, bảo toàn monitoring và overdue cảnh báo. Force process shutdown không có exchange stop bảo vệ: lưu orphan flag, cảnh báo rõ và restart restore deadline/cursor/reservation. Không bán hộ hoặc tự cộng thêm 30m.

## Market events và tính nhân quả
- Source event time + local received_at/ingested_at; dùng closed-kline events cho candidate, ordered public trade IDs/time cho path label. Tick/bar forming chỉ monitor exits, không giả nến đã đóng.
- Quotes/depth capture có sequence provenance cho paper-cost evidence; không lấy last trade như executable ask/bid. Public trade hit không đồng nghĩa stop/limit fill.
- Replay 1m/5m OHLC: nếu cùng bar chạm TP và SL → `AMBIGUOUS`, không TP-first tùy ý. Entry ở giữa bar không dùng high/low cả bar như post-entry path. Trước timeout nếu chỉ có bar cắt qua boundary không lấy phần sau deadline.
- Trade sequence thiếu/out-of-order → freeze new entries; backfill/dedup bằng ID rồi chỉ resume nếu đủ continuity. Backfilled records không rewrite quyết định lúc offline; outcome recomputation version/audit rõ, không đổi prediction.
- Kline/outcome chưa đủ dữ liệu → PENDING; unresolved gap/censored -> UNSCORABLE, không tự TIMEOUT. TIMEOUT event clock là exit instruction; TIMEOUT label yêu cầu path đầy đủ không hit barrier và data qua deadline.

## Resilience và provider latency
- Binance REST honor current exchangeInfo/rate headers, 429 Retry-After, 418 halt; không copy register cũ như fixed IP budget. WS ping/pong, reconnect/server shutdown, 24h lifetime theo [primary WS docs](https://developers.binance.com/en/docs/products/spot/web-socket-streams.md).
- Durable worker stop controls, reconnect/backfill chỉ public-data GET, bounded policy và circuit gate freshness. Không dùng polling UI như heartbeat safety.
- Gemini chỉ narrative theo candidate/version, explicit budget; completion trễ phải kiểm lại cutoff/validity. Candidate expired hoặc price moved → stale report, không BUY. Không auto retry read timeout bằng key khác; trạng thái UNKNOWN có thể đã billed. Chức năng safety/risk quyết deterministic không chờ provider.

## Gate và smoke
- [ ] Sequential replay trên snapshot thật: wait/expire/invalidate/enter/barrier/timeout, output reason/IDs rõ.
- [ ] Live CLI watch public event thật, quan sát closed candle receipts; stop/restart thấy continuity và lease không duplicate.
- [ ] Duplicate tick, equal event timestamp IDs, ordering gaps, race entry/exit, expiry exact boundary, before-entry touches, restart overdue, cancel after OPEN được kiểm.
- [ ] Disconnect OPEN vẫn timeout exit-required; không claim filled hoặc lời/lỗ khi không có fill.
- [ ] EXIT_REQUIRED chưa bán chặn entry/watch mới; paper outcome không đóng manual, partial exit không release reservation, late entry reconcile past SL và same-timestamp boundary.
- [ ] DB migration/API tests isolation; unauthorized write/read fail closed; idempotent requests không mở lệnh lần hai.

## An toàn
Không Binance trading credentials; không log secret/admin key/path DB. Prompt external sources không ra lệnh cho worker. Archiving records không cho record preview trở thành fill thật. Watcher local-first, PostgreSQL/SQLite theo explicit config như repo.
