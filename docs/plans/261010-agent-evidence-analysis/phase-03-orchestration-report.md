# Phase 03 — Agent chính điều phối và tổng hợp bài phân tích đầy đủ

## Context / trạng thái

[Plan tổng](plan.md), [Feed](phase-01-feed-hypotheses.md), [Tra nguồn / tiêu chí](phase-02-research-pattern-criteria.md), [Gate](phase-04-verification.md). **Pending.**

## Quyền và nhiệm vụ từng vai

- **Agent chính / orchestrator:** backend kiểm thứ tự, artifact và quyền tool; khởi chạy vai chuyên trách, giữ trạng thái job. Không tự xuất UP/DOWN ở bước sơ bộ hoặc bỏ research để trả nhanh.
- **Agent phân tích:** chỉ đọc feed và tạo giả thuyết/tóm tắt; không web và không outcome.
- **Agent nghiên cứu:** có Google Search + đọc nguồn được guard; đọc lại feed canonical, tra định nghĩa và điều kiện phản bác. Không ghi APPROVED lessons/rule mới và không quyền reveal.
- **Tool đối chiếu:** Python đo từng criteria, không truy cập nến sau t hoặc forward return. Đây là computation, không phải một LLM nữa “gật đầu”.
- **Agent tổng hợp:** nhận feed + giả thuyết + research/criteria + bảng match; không tự đổi số đo/nguồn và không biết vote/outcome. Viết bài với lập luận công khai, không yêu cầu raw chain-of-thought.
- Backend giữ gate vote/reveal hiện có theo plan UX; scout đọc code không chứng minh mọi gate external đã an toàn, vẫn phải nghiệm thu guards tại plan đó.

## State machine và xử lý công việc

```text
PREPARING_FEED
Enum bổ sung trong `contracts.py`:
- Thêm `RESEARCH_INCOMPLETE` và `FAILED_INTERRUPTED` vào `AnalysisStatus` enum (cùng với migration DB cho enum column nếu backend dùng type tương ứng, hoặc cập nhật mapper chuỗi).

Xử lý tiến trình và Startup Sweep:
- `external_routes.py`: Thay đổi endpoint `POST /external-analysis/jobs` từ sync HTTP 201 sang **HTTP 202 Accepted**. Endpoint ghi nhận job vào DB với trạng thái `PREPARING_FEED`, sau đó đẩy vào `BackgroundTasks` FastAPI. Worker chạy với DB session độc lập được tạo mới qua context manager, không dùng chung session của request.
- Quét dọn khi khởi động (Startup Sweep): Thêm event handler `@app.on_event("startup")` (hoặc lifespan handler) quét tất cả các jobs đang ở trạng thái trung gian (`PREPARING_FEED`, `ANALYZING`, `RESEARCHING`, `MATCHING`, `SYNTHESIZING`) và chuyển chúng về trạng thái `FAILED_INTERRUPTED` với ghi chú rõ ràng: "Tiến trình bị gián đoạn do khởi động lại server; không tự động gọi lại API có phí".
```

- INSUFFICIENT_HISTORY: feed không đạt, dừng trước provider.
- RESEARCH_INCOMPLETE: Google không thực sự search, nguồn chưa truy cập, hoặc định nghĩa trọng yếu không lấy được. Hiện các phần đã làm và phần thiếu, không có kết luận hướng cuối READY.
- FAILED: lỗi call/schema/verification khác; ghi stage lỗi và reason an toàn. Không bịa báo cáo thành công.
- ABSTAIN: **pipeline đã hoàn tất** nhưng evidence không đủ hỗ trợ hướng so với P; vẫn có bài đầy đủ chỉ rõ vì sao. Không nhầm ABSTAIN với chưa nghiên cứu hoặc lỗi.

### Chạy async bằng hạ tầng local-first

Không bắt browser giữ một HTTP request cho nhiều call dài. Tái dùng FastAPI và SQLAlchemy hiện có; không thêm Celery/Redis chỉ cho một pipeline:

