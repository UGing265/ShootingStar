# Phase 04 — UI dễ đọc và nghiệm thu toàn luồng

## Context
[Plan](plan.md), sau phases 01–03. P1; Pending. Dùng [Design](../../DESIGN.md) và [readable-report contract](../261010-readable-evidence-report/plan.md). Không thay chart Replay che tương lai/vote/reveal, không lẫn paper plan với lệnh thật.

## Files
Root: `D:/AShiroru/ProgramCode/Project/Team/ShootingStar/`.
- Create `frontend/src/features/replay/trade-plan-panel.tsx`, `trade-plan-types.ts`: watcher/plan UI typed, đúng feature boundary.
- Modify `frontend/src/features/replay/replay-player.tsx`: thêm mode chiến thuật riêng trong Replay, giữ nhánh direction cũ; chọn mode trước tạo watch. Worker live không gọi snapshot future APIs.
- Reuse `frontend/src/features/replay/replay-chart.tsx` và modify khi cần entry/TP/SL/time labels, không fork canvas implementation; giữ wheel zoom, drag pan, click threshold.
- Create Next server-side proxy routes dưới `frontend/src/app/api/trade-watches/` và `.../trade-plans/` khớp Phase 02; auth forwarding theo `shared/api-client.ts`, không browser secret.
- Modify docs `docs/backend/README.md`, `docs/frontend/README.md`, `docs/local-run.md`, `docs/external-apis.md`, `docs/binance-spot-fees.md` sau smoke, ghi public streams/cost methodology và các gates chưa đủ.
- Backend/API tests cập nhật consumer-visible contracts từ Phase 02/03; frontend không tạo suite mới chỉ để snapshot strings.

## Bề mặt người dùng
1. Chọn Replay snapshot hoặc theo dõi public BTCUSDT live. Live cần worker online và ready/fresh feed; không gọi snapshot là realtime.
2. Nhập notional/max planned loss, wait duration, chọn approved strategy config/artifact và xem fee/slippage source. Thiếu config nói thiếu gì, không auto default risk 1–2%.
3. Hiện `Chờ xác nhận / Chỉ theo dõi — chưa kiểm chứng / Có thể cân nhắc mua / Bỏ lượt`, phần nguyên nhân trên cùng.
4. Kế hoạch card: vùng vào, xác nhận, TP/SL, hạn chờ, planned risk + caveat gap, bằng chứng và điều kiện hủy. Sau vào ghi actual/manual-reported/paper entry, 30m countdown lấy deadline backend; dùng clock sync/health, không trừ client local thời gian như nguồn quyết định.
5. Xác suất: “Chạm mục tiêu trước cắt lỗ”, “Chạm cắt lỗ trước mục tiêu”, “Hết hạn chưa chạm”; interval/N/data period/calibration. Null hiện “Chưa đủ kiểm chứng”, không 0%. Xác suất market-touch không gọi “xác suất có lãi sau phí”.
6. Button “Ghi nhận vào lệnh” tường minh PAPER hoặc MANUAL_REPORTED; không nhãn “Mua BTC”. Manual fill đã xảy ra có đường ghi nhận OFF_PLAN dù candidate expired/ineligible; valid actual time không tương lai, đồng thời reconcile elapsed path/overdue. Không cho paper dùng đường này để bypass approval.
7. TP/SL/time hit → EXIT_REQUIRED; ghi exit cùng immutable execution mode, quantity/fees/time. Manual phải xác nhận đã bán, paper outcome chỉ đóng PAPER. Partial exit còn active reservation; overdue hiển thị actual duration, không clamp thành <=30m.
8. Vùng lời/nguy hiểm trên chart là mục tiêu/invalidation, không tô nó như giá tương lai chắc chắn. Historical Replay che phía sau cutoff đến reveal đúng cơ chế riêng, strategy shadow labels không đưa outcome vào decision pane.

