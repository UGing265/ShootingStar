# Frontend: kiến trúc và thư mục

Next.js App Router, TypeScript, React, CSS thuần, tại `frontend/`.

```text
frontend/src/
├── app/                 # định tuyến và ghép trang
│   ├── page.tsx         # trang chủ (landing)
│   ├── (work)/          # nhóm trang làm việc: about, dashboard, data, replay, report; layout.tsx có sidebar
│   └── api/**/route.ts  # proxy server tới FastAPI
├── features/            # UI theo mảng: data, replay, report, landing
└── shared/              # api-client.ts (server-only), format.ts, ui/ (primitives, sidebar)
```

## Quy tắc

1. Trang trong `app/` chỉ ghép; logic hiển thị nằm trong `features/<mảng>/`.
2. `shared/api-client.ts` chỉ gọi FastAPI từ server qua `SHOOTINGSTAR_API_URL`. Browser gọi các route `app/api/**`, không gọi backend trực tiếp.
3. Không tính lại metric hay công thức thống kê ở client. Format hiển thị (`shared/format.ts`) thì được.
4. Giao diện theo `docs/DESIGN.md`. Menu sidebar chỉ liệt kê trang có thật.
5. Kiểu dữ liệu API đặt ở `features/<mảng>/types.ts` (replay còn `external-types.ts`).
6. Phụ thuộc giữa các `features/*` hiện có: `replay` import kiểu từ `data/types` và hàm từ `report/*` (`labels`, `recent-reports`, `report-view`). Chưa có quy tắc cấm chéo; dùng chung nhiều chỗ thì chuyển lên `shared/`.

## Kiểm tra

`npm run typecheck` hoặc `npm run build` trong `frontend/`. Biến môi trường: `frontend/.env.example`.
