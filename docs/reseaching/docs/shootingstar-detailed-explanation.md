---
title: ShootingStar — Giải thích chi tiết dự án và lộ trình nghiên cứu
status: research-only
implementation: chưa triển khai
---

# ShootingStar là gì?
> Technical design: [2026-08-19-shootingstar-technology-design.md](./superpowers/specs/2026-08-19-shootingstar-technology-design.md)

## Tóm tắt trong một đoạn

ShootingStar là một hệ thống nghiên cứu giúp trả lời một câu hỏi rất cụ thể:

> Tại thời điểm hiện tại, với dữ liệu giá và tin tức đã thực sự xuất hiện, BTC/USDT trong 30 phút tới có khả năng tăng, giảm, hay biến động không đủ lớn để giao dịch?

Hệ thống không hứa đoán đúng mọi lần. Nó cũng không bắt đầu bằng việc tự đặt lệnh. Việc đầu tiên là xây một phép đo đáng tin: dữ liệu có đúng thời điểm không, mô hình có vô tình nhìn thấy tương lai không, kết quả có còn dương sau phí và slippage không, và xác suất mô hình đưa ra có đáng tin không.

Sản phẩm đầu tiên là một **evidence engine**: nhận dữ liệu, phân tích, tạo tín hiệu có xác suất, lưu bằng chứng và cho phép con người kiểm tra. Nếu kết quả không tốt, hệ thống phải chỉ ra điều đó một cách trung thực thay vì làm cho báo cáo trông đẹp hơn.

---

## 1. Dự án sẽ làm gì?

ShootingStar sẽ đi qua quy trình sau:

```text
Dữ liệu giá BTC/USDT
        +
Tin tức có timestamp hợp lệ
        ↓
Kiểm tra chất lượng và thời điểm khả dụng
        ↓
Tạo feature từ dữ liệu quá khứ
        ↓
Mô hình tạo xác suất
        ↓
Signal: UP / DOWN / NO_TRADE
        ↓
Backtest hoặc paper trading
        ↓
Báo cáo kết quả và bằng chứng
```

Mỗi dự đoán gắn với một thời điểm `t`.

- Feature chỉ được dùng dữ liệu có timestamp không mới hơn `t`.
- Label chỉ được tạo bằng giá trong tương lai, từ `t` đến `t + 30 phút`.
- Giá tương lai được dùng để đánh giá kết quả, không được đưa ngược vào feature.
- Tin tức đến sau `t` không được sử dụng cho dự đoán tại `t`, kể cả khi tin đó có timestamp xuất bản sớm hơn.

Mục tiêu là biết signal có giá trị trong điều kiện giống thực tế hay không.

---

## 2. Dự án không làm gì ở giai đoạn đầu?

Các mục tiêu sau chưa thuộc phiên bản đầu:

- không đảm bảo lợi nhuận;
- không cam kết accuracy 90%;
- không tự động đặt lệnh thật;
- không quản lý tiền hoặc tài khoản exchange;
- không cho phép rút tiền;
- không bắt đầu bằng nhiều agent tranh luận;
- không hỗ trợ toàn bộ thị trường crypto ngay;
- không xây dashboard realtime trước khi baseline chứng minh có giá trị;
- không huấn luyện một LLM lớn chỉ vì máy có GPU;
- không trộn dự báo giá, stop-loss, take-profit và position sizing vào cùng một bài toán đầu tiên.

Accuracy khoảng 90% chỉ là giả thuyết cần kiểm tra. Một kết quả cao có thể là giả nếu có data leakage, overfitting, chọn thời kỳ thuận lợi hoặc bỏ qua chi phí giao dịch.

---

## 3. Signal là gì?

**Signal** là kết quả phân tích của hệ thống tại một thời điểm. Signal không phải là lệnh giao dịch.

Một signal có thể trông như sau:

```json
{
  "time": "2026-08-19T10:00:00Z",
  "symbol": "BTCUSDT",
  "decision": "UP",
  "probability": 0.72,
  "horizon": "30m",
  "model_version": "technical-baseline-v1",
  "features_until": "2026-08-19T10:00:00Z",
  "news_used": [],
  "reason": "Tín hiệu kỹ thuật vượt ngưỡng chi phí với xác suất đủ cao"
}
```

