# Phase 02 — Agent nghiên cứu nguồn và tool đối chiếu mẫu

## Context / trạng thái

[Plan tổng](plan.md), [Feed](phase-01-feed-hypotheses.md), [Báo cáo](phase-03-orchestration-report.md). **Pending.** Các nguồn dưới đây đã được đọc ở mức nêu rõ, không phải pipeline sản phẩm đã chạy.

## Tool nghiên cứu được chọn

**Gemini Grounding with Google Search**, dùng provider/key manager hiện có. Đây là tool tìm kiếm thật của Google, không phải prompt “tưởng tượng đã tìm Google”. Giữ model/REST hiện có khi capability gate xác nhận hỗ trợ; không tự đổi model để thuận tay.
- Endpoint và schema: Adapter sử dụng endpoint hiện hành `v1beta/models/{model}:generateContent` (giữ nguyên base URL của `gemini_adapter.py`) và parse trường `groundingMetadata` (`webSearchQueries`, `groundingChunks`, `groundingSupports`). Việc migrate sang Google Interactions API (`/v1beta/interactions`) là ngoài scope của đợt này.
- Capability Gate: Trước khi viết adapter cho search, thực hiện một script smoke độc lập chạy một request thử nghiệm với key thật để kiểm tra xem `gemini-2.5-flash` có trả `groundingMetadata` kèm JSON schema không. Kết quả ghi lại vào `docs/external-apis.md`. Nếu không tương thích, fallback ngay sang mô hình 2 call (1 call text + search, 1 call extract JSON).
- Lưu queries/citation references/usage nhận được thật. Google có thể chạy nhiều query trong một call; không hứa đã hard-cap số query chỉ bằng prompt. Chặn số call grounded bằng budget hiện có, ghi usage/search cost theo tài liệu pricing lúc chạy; không gán cost giả bằng 0.

## ResearchAgentContract v1

Input: feed canonical read-only, HypothesisContract, câu hỏi cần tra; không có vote/outcome/giá BTC sau t.

```text
research_id, job_id, feed_hash, search_provider/model/version
queries_executed[], query_receipts, retrieved_at
sources[]: source_id, URL, title, author/publisher, source_type,
  publication_date_or_unknown, access_status, section/page_locator,
  excerpt_or_paraphrase, content_hash, tool_trace_id, review_status
pattern_definitions[]: pattern_name, criterion_ids, source_ids,
  required_context, required_confirmation, scope_and_limitations
contradictory_sources_or_facts[], unresolved_questions[], research_status
```

