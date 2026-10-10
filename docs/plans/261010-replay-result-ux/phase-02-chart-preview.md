# Phase 02 — Preview biểu đồ và đối chiếu

## Context và trạng thái

[Plan tổng](plan.md), [Nhận định dễ đọc](phase-01-readable-analysis.md), [Tự mở kết quả](phase-03-auto-result.md). **Pending; chưa tạo component.**

## Quyết định

Tách renderer Canvas đang có trong Replay thành **một component dùng chung cho bước 1, 2 và 4**. Không copy thêm một renderer kết quả; không đưa công thức metric/đúng-sai vào chart.

Dùng `replay-chart.tsx` ở cùng feature Replay. `CandlestickChart` của `/data` có điều hướng/range selector gắn snapshot, không phù hợp để nhúng nguyên vào một job bất biến. Giữ nguyên chart `/data`, tái dùng cơ chế vẽ/tương tác hiện có của Replay.

## Người dùng nhìn thấy

### Bước 2 — “Biểu đồ trước thời điểm mua”

- Khung gồm lịch sử 6 giờ trước mua và vùng dự đoán từ **mốc mua t tới t + 30 phút** (nhánh nội bộ dùng horizon của job). Tô rõ ranh giới/vùng chọn tại t, chấm giá mua P và đường ngang giá mua; highlight nến AI nhắc tới ở phần quá khứ.
- **Che phần đồ thị từ t trở về sau theo trục thời gian**, không che theo mức giá P. Vùng bên phải vẫn chiếm chỗ trên chart, phủ nền trung tính và nhãn “Vùng dự đoán — chưa mở”; có mốc “+30 phút” nhưng không có giá/nến/khối lượng kết quả. Điểm mua (t, P) và nhãn tại ranh giới vẫn nhìn thấy.
- Chỉ truyền nến quá khứ hợp lệ vào chart bước 2. Không tải nến tương lai rồi chỉ phủ CSS/canvas lên: tooltip, click, DOM, bảng chi tiết, pan/zoom và tự động scale trục giá cũng không được lộ giá tương lai. Không nối đường giả qua vùng che hoặc vẽ nến phỏng đoán.
- Có khối lượng bên dưới nến quá khứ để đối chiếu lời AI. Hover/click xem thời gian, giá mở cửa/cao nhất/thấp nhất/đóng cửa và khối lượng; vùng bị che không có tooltip giá. Mỗi nến tóm tắt giá trong một khoảng thời gian (`1m` hoặc `5m`).
- Caption rõ “Chỉ thấy quá khứ; vùng sau điểm mua chưa mở”. Không marker đúng/sai hoặc giá kết quả.
- Với context B: chart cho xem lịch sử 6 giờ; nhãn rõ model nhận tóm tắt và một số nến cuối, không tuyên bố đã gửi toàn bộ nến chart.

### Bước 4 — “Giá thực tế sau dự đoán”

- Giữ cùng khung thời gian mặc định với bước 2 để nhìn thấy vùng nào vừa được mở, có cả mốc mua và mốc kết quả; không nhảy về cuối snapshot. Nếu nến tham chiếu thực tế nằm ngoài khung, mở rộng vừa đủ và ghi rõ thời gian đóng nến.
- Khi đủ dữ liệu và backend cho phép reveal: bỏ lớp che, vẽ nến thật cùng snapshot và **highlight toàn đoạn từ t tới t + 30 phút**. Tô vùng chọn tại t, chấm mua (t, P), đánh dấu mốc +30 phút và **điểm giá đóng cửa của nến backend dùng chấm**. Giữ phân biệt mốc horizon với thời gian đóng nến, không giả chúng trùng nhau.
- Phần đọc chính ghi riêng **Mốc kết thúc dự đoán**, **Giá đóng cửa dùng đối chiếu**, **Nến này đóng lúc**. Hai mốc có thể khác nhau; không giấu khác biệt trong chi tiết kỹ thuật.
- Phần trước mua và sau mua được phân biệt bằng đường mốc/caption, không che nến.
- UTC+7 thống nhất; legend rõ giá mua giả định và giá đóng cửa dùng đối chiếu.
- `PENDING`/`UNSCORABLE` hoặc reveal lỗi: giữ vùng sau mua ở trạng thái chưa mở/không có kết quả hợp lệ, vẫn thấy điểm mua và mốc horizon đã biết. Không vẽ giá kết quả giả, không tạo điểm thị trường; nói rõ nến thiếu/chưa đủ điều kiện.

## Contract component dự kiến