Ba trạng thái chính:

### `UP`

Mô hình cho rằng mức tăng trong 30 phút tới có khả năng vượt ngưỡng đáng giao dịch sau khi tính chi phí.

### `DOWN`

Mô hình cho rằng mức giảm trong 30 phút tới có khả năng vượt ngưỡng đáng giao dịch sau khi tính chi phí.

### `NO_TRADE`

Không nên hành động. Có thể do:

- biến động dự kiến quá nhỏ;
- xác suất mô hình thấp;
- dữ liệu bị thiếu hoặc không đáng tin;
- tin tức đến muộn;
- thị trường nằm ngoài phạm vi mô hình đã được kiểm tra;
- lợi thế dự kiến không đủ bù phí và slippage.

`NO_TRADE` không phải lỗi. Đây là một đầu ra quan trọng để hệ thống không bị ép phải chọn tăng hoặc giảm trong mọi tình huống.

---

## 4. Paper trading là gì?

**Paper trading là giao dịch giả lập, không dùng tiền thật.**

Hệ thống vẫn nhận dữ liệu thị trường, tạo signal và giả lập hành động như đang giao dịch:

```text
10:00 — BTC = 100.000 USDT
Signal = UP
Paper order = Mua giả lập

10:30 — BTC = 100.400 USDT
Paper exit = Bán giả lập

Kết quả = lợi nhuận giả lập sau phí và slippage
```

Không có request đặt lệnh thật gửi lên exchange. Không có tiền thật bị khóa hoặc mất.

Paper trading dùng để kiểm tra các vấn đề như:

- signal có xuất hiện đúng thời điểm không;
- dữ liệu có đến trễ không;
- signal có bị trùng không;
- chi phí giả định có được tính không;
- mô hình có phát quá nhiều signal không;
- `NO_TRADE` có hoạt động không;
- người dùng có override signal không;
- kết quả live giả lập có giống kết quả backtest không.

Paper trading không chứng minh chắc chắn rằng live trading sẽ thành công. Nó chỉ là một lớp kiểm tra gần thực tế hơn backtest.

---

## 5. Phí giao dịch và slippage là gì?

### 5.1. Phí giao dịch

Phí giao dịch là khoản exchange thu khi mua hoặc bán.

Một vòng giao dịch thường có hai phía:

```text
Mua BTC → bán BTC
```

Vì vậy cần tính cả phí vào lệnh và phí thoát lệnh. Mức phí phụ thuộc vào exchange, loại thị trường, maker/taker, volume và tài khoản.

### 5.2. Slippage

Slippage là chênh lệch giữa giá dự kiến và giá thực thi.

Ví dụ:

```text
Giá hiển thị lúc quyết định: 100.000 USDT
Giá mua mô phỏng:             100.050 USDT
Slippage:                     50 USDT
```

Slippage có thể xuất hiện vì:

- spread giữa giá mua và giá bán;
- thị trường biến động nhanh;
- thanh khoản thấp;
- lệnh lớn làm quét nhiều mức giá;
- độ trễ giữa lúc phát hiện signal và lúc thực thi.

### 5.3. Vì sao phải tính cả hai?

Giả sử mô hình dự đoán đúng hướng và giá tăng `0,15%`:

```text
Lợi nhuận do giá tăng: +0,15%
Phí mua và bán:        -0,10%
Slippage:              -0,08%
Lợi nhuận ròng:        -0,03%
```

Mô hình đoán đúng chiều nhưng giao dịch vẫn lỗ.

Nếu bỏ qua phí và slippage, hệ thống sẽ báo cáo một signal có vẻ sinh lời nhưng thực tế không đủ lợi thế.

### 5.4. Phí ảnh hưởng đến nhãn như thế nào?

Không nên gắn nhãn đơn giản như sau:

```text
Giá tăng một chút = UP
```

Nhãn phải gắn với ngưỡng chi phí:

```text
UP nếu return > tổng chi phí + biên an toàn
DOWN nếu return < -tổng chi phí - biên an toàn
NO_TRADE nếu biến động nằm trong vùng chi phí
```

