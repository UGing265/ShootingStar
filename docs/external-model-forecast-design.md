# Nghiên cứu tạm: model API bên ngoài cho dự báo BTCUSDT

**Ngày nghiên cứu:** 2026-10-10  
**Trạng thái:** Nghiên cứu để chuẩn bị [kế hoạch tích hợp API model ngoài](plans/261010-external-model-api-research/plan.md); **chưa triển khai, chưa chọn nhà cung cấp, chưa có kết quả đánh giá**, không thay gate `NO_MODEL` hiện tại.  
**Liên quan:** [Kế hoạch replay](plans/261009-historical-replay-research/plan.md), [Phase 02 tự train](plans/261009-historical-replay-research/phase-02-model-window-research.md), [thiết kế tự train cũ đã lưu riêng](self-trained-model-design.md).

## Kết luận để ra quyết định

Không có bằng chứng đáng tin trong các tài liệu API rằng Gemini, OpenAI hay Claude **dự báo BTCUSDT 30 phút–1 ngày tốt nhất**. Tài liệu nhà cung cấp chứng minh khả năng gọi API và trả JSON, **không chứng minh khả năng dự báo giá hoặc độ hiệu chỉnh xác suất**. Đề nghị thử **Gemini dòng Flash trước** vì có bậc miễn phí để thử cấu trúc output và cách tích hợp; **không khẳng định đây là lựa chọn rẻ nhất, nhanh nhất hoặc chính xác nhất**. So với một model OpenAI hoặc Claude và baseline trên cùng quy tắc đầu vào; lựa chọn cuối cùng dựa vào phép đo, chi phí và điều khoản dữ liệu, không dựa thương hiệu.

| Ứng viên | Lợi thế có nguồn | Giới hạn cần đánh giá | Vai trò đề xuất |
|---|---|---|---|
| Gemini Flash API | Có JSON schema/Pydantic và bậc miễn phí/trả phí [1][2] | Chưa có kết quả dự báo BTCUSDT trong ShootingStar; free tier có chính sách sử dụng dữ liệu khác paid tier | Ứng viên pilot dễ thử, **không phải kết luận chính xác/rẻ nhất** |
| OpenAI API | Có Structured Outputs và kiểm soát dữ liệu API được công bố [3][4] | Chi phí theo model/token và lưu trữ theo endpoint phải xác nhận khi chạy; chưa có kết quả dự báo BTCUSDT | Đối chứng độc lập cùng bộ đầu vào |
| Claude API | Có structured outputs và bảng giá theo model/token [5][6] | Chưa có kết quả dự báo BTCUSDT; phí và điều khoản lưu trữ tùy cấu hình | Đối chứng nếu ngân sách cho phép |
| Baseline không LLM | Đo được với cùng tập nến, không mất phí API | Không tạo diễn giải ngôn ngữ như LLM | Mốc tối thiểu để xem LLM có đem lại giá trị hay không |

