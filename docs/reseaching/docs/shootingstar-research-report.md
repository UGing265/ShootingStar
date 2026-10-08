---
title: ShootingStar — Báo cáo định hướng nghiên cứu AI trading crypto
status: research-only
implementation: chưa triển khai
---

# ShootingStar — Báo cáo định hướng nghiên cứu AI trading crypto

> Bản giải thích dễ đọc và chi tiết hơn: [shootingstar-detailed-explanation.md](./shootingstar-detailed-explanation.md)
> Technical design spec: [2026-08-19-shootingstar-technology-design.md](./superpowers/specs/2026-08-19-shootingstar-technology-design.md)

## 1. Tóm tắt

ShootingStar nên bắt đầu như một **hệ thống nghiên cứu và hỗ trợ quyết định**, không phải bot tự động giao dịch.

Câu hỏi nghiên cứu đầu tiên:

> Tại thời điểm `t`, dựa trên dữ liệu thị trường và tin tức đã thực sự khả dụng, giá BTC/USDT trong 30 phút tiếp theo có khả năng tăng, giảm, hay biến động không đủ lớn để giao dịch?

Đầu ra đề xuất gồm ba trạng thái:

- `UP`: mức tăng kỳ vọng vượt ngưỡng chi phí giao dịch.
- `DOWN`: mức giảm kỳ vọng vượt ngưỡng chi phí giao dịch.
- `NO_TRADE`: không đủ lợi thế hoặc không đủ chắc chắn để hành động.

Mục tiêu đầu tiên không phải chứng minh “đúng gần 90%”. Mục tiêu là xây dựng phép đo không dùng dữ liệu tương lai, có thể tái lập, và cho biết tín hiệu có tạo lợi thế sau phí/slippage hay không.

**Trạng thái:** báo cáo nghiên cứu; chưa triển khai source code, model, exchange connector hoặc live trading.

## 2. ShootingStar là gì?

Tên ShootingStar có thể đại diện cho tốc độ, sức mạnh và hình ảnh “đánh đâu thắng đó”. Về kỹ thuật, sản phẩm nên được định nghĩa như sau:

> ShootingStar là một crypto short-horizon evidence engine: hệ thống tổng hợp cấu trúc thị trường, dữ liệu kỹ thuật và tin tức được căn chỉnh theo thời gian; sau đó đưa ra xác suất, bằng chứng và trạng thái nên hành động hay đứng ngoài để con người đánh giá.

ShootingStar không phải là:

- máy dự đoán chắc chắn giá;
- hệ thống đảm bảo lợi nhuận hoặc thu nhập;
- bot giao dịch tự chủ ngay từ phiên bản đầu;
- nhóm LLM tranh luận nhưng không có baseline định lượng để so sánh.

Deliverable đầu tiên là bằng chứng nghiên cứu đáng tin cậy: dữ liệu, cách gắn nhãn, kết quả out-of-sample, giới hạn và các trường hợp mô hình không chắc chắn.

## 3. Lựa chọn đầu ra dự đoán

| Phương án | Ưu điểm | Rủi ro / giới hạn | Đánh giá |
|---|---|---|---|
| `UP/DOWN` nhị phân | Dễ hiểu | Buộc chọn khi thị trường đi ngang; bỏ qua chi phí | Không nên dùng làm đầu ra chính |
| `UP/DOWN/NO_TRADE` | Có quyền từ chối; sát quyết định thực tế | Cần chốt threshold và coverage | **Khuyến nghị cho nghiên cứu đầu tiên** |
| Xác suất từng lớp | Đo được bất định và calibration | Có thể quá tự tin nếu chưa calibration | **Nên đi kèm đầu ra ba lớp** |
| Dự báo return liên tục | Giàu thông tin | Khó đánh giá; dễ bị hiểu nhầm là chắc chắn | Chỉ là thí nghiệm phụ |
| Entry/SL/TP/position size | Gần execution | Trộn forecasting, risk và execution | Hoãn |
| Agent tự đặt lệnh | Tự động hóa cao | Rủi ro tài chính và vận hành lớn | Không thuộc giai đoạn đầu |

### Nhãn đề xuất

Với prediction timestamp `t` và horizon 30 phút:

- `UP` nếu `return(t, t+30m) > +threshold`.
- `DOWN` nếu `return(t, t+30m) < -threshold`.
- `NO_TRADE` nếu giá trị tuyệt đối của return không vượt threshold.