Ví dụ minh họa:

```text
Phí + slippage bảo thủ: 0,20%
Biên an toàn:           0,05%
Ngưỡng cần vượt:        0,25%
```

Một mức tăng `0,10%` sẽ được xếp là `NO_TRADE`, không phải `UP`.

### 5.5. Tại sao đặc biệt quan trọng với horizon 30 phút?

Trong khoảng 30 phút, nhiều chuyển động giá là nhỏ. Nếu hệ thống giao dịch mọi chuyển động nhỏ, chi phí có thể ăn hết lợi thế.

Vì vậy mục tiêu không phải là dự đoán giá có xanh hay đỏ, mà là dự đoán giá có di chuyển đủ lớn để đáng cân nhắc sau chi phí hay không.

---

## 6. Các tầng của hệ thống

### Tầng 1 — Market data

Thu thập dữ liệu BTC/USDT từ một venue cụ thể.

Dữ liệu tối thiểu:

- open, high, low, close;
- volume;
- open time và close time;
- symbol;
- venue;
- timeframe;
- thời điểm tải dữ liệu;
- raw response hoặc hash của snapshot.

Ban đầu nên dùng một pair và một venue để biết kết quả đến từ đâu. Không trộn spot với futures hoặc nhiều exchange trong target đầu tiên.

### Tầng 2 — Data quality và timestamp gate

Tầng này quyết định dữ liệu có được phép đi tiếp hay không.

Nó kiểm tra:

- candle có bị thiếu không;
- timestamp có tăng đều không;
- candle đã đóng hay còn đang hình thành;
- news có `published_at` không;
- news đã được hệ thống nhận trước thời điểm dự đoán chưa;
- item có bị trùng không;
- dữ liệu lỗi hoặc đến muộn có bị loại và ghi log không.

Đây là tầng ngăn lỗi nghiêm trọng nhất: mô hình vô tình thấy thông tin chỉ xuất hiện sau thời điểm dự đoán.

### Tầng 3 — Label construction

Với mỗi thời điểm `t`, hệ thống nhìn giá tương lai tại `t + 30m` để tạo label.

Ví dụ:

```text
Giá tại t:       100.000
Giá tại t+30m:   100.400
Return:          +0,40%
Threshold:       +0,25%
Label:           UP
```

Giá `100.400` chỉ được dùng để tạo label và đánh giá. Nó không được đưa vào feature của thời điểm `t`.

### Tầng 4 — Feature engineering

Tạo các biến đầu vào từ dữ liệu đã có trước `t`.

Ví dụ:

- return 1, 5, 15 và 30 phút trước;
- thay đổi volume;
- volatility;
- moving average;
- momentum;
- cấu trúc candle;
- khoảng cách giữa giá và một đường trung bình.

Feature phải tái tạo được từ cùng một data snapshot. Không dùng indicator được tính bằng toàn bộ dataset rồi mới cắt ngược về quá khứ nếu cách tính đó làm lộ tương lai.

### Tầng 5 — Prediction model

Model nhận feature và trả xác suất cho từng lớp.

Thứ tự phát triển:

1. always-up, always-down và majority-class;
2. technical rule hoặc technical baseline;
3. classifier ML nhỏ, có calibration;
4. technical + news;
5. LLM hoặc multi-agent adapter.

Baseline phải được giữ lại vĩnh viễn để làm đối chứng. Nếu mô hình phức tạp không vượt baseline, không nên thêm phức tạp hơn.

### Tầng 6 — Signal policy

Tầng này chuyển xác suất thành signal.

Nó xem xét:

- xác suất dự đoán;
- threshold lợi nhuận;
- phí và slippage;
- calibration;
- dữ liệu có hợp lệ không;
- model có nằm trong phạm vi đã kiểm tra không.

Kết quả có thể là `UP`, `DOWN` hoặc `NO_TRADE`.

### Tầng 7 — Paper execution

Tầng này không đặt lệnh thật. Nó chỉ mô phỏng:

- giá vào;
- giá thoát;
- phí;
- slippage;
- thời gian giữ vị thế;
- kết quả của từng paper order.

