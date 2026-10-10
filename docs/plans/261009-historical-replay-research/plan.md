---
title: "Preview snapshot và mô phỏng dự đoán BTCUSDT"
description: "Preview rồi lưu snapshot; mô phỏng AI dự báo trước, người chọn UP/DOWN sau, lưu và chấm hai kết quả riêng."
status: in-progress
priority: P1
tags: [research, data, frontend, backend, replay]
blockedBy: [261010-replay-result-ux]
blocks: []
created: 2026-10-09
---
# Kế hoạch preview snapshot và mô phỏng dự đoán

> **IN-PROGRESS: Phase 01 thiếu preview; mô phỏng AI + người chưa nghiệm thu.** UX chính do người dùng xác nhận ngày 2026-10-09: preview → nạp snapshot → đánh dấu điểm mua → job AI → người chọn UP/DOWN (lưu/chấm riêng, **không mù** vì thấy AI trước) → chấm cả hai khi có giá thực tế. Không ép nghiên cứu so cửa sổ học 1/3/6/9 tháng; tua từng nến không phải luồng chính.

**Cập nhật UX 2026-10-10 — đang chờ plan [Replay dễ đọc và kết quả tự mở](../261010-replay-result-ux/plan.md):** Phase 03 chưa thể nghiệm thu trước khi nhận định AI dễ hiểu, có preview biểu đồ ở nhận định/kết quả và lưu lựa chọn bước 3 xong tự mở bước 4. Chỉ dẫn cũ bên dưới yêu cầu bấm riêng “Xem kết quả” đã được thay; backend vẫn khóa vote và kiểm đủ nến trước reveal. Quan hệ blocked chỉ áp gate UX Phase 03, không dừng ingestion/model research; chưa triển khai trong lượt lập kế hoạch này.

## Mục tiêu và lời hứa trung thực

Người dùng chọn BTCUSDT Spot, nến `1m` hoặc `5m`, khoảng lịch sử tùy chỉnh; xem Preview trước khi nạp chính thức, lưu nhiều snapshot có thể chọn lại. Ở khu mô phỏng, chọn snapshot, mốc ngày/giờ, giá BTC và horizon từ 30 phút tới tối đa một ngày; biểu đồ đặt **dấu chấm tại thời điểm/giá chọn** và **đường ngang giá đã nhập**. Job AI dự báo UP/DOWN, xác suất và bằng chứng/giới hạn giải thích; người dùng chọn UP/DOWN sau đó. Hai lựa chọn được lưu và chấm riêng, **không độc lập về thông tin**. Chưa có số liệu chứng minh độ chính xác. Ý nghĩa giá nhập và mốc so sánh phải chốt trước khi code.

**Không phải** streaming giá hiện tại, tư vấn mua bán, giả lập khớp lệnh, ví tiền thật/ảo, giao dịch thật, P&L, hay chứng nhận model có edge. Khoản tiền ảo đã được nhắc khi brainstorm nhưng **chưa được chốt** là chức năng bước này; tách riêng khỏi replay dự đoán. Không có nút đẹp nhưng không chạy pipeline thật.
### Luồng chính tách tab