## An toàn và restart
- Một active exposure `OPEN | EXIT_REQUIRED`/remaining quantity trên operator/symbol; disallow new entry/watch replacement trong DB transaction. UI disable chỉ phụ trợ, không để đổi session/mode bypass.
- Ngừng tìm điểm vào không vô hiệu monitor vị thế. Health DEGRADED cảnh báo rõ, BUY bị khóa; exit instruction không phụ thuộc report LLM.
- Reload/status GET không tạo watch/candidate/entry/Gemini. Restore cả OPEN/EXIT_REQUIRED bằng saved ID; không lấy risk/barriers từ form đã sửa. Shadow research hiển thị riêng không kích hoạt manual entry.
- Bài AI render theo safe Markdown kế hoạch readability; labels/units do backend metadata xuất, frontend chỉ format. Không thêm glossary đối lập; không raw HTML/source scripts.
- Live monitor không thể bảo đảm bảo vệ tiền thật khi app/network dừng. Banner rõ phần mềm chưa gửi SL/TP lên sàn; không coi watcher như stop order thật.

## Nghiệm thu hành vi
| Kịch bản | Kết quả bắt buộc |
|---|---|
| Điều kiện chưa xảy ra | WAIT với điều kiện/hạn chờ, không BUY hoặc vị thế giả |
| Confirmation nhưng chưa cost/calibration/risk | WATCH_ONLY/CONFIG_REQUIRED, p null nếu chưa valid |
| Eligible + explicit entry | Một position, TP/SL lock, deadline entry+30m |
| TP hoặc SL chạm | EXIT_REQUIRED reason đúng; fill/outcome riêng |
| Hết 30m, không chạm | Exit alert; không invent exit price/fee |
| Chạm trong cùng bar không biết thứ tự | AMBIGUOUS; không báo thắng |
| Disconnect/restart | BUY frozen, deadline không đổi, gap/overdue rõ |
| Entry/exit gửi hai lần | Idempotent response; không duplicate trade |
| EXIT_REQUIRED chưa xác nhận bán / partial exit | Giữ reservation/monitor; không entry thứ hai |
| Paper exit cho manual position | Reject, không đóng vị thế hoặc mất cảnh báo |
| Manual ghi entry trễ sau SL | Reconcile → EXIT_REQUIRED, occurrence/receipt tách riêng |
| Refresh/đổi tab/form khác | Same saved plan, không gọi provider hoặc thay TP/SL |

## Verification và docs
- Chạy CLI engine/replay dataset thật; lưu transcript candidate hoặc SKIP thật. Live public watcher: startup/fresh event/reconnect/stop/restart/overdue scenario bằng thời gian và logs có nguồn. Fault injection trong harness chỉ để exercise, không production report.
- Backend `pytest backend/tests/test_entry_strategy.py backend/tests/test_trade_watch.py backend/tests/test_barrier_evaluation.py backend/tests/test_api_and_ui.py` và contract suite liên quan DB test riêng; migrations SQLite/PostgreSQL nếu supported path thay đổi.
- Frontend `npm run typecheck`, `npm run build`. Browser thật desktop 1280/mobile 390: mode switch, fields, wait/entry/exit, disabled gates, time sync, chart pan/zoom/click, refresh; ảnh và network evidence. Không gửi lệnh Binance thật.
- Interval/probability/calibration report trên dữ liệu thật; chưa đạt thì không claim supported BUY/positive expectancy. Muốn done end-to-end actionable gate phải có risk config, approved cost methodology và prospective/OOS evidence, không chỉ UI chạy được.
- Sau smoke update docs/changelog theo convention tìm được; migration/config/commands/user wording; remove throwaway scaffolds. No auto commit/push.

## Checklist
- [ ] UI đủ plan/clock/probability/gate/health, không lẫn hướng giá cuối kỳ.
- [ ] Cảnh báo paper/manual, no real order/guaranteed stop; cannot move SL/time.
- [ ] Browser/CLI/API/report evidence có output.
- [ ] Docs và plan status đúng gate đã quan sát; unresolved ghi chính xác, không “100% thắng”.
