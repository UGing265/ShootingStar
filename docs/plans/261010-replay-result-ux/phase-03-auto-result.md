# Phase 03 — Tự mở kết quả sau bước 3

## Context và trạng thái

[Plan tổng](plan.md), [Chart](phase-02-chart-preview.md). **Pending; chưa đổi handler hoặc API.**

## Nguyên nhân đã xác thực

- `replay-player.tsx:450–485`: `handleVote` chỉ cập nhật job, chưa chuyển bước.
- `replay-player.tsx:1385–1392`: “Tiếp tục” chỉ đổi tab sang bước 4.
- `replay-player.tsx:1408–1439`: bước 4 còn chờ nút “Xem Kết quả thực tế” mới gọi reveal. Hai thao tác tách rời tạo lần bấm dư mà người dùng phản ánh.
- External service hiện chưa kiểm vote ở đầu `reveal_outcome`, và `record_user_vote` ghi đè giá trị. Nhánh local đã chặn reveal trước vote. **Không được nói backend external đã khóa đủ chỉ vì UI không cho bấm.**

## Hành vi mới

1. Người dùng đọc AI ở bước 2; sang bước 3.
2. Bước 3 giải thích tăng/giảm so với giá mua và thời lượng của job; báo trước rằng chọn sẽ lưu và mở kết quả.
3. Chọn Tăng/Giảm: disable hai nút trong lúc lưu; POST vote một lần.
4. Vote thành công: nhận job đã khóa, chuyển ngay bước 4; hiện “Đang tải kết quả…” rồi gọi reveal của đúng job đã trả về.
5. Reveal thành công: hiển thị trạng thái thị trường, chart và điểm backend. Không có nút mở phong ấn hay “Xem kết quả” lần nữa.
6. Quay lại tab Kết quả của job đã có outcome: hiển thị outcome đã lưu, không tạo job mới/call Gemini hoặc gửi vote lại.

## Kiến trúc điều hướng

Một đường vào bước 4 dùng cho tự chuyển sau vote và click tab đã được phép. Không đặt POST reveal vô điều kiện trong render hoặc effect phụ thuộc toàn bộ object job.

```text
handleVote(direction):
  khóa nút trong lúc gửi
  votedJob = await POST vote(job.id, direction)
  nếu lỗi: giữ bước 3, không reveal
  cập nhật votedJob
  enterResults(votedJob)

enterResults(lockedJob):
  nếu chưa có vote khóa: không chuyển
  chuyển bước 4
  nếu outcome đã đủ: hiện dữ liệu đã lưu
  nếu reveal đang chạy cho ID này: dùng request đang có
  nếu chưa có outcome: POST reveal đúng ID, không dùng form hiện tại
  chỉ áp response nếu ID vẫn là job đang xem
```

`enterResults` dùng chính DTO vừa nhận, tránh đọc state React cũ sau `setExternalJob`/`setSimulationJob`. Theo dõi request đang chạy và job ID; bỏ response cũ khi đổi job/reset. Quay lại bước 3 chỉ xem lựa chọn đã khóa.

## Trạng thái và lỗi

| Trạng thái | UI bước 4 | Hành động được phép |
|---|---|---|
| Đang reveal | “Đang tải kết quả…”; không dựng điểm trước response | Quay lại xem nhận định; không gửi lại vote |
| Đã đánh giá | Chart mua–kết quả; giá/hướng và hai dòng đối chiếu | Xem nến; bắt đầu job khác chủ động |
| `PENDING` | “Chưa đủ nến để chấm kết quả” + mốc cần chờ/lý do từ backend | “Kiểm tra lại” chỉ gọi reveal, không call model |
| `UNSCORABLE` | “Không thể chấm: thiếu hoặc không hợp lệ dữ liệu tại mốc kết quả” | Xem lịch sử; chọn snapshot/job khác; không gán SAI |
| Reveal lỗi mạng/4xx/5xx | “Dự đoán đã lưu, chưa tải được kết quả” và lỗi an toàn | “Thử lại” chỉ reveal đúng ID |
| Vote lỗi rõ ràng | Giữ bước 3 và báo chưa lưu | Thử lưu lại; không reveal khi chưa xác nhận khóa |
| Vote timeout không rõ đã ghi chưa | GET job hiện có để kiểm tra, không create job/Gemini | Nếu vote đã lưu thì sang bước 4; nếu chưa thì cho thử lại |