1. **Lịch sử / Preview:** custom khung ngày/giờ → Preview nến/khoảng/phạm vi thiếu và nguồn → xác nhận **Nạp chính thức** mới lưu snapshot bất biến; chọn lại được nhiều bản. Preview không âm thầm ghi bản nạp chính thức vào DB.
2. **Mô phỏng / Điểm mua:** chọn snapshot; **chạm/click biểu đồ chọn mốc mua** (lấy thời gian và giá quan sát tại điểm được chọn) **hoặc nhập ngày/giờ và giá thủ công**; cả hai cách tạo cùng một đầu vào `(t, giá mua giả định)`, cho xem/chỉnh trước khi chạy. Chọn thời lượng dự đoán trong khoảng 30 phút–tối đa 1 ngày bằng mốc chọn hoặc nhập thời lượng hợp lệ. Chart vẽ chấm tại `(t, giá)` và đường ngang giá mua; nếu giá thủ công lệch giá nến thì hiển thị cả hai, không tự sửa. Đây là mốc giả định, không phải lệnh đã khớp.
3. **Mô phỏng / Dự báo:** bấm chạy job; **AI nhận thời điểm `t`, giá mua giả định, horizon và các nến lịch sử đã đóng/khả dụng tới `t`**; không nhận nến sau `t`. Job hiện đang chạy/lỗi/hoàn tất. Chỉ model được huấn luyện/kiểm định cho mục tiêu **giá sau horizon so với giá mua đầu vào** mới được trả UP/DOWN và xác suất; bằng chứng/giới hạn giải thích phải có thật. Sau đó người dùng chọn UP/DOWN; lưu hai bản ghi riêng, không dùng lựa chọn người để đổi dự báo AI vừa đưa.
4. **Mô phỏng / Kết quả:** sau khi đã khóa dự báo AI và lựa chọn người, người dùng bấm **“Xem kết quả”**; backend chỉ mở giá/nến tương lai khi đã đủ nến đóng hợp lệ tới horizon. Chấm AI và người đúng/sai **riêng**, cùng so với **giá mua giả định đã nhập**; chưa đủ thì `PENDING`, nến hỏng/thiếu thì `UNSCORABLE`. Lưu ID snapshot, model, thời gian, horizon, giá mốc và phiên bản. Người dùng thấy AI trước nên đây không phải đánh giá người dự đoán mù.
5. **Học từ thị trường — phương án B người dùng chốt:** lưu kết quả thị trường làm dữ liệu để **huấn luyện lại phiên bản model về sau**, theo lịch/cutoff và kiểm tra ngoài mẫu; **không học theo nút UP/DOWN của người dùng**, không sửa model hoặc xác suất của job đã xong, không học ngay từ kỳ test vừa dùng để tự tuyên bố kết quả. Chưa cam kết model mới sẽ tốt hơn.

**Đã chốt (2026-10-09):** Chọn điểm mua **trên biểu đồ hoặc nhập ngày/giờ và giá** đều được; thời điểm mua `t` và giá mua giả định **là đầu vào AI** cùng với lịch sử nến chỉ đến `t`. Giá mua cũng là mốc để chấm UP/DOWN so với giá sau horizon, **không chứng minh đã khớp lệnh**. Horizon có thể chọn mốc hoặc nhập giá trị trong khoảng 30 phút–tối đa 1 ngày; chỉ mở kết quả sau khi khóa AI, người chọn UP/DOWN và bấm **“Xem kết quả”**. Model hiện tại nếu chưa học/kiểm định với giá mua đầu vào và horizon tương ứng thì không được dùng để dựng phần trăm. Còn cần xác định quy tắc chọn nến khi click/đến `t+horizon`, bước mốc hợp lệ và timezone; không hỏi lại các quyết định UX đã chốt.

### UX đi chính và các trạng thái

| Bước/tab | Hành động chính | Nhìn thấy / không nhìn thấy |
|---|---|---|
| **Lịch sử → Preview** | Chọn BTCUSDT, `1m`/`5m`, bắt đầu/kết thúc; bấm Preview | Xem mẫu nến, khoảng, nguồn, số lượng/độ phủ nếu đã kiểm chứng; lỗi/429/418, trùng bản lưu. **Chưa có snapshot mới**. Đổi input thì preview cũ hết hiệu lực. |
| **Lịch sử → Lưu snapshot** | Xác nhận “Nạp chính thức”, xem tiến độ, sau khi thành công chọn bản đã lưu | Danh sách nhiều snapshot có ID/khoảng/khung/chất lượng; refresh vẫn còn. Lỗi nạp không hiện bản chưa hoàn chỉnh như bản đạt chuẩn. |
| **Mô phỏng → Điểm mua** | Chọn snapshot; click/chạm chart để chọn mốc mua **hoặc** nhập thời gian và giá; chọn mốc horizon hoặc nhập giá trị hợp lệ | Một cặp `t`/giá thống nhất, chấm tại điểm mua và đường ngang giá; có thể chỉnh trước job. Giá nến quan sát được hiển thị riêng nếu nhập giá khác; chưa hiện outcome tương lai. |
| **Mô phỏng → AI dự báo** | Bấm chạy job, xem trạng thái và kết quả | Có model hợp lệ: UP/DOWN, xác suất, version/cutoff và **bằng chứng model thực sự cung cấp**; không có: lý do rõ, không fake phần trăm/lời giải thích. Chưa hiện đúng/sai. |
| **Mô phỏng → Dự đoán của tôi** | Sau khi xem AI, chọn UP hoặc DOWN rồi khóa lựa chọn | AI không đổi; lựa chọn người lưu riêng. Vì thấy AI trước nên chỉ so hai bản ghi, **không báo con người dự đoán mù/độc lập**. |
| **Mô phỏng → Kết quả** | Khóa lựa chọn người, bấm **“Xem kết quả”** | Nếu đủ nến: giá sau horizon so với giá mua giả định đã nhập, hai dòng đúng/sai riêng; chưa đủ: `PENDING`/`UNSCORABLE`. Chưa bấm thì không mở outcome trên tab này; refresh không đổi bản AI/người đã khóa. |

