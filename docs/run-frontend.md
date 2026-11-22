# ShootingStar — Frontend (Next.js App Router)

The frontend is a multi-page research interface built on Next.js 16 (16.4.0) App Router, React 19 (19.3.0), and TypeScript, adhering to the evidence-first Apple design aesthetic (`docs/DESIGN.md`).

## 1. Prerequisites

- Node.js 20.9.0+ (tested with Node 24.15.0)
- npm 9+ (tested with npm 11.3.0)

## 2. Configuration

Set up environment variables in `frontend/.env.local`:

```powershell
Set-Location frontend
if (-not (Test-Path .env.local)) {
    Copy-Item .env.example .env.local
}
```

The file only contains the backend API URL (runs server-side in Next.js Server Components):

```ini
SHOOTINGSTAR_API_URL=http://127.0.0.1:8000
```

> **Security Invariant:** No database connection strings or secret keys are stored in `frontend/`. All data fetching is performed server-side via `shared/api-client.ts`, preventing CORS issues and credential leakage to the browser.

## 3. Installation & Development

```powershell
Set-Location frontend

# Install exact dependencies
npm ci

# Typecheck and linting
npm run typecheck

# Production build
npm run build

# Start development server on port 3000
npm run dev
```

Visit the application at: `http://127.0.0.1:3000`

## 4. Các trang làm việc

Các trang làm việc hiển thị kết quả đã lưu từ backend khi người dùng mở hoặc tải lại trang. Chúng không tự lấy nến mới, chạy thử nghiệm hay tạo dự đoán theo lịch; muốn có dữ liệu mới cần chạy quy trình backend tương ứng.

| Đường dẫn | Tên trên giao diện | Dùng để xem |
|---|---|---|
| `/` | Giới thiệu | Mục tiêu dự án và giới hạn hiện tại. |
| `/dashboard` | Tổng quan | Trạng thái kết nối và những bản ghi gần đây. |
| `/data` | Lịch sử giá | Các bộ nến BTCUSDT đã lưu, khoảng thời gian và tình trạng kiểm tra chất lượng; không phải bảng giá trực tiếp. |
| `/replay` | Mô phỏng | Quay lại một thời điểm trong quá khứ, xem phân tích chỉ từ nến đã đóng, dự đoán rồi đối chiếu với diễn biến thật. |
| `/report` | Báo cáo | Danh sách báo cáo Gemini và chi tiết một báo cáo: nhận định hướng giá, lập luận, nguồn tài liệu và kết quả đối chiếu. |
| `/about` | Phương pháp | Cách hệ thống đánh giá và những giới hạn cần biết. |

## 5. Cấu trúc Route Handlers & Components Nổi bật

### 5.1 Route Handler `/api/snapshots/[id]/candles`
- Tuyến đường Next.js server-side (`src/app/api/snapshots/[id]/candles/route.ts`) đóng vai trò proxy bảo mật chuyển tiếp yêu cầu từ trình duyệt đến backend FastAPI `/snapshots/{id}/candles`.
- Nhận các query parameters: `start_ms`, `end_ms`, và `limit` (mặc định 500).
- Ngăn chặn lộ địa chỉ nội bộ backend và hạn chế vấn đề CORS khi client tương tác với dữ liệu nến.

### 5.2 Thành phần biểu đồ nến `CandlestickChart`
- Nằm tại `src/features/data/candlestick-chart.tsx`, dựng biểu đồ nến tương tác thuần Canvas (zero heavy charting dependencies).
- Hỗ trợ pan kéo thả chuột, phóng to/thu nhỏ (zoom), tooltip hiển thị chỉ số OHLCV khi hover, bảng chi tiết nến và công cụ nhảy nhanh theo khoảng thời gian (`start_ms` / `end_ms`).
- Tích hợp trực tiếp trên trang `/data` để hiển thị trực quan các bộ nến Parquet đã đăng ký.

## 6. Playwright E2E

From `frontend/`, install Chromium and set `E2E_SNAPSHOT_ID` to an existing snapshot ID:

```powershell
npx playwright install chromium
$env:E2E_SNAPSHOT_ID = "<snapshot-id>"
npm run e2e
```

Tests start the backend using `backend/.venv/Scripts/python.exe` on port 8100 and the frontend on port 3100. Both ports must be free. The backend uses the main database configured in the repository `.env`; tests may create jobs in that database. No test database or migration is created.

During an E2E run, Next.js temporarily points `next-env.d.ts` at `.next-e2e`. Do not run `tsc` or rely on frontend editor diagnostics until the run finishes.

If the shell has `SHOOTINGSTAR_ADMIN_KEY` set, it must match the repository `.env`. Remove the shell variable if preflight reports a mismatch. Preflight never prints its value.

The default run excludes `@real-gemini` tests. To run only those tests manually, with real Gemini quota:

```powershell
npm run e2e:gemini
```