**Giá:** Không chốt mức USD/triệu token trong thiết kế; model, giá, hạn mức và chính sách thay đổi. Trước thử nghiệm, lấy bảng giá hiện hành [2][6] và [trang giá OpenAI](https://developers.openai.com/api/docs/pricing); ước tính `số lượt × (token đầu vào × đơn giá đầu vào + token đầu ra × đơn giá đầu ra)`, thêm số lần thử lỗi/giới hạn rate và ngân sách trần. Không gửi nguyên snapshot hàng chục nghìn nến cho từng request nếu không cần: chỉ chuyển cửa sổ lịch sử được định nghĩa trước, sau kiểm tra causal.

## Tại sao không nối API thẳng vào Replay và tuyên bố đã giải khóa

`ExperimentRunner.run_experiment` hiện train và báo cáo nhãn close-to-close horizon 30m (`application/experiment.py`); `_evaluate_ai_prediction` trong `application/replay.py` trả `NO_MODEL` kể cả với manifest trông hợp lệ vì chưa có model point-price OOS. **Lệnh `run-experiment` hiện không tự sinh artifact hợp lệ cho Replay**. Dòng chữ UI “chọn model đã được đánh giá” không phản ánh được lựa chọn hiện có: chưa có luồng chọn model point-price đạt gate. Việc gọi Gemini/Claude/OpenAI **không tự tạo ra artifact train với cutoff trước `t`**, không đủ điều kiện thay cho gate Phase 02.

LLM thương mại có thể đã biết dữ liệu/sự kiện sau thời điểm replay lịch sử, dù prompt chỉ đưa nến trước `t`. Không thể bảo đảm kiểm định zero-lookahead trên dữ liệu quá khứ nếu không có bằng chứng cutoff tri thức/phiên bản model phù hợp. Một nghiên cứu về lookahead bias trong LLM tài chính ghi nhận nguy cơ này [7]; **không** xem nghiên cứu đó như kết quả so sánh trực tiếp Gemini/OpenAI/Claude trên BTC Spot. Vì thế:

- **Replay lịch sử với API model hiện tại:** chỉ gọi là *nhận định hồi cứu thử nghiệm*; không báo là dự báo lịch sử khách quan, không gộp với báo cáo OOS của Phase 02 hay mở khóa xác suất chính thức.
- **Theo dõi tiến về phía trước:** khóa request và câu trả lời tại thời điểm hiện tại, chờ nến tương lai đóng rồi chấm điểm. Đường này có thể kiểm tra chất lượng thực tế mà không đòi bạn tự train trước; vẫn cần đủ số mẫu và so baseline trước khi gọi kết quả đáng tin.
- **Mô hình tự train hợp lệ:** quy trình riêng từ Phase 02 để đạt kiểm định lịch sử point-in-time; kết quả thử LLM không thay thế nó.

## Thiết kế khi quyết định triển khai sau này

1. **Giao diện:** Có nhãn riêng “Nhận định API — thử nghiệm” tách khỏi “Dự báo đã kiểm định”; không xóa hoặc biến `NO_MODEL` thành số giả. Không để trình duyệt giữ API key hoặc gọi nhà cung cấp trực tiếp.
2. **Đầu vào/backend:** Backend xác thực snapshot ID/hash, `(t, giá mua giả định, horizon)`, timeframe 1m/5m, chỉ lấy nến đóng có `available_at <= t`; quy tắc gap và mốc kết quả dùng chung với Replay. Mốc giao diện UTC+7, API giữ epoch UTC. Không gửi nến tương lai, outcome, lựa chọn UP/DOWN của người hay nội dung ngoài mục tiêu vào prompt. Không bật search/web grounding cho thử nghiệm lịch sử.
3. **Đầu ra có schema:** Model trả `UP | DOWN | ABSTAIN`, lời giải thích ngắn và thông tin bất định; backend kiểm tra schema, ghi nhà cung cấp/model ID phiên bản, thời điểm request/response, fingerprint prompt, input snapshot/hash, cutoff nến, token usage và chi phí khi có. Không diễn giải con số tự khai của LLM thành `probability_up/down` đã hiệu chỉnh; mặc định `null` cho đến khi có phép đo calibration riêng. API hỏng/timeout: trạng thái lỗi minh bạch, không dự báo dự phòng giả.
4. **Đóng băng và chấm:** Persist nhận định trước khi xem nến tương lai; backend tính kết quả so với **giá mua giả định** khi horizon trưởng thành và dữ liệu đủ/gap hợp lệ. Không cho lựa chọn người cập nhật lời AI. Tách kết quả demo hồi cứu và kết quả prospective.
5. **Quyền truy cập và chi phí:** Chỉ backend local/admin bật thử nghiệm ghi/có phí; cấu hình bí mật qua env, không ghi key trong DB/log/client. Giới hạn lượt gọi/ngân sách; lưu số token dùng thực tế. Kiểm tra điều khoản dữ liệu theo bậc dịch vụ: Gemini free/paid khác nhau [2][8], OpenAI mặc định không dùng dữ liệu API để train nhưng vẫn có retention [4]; chính sách Claude theo tính năng/hợp đồng. Không khẳng định zero retention nếu chưa cấu hình/kiểm tra.
6. **Đánh giá chọn model:** Cố định phiên bản, prompt, schema, snapshot/window/horizon và tiêu chí trước thử; kiểm tra nhiều thời kỳ thị trường và so cùng baseline (ví dụ tỉ lệ đa số, luôn UP), báo số mẫu, tỷ lệ abstain, accuracy có định nghĩa, calibration nếu được kiểm định, latency và chi phí/lượt; không chọn model trên test rồi dùng test đó để tự tuyên bố thắng. Nếu không hơn baseline/không đủ dữ liệu: nói rõ không đủ cơ sở.

### Nhiều Gemini key — vận hành, không né quota

Có thể cấu hình **tối đa 10 key do người vận hành sở hữu** trong env/secret store ở backend; không ghi key vào DB, log, file docs hay frontend. Mỗi key gắn với project trong cấu hình BE để đối chiếu quota; không lưu giá trị key trong bản ghi prediction. Chọn key đang hoạt động theo vòng hoặc key chính/dự phòng; chỉ ghi key index và project alias nội bộ vào log quản trị (không vào public DTO), model ID, usage và chi phí. Key bị thu hồi/sai quyền được vô hiệu hóa và báo người vận hành; không thử đi thử lại vô hạn. Nếu không có key hợp lệ thì dừng với trạng thái chưa có API, không phát dự báo giả.

**Giới hạn quan trọng:** [Google áp quota theo *project*, không theo API key](https://ai.google.dev/gemini-api/docs/rate-limits); 10 key trong cùng project **không cho thêm 10 lần RPM/TPM/RPD**. `429 RESOURCE_EXHAUSTED` theo project/billing → tôn trọng `Retry-After`/backoff và ngân sách, không quay sang key khác để né quota; nếu dự định phân bổ nhiều project phải xác minh điều khoản và giới hạn của từng project, không dùng rotation như cơ chế lách hạn mức. Mọi request phải có trần chi phí chung; lỗi không rõ request đã được tính phí thì không tự động gửi lại sang key khác. [Hướng dẫn quản lý key Gemini](https://ai.google.dev/gemini-api/docs/api-key).

### Quyết định sản phẩm đã chốt để đưa vào kế hoạch

- **Hai BE folder theo trách nhiệm:** tự train cũ giữ chức năng, chuyển sang `application/training/` khi migration callers hoàn chỉnh; nhánh gọi API riêng `application/external_analysis/`, adapter provider ở `adapters/model_api/`. Cùng dùng snapshot, Candle, outcome, không nhân bản logic hoặc cho vote người làm nhãn train.
- **Input Gemini thử nghiệm 30m:** 6h nến `1m`/`5m` trước `t` (có thể là ngày trước nếu snapshot chứa, tuyệt đối không mượn nến sau `t`); kiểm checksum, available_at, gaps và lịch sử đủ. Thử context A toàn 6h OHLCV có thứ tự; B vài phép tính deterministic với công thức/source bars + đoạn nến cuối. Đây là cách trình bày dữ liệu, không phải huấn luyện hay “bằng chứng” dự báo. Bản nào hơn phải so bằng prospective đã khóa trước giá tương lai.
- **Kiến thức trading và link:** agent nghiên cứu nguồn **offline**, đề xuất lesson với định nghĩa/rule text/caveat ngắn và URL; trang admin cho người duyệt/sửa/từ chối; DB lưu version/status/reviewer; Gemini chỉ nhận **bản đã duyệt** và trỏ `lesson_id` + timestamp nến, backend mới gắn URL. Không để Gemini tự đi tìm link lúc dự báo. Link giải thích khái niệm, không chứng nhận pattern dự báo đúng; verifier code chỉ kiểm hợp đồng/allowlist, không thể xác nhận mọi lời giải thích tự do.
- **Hành trình UX:** Replay Điểm mua (UTC+7, 6h coverage, chart zoom/pan) → Nhận định Gemini thử nghiệm UP/DOWN/ABSTAIN và link học đã duyệt → Vote người riêng không cho AI học → Reveal `PENDING/UNSCORABLE/EVALUATED`. Snapshot cũ là **minh họa hồi cứu có nguy cơ model biết tương lai**; chỉ prospective khóa nhận định trước outcome mới đem so baseline. Admin review UI local/admin-only, không bắt sửa DB tay. Xem [plan chi tiết BE/FE/UX và 4 phase](plans/261010-external-model-api-research/plan.md).

## Tiêu chí để mở tính năng — chưa đạt

- [ ] Có định nghĩa đầu vào/nhãn cho giá mua tùy ý, horizon và gap; không lẫn output API thử nghiệm với artifact Phase 02.
- [ ] Provider key chỉ ở backend; chi phí trần, chính sách lưu dữ liệu và phân quyền ghi được kiểm tra.
- [ ] Request/response khóa trước outcome, có log phiên bản/cutoff/hash và test không rò nến sau `t`.
- [ ] Đo prospective theo từng horizon cùng baseline, số mẫu và trường hợp thiếu dữ liệu; không phát xác suất chưa hiệu chỉnh.
- [ ] UI nêu rõ “thử nghiệm” và “chưa kiểm định”, không hứa lãi hay tự động giao dịch.

## Câu hỏi còn mở

- Ngân sách API/lượt và chính sách gửi nến ra bên thứ ba có chấp nhận được không?
- Chốt quy tắc click giữa nến/gap, giá chấm ở `t+30m`, ngưỡng lịch sử đủ 6h và mức phí/trần ngân sách trước khi chạy thật; timeframe 1m/5m, đầu vào 6h và horizon thử nghiệm đầu tiên 30m đã chọn.

## Nguồn (truy cập 2026-10-10)

1. [Gemini API Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output) — JSON schema/Pydantic.
2. [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing) — bậc giá, khác biệt free/paid.
3. [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs) — JSON schema.
4. [OpenAI API data controls](https://platform.openai.com/docs/guides/your-data) — training/retention theo endpoint.
5. [Claude Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
6. [Claude API pricing](https://platform.claude.com/docs/en/about-claude/pricing).
7. [Look-Ahead-Bench, arXiv:2601.13770](https://arxiv.org/abs/2601.13770) — nguy cơ lookahead, không phải benchmark ba nhà cung cấp cho BTC Spot.
8. [Gemini API data retention](https://ai.google.dev/gemini-api/docs/zdr) — giới hạn retention/grounding, cấu hình khác nhau.