**Điều hướng:** Lịch sử giá (`/data`) dành cho preview/nạp/danh sách; một khu Mô phỏng (`/replay` hiện có, đổi tên/điều hướng) chứa 4 tab Điểm mua → AI dự báo → Dự đoán của tôi → Kết quả. Tab sau bị khóa cho tới khi đủ điều kiện, có thông báo lý do và đường quay lại; mobile xếp theo bước dọc, bàn phím vào tab và nút được. Tham chiếu `docs/DESIGN.md` cho palette/chữ/tương tác.

### BE/FE cần sửa — định hướng, chưa triển khai

| Luồng | Backend (nguồn sự thật) | Frontend (giao diện) |
|---|---|---|
| Preview → nạp | API preview bounded, **không ghi snapshot chính thức**; backend giữ/đối chiếu nguồn preview trước khi xác nhận hoặc báo hết hạn; reuse ingestion job hiện có khi xác nhận; danh sách snapshot/quality. Chặn khoảng >65 ngày theo giới hạn hiện tại hoặc trả lỗi rõ, không tự tăng hạn. | Form `/data` gọi preview rồi mới bật “Nạp chính thức”; hiển thị nến mẫu/độ phủ có nguồn gốc, trạng thái job, danh sách nhiều bản; input đổi thì bỏ preview. |
| Chọn điểm → AI | Kiểm tra snapshot hash/mốc giá/giờ/horizon, artifact cutoff trước mốc và horizon khớp; tạo job, lưu dự báo bất biến, trạng thái/lý do, chỉ trả bằng chứng hiện có. | Chart marker + đường giá, form và trạng thái job/poll; không tính nhãn/xác suất ở browser. |
| Người chọn → Kết quả | Lưu lựa chọn người một lần, tính nhãn thị trường khi đủ nến đóng, chấm AI/người riêng, giữ outcome/version; lịch sử job qua refresh; dữ liệu thị trường trưởng thành dùng cho **chu kỳ train model mới** sau này. | Tab dự đoán UP/DOWN, khóa sau gửi; tab Kết quả chỉ hiển thị payload backend, trạng thái thiếu nến và bằng chứng model. |

**Cutover:** Repo **đã có** `application/replay.py`, `api/replay_routes.py`, `frontend/src/features/replay/replay-player.tsx` và `/replay` cho tua từng nến 30m; đó **không phải** job người dùng yêu cầu. Khi triển khai, thay/migrate các callsite/route và bỏ luồng tua cũ khỏi điều hướng chính, không giữ API mồ côi hay quảng cáo là mô phỏng đã làm xong. Mã nguồn và test hiện có chưa được đổi trong lần viết plan này.

## Hiện trạng đã kiểm tra (2026-10-09)

