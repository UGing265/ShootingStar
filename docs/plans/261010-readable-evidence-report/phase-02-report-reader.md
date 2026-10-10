# Phase 02 — Giao diện đọc báo cáo và nghiệm thu

## Context và trạng thái
[Plan](plan.md), [contract trình bày](phase-01-presentation-contract.md), [Design](../../DESIGN.md). Priority P1; In Progress (Implementation Verified / Acceptance Gates Pending); sau Phase 01.

## Files
Root tuyệt đối: `D:/AShiroru/ProgramCode/Project/Team/ShootingStar/`.
- Modify `frontend/src/features/replay/replay-player.tsx`: thay khu báo cáo bằng component chuyên biệt; không đổi polling, retry, chart, vote/reveal.
- Modify `frontend/src/features/replay/external-types.ts`: typed feed tối thiểu khớp `feed_contract_to_dict`; guard dữ liệu cũ thiếu field, không cast mù.
- Create `frontend/src/features/replay/evidence-report.tsx`: dữ liệu canonical, bài viết, technical details.
- Create `frontend/src/features/replay/report-format.ts`: format thuần, glossary nhãn chỉ trình bày theo Phase 01. Không tính lại feature.
- Create `frontend/src/features/replay/evidence-report.module.css`: body gần 17px/line-height ≥1.5, caption ≥14px, content max-width khoảng 75ch; nền parchment, border hairline, không shadow.
- Modify `frontend/package.json`, `frontend/package-lock.json` nếu thêm Markdown parser. Chọn parser duy trì phổ biến, mặc định escape HTML (ưu tiên `react-markdown`); chỉ bật GFM nếu cần bảng trong bài. Xác minh docs/version tương thích trước cài; không viết parser Markdown bằng regex.
- Modify `docs/frontend/README.md`, `docs/backend/README.md` sau smoke: cách đọc báo cáo, UTC+7/ratio, giới hạn bản lưu cũ, không auto-call model.

## Luồng người đọc
1. Giữ nhãn thử nghiệm/caveat hồi cứu và rationale hiện có; không tạo tóm tắt AI thứ hai.
2. “Câu hỏi và dữ liệu”: câu mô tả mục tiêu từ symbol/timeframe/t/P/horizon job; phạm vi 6h/candle count/quality từ feed đã lưu. Bảng `Chỉ số | Giá trị | Ý nghĩa` từ features canonical.
3. Sáu phần còn lại hiển thị đầy đủ bằng Markdown an toàn, tiêu đề do UI quản lý. Đoạn/list/bold/links rõ, không chỉ `<p>` giữ xuống dòng.
4. “Chi tiết kỹ thuật” đóng mặc định: model/version/hash, feature IDs/giá trị thô và nguyên văn section 1 cũ; người dùng mở được bằng bàn phím. Không sửa DB/raw text.
5. Thiếu feed: báo “Không có dữ liệu chi tiết đã lưu”, vẫn render bài gốc và glossary; không tái tính từ snapshot hoặc tự xin dữ liệu tương lai. Thiếu phần: nêu phần chưa có, không ép đủ bảy đoạn giả.

## Job cũ và giới hạn
- Section 1 chính thay bằng canonical summary/table, nguyên văn nằm trong technical details để không mất bằng chứng.
- Với sáu phần cũ: format Markdown, dịch tên feature đã biết tại node text bằng mapping và ngày giờ chỉ khi khớp chính xác epoch field có trong feed/job. Không chạm URL, citation ID, code hoặc hash; không regex mọi số 13 chữ số.
- Không đổi số trong prose bằng suy đoán. Đơn vị/ratio mơ hồ giữ nguyên và giải thích bằng glossary/đối chiếu canonical, không gắn `%` tự tiện. Điều này không phải dịch lại ngữ nghĩa bài cũ.
- Không ẩn câu phản biện, đoạn dài hoặc điều kiện bất lợi để “dễ đọc”. Không cần LLM call nào để mở/refresh báo cáo cũ.