`threshold` phải được chốt từ giả định phí và slippage bảo thủ trước khi so sánh model. Không dùng nhãn chỉ dựa vào candle xanh/đỏ nếu mức biến động không đủ bù chi phí.

## 4. Tiêu chí thành công

### 4.1. Không rò rỉ dữ liệu tương lai

Một sample tại `t` chỉ được dùng:

- OHLCV có timestamp không mới hơn `t`;
- news có `published_at <= t` và `ingested_at <= t`;
- feature từ candle hiện tại và quá khứ;
- giá tại `t+30m` chỉ dùng để tạo label/evaluate.

News publish trước nhưng ingestion sau `t` phải bị loại khỏi sample đó và ghi rõ lý do. Không backfill news đến muộn vào quá khứ.

### 4.2. Baseline bắt buộc

So sánh theo thứ tự:

1. Always-up, always-down và majority-class.
2. Technical baseline từ OHLCV lagged và một nhóm indicator nhỏ.
3. Classifier thống kê/ML có xác suất và calibration.
4. Technical + news features đã căn chỉnh timestamp.
5. LLM hoặc multi-agent chỉ sau khi bốn lớp trước có kết quả.

Nếu model không vượt technical baseline trên dữ liệu out-of-sample, không chữa bằng cách thêm agents. Kiểm tra data quality, target, leakage, overfitting và regime shift trước.

### 4.3. Metrics bắt buộc

Báo cáo kết quả phải có:

- precision và recall riêng cho `UP` và `DOWN`;
- confusion matrix hoặc class distribution;
- calibration;
- coverage, tức tỷ lệ timestamp không phải `NO_TRADE`;
- expectancy sau phí và slippage;
- số giao dịch, win rate và loss streak;
- maximum drawdown và giai đoạn tệ nhất;
- kết quả theo thời gian và market regime;
- walk-forward/out-of-sample.

Accuracy đơn độc không đủ. Mô hình có 90% accuracy vẫn có thể lỗ nếu các lần sai có mức lỗ lớn. “Gần 90%” chỉ là giả thuyết cần kiểm tra, không phải cam kết.

## 5. Trách nhiệm của người, model và agents

### Con người

- Chốt target, threshold, phí/slippage và phạm vi tài sản.
- Kiểm tra chất lượng và quyền sử dụng dữ liệu/news.
- Duyệt thay đổi feature/model.
- Review tín hiệu trong research và paper trading.
- Ghi manual override riêng, không trộn vào kết quả model.
- Quyết định chuyển stage an toàn.

### Model định lượng

- Nhận feature đã freeze và tạo xác suất.
- Không tự thay đổi target, split hoặc threshold.
- Lưu model version, feature window và timestamp.
- Có thể trả `NO_TRADE` khi không đủ confidence.

### News model / LLM

- Trích xuất sentiment/event từ news có timestamp hợp lệ.
- Giữ headline hoặc immutable reference để audit.
- Trả evidence và confidence riêng.
- Không tự cấp quyền giao dịch hoặc tự quyết định đặt lệnh.

### Agents

Agents chỉ nên có nhiệm vụ hẹp: thu thập/chuẩn hóa news, kiểm tra timestamp/duplicate, phân tích kỹ thuật theo schema và kiểm tra chất lượng report. Không nên bắt đầu bằng hội đồng agents tự tranh luận vì chi phí, latency, nondeterminism và khó truy nguyên lỗi.

## 6. Các stage an toàn

### Stage 0 — Research offline

Dữ liệu lịch sử cố định, không có credential giao dịch, không gọi lệnh exchange; kiểm tra label, timestamp, leakage và reproducibility.

### Stage 1 — Historical backtest

Time-ordered train/validation/test, walk-forward, phí/slippage bảo thủ, drawdown, loss streak và regime breakdown.

### Stage 2 — Paper trading

Dùng dữ liệu live công khai hoặc delayed data; chỉ tạo signal/paper order; log model output, news được dùng, news bị loại và thao tác người dùng.

### Stage 3 — Shadow mode

Nếu cần, chạy cạnh thị trường thật nhưng không đặt lệnh; theo dõi drift, latency, missing data, duplicate signal và calibration.

### Stage 4 — Live trading có giới hạn

Đây là dự án safety-critical riêng, không thuộc MVP. Điều kiện tối thiểu sẽ gồm API key không có quyền rút tiền, position/daily-loss limit, kill switch, duplicate-order protection, pre-trade validation, audit log, alert, circuit breaker và phê duyệt con người.

