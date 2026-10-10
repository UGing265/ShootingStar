# Nghiên cứu và quyết định cho chiến thuật 30 phút

## Phạm vi bằng chứng
Hai agent nghiên cứu đọc source repo và tài liệu primary; parent đọc lại Binance REST overview/WS. Không chạy watcher, trade, model training hay backtest trong lần lập plan. Các kết luận thiết kế là đề xuất, không metrics thực nghiệm.

## Nguồn primary
- [Binance REST general information](https://developers.binance.com/en/docs/products/spot/rest-api.md): public market-data endpoint, timestamps millisecond default, asynchronous data-source delays, 429/418/Retry-After, rateLimits từ exchangeInfo. Không hardcode IP budget 1200 trong register cũ là giới hạn hiện hành.
- [Binance WebSocket information](https://developers.binance.com/en/docs/products/spot/web-socket-streams.md): market-only streams, connection lifetime 24h, ping mỗi20s/pong trong60s, serverShutdown, local book snapshot+update-ID continuity. Đây không phải SLA fill/latency.
- [Binance symbol filters](https://developers.binance.com/en/docs/products/spot/filters): PRICE_FILTER/tickSize, LOT_SIZE/stepSize, MARKET_LOT_SIZE, NOTIONAL/MIN_NOTIONAL. Lấy values BTCUSDT từ exchangeInfo lúc chạy, không copy numbers minh họa.
- [Binance commission FAQ](https://developers.binance.com/en/docs/products/spot/faqs/commission_faq): standard/tax/special rates, discounts có điều kiện, fee asset và lượng BTC net. FAQ examples là fictional; không dùng như account fee thực.
- [Fee schedule](https://www.binance.com/en/fee/trading) được register repo đăng ký ngày2026-10-09; không fetch lại hoặc xác nhận fee account trong lần plan này.

## Repo đã khảo sát
- `application/training/modeling.py`: binary logistic + calibration; thiếu class calibration có fallback raw probability, không tự dùng làm approved barrier artifact.
- `application/training/labels.py`: label forward return cố định; không first TP/SL event.
- `application/training/splits.py`: temporal splits và purge conventions; phải kiểm interval waiting/holding mới, không nói existing gap đã chứng minh mọi leakage được chặn.
- `application/evaluation.py`: binary probability metrics, cost fields gated; reuse patterns, không reuse semantics cho multiclass.
- `application/signals.py`: immutable prediction/outcome riêng; không sửa meaning p_up/down thành barrier classes.
- `application/external_analysis/context.py`: causal availability/feed; `service.py` probability LLM null; giữ nguyên.

## Quyết định chấp nhận
- Ưu tiên empirical 3-outcome baseline với smoothing/uncertainty thay vì LLM score hoặc model binary sai mục tiêu.
- Trade path ordering giúp phân giải market-touch; OHLC same-bar không biết thứ tự. Fills/costs là lớp riêng.
- Replay snapshot + prospective live receipts; historical book thiếu không thể tự tạo net fills/slippage.
- WATCH_ONLY khi chưa approve risk/cost/estimator; không claim sự thiếu dữ liệu được chữa bằng thêm agent.

## Đề xuất nghiên cứu bị bác bỏ
- Agent đưa ví dụ công thức SL phía trên entry/TP phía dưới cho short Shooting Star: **không áp dụng** long-only người chưa mua. Contract yêu cầu SL < entry < TP.
- “Mọi ambiguous mặc định SL_FIRST”: chỉ dùng sensitivity bảo thủ riêng; ground truth vẫn AMBIGUOUS, không relabel để fit/calibrate.
- Ngưỡng “N<50” và “ECE>10%”: không có evidence chốt cho dự án; bỏ. Ngưỡng selection phải chốt trước final test từ validation/risk và uncertainty.
- “Empirical estimator đáng tin nhất/0% độ tin cậy LLM”: không có metric chứng minh; baseline dễ audit, reliability vẫn cần kiểm chứng. Không công bố số confidence giả.

## Giới hạn cần giải trong triển khai
REST trade/aggTrade pagination và semantics cụ thể phải đọc đúng endpoint docs trước code; không đoán sequence/aggregation hoặc claim receipt time lịch sử. Các rule/buffer/bin thresholds và cost tail vẫn là phần nghiên cứu của phase, không một tham số mặc định bảo đảm lãi.
