# Frontend: dữ liệu và chart

## Luồng dữ liệu

Browser, rồi proxy `app/api/**/route.ts`, rồi `shared/api-client.ts`, rồi FastAPI. Danh sách route proxy hiện có:

- `ingestion/preview`, `ingestion/jobs`, `ingestion/jobs/[id]`
- `snapshots/[id]/candles`
- `replay/jobs`, `replay/jobs/[id]`, `.../vote`, `.../reveal`
- `external-analysis/jobs`, `external-analysis/jobs/[id]`, `.../vote`, `.../reveal`

Bảng điểm forecast không có proxy trình duyệt. Trang server `app/(work)/report/page.tsx` gọi thẳng `fetchForecastScoreboard` trong `shared/api-client.ts` tới `/external-analysis/scoreboard` với `snapshot_id`, `horizon`, `lookback_days`. Trình duyệt chỉ nhận kết quả đã tính và hiển thị bằng `features/report/scoreboard-card.tsx`, không tự tính accuracy hay khoảng Wilson.

## Job dự báo 6 giờ

`features/replay/use-replay-session.ts` tạo job qua `/api/external-analysis/jobs` với `horizon_minutes: 360`, `lookback_days: 14`, `mode: RETROSPECTIVE`. Production không dùng mock: không gửi `mock_mode`. Job nền (`202`) được hỏi lại định kỳ bởi `features/report/auto-refresh.tsx` và hook `use-replay-session.ts`.

Envelope `forecast-6h-v1` gồm `digest.features[]`, `answer{direction, confidence, reasons, risks}`, `verification`, `agreement_score`, `baselines`, `possible_memorization`, `horizon_minutes`, `lookback_days`, `flat_threshold_pct`, `token_usage`. Envelope legacy `evidence-pipeline-v1` vẫn được đọc để hiển thị job cũ; `direction: ABSTAIN` hiện "Không dự báo".

## Trạng thái và lưu cục bộ

- `use-replay-session.ts` giữ phiên mô phỏng: engine `strategy` hoặc `gemini`, job đang chạy, vote, reveal. Hai engine dùng horizon khác nhau: chiến thuật 30 phút, dự báo 6 giờ.
- Danh sách báo cáo gần đây lưu ở `localStorage` (`features/report/recent-reports.ts`), tách khỏi DB. Đổi trình duyệt hoặc xoá cache sẽ mất danh sách; job vẫn còn trong DB.

## Chart nến

Bắt buộc cho mọi chart tương tác:

- Cuộn chuột: zoom in/out.
- Kéo giữ chuột trái: pan trái/phải.
- Click chọn mốc, phân biệt với kéo bằng ngưỡng dịch chuyển chuột để kéo không kích hoạt click.
- Giờ hiển thị UTC+7 (Asia/Ho_Chi_Minh). Dữ liệu từ API là epoch millisecond UTC; chỉ đổi múi giờ khi hiển thị.

Component: `features/data/candlestick-chart.tsx`, `features/replay/replay-chart.tsx`.

## Trạng thái rỗng và lỗi

Thiếu dữ liệu: `Chưa có dữ liệu` hoặc `Gated`. API lỗi: banner rõ ràng, ví dụ `Không kết nối được dịch vụ dữ liệu`. Không hiển thị số giả. Mốc đi ngang dưới ngưỡng 0.5% hiện "Đi ngang (dưới 0.5%), không chấm."