| Mảng | Có trong repo | Chưa có / giới hạn |
|---|---|---|
| Lấy nến | Ingestion nhận khoảng bắt đầu/kết thúc; CLI `fetch-history`, backend job và UI nạp đã có | **Chưa có Preview trước khi tạo snapshot chính thức**; chưa nghiệm thu dataset thật theo khoảng tùy chọn |
| Lưu/xem | Snapshot Parquet + DB metadata; API đọc nến có lọc cửa sổ; Canvas chart có handler pan/wheel/touch | Response chưa kèm snapshot/hash, integrity cache theo size/mtime chưa kiểm chứng thay file giữ metadata, benchmark và browser smoke chưa có |
| Học/đánh giá | `ExperimentRunner` và split tuần tự/purge hiện có | Chưa có model được xác minh cutoff/horizon phù hợp cho job mô phỏng, chưa có chu kỳ huấn luyện lại bằng kết quả thị trường |
| Dự đoán | `modeling.py` có artifact và probability; `signals.py` có record | Chưa có job AI theo điểm mua, hai bản ghi AI/người riêng hay chấm riêng đúng/sai |
| Giao diện | `/data`, `/research`, `/signals` cùng chart đọc API | Chưa có các tab Điểm mua / Dự báo AI / Dự đoán của tôi / Kết quả |

## Nghiên cứu nguồn ngoài: dùng đúng phạm vi

