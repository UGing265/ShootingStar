# Frontend: kiến trúc và thư mục

Next.js App Router, TypeScript, React, CSS thuần, tại `frontend/`.

## Công nghệ

| Phần | Chi tiết |
|---|---|
| Framework | Next.js 16 (App Router), React 19, TypeScript 5 |
| Giao diện | CSS thuần theo `docs/DESIGN.md`; không dùng thư viện UI hay Tailwind |
| Biểu đồ nến | Tự vẽ bằng Canvas (`features/data/candlestick-chart.tsx`, `features/replay/replay-chart.tsx`) |
| Markdown | `react-markdown` |
| Gọi backend | `fetch` từ server, `server-only`; địa chỉ qua `SHOOTINGSTAR_API_URL` |
| Kiểm thử | Playwright E2E trong `frontend/e2e/` (backend 8100, frontend 3100, dist riêng `.next-e2e`); xem [../../run-frontend.md](../../run-frontend.md) |
| Lệnh | `npm run dev`, `build`, `start`, `lint`, `typecheck`, `e2e`, `e2e:gemini` |

## Trang (6)

| Đường dẫn | Mục sidebar | Dữ liệu từ backend (server-side) |
|---|---|---|
| `/` | (landing) | không |
| `/about` | Phương pháp | không |
| `/dashboard` | Tổng quan | `/health`, `/snapshots` |
| `/data` | Lịch sử giá | `/ingestion-runs`, `/snapshots`, `/snapshots/{id}/quality`, `/snapshots/{id}/candles` |
| `/replay` | Mô phỏng | `/snapshots`, `/snapshots/{id}/candles`; phần còn lại gọi proxy từ trình duyệt |
| `/report` | Báo cáo | `/external-analysis/scoreboard` |

Sidebar nằm ở `shared/ui/sidebar.tsx`: nhóm làm việc (Tổng quan, Lịch sử giá, Mô phỏng, Báo cáo) và nhóm giới thiệu (Giới thiệu, Phương pháp). Cây proxy `app/api/**` có 12 route; danh sách ở [02-data-fetching-and-charts.md](02-data-fetching-and-charts.md).

```text
frontend/src/
├── app/                 # định tuyến và ghép trang
│   ├── page.tsx         # trang chủ (landing)
│   ├── (work)/          # about, dashboard, data, replay, report; layout.tsx có sidebar
│   └── api/**/route.ts  # proxy server tới FastAPI
├── features/
│   ├── data/            # tải và xem nến, snapshot
│   ├── replay/          # phiên mô phỏng, chart, vote, kết quả, external-types.ts
│   ├── report/          # report-view.tsx, forecast-report.tsx, forecast-comparison.tsx,
│   │                    # scoreboard-card.tsx, legacy-report-sections.tsx
│   └── landing/         # trang giới thiệu
└── shared/              # api-client.ts (server-only), format.ts, ui/ (primitives, sidebar)
```

## Quy tắc

1. Trang trong `app/` chỉ ghép; logic hiển thị nằm trong `features/<mảng>/`.
2. `shared/api-client.ts` chỉ gọi FastAPI từ server qua `SHOOTINGSTAR_API_URL`. Browser gọi các route `app/api/**`, không gọi backend trực tiếp.
3. Không tính lại metric hay công thức thống kê ở client. Format hiển thị (`shared/format.ts`, `features/report/report-format.ts`) thì được.
4. Giao diện theo `docs/DESIGN.md`. Menu sidebar chỉ liệt kê trang có thật.
5. Kiểu dữ liệu API đặt ở `features/<mảng>/types.ts`; `features/replay/external-types.ts` giữ cả envelope `forecast-6h-v1` và envelope legacy `evidence-pipeline-v1`.
6. `features/replay/` import hàm từ `features/report/` (`labels`, `recent-reports`, `report-view`, `forecast-comparison`). Dùng chung nhiều chỗ thì chuyển lên `shared/`.

## Bố cục báo cáo

- `features/report/report-view.tsx` là khung chung: tiêu đề job, trạng thái, cảnh báo, kết quả thực tế, chi tiết kỹ thuật.
- Job `forecast-6h-v1`: `forecast-report.tsx` hiện hướng, confidence, điểm đồng thuận, lý do kèm chỉ số đọc được, rủi ro, cảnh báo kiểm chứng và banner có thể bị nhớ sẵn. `forecast-comparison.tsx` so Gemini với luật "Luôn TĂNG" và "Theo đà 6h".
- Job legacy `evidence-pipeline-v1`: `legacy-report-sections.tsx` hiện các mục cũ (báo cáo 7 phần, đối chiếu mẫu nến, nguồn tài liệu). Không có mục nguồn cho job mới.
- `scoreboard-card.tsx` chỉ hiển thị dữ liệu bảng điểm; trang báo cáo tải dữ liệu server-side bằng `fetchForecastScoreboard` trong `shared/api-client.ts`.
- Không hiển thị UUID, hash hay id kỹ thuật thô. Thời gian hiển thị UTC+7.

## Kiểm tra

`npm run typecheck` hoặc `npm run build` trong `frontend/`. Biến môi trường: `frontend/.env.example`.
