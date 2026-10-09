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
| `/research` | Kết quả thử nghiệm | Các lần thử phương pháp dự đoán trên dữ liệu lịch sử. |
| `/research/[id]` | Chi tiết thử nghiệm | Kết quả từng giai đoạn, đối chiếu và kiểm tra xác suất. |
| `/patterns` | Mẫu hình giá | Các quy tắc nhận diện mẫu nến đã đăng ký. |
| `/patterns/[id]` | Chi tiết mẫu hình | Những lần mẫu hình xuất hiện trong dữ liệu lịch sử và diễn biến sau đó. |
| `/signals` | Dự đoán | Những dự đoán đã ghi nhận cùng trạng thái chờ hoặc đã có kết quả. |
| `/signals/[id]` | Chi tiết dự đoán | Thông tin và kết quả của một dự đoán. |
| `/about` | Phương pháp | Cách hệ thống đánh giá và những giới hạn cần biết. |
