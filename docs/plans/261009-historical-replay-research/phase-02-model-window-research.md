# Phase 02 — Model hợp lệ cho mô phỏng và học từ kết quả thị trường

**Trạng thái:** Chưa nghiệm thu. Không ép so cửa sổ học 1/3/6/9 tháng; với 65 ngày hiện có, các cửa sổ dài hơn dữ liệu không đủ điều kiện. Xem [plan.md](plan.md). Phase này tạo artifact có nguồn gốc và đánh giá ngoài mẫu trước khi cho job AI phát dự báo.

## Người dùng nhận được gì

- Job ở tab Mô phỏng chỉ nhận model có phiên bản, cutoff học, horizon và bằng chứng kiểm tra tương ứng. Không có model hợp lệ: nêu lý do thay vì tạo UP/DOWN hoặc xác suất.
- “Học” theo lựa chọn **B**: chỉ thêm dữ liệu và kết quả giá **thực tế của thị trường** vào nguồn dùng cho đợt huấn luyện lại **sau này**. Nút UP/DOWN của người dùng lưu để chấm riêng, **không phải nhãn huấn luyện**.
- Artifact đang dùng cho job và dự báo đã phát không bị cập nhật tại chỗ; phiên bản mới phải trải qua đánh giá trước khi sử dụng. Không khẳng định học thêm sẽ tăng độ chính xác.

## Quy tắc không nhìn trước

1. Điểm mua do người dùng **chọn trên chart hoặc nhập tay** tạo đầu vào `(t, giá mua giả định, horizon)` cho AI; feature giá mua và nến lịch sử đóng/khả dụng đến `t` phải được huấn luyện/kiểm định cùng định nghĩa nhãn **giá sau horizon so với giá mua đầu vào**. Cho chọn mốc hoặc nhập horizon trong khoảng 30 phút–tối đa 1 ngày; chỉ hỗ trợ mốc backend có nhãn và model đã kiểm định. Không tái sử dụng xác suất model huấn luyện nhãn close-nến-so-close-nến như xác suất theo giá mua giả định.
2. Với mốc job `t`, mọi nến/feature đầu vào phải đóng và có `available_at <= t`; train, hiệu chỉnh xác suất và chọn cấu hình phải kết thúc trước `t`. Nhãn tương lai chỉ dùng để chấm **sau** khi prediction đã khóa.
3. Tách theo thời gian train → calibration → validation → held-out test; purge ranh giới đủ horizon và latency, kiểm tra nến thiếu/gap. 65 ngày chỉ cho thí nghiệm giới hạn; không suy ra model tốt lâu dài hoặc nhiều giai đoạn thị trường.
4. Chọn model/cấu hình bằng dữ liệu trước phần test. Báo kết quả kể cả thua baseline, xác suất chưa hiệu chỉnh hoặc không đủ mẫu. Dữ liệu từ job đã chấm chỉ có thể tham gia chu kỳ huấn luyện **phiên bản mới** với cutoff và tập kiểm tra mới, không dùng lại bản ghi test làm bằng chứng thành công cho chính model vừa học.

## Hạng mục cần thiết kế/triển khai

- `backend/shootingstar/application/splits.py`: tái dùng chia tuần tự/purge đang có; bổ sung ràng buộc theo cutoff/horizon khi thực sự cần. Không triển khai rolling 1/3/6/9 tháng chỉ để phục vụ UI này.
- `backend/shootingstar/application/experiment.py`, `modeling.py`: kiểm tra artifact train/calibration/selection cutoff, snapshot/hash, horizon, trạng thái đánh giá, tải lại và dự đoán nhất quán; giữ version cũ khi có đợt huấn luyện mới.
- Backend job và trang Mô phỏng: chỉ chọn artifact hợp lệ trước `t` và đúng horizon; frontend hiển thị nguồn model/giới hạn, không tự tính xác suất hoặc lời giải thích.

### File BE/FE cần sửa khi triển khai

| Sửa/tạo | Bước và contract |
|---|---|
| Sửa `backend/shootingstar/application/labels.py`, `splits.py`, `experiment.py`, `modeling.py` | Sau khi chốt mốc giá/horizon, định nghĩa nhãn theo horizon; dùng nến đóng trước `t`, split/purge, fit/hiệu chỉnh/test ngoài mẫu, persist artifact bất biến và metadata cutoff/snapshot hash/horizon. Tái dùng pipeline hiện có, không làm nghiên cứu rolling nhiều tháng ngoài scope. |
| Sửa `backend/shootingstar/adapters/db/models.py`, `repository.py` và thêm Alembic migration trong `alembic/versions/` **nếu** metadata artifact hiện tại không đủ | Ghi version, train/calibration/selection cutoff, horizon và nguồn dữ liệu để backend kiểm tra trước job; không lưu thông tin đường dẫn file trong public DTO. |
| Sửa `backend/shootingstar/api/schemas.py` và API phục vụ model đủ điều kiện | Chỉ cung cấp ID/version/horizon, tình trạng có thể dùng hoặc lý do thiếu. Quyền kích hoạt huấn luyện qua web cần giới hạn local/admin trước khi mở endpoint ghi. |
| Sửa `frontend/src/app/(work)/research/page.tsx` nếu cần hiển thị báo cáo; tab AI ở `frontend/src/features/replay/` | Chỉ đọc trạng thái/model/metric đã tính từ backend; không có UI chọn cửa sổ học 1/3/6/9 tháng. |
| Sửa `tests/test_evaluation_and_modeling.py`, `tests/test_labels_features_baselines.py` | Test horizon/cutoff, nhãn khi thiếu nến, baseline, artifact reload và không dùng lựa chọn người làm nhãn. |

**Thứ tự:** chốt quy tắc chọn nến khi click/gap, bước horizon và nến sau horizon → xây feature giá mua + lịch sử tới `t`, nhãn so với giá mua đầu vào → gate dữ liệu → fit/đánh giá → artifact/version → nối job Phase 03. Huấn luyện lại từ kết quả thị trường là chu kỳ model mới được đánh giá, không tự chạy mỗi khi người bấm UP/DOWN.

## Gate nghiệm thu

- [ ] Test đổi dữ liệu **sau `t`** không đổi dự báo tại `t`; artifact có bất kỳ cutoff học/chọn model sau `t` bị từ chối; test gap, purge, nhãn và latency theo từng horizon.
- [ ] Test cùng snapshot/config/model version cho kết quả lặp lại; artifact sau khi reload giữ kết quả; không có model/thiếu mẫu/không hiệu chỉnh xác suất thì không phát phần trăm giả.
- [ ] Report ngoài mẫu so baseline, nêu số mẫu/cutoff/horizon/hash và kết quả thực; không chọn lại theo kỳ test đã xem. Chưa đủ dữ liệu thì ghi không đủ điều kiện.
- [ ] Kiểm tra bản ghi lựa chọn người không vào training set; model mới học từ thị trường chỉ sau chu kỳ đánh giá riêng và không thay đổi dự báo/điểm số phiên cũ.