Tầng này giúp chuyển signal thành kết quả kinh tế giả lập thay vì chỉ đếm đúng/sai hướng giá.

### Tầng 8 — Audit và report

Mỗi signal cần lưu:

- timestamp;
- symbol và venue;
- model version;
- feature window;
- xác suất;
- signal;
- threshold;
- news đã dùng;
- news bị loại và lý do;
- paper-trade result;
- manual override nếu có.

Báo cáo phải cho phép trả lời câu hỏi: “Tại sao hệ thống phát signal này tại thời điểm đó?”

---

## 7. Các stage phát triển an toàn

### Stage 0 — Research offline

Dùng data snapshot cố định.

Mục tiêu:

- kiểm tra label;
- kiểm tra timestamp;
- kiểm tra leakage;
- kiểm tra feature generation;
- kiểm tra khả năng chạy lại và tái lập.

Chưa có credential giao dịch và không gọi endpoint đặt lệnh.

### Stage 1 — Historical backtest

Dùng dữ liệu lịch sử theo thứ tự thời gian.

Cần có:

- train/validation/test theo thời gian;
- walk-forward evaluation;
- phí và slippage;
- drawdown;
- loss streak;
- kết quả theo regime và từng khoảng thời gian.

Không dùng random split như phép đo chính cho bài toán này.

### Stage 2 — Paper trading

Dùng dữ liệu live công khai hoặc delayed data, nhưng chỉ tạo signal và paper order.

Cần log:

- output của model;
- dữ liệu news đã dùng;
- news bị loại;
- dữ liệu đến trễ;
- thao tác review hoặc override của người dùng.

### Stage 3 — Shadow mode

Nếu cần, chạy hệ thống song song với thị trường thật nhưng không đặt lệnh.

Theo dõi:

- drift;
- latency;
- missing data;
- duplicate signal;
- calibration;
- chênh lệch giữa giá giả lập và điều kiện thị trường.

### Stage 4 — Live trading có giới hạn

Đây là một dự án an toàn tài chính riêng, không phải phần mặc định của MVP.

Nếu sau này xem xét, tối thiểu phải có:

- API key không có quyền rút tiền;
- giới hạn vị thế;
- giới hạn lỗ ngày;
- kill switch;
- bảo vệ duplicate order;
- pre-trade validation;
- audit log;
- alert;
- circuit breaker;
- phê duyệt của con người.

---

## 8. AI, model và con người làm gì?

### Model định lượng

Model chịu trách nhiệm:

- đọc feature đã được freeze;
- tạo xác suất;
- trả `UP`, `DOWN` hoặc `NO_TRADE` theo policy;
- lưu model version và timestamp.

Model không được tự thay đổi target, threshold hoặc test split để làm kết quả đẹp hơn.

### LLM hoặc news model

Nếu được thêm vào, LLM chỉ nên:

- trích xuất sentiment hoặc event;
- chuẩn hóa headline;
- phát hiện duplicate;
- trả evidence và confidence;
- giữ reference về bài gốc.

LLM không được tự cấp quyền giao dịch hoặc tự đặt lệnh.

### Con người

Con người chịu trách nhiệm:

- chốt target;
- chốt threshold;
- chọn phí/slippage;
- kiểm tra quyền sử dụng dữ liệu;
- duyệt thay đổi feature/model;
- review signal;
- ghi manual override riêng;
- quyết định có chuyển sang stage tiếp theo hay không.

Manual override phải được lưu riêng. Nếu trộn override vào prediction, kết quả đánh giá sẽ không còn phản ánh năng lực model.

---

## 9. News được xử lý thế nào?

News chỉ có giá trị cho dự đoán nếu hệ thống biết nó đã thực sự khả dụng tại thời điểm `t`.

Mỗi news item nên có:

- `published_at`: thời điểm nguồn công bố;
- `ingested_at`: thời điểm hệ thống nhận được;
- source ID;
- headline hoặc raw text;
- immutable reference;
- trạng thái xử lý;
- lý do bị loại nếu không hợp lệ.

Điều kiện tối thiểu:

```text
published_at <= t
và
ingested_at <= t
```

Nếu bài được xuất bản lúc 09:55 nhưng hệ thống chỉ nhận được lúc 10:05, nó không được dùng cho signal lúc 10:00.

