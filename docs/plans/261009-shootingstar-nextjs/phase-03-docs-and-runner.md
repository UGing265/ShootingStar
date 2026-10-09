# Docs & launcher — chạy Backend và Frontend

## Phạm vi

Chi tiết D1–D2 trong [`plan.md`](plan.md). Tài liệu được viết sau khi hai dịch vụ chạy được thật; giai đoạn lập kế hoạch **chưa tạo script**.

## Cấu trúc bàn giao

- `docs/backend/README.md`: Python/venv/PostgreSQL/.env/Alembic/FastAPI 8000 và lệnh smoke.
- `docs/frontend/README.md`: Node/`npm ci`/`web/.env.local`/Next 3000/build/typecheck/5 trang.
- `docs/local-run.md`: 2 terminal PowerShell + script một lệnh; start/stop và lỗi thông dụng.
- `docs/README.md`: mục lục Frontend / Backend / kiến trúc-API chung. README root trỏ về ba mục.
- `scripts/run-local.ps1`: khởi backend → health → frontend → browser; dọn đúng child processes.
- `.env.example` ở root hiện đã có; kiểm tra biến `SHOOTINGSTAR_DATABASE_URL` vẫn là placeholder. **Tạo mới** `web/.env.example` chỉ chứa `SHOOTINGSTAR_API_URL=http://127.0.0.1:8000`; ignore `web/.env.local`.

- [ ] Hoàn tất và kiểm tra cả hai template môi trường trước khi xuất bản hướng dẫn `Copy-Item`; không thay thế `.env` người dùng.

## Hướng dẫn sẽ kiểm chứng khi triển khai

Terminal A (repo root):

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }   # điền URL DB riêng; không commit
.venv\Scripts\python.exe -m pip install -e '.[dev]'
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\shootingstar.exe serve --host 127.0.0.1 --port 8000
```

Terminal B (repo root, sau khi backend `/health` hoạt động):

```powershell
Set-Location web
npm ci
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }   # chỉ URL API; không secret
npm run dev
```

Sau F1–F4: `http://127.0.0.1:8000/docs` là API; `http://127.0.0.1:3000` là Next; `/health` DB offline phải cảnh báo chứ không ghi Connected. Hai terminal dừng bằng `Ctrl+C`.

Một lệnh **dự kiến sau khi hoàn tất** `scripts/run-local.ps1`:

```powershell
powershell -NoProfile -File .\scripts\run-local.ps1
```

- [ ] Kiểm chứng script từ root/cwd khác, port bận, thiếu `.venv`/`node_modules`/`.env`, backend offline, Ctrl+C cleanup, không in secret. Nếu file chưa tồn tại thì **chưa thể chạy một lệnh**; không khuyên chạy lệnh đó ở hiện tại.
- [ ] README nêu rõ backend HTML `/` cũ không phải frontend Next; không yêu cầu Docker, không fetch Binance hoặc train model để chỉ mở UI (data views có thể rỗng).