## An toàn nội dung
- Không `dangerouslySetInnerHTML`, không raw HTML parser/plugin. Không render ảnh/iframe/script/styles từ model.
- Link chỉ HTTPS công khai hợp lệ; chặn javascript/data/file và link tương đối nội bộ từ model. Link nguồn mới mở tab có `noopener noreferrer`.
- Nội dung thiếu/malformed là text an toàn hoặc thông báo thiếu; không bỏ toàn bộ báo cáo khi một trường lỗi. Không fetch arbitrary URL khi render.
- Nếu không có backend-enforced public URL validation ở field bài viết, frontend ít nhất giới hạn scheme và host localhost/private literals; xác minh DNS/SSRF là boundary backend fetch, không giải bằng JS.

## Bước triển khai
1. Khớp typed feed với serializer; reuse formatter UTC+7 của Replay hoặc trích xuất phần dùng chung cho báo cáo, không thay chart/input datetime trong scope này.
2. Viết renderer và format số theo unit/mapping. Canonical feature giữ nguồn; feature không biết đưa technical details có nhãn chưa có mô tả.
3. Tích hợp báo cáo trong `replay-player.tsx`; giữ warning/status/source access và citations. Không lặp tiêu đề section mới; heading cũ chỉ bỏ nếu đúng prefix tiêu đề của phần, không cắt paragraph tùy tiện.
4. Responsive: bảng cuộn trong container riêng hoặc chuyển nhãn dạng danh sách, không làm page tràn ngang; URL dài wrap; focus-visible/summary accessible.
5. Smoke bề mặt thật và test boundaries; cập nhật docs sau bằng chứng.

## Nghiệm thu
- Dùng một job thật đã lưu có hình thức giống ảnh người dùng. Main section 1 không `latest_close_vs_p_pct`, epoch `... ms`, `**...**` hoặc `-5e-06`; technical details vẫn truy được raw.
- Ratio `0.001768` → `0,1768%`; `-5e-06` → `-0,0005%`; `1` thân nến → `100%`; volume `969.9297` → `969,9297 BTC`. Không coi “100% thân” là “100% thắng”.
- Giờ UTC+7 nhất quán chart/job. Dùng dữ liệu job đã lưu kể cả form chọn snapshot khác.
- Giữ sáu phần lập luận còn lại và nguồn dẫn, paywall/snippet/unknown access không bị nâng thành đã đọc sách.
- Browser 1280px và 390px: đọc/scroll/mở technical details/click nguồn/bàn phím; ảnh trước/sau. Quan sát network: refresh/đổi tab/mở details chỉ GET cần thiết, không POST job/vote/reveal và không Gemini call mới.
- Browser nội dung độc hại thử trong harness cục bộ: script không chạy, javascript link không click được, HTML/ảnh không render. Không lưu fake output vào production.
- `npm run typecheck`, `npm run build` trong `frontend/`; backend contract tests theo Phase 01. Permanent tests chỉ thêm cho sai đơn vị/timestamp/unsafe links/immutability thực sự có rủi ro, theo suite hiện có; không tạo snapshot test khóa wording.

## Checklist
- [x] Canonical section 1 + Markdown an toàn + details hoạt động với job cũ/mới.
- [x] Mobile, số nhỏ âm, timezone, thiếu dữ liệu, source links kiểm chứng.
- [x] Không gọi lại provider, không sửa dự báo/outcome.
- [x] Typecheck/build/backend tests có output; docs cập nhật sau smoke.

## Rủi ro và bàn giao
Prompt không bảo đảm accuracy; UI readable không nghiệm thu nghiên cứu thật hoặc dự báo hiệu quả. Không đánh dấu plan complete chỉ dựa trên build. Khi bàn giao ghi job ID, phiên bản, lệnh đã chạy và giới hạn nào chưa quan sát.