Không được lấy bài hiện tại rồi gán ngược vào quá khứ. Nếu lịch sử news không có timestamp đáng tin, phải chạy technical-only và ghi rõ news hypothesis chưa kiểm thử được.

---

## 10. Đánh giá model bằng gì?

Accuracy không đủ.

Một model có thể đúng 90% vì chỉ dự đoán một số trường hợp dễ, hoặc vì bỏ qua các lệnh sai có mức lỗ lớn. Báo cáo cần ít nhất:

### Precision và recall

Đo riêng cho `UP` và `DOWN`.

- Precision: trong số signal `UP`, bao nhiêu signal thực sự là `UP`?
- Recall: trong số các trường hợp thực sự `UP`, model bắt được bao nhiêu?

### Calibration

Nếu model nói xác suất 70%, thì trong nhiều mẫu tương tự, kết quả đúng nên xấp xỉ 70%.

Nếu model liên tục nói 90% nhưng thực tế chỉ đúng 55%, nó đang quá tự tin.

### Coverage

Tỷ lệ timestamp mà model phát `UP` hoặc `DOWN` thay vì `NO_TRADE`.

Model có precision cao nhưng chỉ phát signal 1% thời gian có thể không hữu ích trong vận hành.

### Expectancy sau phí/slippage

Đây là lợi nhuận kỳ vọng sau khi tính chi phí.

Cần xem:

- lợi nhuận trung bình mỗi paper trade;
- số lượng trade;
- tỷ lệ thắng;
- mức lãi trung bình;
- mức lỗ trung bình;
- phí và slippage.

### Drawdown và loss streak

Cần biết chuỗi thua dài nhất và giai đoạn tài khoản giả lập giảm sâu nhất.

### Walk-forward và regime breakdown

Kết quả phải được xem theo:

- từng khoảng thời gian;
- thị trường tăng;
- thị trường giảm;
- thị trường đi ngang;
- giai đoạn volatility cao;
- giai đoạn volatility thấp.

Một model chỉ tốt trong một regime chưa thể xem là ổn định.

---

## 11. Ví dụ đầy đủ từ đầu đến cuối

Giả sử tại 10:00:

```text
BTCUSDT: 100.000 USDT
Horizon: 30 phút
```

### Bước 1: kiểm tra dữ liệu

- Candle đến 10:00 đã đóng.
- Không có missing data trong cửa sổ feature.
- Không có news đến muộn được đưa vào.

### Bước 2: tạo feature

Model dùng:

- return 5 phút trước;
- return 15 phút trước;
- volume change;
- volatility;
- moving average distance.

Tất cả đều được tính từ dữ liệu không mới hơn 10:00.

### Bước 3: model dự đoán

```text
P(UP)       = 0,72
P(DOWN)     = 0,16
P(NO_TRADE) = 0,12
```

### Bước 4: áp dụng chi phí

```text
Phí + slippage bảo thủ: 0,20%
Biên an toàn:           0,05%
Threshold:              0,25%
```

Nếu expected move đủ vượt threshold và calibration đạt yêu cầu, hệ thống phát:

```text
Signal: UP
```

Nếu expected move chỉ là `0,10%`, hệ thống phát:

```text
Signal: NO_TRADE
Reason: expected move không đủ bù chi phí
```

### Bước 5: paper execution

Trong paper trading, signal `UP` tạo một paper order. Không có lệnh thật.

Sau 30 phút:

```text
Giá BTC: 100.400 USDT
Return giá: +0,40%
Chi phí giả định: -0,20%
Kết quả ròng giả lập: +0,20%
```

Kết quả này được lưu cùng model version, feature window và evidence của signal.

---

## 12. Trước khi viết code cần chốt gì?

Các quyết định còn phải chốt:

1. Venue và nguồn dữ liệu lịch sử.
2. Dùng candle `1m` hay `5m`.
3. Mức phí và slippage bảo thủ.
4. Nguồn news có lịch sử và timestamp đáng tin.
5. Khoảng thời gian evaluation.
6. Các market regime cần kiểm tra.
7. Coverage tối thiểu chấp nhận được.
8. Thời gian paper trading.
9. Signal chỉ hiển thị hay có thêm explanation/audit report.
10. Cách lưu raw data snapshot và version config.