## 7. Trade-off tài nguyên

| Hạng mục | Tiết kiệm | Nhiều tài nguyên | Khuyến nghị đầu tiên |
|---|---|---|---|
| Market data | OHLCV 5 phút, một pair | 1 phút, nhiều pair, order book | Một pair; ưu tiên dữ liệu đáng tin |
| News | Dataset lịch sử có timestamp | Nhiều nguồn realtime/licensing | Chỉ dùng khi timestamp/audit được |
| Model | Linear/tree nhỏ | Deep model/LLM fine-tuning | Baseline nhỏ, deterministic |
| Compute | CPU | GPU/hosted inference | RTX 3060 đủ; chưa cần train model lớn |
| Agents | Pipeline tuần tự | Nhiều agent tranh luận | Chỉ thêm khi đo được giá trị tăng thêm |
| Vận hành | Offline CLI/report | Dashboard realtime/workers | Offline/backtest rồi paper trade |
| Phạm vi | BTC/USDT | Toàn thị trường | Một pair để attribution rõ |

Python phù hợp cho research vì repository không có ràng buộc sẵn. Chưa cần khóa framework, database, cloud hay dashboard trước khi dữ liệu và câu hỏi được chốt.

## 8. Phạm vi đề xuất

### Nằm trong research slice đầu tiên

- Một liquid pair: BTC/USDT.
- Một horizon: 30 phút.
- Nhãn `UP/DOWN/NO_TRADE`.
- Dataset OHLCV có timestamp.
- Technical baseline nhỏ, giải thích được.
- News alignment với `published_at` và `ingested_at`.
- So sánh technical-only với technical + news.
- Time-ordered split và walk-forward report.
- Paper-trading logic trên dữ liệu cố định.

### Hoãn lại

Multi-asset, order-book phức tạp, multi-agent debate, fine-tuning LLM lớn, dashboard realtime, exchange execution, position sizing động và tự động hóa hoàn toàn.

Lý do: các hạng mục này làm tăng chi phí và failure modes nhưng chưa trả lời câu hỏi cơ bản rằng tín hiệu có predictive value hay không.

## 9. Các quyết định cần chốt trước implementation

1. Venue và nguồn dữ liệu lịch sử nào được phép sử dụng?
2. Dùng candle 1 phút hay 5 phút dựa trên chất lượng dữ liệu thực tế?
3. Fee và slippage bảo thủ nào dùng để chọn threshold?
4. News provider có lịch sử, timestamp và quyền sử dụng phù hợp không?
5. Khoảng thời gian và market regimes nào dùng cho evaluation?
6. Coverage tối thiểu chấp nhận được là bao nhiêu?
7. Paper trading kéo dài bao lâu trước khi đánh giá stage tiếp theo?
8. Hệ thống chỉ cung cấp signal hay cần thêm explanation/audit report?

## 10. Kết luận

Hướng an toàn và có giá trị nhất là xây ShootingStar như một **hệ thống nghiên cứu đo lường được**, không phải bot hứa hẹn thắng lớn. Bắt đầu với một cặp BTC/USDT, horizon 30 phút, nhãn ba trạng thái, technical baseline, news time alignment, walk-forward evaluation và paper trading.

Chỉ khi baseline chứng minh kết quả ổn định sau chi phí mới cân nhắc news model, LLM hoặc agents. Nếu không chứng minh được, kết quả đó vẫn hữu ích vì ngăn dự án tiếp tục mở rộng dựa trên kỳ vọng chưa được đo đúng.

## 11. Nghiên cứu bổ sung từ nguồn chính thức

Phần này bổ sung bằng chứng kỹ thuật để biến hướng nghiên cứu thành quyết định có thể triển khai. Đây là kết luận về phương pháp và nguồn dữ liệu, không phải kết quả dự đoán giá.

### 11.1. Market data