```typescript
interface ReplayChartProps {
  candles: CandleDTO[];
  phase: 'selection' | 'analysis' | 'result'; // Analysis luôn che tương lai; result chỉ mở khi backend cho phép.
  buyTimeMs: number;
  buyPrice: number;
  targetTimeMs?: number; // Mốc t + horizon, không giả là thời gian đóng nến.
  targetPrice?: number | null; // Giá backend đã dùng đối chiếu.
  targetCandleCloseMs?: number | null; // Bắt buộc có cho kết quả mới đã đánh giá; null nếu bản cũ thiếu metadata.
  evidenceTimes?: number[];
  onSelect?: (candle: CandleDTO) => void;
  showAll?: boolean;
}
```

`onSelect` chỉ ở bước 1. Click ở bước 2/4 đọc nến đã được phép hiển thị, không thay job. `showAll` khởi tạo khung bao gồm cả lịch sử và vùng thời gian dự đoán chưa mở, **không chỉ fit nến quá khứ rồi làm mất vùng che**. Parent truyền `targetTimeMs = t + horizon` ngay ở bước 2 vì mốc thời gian này đã biết, nhưng không truyền targetPrice/targetCandleCloseMs hoặc nến tương lai trước reveal. Trục giá bước 2 chỉ dựa trên nến quá khứ và giá mua. Zoom/pan giữ lớp che đúng tọa độ thời gian; không reveal do tương tác.

Parent chọn `phase='result'` chỉ khi outcome đã đánh giá và dữ liệu biểu đồ được phép mở. Bước 4 đang loading/PENDING/UNSCORABLE/lỗi vẫn dùng trạng thái che như analysis; không chọn chế độ mở chỉ vì `activeTab === 'step4'`.

## File thay đổi khi triển khai

- **Tạo:** `frontend/src/features/replay/replay-chart.tsx` — renderer/tương tác tách từ Replay hiện có.
- **Sửa:** `frontend/src/features/replay/replay-player.tsx` — bỏ renderer trùng; truyền props; tải cửa sổ nến của job bằng proxy có sẵn.
- **Sửa contract/mapping bắt buộc:** `backend/shootingstar/application/external_analysis/contracts.py`, `service.py`, `backend/shootingstar/application/replay.py`, `backend/shootingstar/api/schemas.py`, `backend/shootingstar/api/replay_routes.py` (đặc biệt `_to_job_response`); `frontend/src/features/replay/external-types.ts`, `types.ts`. Truyền bounds preview và timestamp nến backend thật sự chọn qua toàn đường lưu/đọc/API; phải tìm references trước khi đổi exported symbols.
- **Lưu metadata external mới:** `backend/shootingstar/adapters/db/models.py` và một Alembic revision trong `backend/alembic/versions/` sinh bằng `alembic revision -m "persist replay preview metadata"`; ba cột nullable được mô tả bên dưới. Không backfill job cũ bằng dữ liệu tự đoán.
- **Giữ nguyên endpoint:** chart `/data`, proxy `/api/snapshots/[id]/candles` và read API; dùng bounded candle API hiện có, không tạo endpoint context mới hoặc công khai payload model.

### Metadata backend-owned chốt

- `context_start_open_time_ms` và `context_end_close_time_ms`: lấy từ nến đầu/cuối của chính `window_candles = extract_causal_window(...)` đã dùng khi tạo job external. Lưu cùng job mới, trả qua DTO; không cho browser dựng lại latency hoặc suy bounds từ evidence nến cuối. Bản B có cùng cửa sổ nguồn nhưng chỉ gửi tóm tắt/tail như nhãn đã nêu.
- `target_candle_close_time_ms`: lấy từ nến backend đã chọn khi đánh giá; **bắt buộc có cho outcome mới UP/DOWN/FLAT hoặc local EVALUATED**. Không dùng `outcome_evaluated_at_ms` hay `horizon_time_ms` thay timestamp nến.
- External lưu các trường nullable riêng trong DB; local bổ sung timestamp nến vào outcome persisted hiện có và cập nhật cả đường deserialize, schema và `_to_job_response`. GET trước reveal luôn ẩn timestamp/giá nến kết quả.
- Job cũ thiếu metadata: giữ null, nhãn rõ “Bản cũ không lưu thời gian nến tham chiếu/cửa sổ AI”. Có thể xem lịch sử trước mua theo bounds an toàn **do backend trả** nhưng không gọi đó là payload gốc; không đoán vị trí marker giá kết quả, không chấm lại outcome hoặc gọi Gemini. Tái dựng bounds preview cũ chỉ bằng extractor tại backend theo phiên bản/giả định xác định; nếu không xác định thì báo thiếu metadata thay vì hứa preview chính xác.
- Không đổi rationale/prompt/score đã lưu để lấp thiếu metadata. Migration chỉ thêm cột nullable, giữ nguyên dữ liệu cũ.