Các quyết định này phải được freeze trước khi so sánh model. Nếu thay đổi threshold hoặc split sau khi thấy kết quả, kết quả cũ không còn là phép đo công bằng.

---

## 13. Thứ tự xây dựng thực tế

### Giai đoạn đầu tiên

- tạo project Python cho research;
- định nghĩa schema dữ liệu;
- tải một snapshot BTC/USDT cố định;
- kiểm tra missing candle và timestamp;
- viết label construction;
- viết leakage checks;
- tạo baseline đơn giản.

### Giai đoạn thứ hai

- thêm feature kỹ thuật nhỏ;
- chạy time-ordered backtest;
- tính precision/recall, calibration, coverage và expectancy;
- tính phí/slippage;
- tạo báo cáo tái lập được.

### Giai đoạn thứ ba

- thêm historical news nếu timestamp hợp lệ;
- chạy technical-only và technical + news trên cùng các window;
- đo giá trị tăng thêm của news.

### Giai đoạn thứ tư

- chạy paper trading;
- log signal và paper order;
- review drift và chênh lệch với backtest.

### Giai đoạn sau

Chỉ khi các kết quả trên ổn định mới cân nhắc LLM, agent hoặc live trading có giới hạn.

---

## 14. Kết luận dễ nhớ

ShootingStar không bắt đầu bằng câu hỏi:

> “Làm thế nào để AI thắng mọi giao dịch?”

Mà bắt đầu bằng câu hỏi:

> “Khi không dùng dữ liệu tương lai, sau phí và slippage, signal này có thật sự có giá trị không?”

Cách làm đúng là:

```text
Một pair
→ Một horizon
→ Một target rõ ràng
→ Baseline đơn giản
→ Chống leakage
→ Tính đủ chi phí
→ Walk-forward evaluation
→ Paper trading
→ Sau đó mới xem xét mở rộng
```

Nếu model không vượt baseline, đó vẫn là kết quả có giá trị. Nó giúp dừng việc thêm LLM, agent và hạ tầng phức tạp vào một giả thuyết chưa được chứng minh.

---

## 15. Thuật ngữ nhanh

| Thuật ngữ | Nghĩa |
|---|---|
| Signal | Kết luận dự đoán của hệ thống, chưa phải lệnh thật |
| Paper trading | Giao dịch giả lập, không dùng tiền thật |
| Backtest | Kiểm tra chiến lược trên dữ liệu lịch sử |
| Slippage | Chênh lệch giữa giá dự kiến và giá thực thi |
| Fee | Phí exchange thu khi giao dịch |
| Horizon | Khoảng thời gian dự đoán; ở đây là 30 phút |
| Feature | Biến đầu vào của model |
| Label | Kết quả thực tế dùng để huấn luyện/đánh giá |
| Leakage | Dữ liệu tương lai vô tình lọt vào quá trình dự đoán |
| Calibration | Mức độ đáng tin của xác suất model đưa ra |
| Coverage | Tỷ lệ thời điểm có signal thay vì `NO_TRADE` |
| Walk-forward | Đánh giá theo thứ tự thời gian giống vận hành thật |
| Baseline | Mô hình đối chứng đơn giản để biết model mới có tạo giá trị không |
| Shadow mode | Chạy cạnh thị trường thật nhưng không đặt lệnh |

---

## Nguồn tham khảo

- Binance Spot REST API và kline: <https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#klinecandlestick-data>
- CCXT Manual: <https://github.com/ccxt/ccxt/wiki/Manual#ohlcv-candlestick-charts>
- scikit-learn `TimeSeriesSplit`: <https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>
- scikit-learn Probability Calibration: <https://scikit-learn.org/stable/modules/calibration.html>
- Niculescu-Mizil & Caruana, *Predicting Good Probabilities With Supervised Learning*: <https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf>
- GDELT Data: <https://www.gdeltproject.org/data.html>
- NIST AI Risk Management Framework: <https://www.nist.gov/itl/ai-risk-management-framework>