1. `POST /external-analysis/jobs`: validate auth/input/budget, persist job và input bất biến, trả HTTP202 + job ID/status. Không trả READY trước khi pipeline hoàn thành. Các caller/proxy/test đang mong 200 phải migrate sang contract mới.
2. BackgroundTasks chạy worker riêng với DB session riêng; không giữ/reuse request session sau response. Giới hạn concurrency theo budget/key manager; không spawn agent không giới hạn.
3. Persist stage start/end + artifact hash/source/usage khi mỗi bước xong. GET job trả progress; frontend poll **GET read-only** khi đang chạy, dừng ở terminal state; poll không tạo job hoặc gọi model.
4. Khi process restart, job đang chạy chuyển FAILED_INTERRUPTED/cảnh báo chưa hoàn tất, không auto replay paid calls. Không hứa durable queue nếu chưa có; không thêm resume phức tạp hoặc retry vòng lặp tự động.
5. Thử lại phân tích là thao tác có phí do người dùng chủ động tạo job mới. Mở tab kết quả/reveal không restart pipeline. Stage lưu thành công của job cũ chỉ đọc lại.

Điều phối nhiều vai là nhiều lượt API: analyst, grounded research, JSON criteria extraction, synthesis; không báo tổng thành một call. Cùng provider/key manager để giữ project quota. Lưu model/prompt version và usage thực từng stage; cost chưa đo được thì null kèm lý do, không suy số tiền giả từ mock hoặc từ token-only khi có search phí riêng.

## Artifact và persistence

Bổ sung một envelope JSON có schema/version gắn job, cùng các cột trạng thái/report cần cho đọc API; không dựng một framework agent tổng quát:

```text
analysis_protocol_version: evidence-pipeline-v1
feed_ref/hash/locked_inputs
stage_records[]: stage_id/role/status/started_at/ended_at/model/prompt_version,
  input_hash/output_hash/artifact_data/usage/search_metadata/error
research_refs[], rule_versions[], criterion_results[]
report: structured sections + immutable citation/evidence IDs
final_direction: UP | DOWN | ABSTAIN (chỉ có sau gate)
probability_up/down: null
```

- Stage artifact chỉ giữ dữ liệu cần audit/reproduce; short excerpts/paraphrases được phép, không lưu whole book/raw HTML không giới hạn. Feed có recipe/hash và snapshot checksum.
- Bản ghi báo cáo và nguồn của job khóa trước vote; quay lại không cập nhật citation từ trang hiện tại làm thay nội dung lịch sử.
- Job v1 cũ không bị viết lại thành “đã chạy nhiều agent”. UI ghi “Bản phân tích cũ — chưa có quy trình nghiên cứu/đối chiếu này”; hiển thị nội dung gốc, không tạo báo cáo dài bịa từ rationale cũ.
- Scope hiện một snapshot/timeframe/job; không tự yêu cầu model mới hoặc train multi-timeframe. A/B là định dạng input, không phải hai agent chứng minh nhau.

## Báo cáo người dùng cần đọc

**Bài phân tích đầy đủ hiển thị tại bước 2**, không giấu toàn bộ trong “Chi tiết kỹ thuật”. Có tóm tắt ở đầu để định hướng đọc, nhưng không thay bài bằng tóm tắt ba câu. Độ dài theo evidence, không ép số từ hoặc thêm văn cho đủ dài.