- Binance Spot REST có endpoint công khai `GET /api/v3/klines`; mỗi kline được định danh bằng `open time`. Endpoint hỗ trợ `1m`, `5m`, `15m`, `30m` và các interval khác; mặc định trả 500 mẫu, tối đa 1.000 mẫu mỗi request. Timestamps mặc định là milliseconds và `startTime`/`endTime` được diễn giải theo UTC. Nguồn dữ liệu của endpoint là database.
- Binance ghi rõ API có thể trễ, giới hạn request theo IP, trả `429` khi vượt giới hạn và có thể ban IP `418` nếu tiếp tục vi phạm. Downloader phải lưu raw response, khoảng thời gian truy vấn, timezone, status và backoff; không được coi dữ liệu tải lỗi là khoảng thời gian không có giao dịch.
- CCXT cung cấp lớp thống nhất `fetchOHLCV` cho nhiều exchange, nhưng không loại bỏ khác biệt về giới hạn lịch sử, missing candle, timestamp và rate limit của từng venue. Dùng CCXT như adapter tùy chọn; venue thực tế và response raw vẫn phải được lưu trong dataset snapshot.

**Quyết định:** bắt đầu với Binance Spot BTCUSDT và candle `1m` nếu kiểm thử dữ liệu xác nhận đủ liên tục; nếu không, chuyển sang `5m` và ghi rõ độ phân giải hiệu dụng. Không trộn spot, futures hoặc nhiều venue trong target đầu tiên.

### 11.2. Time-series evaluation và calibration

- `sklearn.model_selection.TimeSeriesSplit` giữ thứ tự thời gian, tránh train trên tương lai và hỗ trợ `gap` giữa train và test. Tài liệu yêu cầu mẫu cách đều nếu muốn các fold bao phủ cùng thời lượng.
- Với nhãn nhìn trước 30 phút, split thông thường vẫn có thể bị ảnh hưởng bởi nhãn chồng lấn. Evaluation cần walk-forward theo thời gian và loại vùng chồng lấn; `gap` tối thiểu phải được tính từ horizon và resolution, không hard-code theo số fold.
- Scikit-learn nêu rõ calibration phải fit trên dữ liệu độc lập với dữ liệu train; reliability diagram, Brier score và log loss cần được báo cáo cùng precision/recall. Brier hoặc log loss không nên là metric calibration duy nhất vì chúng trộn reliability, resolution và uncertainty.

**Quyết định:** khóa target/threshold trước; dùng train → calibration/validation → held-out test theo thời gian; không fit scaler, feature selector, threshold hoặc calibrator trên test. Báo cáo `UP` và `DOWN` riêng, coverage và calibration theo từng fold/regime.

### 11.3. News và khả năng tái lập

- GDELT công bố dữ liệu mở và nói GDELT 2.0 cập nhật mỗi 15 phút, nhưng nguồn này là kho news/event toàn cầu chứ không phải bằng chứng rằng mọi bài có publication timestamp đủ chính xác cho quyết định 30 phút.
- Vì vậy `published_at` phải đến từ metadata đáng tin của source article; `ingested_at` phải do hệ thống ghi khi nhận được. Nếu chỉ biết thời điểm GDELT phát hiện hoặc cập nhật, coi đó là thời điểm khả dụng bảo thủ, không suy ngược thành thời điểm bài được xuất bản.

**Quyết định:** technical-only là nhánh bắt buộc và có thể là kết quả cuối cùng. News-augmented chỉ được chạy khi từng item có timestamp khả dụng, source ID, immutable reference/raw text và log bị loại vì đến muộn. Không dùng headline hiện tại để backfill lịch sử.

### 11.4. Kết luận cập nhật

Hướng đã duyệt vẫn đúng. Bổ sung quan trọng là: chọn một venue cụ thể trước khi thiết kế schema; lưu snapshot raw để xử lý thay đổi API; dùng custom walk-forward có khoảng cách theo horizon; tách calibration khỏi train/test; và không coi nguồn news cập nhật nhanh là nguồn có publication-time đáng tin mặc định. Các điểm này là điều kiện trước implementation, không phải tính năng mở rộng.

## 12. Nguồn tham khảo chính

1. Binance Spot API — REST market data và kline: <https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#klinecandlestick-data>
2. CCXT Manual — unified exchange API và `fetchOHLCV`: <https://github.com/ccxt/ccxt/wiki/Manual#ohlcv-candlestick-charts>
3. scikit-learn — `TimeSeriesSplit`: <https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>
4. scikit-learn — probability calibration: <https://scikit-learn.org/stable/modules/calibration.html>
5. Niculescu-Mizil & Caruana, *Predicting Good Probabilities With Supervised Learning*: <https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf>
6. GDELT — data and update model: <https://www.gdeltproject.org/data.html>
7. NIST AI Risk Management Framework: <https://www.nist.gov/itl/ai-risk-management-framework>