- Nguồn lưu theo yêu cầu ở `link.txt`: [Bysik & Ślepaczuk, *Machine Learning-Based Bitcoin Trading Under Transaction Costs*, arXiv:2606.00060v1](https://arxiv.org/html/2606.00060v1). Nghiên cứu dùng **BTC/USDT futures, nến 1 giờ, dự đoán lợi suất giờ tới**, chia rolling **12 tháng học / 3 tháng chọn / 3 tháng kiểm tra**, có giả định chi phí giao dịch. **Không** phải bằng chứng nên dùng 12 tháng, XGBoost, tỷ lệ thắng hay P&L tương tự cho **Spot 1m/5m, horizon 30 phút** của ShootingStar. Paper thay thế nến thiếu bằng giá đóng cửa cũ: **không sao chép** vì plan này cấm tự lấp khoảng thiếu mà không công khai tác động.
- [Binance Spot REST API, `GET /api/v3/klines`](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#klinecandlestick-data): hỗ trợ `startTime`, `endTime` và trả nến từng trang có giới hạn; cần tôn trọng giới hạn request, xử lý 429/418, chỉ lấy nến đã đóng. Đây là nguồn khả thi cho các khoảng được chọn, không buộc tải toàn bộ lịch sử trước.
- So sánh cửa sổ học nhiều tháng không thuộc luồng chính hiện tại. 65 ngày dữ liệu không đủ kiểm định cửa sổ 3/6/9 tháng; Phase 02 chỉ cần một quy trình huấn luyện/kiểm tra hợp lệ với dữ liệu đủ điều kiện cho từng horizon đã chốt, không dựng phần trăm hoặc tuyên bố model có lợi thế khi chưa thử ngoài mẫu.

## Quyết định kiến trúc tạm chốt cho bước 1

1. **Preview trước nạp, tái sử dụng snapshot.** Không nhập toàn bộ lịch sử vào DB hay tải hàng triệu nến mỗi lần mở trang. DB chỉ ghi bản nạp chính thức sau xác nhận; nến nằm trong snapshot bất biến, metadata/index trong DB. Khoảng học trước mốc mô phỏng và đoạn dùng để chấm phải được phân biệt bằng cutoff, ID/hash.
2. **Biểu đồ làm bề mặt chính.** Backend trả nến theo cửa sổ; frontend chỉ vẽ OHLCV, marker và đường giá người nhập, không tự tính nhãn/xác suất/P&L. Không forward-fill khoảng thiếu hoặc giả vờ chart giá live.
3. **Khóa model trước job.** Chọn phiên bản artifact có cutoff học/chọn cấu hình trước mốc mô phỏng và đúng horizon đã kiểm định; không dùng cùng kỳ đang chấm để chọn model rồi tuyên bố thắng. Nếu chưa có model hợp lệ, báo không thể dự báo; vẫn cho xem snapshot và điểm đánh dấu.
4. **Job và chấm điểm tại backend.** Input snapshot ID/hash, điểm thời gian, giá nhập, horizon; lưu AI prediction/version trước khi lưu lựa chọn UP/DOWN của người. Dữ liệu model được phép dùng có `available_at <= t`; outcome chỉ mở khi có dữ liệu đóng đến `t+horizon`. Bản ghi người không đi vào dữ liệu train; kết quả thị trường chỉ được dùng ở chu kỳ huấn luyện phiên bản mới sau đó. Tua nến từng bước hoãn, không phải gate UX này.
5. **Không suy ra giao dịch.** Chỉ ghi điểm mua giả định, dự đoán và đúng/sai khi chốt mốc so sánh; không mô phỏng khớp, ví, phí, trượt giá hay P&L.

## Thứ tự giao hàng và chứng cứ

| Phase | File | Trạng thái & Phân công nhiệm vụ |
|---|---|---|
| 01. Preview/nạp/lưu lịch sử | [phase-01-history-and-chart.md](phase-01-history-and-chart.md) | **In-progress**: thiếu preview trước nạp, gate dữ liệu thật/benchmark/browser. |
| 02. Model có cutoff và đánh giá ngoài mẫu | [phase-02-model-window-research.md](phase-02-model-window-research.md) | **Chưa nghiệm thu**: bỏ so 1/3/6/9 tháng bắt buộc; học từ kết quả thị trường trong phiên bản model sau, không học từ người. |
| 03. Mô phỏng AI + người, chấm riêng | [phase-03-causal-replay.md](phase-03-causal-replay.md) | **Chưa nghiệm thu**: điểm chấm/đường giá, job, lựa chọn người, outcome; tua từng nến hoãn. |

Phase 01 cần preview trước nạp. Phase 03 cần model hợp lệ Phase 02 để hiện dự báo; không có model thì báo trạng thái thiếu, không giả xác suất. Mỗi horizon cần định nghĩa nhãn/kiểm định riêng; không lấy model 30m suy ra 1 ngày.

## Phân biệt ba mục tiêu

- **Xem lại để hiểu:** người dùng có thể đã biết trước sự kiện tháng 3–4/2024; phiên này mang tính giáo dục, không chứng minh model tổng quát hóa.
- **Đánh giá model công bằng:** trước khi xem test, khóa cửa sổ học/config, đánh giá nhiều đoạn thời gian độc lập với baseline; giữ test cuối chỉ dùng một lần.
- **Giả lập lệnh mua/bán và P&L** cần giá khớp, phí, slippage, vốn và luật Spot; **không thuộc mô phỏng dự đoán** này. Điểm mua trên chart là dấu mốc giả định, không phải lệnh đã khớp.

## Câu hỏi mở / ranh giới người dùng chưa chốt

1. **Đã chốt** thời điểm mua và giá mua giả định là đầu vào AI, cùng lịch sử nến khả dụng tới mốc mua; AI dự báo giá sau horizon so với giá mua này. Còn cần quy tắc chọn nến đóng nếu click giữa nến/gap hoặc mốc `t+horizon` nằm giữa hai nến.
2. **Đã chốt** horizon chọn mốc hoặc nhập trong khoảng 30 phút–tối đa 1 ngày; còn xác định bước giá trị hợp lệ theo khung nến, cách khớp nến kết quả và xác nhận 1 ngày = 24 giờ.
3. **Đã chốt** sau khi khóa AI và lựa chọn người mới bấm “Xem kết quả”; API phải từ chối phát outcome trước thao tác này và trước khi đủ nến hợp lệ. API lịch sử công khai vẫn có thể cho xem trước nên không gọi đây là blind test.
4. Tần suất train model phiên bản mới từ kết quả thị trường, ngưỡng chất lượng và quyền kích hoạt cần chốt qua đánh giá; không tự học ngay sau mỗi lượt.
5. Mốc giờ hiển thị UTC hay Asia/Ho_Chi_Minh (API lưu UTC); xác minh giới hạn dữ liệu lịch sử Binance.

## Không được nói khi bàn giao

- Không nói "đã có biểu đồ live", "AI tự chọn tốt nhất", "dự đoán chính xác", "đã backtest có lãi" nếu gate tương ứng chưa chạy và có output.
- Không dùng chính khoảng người dùng vừa chọn để vừa train vừa tuyên bố dự đoán trước tương lai.
- Không mặc định `30m` là timeframe nến, không suy ra price execution từ OHLCV, không ép DOWN thành lãi short trong Spot.
