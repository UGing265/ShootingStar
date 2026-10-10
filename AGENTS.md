# AGENTS.md — ShootingStar Operating Guidelines & Engineering Standards

Tài liệu này là quy chuẩn bắt buộc dành cho AI Agents khi làm việc, lập kế hoạch và phát triển trong repository **ShootingStar**.

---

## 1. Tổng quan Dự án & Triết lý Cốt lõi (Core Principles)

- **Tên dự án:** ShootingStar
- **Bản chất:** Nền tảng nghiên cứu định lượng độc lập (**Evidence-first Research Platform**) dự đoán hướng giá BTCUSDT (Binance Spot) trong 30 phút tới, dùng nến `1m` hoặc `5m` theo cấu hình thí nghiệm; nghiên cứu probability calibration và rule-based Pattern Lab. `30m` là horizon dự đoán, không phải khung nến.
- **Nguyên tắc "Bằng chứng trước - Tốc độ sau" (Accuracy Before Speed):**
  - **Không bịa số liệu:** Tuyệt đối không giả lập metrics, không đưa ra kết quả ảo hoặc P&L mô phỏng thiếu cơ sở phí giao dịch / trượt giá (slippage).
  - **Chống rò rỉ dữ liệu (No Lookahead Leakage):** Dự báo tại thời điểm $t$ chỉ được phép sử dụng nến đã đóng có `available_at <= t`.
  - **Single Source of Truth:** Python/FastAPI và SQLite/PostgreSQL/Parquet là nguồn tính toán duy nhất. Frontend Next.js chỉ hiển thị và truy vấn dữ liệu thông qua API, không tự ý sao chép hay tính lại công thức thống kê ở client.
  - **Local-first:** Hệ thống phải chạy được độc lập trên môi trường cục bộ (Windows / Linux) trước khi cấu hình container hoá.

---

## 2. Kiến trúc & Phân chia Trách nhiệm (Tech Stack)

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy/Alembic, PostgreSQL hoặc SQLite theo `SHOOTINGSTAR_DATABASE_URL` (test dùng `SHOOTINGSTAR_TEST_DATABASE_URL`), Parquet cho snapshot; không có DB mặc định nếu thiếu biến môi trường.
- **Luồng nghiệp vụ:** `backend/shootingstar/cli/` (`argparse`) và `api/` (FastAPI read API) gọi `application/` (ingestion, features, labels, evaluation, experiments, patterns, signals). `domain/` giữ model/quy tắc; `adapters/` làm việc với Binance, file snapshot và SQLAlchemy DB. CLI `shootingstar --help` đăng ký qua `pyproject.toml`.
- **Frontend:** Next.js App Router, TypeScript, React và CSS tại `frontend/`; `src/app/` định tuyến/ghép trang, `src/features/` giữ UI theo mảng, `src/shared/api-client.ts` gọi FastAPI **chỉ ở server** qua `SHOOTINGSTAR_API_URL`. Browser không tính lại metric, đọc trực tiếp DB/Parquet hoặc gọi API với thông tin nội bộ.
- **Trạng thái sản phẩm:** Trang giới thiệu không trình bày chỉ số chưa kiểm chứng; các trang làm việc hiển thị dữ liệu thật/thiếu dữ liệu từ API. News/agents, paper trading, action policy `NO_TRADE` theo chi phí và P&L sau slippage chưa được coi là chức năng đã nghiệm thu.

---

## 3. Quy chuẩn Quản lý Kế hoạch & Tài liệu (Planning & Docs System)

### 3.1. Hệ thống Lập Kế hoạch (`docs/plans/`)
Mọi đầu việc lớn, phase nghiên cứu mới hoặc đợt tái cấu trúc **bắt buộc** có thư mục kế hoạch riêng trong `docs/plans/`:
- **Định dạng thư mục:** `docs/plans/<yymmdd>-<tên-kế-hoạch>/` (Ví dụ: `docs/plans/261009-shootingstar-nextjs/`).
- **Cấu trúc bên trong:**
  - `plan.md`: File tổng quan, mục tiêu (Goal), Invariants, Gate kiểm định, danh sách các phase và ranh giới trách nhiệm.
  - `phase-XX-<tên-phase>.md`: Chi tiết các bước thực hiện, files cần tạo/sửa, checklist nghiệm thu.
