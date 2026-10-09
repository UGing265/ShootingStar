# Frontend — Next.js App Router

## Phạm vi

Chi tiết F1–F4 trong [`plan.md`](plan.md). `web/` hiện chỉ có package/lock/TS config: **chưa có ứng dụng**. Chỉ bắt đầu UI theo API schema đã kiểm chứng của Backend; trước khi trình bày quality/report/hits/signal như kết quả thật phải vượt gate A0 (producer và mô hình có provenance), không copy dashboard FastAPI `/` hoặc narrative hardcode.

## Cấu trúc đã chọn: feature-based gọn, không FSD đầy đủ

```text
web/src/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                  # Overview, route ghép status và liên kết
│   ├── data/page.tsx
│   ├── research/page.tsx
│   ├── research/[id]/page.tsx
│   ├── patterns/page.tsx
│   ├── patterns/[id]/page.tsx
│   ├── signals/page.tsx
│   ├── signals/[id]/page.tsx
│   └── about/page.tsx            # Landing tách khỏi năm trang làm việc
├── features/
│   ├── data/                     # quality, candles, API và types riêng
│   ├── research/                 # experiments, reports, calibration
│   ├── patterns/                 # rule, hit, outcome
│   └── signals/                  # prediction, decision, review
└── shared/
    ├── api-client.ts            # HTTP tới FastAPI, chạy server-side
    └── ui/                      # chỉ primitive thật sự dùng nhiều nơi
```

`app` chỉ chọn route, đọc search params và ghép feature; code riêng từng mảng nằm ở `features/<mảng>` (đặt file cạnh nhau trước, chưa tạo tầng con rỗng). `features` chỉ import `shared`, không import lẫn nhau. `shared` không import từ `features`/`app`; UI common phải chứng minh dùng ở ít nhất hai nơi, không hút quy tắc nghiệp vụ từ một feature. Overview/landing chưa có logic phức tạp thì giữ ngay route; nếu phát sinh mới tách thành feature. DTO của một mảng đặt trong mảng, không tạo type chung giả.

## Trang, dữ liệu và trạng thái

| Trang | Đầu vào backend | Điều kiện nghiệm thu |
|---|---|---|
| `/` Overview | health, runs/snapshots, experiments, latest signals | Status từ dữ liệu thật; không hiển thị số hardcode; empty/error rõ |
| `/data` | runs, snapshot quality, bounded candles | UTC coverage và checksum, gap nếu đã lưu; không tự tạo gap timeline |
| `/research` + `/research/[id]` | experiments, splits, reports/baselines/calibration | Cùng test window, sample_count, cost gate rõ, provenance |
| `/patterns` + `/patterns/[id]` | persisted rules, hits, outcomes, candle OHLC nếu có | Rule version + failure, cảnh báo overlapping windows, không gọi hit rate là P&L |
| `/signals` + `/signals/[id]` | prediction, distinct decision, outcome, review/audit | Pending/Evaluated/Unscorable + reason, không dùng DOWN làm short profit |
| `/about` (landing tách khỏi 5 trang) | origin/purpose/approved report, hoặc không có kết quả | Kể lý do ra đời và kết quả/giới hạn, không kể quy trình; SVG/canvas sao băng tiết chế, một sticky scene desktop native scroll; mobile stacked/reduced-motion tĩnh |

## Thứ tự

- [ ] F1: sửa scaffold `web/package*.json`, Next App Router, TypeScript, layout/style theo `docs/DESIGN.md`; `shared/api-client.ts` fetch server-only từ `SHOOTINGSTAR_API_URL`, DTO riêng theo feature. Cấu hình tránh CORS/truy xuất DB từ browser.
- [ ] F2: Overview, Data; mỗi trang empty/error/loading.
- [ ] F3: Research, Pattern Lab; drilldown/report versioned.
- [ ] F4: Signals và landing; desktop kiểm tra sticky scene/native scroll, mobile stacked, `prefers-reduced-motion`, keyboard/focus; trang làm việc chỉ chuyển động cơ bản.
- [ ] Browser smoke qua migrated test DB và backend thật: gap/report/pattern dùng fixtures có provenance; tín hiệu PENDING phải được tạo bởi lệnh model-driven rồi mature sau nến đóng. `npm ci`, `npm run typecheck`, `npm run build`, mở browser xem 5 trang và landing. Không đánh dấu hoàn thành chỉ nhờ compile hay insert signal synthetic.

## Docs

Viết `docs/frontend/README.md` sau khi chạy được: Node requirements, `web/.env.example`, `npm ci`, `npm run dev`, port 3000 và đường dẫn trang. Backend vẫn là dịch vụ khác trên port 8000.
