# Phase 01 — Chọn lịch sử và xem biểu đồ nến

**Trạng thái:** in-progress (đang triển khai, đã hoàn thành các milestone kỹ thuật cốt lõi; một số gate môi trường/benchmark thực tế còn mở). Xem [plan.md](plan.md). Phase này chỉ tạo bề mặt khám phá lịch sử, **không train, không dự đoán, không mô phỏng giao dịch**.

## Người dùng làm gì

**Ưu tiên UX mới:** Trình tự bắt buộc là **custom khoảng → preview → xác nhận nạp → lưu bản snapshot → chọn lại nhiều bản**. Preview là bước riêng, hiện **chưa có** trong luồng đang triển khai; không đánh dấu phase hoàn tất chỉ vì form nạp hoặc chart đã chạy.
- Chọn BTCUSDT Spot, `1m` hoặc `5m`; xem danh sách snapshot đã có (khoảng ngày, ngày nạp, nguồn, số nến, chất lượng, checksum). Chọn snapshot cũ không tải lại Binance; yêu cầu khoảng cụ thể mới (ví dụ 01/03–30/04/2024) mới thực hiện tác vụ nạp.
- Sau nạp, xem trạng thái đang lấy từng phần, thất bại/429/418, khoảng thiếu và bản dữ liệu có thể dùng hay không. Không hiển thị snapshot chưa hoàn chỉnh như đã xác minh. Nếu khoảng đã có, đề xuất dùng bản cũ; nếu thật sự nạp lại, tạo phiên bản snapshot mới, không ghi đè bản cũ.
- Mở snapshot: biểu đồ nến và khối lượng là chính; pan/zoom/chọn vùng thời gian; bật bảng OHLCV khi cần. Không tự nhận biểu đồ là giá mới nhất hoặc giá live. Nêu múi giờ đang hiển thị và nhãn nến `1m`/`5m`.
- Preview phải cho người dùng biết chính xác nội dung nào đang được xem (nến lấy từ snapshot sẵn có hay dữ liệu xem thử), khoảng UTC, số nến dự kiến/thực tế, khoảng thiếu và lỗi nếu đã kiểm tra. Không được ghi snapshot/ingestion run **chính thức** chỉ vì bấm Preview; cache tạm nếu cần phải có hạn dùng và không hiển thị như bản đã lưu. Sau Preview, nút **Nạp chính thức** mới tạo bản snapshot bất biến; danh sách cho chọn nhiều bản theo ID, khoảng ngày và trạng thái chất lượng. Nếu nguồn dữ liệu thay đổi giữa Preview và xác nhận, hiển thị lại phạm vi/nguồn và yêu cầu xác nhận thay vì lưu âm thầm bản khác.

## Backend và dữ liệu

- **BE:** `backend/shootingstar/api/ingestion_routes.py` đã có `POST /ingestion/jobs` (giới hạn **65 ngày**, 1 job chạy cùng lúc); bổ sung contract preview riêng chỉ đọc, cùng validation BTCUSDT/`1m`/`5m`, nến đã đóng, giới hạn số nến/weight. `backend/shootingstar/application/ingestion.py` và `adapters/binance.py` tái dùng logic lấy nến để preview một lô giới hạn **không gọi `execute_and_persist_ingestion`**. Preview trả khoảng yêu cầu, khoảng thực đã xem, nguồn, nến mẫu và trạng thái chất lượng theo phạm vi **thực sự kiểm tra**; không báo coverage toàn khoảng nếu chưa tải toàn khoảng. Trước khi xác nhận, kiểm tra input/preview còn hợp lệ; nạp chính thức qua job hiện có, trả snapshot ID/chất lượng. Nếu cần cache preview, chỉ lưu tạm không đăng ký snapshot/ingestion run.
- `backend/shootingstar/adapters/storage.py`, `api/read_routes.py`: giữ Parquet + metadata DB, đọc window bounded; kiểm tra integrity snapshot không được dựa **chỉ** vào size/mtime khi coi là bất biến; test thay file giữ metadata trước khi gọi gate đạt. API danh sách/quality/candles cần đủ snapshot ID/hash provenance cho FE. Không gửi hàng chục nghìn nến cho Preview hoặc một response chart.
- Phân biệt response rỗng thật, nến thiếu, Binance trả ít nến hơn yêu cầu, file hỏng, backend offline. Request nạp trùng idempotent hoặc tái sử dụng có chứng cứ; tránh tạo các snapshot không phân biệt được provenance.

## Frontend và hợp đồng