Nút thử lại do người dùng chủ động; không thêm vòng polling/retry tự động. Không mở rộng luồng refresh/resume toàn hệ thống; nếu màn hình có job ID đã lưu thì đi qua cùng đường vào kết quả.

## Backend gate trực tiếp cần cho luồng này

Không gộp vote/reveal thành endpoint mới: dùng proxy và endpoint hiện tại.

- External reveal phải từ chối khi chưa có user vote. Outcome vẫn null trong GET trước reveal; chỉ auto call từ UI sau vote không thay được gate backend.
- External vote phải lưu một lần: cùng vote gửi lại trả bản đã khóa; đổi vote sau khi khóa trả HTTP409, không sửa prediction/vote/outcome. Ghi atomic tại repository với điều kiện `user_vote IS NULL AND is_revealed = false`, không chỉ check rồi overwrite. Job cũ đã reveal nhưng chưa có vote cũng từ chối vote đầu tiên bằng HTTP409; giữ dữ liệu cũ, không cho đoán sau khi biết kết quả.
- Giữ giá mua làm mốc so sánh; AI không dự đoán/lỗi không ngăn người xem giá thực tế nhưng điểm AI null.
- Prospective chỉ chấm khi tới hạn **và nến tham chiếu đã đóng/khả dụng**. Source hiện chỉ check thời gian `t+horizon`; kiểm tra điều kiện đóng/availability khi triển khai, không cho auto reveal làm lộ nến chưa hợp lệ.
- Không thay thuật toán chọn nến/horizon để tiện vẽ chart; nếu backend dùng nến đóng sau mốc yêu cầu, công khai thời gian đó theo Phase 02.
- Giữ idempotency của outcome đã đánh giá. Nhánh local hiện persist `PENDING` rồi return outcome đã có: “Kiểm tra lại” phải thể hiện đúng khả năng đánh giá lại; snapshot bất biến thiếu nến thì báo không có dữ liệu mới, không cho nút giả luôn trả cùng trạng thái mà nói đang lấy nến mới.

## File thay đổi khi triển khai

- `frontend/src/features/replay/replay-player.tsx`: `handleVote`, reveal/đường vào step4, tab/continue, loading/error, bỏ nút xem kết quả dư; horizon lấy từ job.
- `backend/shootingstar/application/external_analysis/service.py`: guard reveal, khóa vote, nullable score theo Phase 01.
- `backend/shootingstar/adapters/db/repository.py`: cập nhật vote có điều kiện trong transaction theo convention repository hiện có.
- `backend/shootingstar/api/external_routes.py`: giữ auth; lỗi reveal trước vote trả HTTP400, đổi vote đã khóa HTTP409; không ngụy trang thành 404 job không tồn tại. Các lỗi thiếu job giữ 404.
- Next proxy external/local vote/reveal: cập nhật khi contract lỗi mới yêu cầu, không đổi URL hoặc chuyển auth/key xuống browser.
- `backend/tests/test_external_analysis.py`, `test_api_and_ui.py`: contract vote một lần/reveal trước vote/điểm và dữ liệu chưa đủ. `application/replay.py` chỉ sửa nếu cần giữ ý nghĩa trạng thái đã có; không làm lại toàn engine.

## Checklist và nghiệm thu

- [ ] Chọn dự đoán một lần thì tự bước 4, không bấm “Tiếp tục”/“Xem kết quả” thêm.
- [ ] Không reveal trước khi vote xác nhận thành công; bấm nhanh không tạo hai lựa chọn hoặc hai job.
- [ ] Vote/AI bất biến; retry không sửa lựa chọn và không call Gemini.
- [ ] Lỗi reveal giữ vote; đổi tab/back không tạo lần lưu mới.
- [ ] `PENDING`, `UNSCORABLE`, ABSTAIN, NO_MODEL có trạng thái đọc được và không tô sai thành SAI.
- [ ] Hai nhánh external/local đều đi cùng UX; nhãn giá sau `{horizon_minutes}` phút đúng job.
- [ ] Khi đổi job/reset trong lúc chờ, response cũ không thay chart/kết quả mới.

## Rủi ro

Tự mở là thay **thao tác UX**, không phải bỏ khóa dữ liệu. Gate backend, dữ liệu nến và bản ghi bất biến vẫn bắt buộc. Không thêm request provider hay chi phí khi sang kết quả.