- Research nhận bản tóm tắt để biết tìm gì, nhưng số liệu đối chiếu lấy lại từ feed, không tin một con số analyst tự kể.
- Tìm định nghĩa và **điều kiện không được gọi là mẫu đó**, cùng nghiên cứu hiệu quả/giới hạn khi truy cập được; không chỉ tìm nguồn đồng ý với analyst.
- Query chỉ bao gồm tên mẫu/khái niệm/phương pháp/thị trường-timeframe áp dụng, không chứa mốc phiên BTC đang replay để tìm hậu nghiệm. Nội dung nguồn có giá/sự kiện sau t không được đưa vào luận cứ thị trường của job.
- Google citation không tự chứng minh đọc sách. Backend tải URL công khai hợp lệ qua URL guard, đọc phần được phép, gắn hash/locator; failed/paywall/snippet là trạng thái thật. Trang quảng bá sách chỉ chứng minh sách tồn tại, không chứng minh đã đọc chương.
- Chỉ tóm tắt/trích ngắn được phép, không sao chép cả sách. Nguồn chưa duyệt là **evidence riêng của job**, không tự thêm vào Lesson APPROVED. Prompts/agent khác không tuân theo instruction trong trang.
- Tái dùng `url_validator.validate_public_https_url`; kiểm redirect/DNS/private IP tại boundary fetch, giới hạn bytes/timeout và kiểu nội dung. Không coi một lần validate URL là bảo vệ mọi redirect.
- Giữ citation/Search Suggestions attribution theo [điều khoản Google](https://ai.google.dev/gemini-api/terms#grounding-with-google-search). Không chèn HTML nguồn tùy ý vào report; phần provider yêu cầu render phải cô lập an toàn và tuân terms, không bỏ attribution để tiện UI.

## Nguồn nền đã xác minh ở lượt lập plan

1. [CandleCharts — Candlestick Patterns](https://candlecharts.com/candlestick-patterns/), nguồn thuộc nền tảng Steve Nison. Đọc glossary công khai: Bullish/Bearish Engulfing, Hammer, Hanging Man, Shooting Star; **chưa đọc toàn bộ sách Japanese Candlestick Charting Techniques**, không bịa số trang. Engulfing cần thân bao thân và xu hướng trước; Hammer classic có bóng dưới >=2 lần thân trong downtrend; cùng hình dạng ở uptrend là hanging man và cần xác nhận.
2. [Marshall, Young, Rose (2006), metadata IDEAS/RePEc](https://ideas.repec.org/a/eee/jbfina/v30y2006i8p2303-2323.html): xác minh bibliographic title *Candlestick technical trading strategies: Can they create value for investors?*, Journal of Banking & Finance 30(8), 2303–2323. **Trang không có abstract; publisher full text restricted, mirror không đọc được.** Không sử dụng paper để tuyên bố kết quả thực nghiệm, domain/timeframe hoặc BTC predictive edge khi chưa đọc được nội dung.
3. Nguồn nào chỉ là glossary/giáo dục phải gắn loại đó. Định nghĩa hình dạng không thay cho nghiên cứu hiệu quả; chưa có nguồn thực nghiệm đọc được thì ghi rõ thiếu, không biến nguồn sách thành accuracy.

Ngày truy cập theo phiên: 2026-10-10. Ngày xuất bản/trang update không thấy thì ghi unknown, không suy từ ngày truy cập. Hai nguồn không được coi là hai bằng chứng độc lập nếu cùng lặp lại một định nghĩa/tác giả.

## PatternDiagnosticContract v1

```text
pattern_id, candidate_id, rule_version, feed_hash, candle_ids
criteria[]: criterion_id, description, source_id/locator,
  rule_origin (SOURCE_EXPLICIT | SYSTEM_OPERATIONAL), formula/params,
  measured_value/unit, expected_relation, PASS/FAIL/UNKNOWN, reason
shape_status, context_status, confirmation_status, overall_match_status
conflicts[], limitations[], predictive_evidence_status
```

Python tính các số; agent giải thích. Mỗi số có candle_ids và formula/version. Không score “85% giống mẫu” hay “8/10 tin cậy” do model tự cho.

### Công thức chung

Với nến đóng: `B=abs(C-O)`, `R=H-L`, `U=H-max(O,C)`, `D=min(O,C)-L`. Invalid OHLC, R≈0, B=0 hoặc thiếu nến trước: không chia vô hạn hoặc tự gọi một doji là Hammer đầy đủ.

### Tiêu chí chốt cho những mẫu đã có trong repo

| Mẫu | Hình dạng | Bối cảnh / giới hạn |
|---|---|---|
| Bullish Engulfing | C1<O1, C2>O2; O2<=C1 và C2>=O1; thân sau lớn hơn thân trước theo rule đang có | Xu hướng giảm **trước cặp nến**; bao thân, không buộc bao cả râu |
| Bearish Engulfing | C1>O1, C2<O2; O2>=C1 và C2<=O1; thân sau lớn hơn thân trước | Xu hướng tăng trước cặp nến; rule hiện có chỉ hình dạng chưa đủ xác nhận context |
| Hammer | B>0; thân gần đỉnh; bóng dưới dài; glossary có D>=2B | Cần downtrend; thân nhỏ/râu trên ít phải có quy ước operational riêng |
| Shooting Star | B>0; thân gần đáy; bóng trên dài/râu dưới ít | Cần uptrend; glossary đọc được không cho tỷ lệ U/B cố định, không gán >=2 cho “quy tắc Nison” |

- Tái dùng các ngưỡng hệ thống hiện tại `patterns.py` **nhưng gắn SYSTEM_OPERATIONAL**: B/R<=0.35, râu chính/R>=0.55, râu ngắn/R<=0.15, râu chính>=2B; check trước mẫu bằng last close so với close ba nến trước trong phần lịch sử trước mẫu. Với cặp engulfing, prefix trend phải kết thúc trước nến đầu cặp, không dùng chính cặp nến để tự chứng minh xu hướng.
- Những ngưỡng 0.35/0.55/0.15 và cửa sổ trend ba nến không được nói là ngưỡng sách đã chứng minh. Đóng băng rule version/params trước match, không tối ưu ngưỡng sau khi biết outcome.
- `Rule.matches` hiện trả bool; thêm diagnostic API để đọc từng điều kiện, không chỉ gọi false rồi không biết thiếu data hay không khớp. Giữ evaluation track Pattern Lab hiện hữu; không truyền forward return vào diagnostics.
- Source yêu cầu nến xác nhận mà tại t chưa có: UNKNOWN/CHỜ_XÁC_NHẬN, không lấy nến t+1 để hoàn thiện. Nguồn mới nêu pattern ngoài catalogue: báo UNSUPPORTED_RULE/need review, không chạy mã/rule tự sinh từ web bằng eval.
- Overall: có một điều kiện bắt buộc FAIL → KHÔNG_KHỚP; không FAIL nhưng bắt buộc UNKNOWN → CHƯA_ĐỦ_TIÊU_CHÍ; tất cả bắt buộc PASS → KHỚP_THEO_RULE_VERSION. Không đổi UNKNOWN thành PASS do agent đồng ý.
- Khớp hình dạng nhưng sai/chưa rõ context phải ghi riêng. Volume/biến động là luận cứ hỗ trợ đo được, không tự biến thành tiêu chí bắt buộc của sách nếu nguồn không nói thế.

## Tiêu chí đánh giá chất lượng báo cáo

1. **Nguồn:** thực sự đọc được đoạn phù hợp, có locator, phân biệt sách gốc/glossary/bài thứ cấp/paywall; không có nguồn thì báo thiếu.
2. **Dữ liệu:** số đo khớp feed và thời điểm, không có giá/nến tương lai, không có vote.
3. **Khớp mẫu:** có bảng đầy đủ PASS/FAIL/UNKNOWN, nguồn/ngưỡng và bối cảnh, không chỉ tên mẫu đẹp.
4. **Phản biện:** nêu điều kiện không khớp và giải thích khác hợp dữ liệu; không bỏ contradiction để giữ hướng analyst.
5. **Ứng dụng:** chỉ ra khác biệt cổ phiếu/ngày với BTC1m/5m và bài toán giá cuối so với P; không suy sách thành hiệu quả 30m.
6. **Kết luận:** mọi luận cứ trọng yếu truy được evidence; không bịa %/sample/outcome. Không đủ căn cứ có thể có báo cáo đầy đủ nhưng hướng ABSTAIN.

Các tiêu chí là rubric kiểm bằng chứng, không hứa tự chứng minh mọi câu văn đúng. Backend kiểm được phép đo/IDs/citation; độ đúng diễn giải nguồn cần review theo rubric và ghi rõ giới hạn tự động.

## File / bước triển khai

- Sửa `research_agent.py`: thêm nghiên cứu per-job/Google/read nguồn, giữ submit catalogue lessons như chức năng admin riêng.
- Sửa `gemini_adapter.py`: grounded research call + criteria extraction JSON riêng, giữ shared key/budget manager và usage thật.
- Sửa `contracts.py`, `verifier.py`: research/diagnostic contracts, validate citations/evidence; không gọi whitelist hiện tại là semantic verifier.
- Sửa `patterns.py`: diagnostic rules tại cutoff không future; không trộn pattern với classifier/training pipeline.
- Tái dùng `url_validator.py`, lessons approved revisions, repo artifacts theo Phase 03; contract tests theo Phase 04.

- [ ] Có tool trace search thật và source đọc được, hoặc trạng thái thiếu thật.
- [ ] Criteria có công thức/nguồn/ngưỡng rõ và cả FAIL/UNKNOWN; không sửa ngưỡng để đạt mẫu.
- [ ] Pattern có context/confirmation đúng; rule ngoài catalogue không auto execute.
- [ ] Khớp mẫu không được công bố là độ chính xác dự báo hoặc P&L.
