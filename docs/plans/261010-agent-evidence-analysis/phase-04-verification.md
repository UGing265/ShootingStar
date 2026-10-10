# Phase 04 — Gate nghiên cứu, báo cáo và vận hành

## Context / trạng thái

[Plan tổng](plan.md), [Feed](phase-01-feed-hypotheses.md), [Research/criteria](phase-02-research-pattern-criteria.md), [Điều phối/report](phase-03-orchestration-report.md).

**Pending. Chưa chạy feature hoặc các lệnh dưới đây.** Không nghiệm thu bằng việc agent nói đã nghiên cứu hoặc bằng bài viết dài.

## Contract regressions bắt consumer-visible bugs

- Cửa sổ6h canonical đúng cutoff/latency, t/P/h/timeframe; thay nến tương lai không ảnh hưởng bất kỳ input stage nào; vote/outcome vắng mặt trong feed và research.
- Hypothesis không được trở thành final direction trước research/match/validation; mất bất kỳ artifact/source critical thì không READY.
- Source có URL nhưng fetch không đọc được/paywall/snippet không được ghi “đã đọc sách”. Citations ngoài retrieved refs bị từ chối; excerpt do model bịa không được xác thực.
- Google tool không chạy/không trả trace: RESEARCH_INCOMPLETE, không fallback sang one-shot conclusion. Hết budget/quota thì dừng đúng stage, không xoay key lách quota.
- Matcher: cùng hình dáng nhưng trend ngược; engulfing bao râu nhưng không bao thân; boundary ratios; B=0/R=0; thiếu prefix; xác nhận sau t; unknown rule; criteria FAIL/UNKNOWN không được tổng hợp thành full-match.
- Rule params gắn source-explicit/system-operational đúng; số đo/report dùng cùng feed/rule version, không mutate theo outcome. Sách khác timeframe không thành bằng chứng BTC30m đã kiểm định.
- Job/report/stages persist→restart→GET không mất evidence/versions hoặc sửa báo cáo cũ. Job đang chạy khi restart ghi interrupted thật, không tự thực hiện lại paid call.
- Source có prompt injection, redirect private/DNS rebind/oversize nội dung: không có tool execution hoặc private network fetch, không lộ secrets trong API/report.
- Report đầy đủ nhưng ABSTAIN vẫn hợp lệ; thiếu nghiên cứu không gọi ABSTAIN như đã hoàn tất. Score accuracy không đưa ABSTAIN/failed vào predicted direction giả.
- Gate Prospective Reveal: Bổ sung contract test kiểm tra `reveal_outcome` bị từ chối và giữ trạng thái `PENDING` nếu mốc `t + horizon` chưa tới HOẶC nến chứa mốc đó chưa đóng/chưa khả dụng.
Tái dùng `backend/tests/test_external_analysis.py`, `test_lessons.py`, `test_pattern_lab.py`, `test_api_and_ui.py`; thêm test theo convention khi các behavior mới cần cô lập. Không permanent test nguyên văn prompt, count sentences/source lines, wiring/forwarding hoặc mock echo. Mock provider chỉ kiểm lỗi/boundary offline, không làm bằng chứng tool tìm Google thật.

## Lệnh nghiệm thu sau triển khai

Dùng environment backend đã cài và PostgreSQL test DB riêng theo `docs/backend/README.md`; không test vào DB vận hành. Schema migration phải được chạy trên test DB riêng trước. Điều kiện an toàn DB theo gate plan UX.

```powershell
python -m pytest backend/tests/test_external_analysis.py backend/tests/test_lessons.py backend/tests/test_pattern_lab.py backend/tests/test_api_and_ui.py
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Không commit/push tự động. Feature phải smoke thật ngoài test.

## Smoke thật và review report

1. Snapshot thật đủ6h; job mới khóa t/P/h. Dùng provider/key và search capability đã cấu hình; không hardcode key/model mới.
2. Quan sát HTTP202/GET tiến trình: feed→phân tích→nghiên cứu→đối chiếu→tổng hợp→kiểm report. Không output hướng cuối ở stage đầu.
3. Có Google `webSearchQueries`/grounding refs và source đọc thật; schema parser/search combi tương thích model chọn. Bắt payload adapter ở backend để chứng minh không future; network browser không quan sát provider input.
4. Đọc bài cuối theo rubric Phase02: chọn các claim trọng yếu, mở nguồn/nến, kiểm số đo/formula/rule và phần FAIL/UNKNOWN. Nguồn chỉ glossary không được gọi đã đọc sách; không gán tài liệu chưa đọc là empirical evidence.
5. Negative smoke: nguồn inaccessible, Google disabled/quota, candidate rule unsupported, contradiction hoặc missing candle. Hệ thống nêu thiếu/thất bại, không fake READY hoặc kéo dài prose để che thiếu evidence.
6. Review một ca đúng hình nhưng sai trend, một ca chưa có confirmation và một ca P khác giá hiện tại. Agent tổng hợp phải phân biệt nguồn/shape/context và giá cuối so với P.
7. UI bước2 có bài đầy đủ và chart vùng tương lai che; nến/volume/tooltip/report không lộ kết quả. Vote bước3 xong tự bước4; reveal/mở lại không gọi lại research/Gemini, report trước đó không được chỉnh theo outcome.
8. Artifact mẫu lưu ở report path của plan sau triển khai, dữ liệu thật có anonymized safe IDs/trace; token/search phí chỉ ghi đo được. Chưa có key hoặc source thật thì gate tương ứng vẫn mở, không lấy mock thay.

## Ba cấp kết luận được phép

- **Hoàn thành workflow:** đủ stage/tool/source/report và evidence của việc đó. Không chứng minh forecast đúng.
- **Nhận diện mẫu theo rule:** criteria/timeframe/context đạt phiên bản cụ thể. Không chuyển thành xác suất hay lợi nhuận.
- **Hiệu quả dự báo:** phải follow plan prospective hiện có, outcome thật sau horizon, baseline và sample coverage/uncertainty. Không nghiệm thu accuracy chỉ bằng một mẫu match hoặc nhiều agent đồng ý; không mở thêm benchmark giả trong lượt này.

## Tài liệu / cutover

- Đồng bộ plan API/UX: không còn một request, research chỉ ngoài luồng hoặc giới hạn ba câu như yêu cầu hiện hành. Đánh dấu chúng là thiết kế cũ, không ghi đã triển khai multi-agent từ kết quả test cũ.
- Sau smoke thật cập nhật `docs/backend/README.md`, `docs/frontend/README.md`, `docs/external-apis.md`: search capability, HTTP202/stages, usage/cost limitations, nguồn/rule/report provenance, hồi cứu warning.
- Các status/checklist chỉ completed khi có evidence chạy đúng; xóa smoke scaffold của lượt triển khai, không sửa source trong lượt lập plan.

## Checklist

- [ ] Contract tests riêng và typecheck/build cần thiết pass, có output thật.
- [ ] Trace Google/đọc nguồn thật, matcher có PASS/FAIL/UNKNOWN, report full có phản biện.
- [ ] Human review rubric kiểm claim critical, không bịa sách/link/page/accuracy.
- [ ] Negative cases thiếu nguồn, missing data, unsupported pattern và interrupted job trung thực.
- [ ] Không future trong inputs/report trước reveal, không paid calls do GET/reveal.
- [ ] Docs/plans cập nhật theo evidence, gate prospective accuracy giữ riêng.
