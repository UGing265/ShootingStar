# Phase 01 — Hiển thị bài phân tích có nguồn và lập luận

## Context và trạng thái

[Plan tổng](plan.md), [Pipeline điều phối–nghiên cứu](../261010-agent-evidence-analysis/plan.md), [Chart](phase-02-chart-preview.md). **Complete.** Đã cải thiện nhận định AI bằng tiếng Việt rõ ràng, giải thích cụ thể mốc t (UTC+7), giá mua P, horizon 30m, cảnh báo thử nghiệm, cùng thông báo minh bạch cho các trạng thái NO_MODEL và ABSTAIN.

Yêu cầu mới thay thiết kế ban đầu chỉ sửa rationale/prompt và giới hạn ba câu. **Không còn giới hạn ba câu, không lấy một agent trả kết luận ngắn làm đầu ra đã đủ.** Backend report/nguồn/criteria thuộc plan pipeline; phase này tích hợp hiển thị, không tạo một pipeline khác.

## Hiện trạng đã đọc từ source

- UI hiện trộn `strictly`, `Zero-Lookahead Causal Window`, `READY`, `RETROSPECTIVE`, “Chưa hiệu chuẩn” với rationale nguyên văn.
- Prompt hiện đã yêu cầu tiếng Việt và giới hạn3 câu. Ảnh vẫn tiếng Anh, chưa xác định job cũ hay response không tuân thủ; không khẳng định chỉ thiếu lệnh “viết tiếng Việt”.
- External service hiện một call và verifier chỉ lọc schema/IDs/timestamps; chưa semantic-verify lời giải thích hoặc đọc sách per-job.
- DTO external chưa có score backend như nhánh local; các trạng thái đang nghiên cứu không được nhầm READY/ABSTAIN hoặc forecast sai.

## Nội dung người dùng nhìn thấy ở bước 2

1. **Tiến trình đang làm gì:** chuẩn bị feed → phân tích → tra tài liệu → đối chiếu → viết bài → kiểm báo cáo. Hướng cuối chưa có thì không hiển thị UP/DOWN giả. GET poll chỉ đọc progress, không gọi lại Gemini.
2. **Tóm tắt kết luận** sau terminal report: nghiêng tăng/giảm so với giá P sau horizon hoặc không đủ căn cứ. Tóm tắt giúp định hướng đọc, không thay bài chi tiết. READY nghĩa pipeline hoàn tất, không chứng minh accuracy.
3. **Câu hỏi/dữ liệu:** t UTC+7, P, timeframe, horizon, cửa sổ6h/bounds thật và gap. Giá dùng chấm là giá đóng cửa của nến hệ thống chọn; bước4 ghi riêng mốc horizon/thời gian đóng nến, không gọi đó là giá chính xác từng giây.
4. **Bài phân tích đầy đủ:** diễn biến đo được; các mẫu đã xem xét; nguồn đã đọc; bảng tiêu chí PASS/FAIL/UNKNOWN với số đo–ngưỡng–source; lập luận ủng hộ và phản bác; cách hiểu khác; kết luận có điều kiện và giới hạn. Không giấu bài vào details, không rút xuống ba câu hoặc kéo dài văn không có evidence.
5. **Tương tác bằng chứng:** mỗi luận điểm/candidate có nến/feature ID; click highlight nến quá khứ trên chart. Hover/chi tiết hiển thị giá mở/cao/thấp/đóng và khối lượng. Numeric timestamps chuyển UTC+7, không epoch trong câu chính.
6. **Nguồn:** title/tác giả/URL/section đã đọc, loại sách/glossary/thứ cấp, access/paywall, nguồn ad hoc chưa duyệt hoặc approved revision. Chỉ search snippet thì không gọi đọc sách; link thật từ retrieved evidence, không lấy URL AI tự bịa.
7. **Cảnh báo luôn thấy:** đây là nhận định thử nghiệm, chưa có bằng chứng về độ chính xác; AI và nguồn web hiện tại có thể có thông tin sau thời điểm lịch sử. Với prospective dùng cảnh báo phù hợp, không gọi report như này historical OOS sạch.
8. Model từng vai/prompt version/A-B/usage/stage trace ở **Chi tiết kỹ thuật**. A/B mô tả cách đóng gói dữ liệu, không gọi hai bằng chứng độc lập hoặc nói B tốt hơn.

Chart bước2 giữ điểm mua (t,P), quá khứ bên trái và vùng t→t+30m che; chỉ mở ở bước4 khi backend đủ điều kiện. Full report không được chứa giá/outcome/nến tương lai.

## Trạng thái và bản cũ