## Tải cửa sổ theo job

1. Khóa nguồn từ `job.snapshot_id`, thời điểm mua, giá mua, timeframe và horizon của job. Form bước 1 không được thay nguồn chart của job đang xem.
2. Preview AI dùng `context_start_open_time_ms`/`context_end_close_time_ms` của job để query nến. Source hiện nhận `close_time_ms + 1000 <= t` và neo 6 giờ vào nến hợp lệ cuối (`context.py:14–65`), **không phải cứ query `[t-6h,t]`**. `limit=1500` đủ khoảng 360/72 nến. Client không tính lại availability; nếu thiếu bounds, làm theo quy tắc job cũ phía trên.
3. Kết quả chỉ tải đoạn sau mua khi vote đã khóa và backend trả kết quả đã đánh giá. Giữ cửa sổ lịch sử bước 2 làm mặc định, thêm vùng tới mốc horizon và `target_candle_close_time_ms` để so trước/sau trên cùng khung; không tự rút lịch sử xuống 30 phút khi sang kết quả. Horizon nội bộ dài có thể vượt 1500 nến: chia cửa sổ thời gian không chồng nến, ghép theo open time, không cắt mất mốc cuối hoặc đổi horizon.
4. Storage lọc `open_time_ms >= start_ms` và `close_time_ms <= end_ms` (`adapters/storage.py:200–212`). Truyền bounds backend đã chốt; không dùng query end=t như bảo chứng cửa sổ đúng payload AI. Không gọi preview là payload gốc nếu không có metadata chứng minh.
5. Mỗi response nến gắn job ID + kiểu chart/cửa sổ. Hủy/bỏ response cũ khi đổi job hoặc tab; không hiển thị chart job trước trong khung job mới.
6. Loading/error/empty hiện riêng. “Thử tải lại biểu đồ” chỉ tải nến; không gọi Gemini, vote hoặc reveal.

## Tương tác và thời gian

- Wheel zoom, giữ trái pan, di chuyển >3px tính là drag và không gọi onSelect; kể cả thả chuột ngoài canvas.
- Nút phóng to/thu nhỏ/đặt lại có tên tiếng Việt; giới hạn view đúng cả khi <15 nến.
- Mỗi instance gắn wheel listener khi canvas mount và tháo khi unmount; redraw sau đổi tab/resize theo kích thước thật và device pixel ratio.
- Marker mua dùng **thời điểm yêu cầu**, không quy tắc gần timestamp ±60 giây của renderer cũ. Giữa nến/gap phải vẫn định vị đúng trục thời gian; không đặt dấu trên nến lân cận như đã mua ở đó.
- Mốc t+horizon và thời gian đóng nến tham chiếu có thể khác nhau. Label không gọi giá đóng nến là “giá chính xác tại giây mua/giây kết thúc”. Không thay thuật toán chọn nến của backend trong phase chart.
- Giá mua/giá tham chiếu có thể nằm ngoài high/low hiển thị; trục giá phải chứa markers. Không làm biến mất giá nhập thủ công.

## Checklist và nghiệm thu

- [ ] Renderer hiện có được tách, không còn bản trùng trong parent.
- [ ] Bước 2 có nến/khối lượng/evidence trước t và không có tương lai.
- [ ] Bước 2 có vùng thời gian t → t+horizon được che, điểm mua vẫn thấy; nến/volume/tooltip/scale không lộ tương lai khi zoom/pan/resize.
- [ ] Bước 4 fit mua–kết quả đúng snapshot/job và dùng giá backend.
- [ ] Bước 4 tự mở vùng đã che khi đủ dữ liệu, highlight đoạn 30 phút và đánh dấu cả điểm mua lẫn điểm kết quả; mốc horizon và thời gian nến tham chiếu được phân biệt.
- [ ] Bounds preview lấy từ context backend; timestamp nến kết quả đi qua persist/deserialize/schema/`_to_job_response`. Job cũ thiếu metadata có nhãn thật và không marker suy đoán.
- [ ] Click/drag/zoom/resize/đổi tab hoạt động; thao tác ở bước 2/4 không đổi mua/vote.
- [ ] Tải nến lỗi có thử lại riêng; empty/gap không được lấp giá giả.
- [ ] Kiểm ranh giới timestamp giữa nến, cuối snapshot, giá ngoài range, 1m/5m và horizon nội bộ dài.

## Rủi ro

Chart đẹp nhưng lấy nhầm đoạn nến vẫn sai UX. Gate chính là **đúng job, đúng cửa sổ, đúng mốc tham chiếu**, không phải chỉ có canvas không trắng. Không quảng cáo đây là chart giá trực tiếp hoặc bằng chứng model đúng.