1. **Câu hỏi và dữ liệu:** BTCUSDT, timeframe, mua tại t với giá P, horizon30m, cửa sổ6h thật, độ phủ/gap, mốc dữ liệu cuối hợp lệ.
2. **Diễn biến quan sát:** giá/khối lượng/biến động đo được, số liệu có đơn vị và candle/feature ID; không gọi diễn giải của AI là fact đã xác minh.
3. **Giả thuyết và mẫu được kiểm:** vì sao xem xét mỗi mẫu, bảng từng criteria số đo–ngưỡng–nguồn–PASS/FAIL/UNKNOWN, bối cảnh/confirmation; cả mẫu không khớp cũng hiển thị lý do.
4. **Tài liệu đã tra:** tên tác giả/tổ chức, định nghĩa/section/URL, đã đọc phần nào, chưa truy cập phần nào, nguồn ad hoc chưa duyệt hay approved revision; không nhận vơ đã đọc sách.
5. **Lập luận và phản biện:** dữ kiện ủng hộ, dữ kiện chống, cách giải thích khác, source disagreement, quan hệ giữa một mẫu và giá cuối so với P; không đếm consensus agents thành bằng chứng độc lập.
6. **Kết luận có điều kiện:** hướng thử nghiệm UP/DOWN hoặc ABSTAIN và lý do, điều kiện tại t khiến giả thuyết yếu/không đủ; không kể dữ liệu +30m chưa được phép xem. Không % khi chưa có calibration.
7. **Giới hạn và khả năng áp dụng:** khác biệt sách/thị trường/timeframe, độ lớn mẫu kiểm định còn thiếu, hồi cứu/model knowledge/web hiện tại; khớp mẫu không chứng minh accuracy/P&L.

Chọn claim vào chart để highlight các candle ID đã được phép thấy. Vùng t→t+30m vẫn che tại bước2; bài/report/tooltip không chứa outcome. Bước4 giữ mở vùng/đánh dấu mốc và bảng giá thực tế; không sửa báo cáo trước đó dựa trên kết quả để trông như dự báo đúng.

### Gate công bố report

- Required sections/criteria/source/evidence refs tồn tại và hợp lệ; số đo critical khớp Python outputs; citations thực sự có trong retrieved artifacts, không chỉ URL có vẻ tồn tại.
- Source excerpts và deterministic computations được phân biệt với AI inference. Semantic interpretation không tự chứng minh hoàn toàn bằng IDs; rubric/human review và hạn chế tự động vẫn được công khai.
- Critical claim thiếu provenance hoặc contradiction chưa xử lý: không cho direction UP/DOWN đạt READY; trả trạng thái thiếu hoặc ABSTAIN thích hợp. Không sửa claim bằng một fake evidence hoặc quote không có trong nguồn.
- READY nghĩa hoàn thành quy trình và báo cáo đạt gate, **không phải dự báo đã chứng minh đúng**. Điểm đúng/sai chỉ do outcome ở bước4.

## File khi triển khai / ownership

| File / khu vực | Thay đổi |
|---|---|
| `application/external_analysis/service.py` | Orchestrator async job/role calls, stage transitions, report lock; giữ vote/reveal tách biệt |
| `contracts.py`, `verifier.py` | Stage/report/evidence schema và kiểm refs/provenance; migrate exported callers |
| `adapters/model_api/gemini_adapter.py` | Role-specific request/parser, search text/JSON normalization riêng; usage/budget thật |
| `application/external_analysis/research_agent.py` | Per-job research, không chỉ catalogue lessons |
| `adapters/db/models.py`, `repository.py`, `backend/alembic/versions/` | Persist envelope/stages/report/versions, nullable old metadata, không rewrite job cũ |
| `api/external_routes.py` | HTTP202 create + GET progress, auth, error-safe payload |
| `frontend/src/features/replay/external-types.ts`, server proxies | Contract progress/report, không browser key hoặc backend computation |
| `frontend/src/features/replay/replay-player.tsx` | Hiển thị tiến trình từng vai, bài/report/citations đầy đủ; UI owner của plan UX tích hợp |

Một integration owner giữ service/contracts/model adapter; các agent triển khai không ghi cùng file đồng thời. Chart/mask/auto-result vẫn thuộc plan UX; plan này sở hữu report backend và schema, không tạo renderer chart khác.

## Checklist

- [ ] Main bắt buộc đi đủ feed→hypothesis→research→match→synthesis→validate trước hướng cuối.
- [ ] Có stage artifacts/usage thật, Google trace/nguồn thật, criteria đo bằng Python.
- [ ] Bài tiếng Việt đầy đủ có phản biện/giới hạn, không chỉ một câu hoặc ba câu.
- [ ] Search lỗi/ABSTAIN/FAILED_INTERRUPTED khác nhau và UI giải thích đúng.
- [ ] Report cũ bất biến, không tự nâng thành pipeline mới; mở kết quả không call provider.