- RESEARCH_INCOMPLETE: chưa có source/tool trace đủ, báo đã làm gì/thiếu gì; không lấy một rationale ngắn thay bài rồi ghi “đã nghiên cứu”.
- ABSTAIN: đã hoàn tất nghiên cứu/đối chiếu nhưng chưa đủ căn cứ cho hướng; vẫn có bài đầy đủ, không chấm là dự đoán SAI.
- Failed/interrupted: nêu stage lỗi và dữ liệu đã giữ, không hứa đã hoàn tất. Nút tạo job phân tích lại có phí chỉ người dùng chủ động.
- Job v1 cũ: nguyên văn rationale/model/prompt giữ nguyên; nhãn **“Bản cũ chưa có quy trình nghiên cứu và đối chiếu này; lý do có thể còn tiếng Anh.”** Không dựng bài dài hoặc stage trace giả từ một câu cũ.
- Nhánh local NO_MODEL: **“Chưa có mô hình đã được kiểm tra cho câu hỏi giá tương lai cao/thấp hơn giá mua bạn chọn. Bạn vẫn có thể chọn hướng và xem kết quả thực tế.”** Giải thích OOS/cutoff/point-price đưa vào details, không giả có research pipeline.

## Files / ownership khi triển khai

- `frontend/src/features/replay/replay-player.tsx`: progress, full report, criteria/source/claim-to-chart, empty/error/legacy states.
- Nếu cần tách UI để tránh parent quá lớn: tạo `frontend/src/features/replay/analysis-report.tsx` dùng DTO đã có, chỉ renderer báo cáo; không sao chép tính toán backend.
- `frontend/src/features/replay/external-types.ts` và server proxies: stage/report/research/citation types, HTTP202+GET status; tích hợp contract từ plan pipeline.
- `frontend/src/app/(work)/replay/page.tsx`: mô tả dễ hiểu, không claim “bảo chứng” suy luận không nhìn trước cho model hồi cứu.
- Backend `contracts.py/service.py/gemini_adapter.py/verifier.py/research_agent.py` do plan pipeline sở hữu: phase UX không tự sửa một prompt v2 ba câu nữa. Migrate callsites đồng bộ, không để worker hai plan ghi cùng file.
- Score external `ai_is_correct/user_is_correct` nullable do backend trả theo gate kết quả đã có trong plan UX; browser không tính lại hướng/đúng-sai. DB/report migrations theo plan pipeline, không sửa rationale cũ.

## Các bước

1. Chờ schema/stages/report đã chốt của pipeline; mock DTO chỉ cho test giao diện có nhãn, không production flow.
2. Tích hợp create HTTP202 / GET progress; abort/ignore response job cũ khi reset/đổi job; chỉ poll read-only.
3. Render bài đầy đủ bằng các section/criteria backend cung cấp; số đo và source ref giữ nguyên, không frontend tự tóm tắt lại hoặc tự dịch bằng câu giả.
4. Tách measurement đã tính, định nghĩa đã đọc và AI inference trong nhãn. ID/source hợp lệ không đủ chứng minh diễn giải đúng; caveat rõ.
5. Click claim highlight nến đúng job/cutoff; không fetch tương lai hoặc mở vùng che qua tooltip/report.
6. Terminal report/ABSTAIN/lỗi mới cho luồng chọn dự đoán phù hợp; khi đang nghiên cứu chưa hiển thị kết quả thị trường để tránh báo cáo bị outcome tác động. Nhánh không AI vẫn cho người xem thị trường theo gate vote đã có.
7. Khi reveal/retry kết quả không gọi lại analysis/research, không cập nhật bài trước đó dựa trên giá thực tế.

## Checklist / nghiệm thu

- [ ] Thấy tiến trình các vai; không một câu từ main trước nghiên cứu trở thành kết luận cuối.
- [ ] Có bài đầy đủ, criteria đo được, nguồn thật, phản biện và giới hạn; không giới hạn3 câu hoặc % giả.
- [ ] Critical claim truy được nến/feature/source; thiếu source, unsupported rule và UNKNOWN hiển thị trung thực.
- [ ] Chart/highlight/mask đúng job; full report không lộ outcome trước bước4.
- [ ] Bản cũ/NO_MODEL không tự biến thành báo cáo nghiên cứu mới; ABSTAIN/failed không chấm SAI.
- [ ] Bài mới tiếng Việt được kiểm từ response thật, không tuyên bố prompt bảo đảm mọi lần.

## Rủi ro

Bài dài không mặc nhiên đúng, citation không mặc nhiên chứng minh suy luận, nhiều vai cùng model không tăng accuracy bằng biểu quyết. Gate là dữ liệu–nguồn–criteria–lập luận kiểm được, còn predictive performance phải đo riêng.