- `frontend/src/app/(work)/data/page.tsx`, `frontend/src/features/data/`: biểu đồ dưới nhãn **Lịch sử giá**; điều khiển chọn snapshot/khoảng ngày; thông báo trạng thái rõ. Giữ `docs/DESIGN.md` và tương tác nhẹ, mobile/touch/keyboard. Chọn thư viện biểu đồ phù hợp OHLCV/volume và giấy phép, xem xét UX giống **cách quan sát** Binance Spot chứ không sao chép thương hiệu/widget để tự nhận giá trực tiếp.
- API trả OHLCV theo cửa sổ UTC có thứ tự, snapshot ID/hash và biên nến; frontend **chỉ vẽ**. Biểu đồ có lỗ trống nếu thiếu nến; không vẽ nến giả bằng forward-fill. Hiển thị trạng thái “không có dữ liệu”, “nạp đang chạy”, “lỗi nạp”, “chưa kiểm tra chất lượng” khác nhau.

### File và bước triển khai cụ thể (plan, chưa code)

| Sửa/tạo | Trách nhiệm |
|---|---|
| Sửa `backend/shootingstar/api/ingestion_routes.py`, `backend/shootingstar/api/schemas.py` | Preview endpoint + response giới hạn và validation dùng chung với job nạp; xác nhận không chấp nhận preview cũ/input thay đổi. |
| Sửa `backend/shootingstar/application/ingestion.py`, `backend/shootingstar/adapters/binance.py` | Lấy nến xem thử có quota/timeout, không persist; reuse pipeline kiểm tra gap/provenance khi nạp chính thức. |
| Sửa `backend/shootingstar/api/read_routes.py`, `backend/shootingstar/adapters/storage.py` | Window và checksum an toàn, kèm ID/hash nguồn; giữ nguyên bản snapshot đã lưu. |
| Sửa `frontend/src/features/data/snapshot-downloader.tsx`, `frontend/src/app/(work)/data/page.tsx`, `frontend/src/features/data/candlestick-chart.tsx`, `frontend/src/features/data/types.ts` | Tách trạng thái **Chọn khoảng → Preview → Nạp → Chọn bản đã lưu**, vẽ mẫu nến và chất lượng/nguồn, vô hiệu xác nhận nếu đổi input; không lẫn preview với chart snapshot chính thức. |
| Thêm proxy theo convention `frontend/src/app/api/ingestion/preview/route.ts`; sửa `frontend/src/app/api/ingestion/jobs/route.ts` nếu contract đổi | Browser gọi Next server route rồi FastAPI, không gọi Binance trực tiếp. |
| Sửa `tests/test_storage_and_ingestion.py`, `tests/test_api_and_ui.py` | Chứng minh preview không ghi DB/snapshot, nạp sau xác nhận có bản riêng, lỗi và giới hạn không sinh bản hợp lệ. |

**Thứ tự:** xác định preview là lô mẫu hay xem trọn khoảng và giới hạn request → chốt contract preview → BE đọc-không-ghi → FE preview/confirm → nạp hai snapshot khác nhau → test DB/Parquet và browser. Không hứa preview lô mẫu là kiểm định hoàn chỉnh của toàn khoảng.

**Gate UX mới (chưa đạt):** Kiểm tra từ browser: chọn custom khoảng, Preview thấy dữ liệu/giới hạn và **không xuất hiện snapshot chính thức mới**; chỉ sau khi bấm Nạp chính thức mới xuất hiện bản mới; nạp khoảng thứ hai vẫn chọn được bản đầu, refresh vẫn giữ cả hai. Test lỗi preview, dữ liệu thiếu, preview cũ và nạp thất bại không tạo bản hoàn chỉnh.
## Kiểm thử và gate (chưa nghiệm thu)

- [ ] **Backend nạp lịch sử & phân trang:** Có `load_snapshot_window` và CLI bounded range; đã thêm test 418/429, nhưng **timeout chưa có test**. Cần test gap/range/quá lớn và kiểm chứng dữ liệu Binance thật. Route candles đang có checksum cache theo size/mtime: **chưa chứng minh bắt được thay file nhưng giữ metadata**, không đánh dấu integrity đạt; response `List[CandleDTO]` chưa bọc provenance snapshot/hash.
- [ ] **UI biểu đồ & bảng nến:** Có Canvas chart, pan bằng chuột, wheel zoom và touch handler trong mã; chưa browser smoke với dữ liệu thật/mobile để xác nhận hành vi. Proxy vẫn forward tham số chưa kiểm tra trước khi gửi backend; cần thử lỗi backend offline/snapshot chưa kiểm định. **Preview trước nạp chưa triển khai.**
- [ ] **Đo kích thước/tốc độ request 1m hai tháng trên máy local**: Chưa thực hiện đo đạc benchmark throughput/latency trên snapshot 2 tháng thật; gate này bắt buộc phải có số liệu đo đạc thực tế trước khi đánh dấu hoàn thành.
- [ ] **Cập nhật tài liệu & ghi nhận bằng chứng**: Đã cập nhật docs README về CLI và route. Chưa có output request/response được lưu trữ và ảnh chụp browser smoke live.
**Không làm trong Phase 01:** mô hình, tái huấn luyện, số dư ảo, P&L, WebSocket giá live, toàn bộ lịch sử Binance từ đầu tới nay.