- **Nguyên tắc "Evidence-Based Completion":**
  - **Chỉ đánh dấu hoàn tất** khi đã có kết quả chạy thực tế (output lệnh CLI, kết quả `pytest`, build Next.js thành công).
  - Không tuyên bố hoàn thành trước khi chạy thử hoặc chỉ mới scaffold code rỗng.

### 3.2. Hệ thống Tài liệu Kỹ thuật (`docs/`)
- `docs/DESIGN.md`: Ngôn ngữ thiết kế trực quan (Light/Parchment palette, interactive blue, hairline border, shadow-free, typography chuẩn). Mọi UI Next.js bắt buộc tham chiếu file này.
- `docs/external-apis.md`: Sổ đăng ký tích hợp API bên ngoài (Binance Spot REST API, rate weights, headers, error handling).
- `docs/binance-spot-fees.md`: Quy chuẩn phí giao dịch VIP 0, Maker/Taker và slippage assumptions.
- `docs/backend/README.md`: Hướng dẫn cấu hình DB, chạy migration Alembic, biến môi trường và chạy test API.
- `docs/frontend/README.md`: Hướng dẫn cấu hình `frontend/`, Node.js, biến môi trường `SHOOTINGSTAR_API_URL` và kiến trúc `features/`.
- `docs/local-run.md`: Hướng dẫn khởi chạy song song Backend + Frontend cục bộ.

---

## 4. Quy tắc Bất di bất dịch dành cho AI Agents (Guardrails)

1. **Không che giấu sự thật (Honest Reporting):**
   - Nếu dữ liệu chưa có (chưa chạy ingestion hoặc signals chưa mature), hiển thị rõ trạng thái `Chưa có dữ liệu` / `Gated`. Tuyệt đối không tạo dữ liệu giả lập (mock data) đánh lừa người dùng trong production flow.
2. **Bảo mật & Phân quyền:**
   - Không làm lộ đường dẫn file nội bộ (`file_path`, `artifact_path`), thông tin mật hoặc chuỗi kết nối Database qua các endpoint public của API (như `/health`, `/snapshots`).
   - `frontend/.env.local` phải được git-ignore; `frontend/.env.example` chỉ chứa biến cấu hình công khai (`SHOOTINGSTAR_API_URL`).
3. **Kiểm thử trước khi bàn giao:**
   - Khi chỉnh sửa backend: Chạy `pytest backend/tests/test_api_and_ui.py` (hoặc test tương ứng) để xác nhận không vỡ contract.
   - Khi chỉnh sửa frontend: Chạy `npm run typecheck` hoặc `npm run build` trong `frontend/`.
4. **Git & Commit Hygenic:**
   - Commit dạng atomic, có prefix rõ ràng: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
   - Không tự ý commit hoặc push lên remote repository khi chưa có lệnh xác nhận từ người dùng.
5. **Phong cách giao tiếp:**
   - Tiếng Việt, ngắn gọn, gãy gọn, tập trung thẳng vào giải pháp kỹ thuật và kết quả kiểm chứng.
6. **Quy chuẩn Biểu đồ & Tương tác Chart (Charting Standards):**
   - Mọi biểu đồ nến / chart tương tác bắt buộc phải hỗ trợ các tương tác cơ bản:
     - **Cuộn chuột (Scroll / Wheel Up/Down):** Phóng to / thu nhỏ (Zoom in / Zoom out).
     - **Kéo giữ chuột trái (Click & Hold / Drag):** Trượt qua lại (Pan left / right) để duyệt dữ liệu.
     - **Click chọn mốc (Click Selection):** Phân biệt rõ thao tác kéo (drag) và nhấp chuột (click) bằng ngưỡng dịch chuyển chuột để không kích hoạt click ngoài ý muốn khi kéo.
   - **Múi giờ chuẩn:** Giao diện hiển thị người dùng và biểu đồ mặc định thống nhất theo **UTC+7** (Asia/Ho_Chi_Minh); Backend API, Database và Parquet lưu trữ gốc theo mốc chuẩn UTC / epoch millisecond.
