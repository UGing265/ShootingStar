# Storyboard & Bản thảo Lời văn Landing Page (6 Đoạn)

Tài liệu này xác lập bản thảo nội dung chính thức cho 6 phân đoạn của Landing Page ShootingStar, tuân thủ nghiêm ngặt các ranh giới kiểm định (invariants) tại `plan.md` và `docs/landing-page-narrative.md`.

---

## Phân đoạn 1 — Hero: Khát vọng & Tên gọi
- **Tiêu đề lớn:** ShootingStar
- **Thông điệp cốt lõi:** Chính xác hơn là tốc độ.
- **Nội dung:**
  Như một vệt sao băng rạch ngang bầu trời đêm, cơ hội trong thị trường crypto xuất hiện chớp nhoáng giữa vô vàn biến động. Tên gọi ShootingStar đại diện cho sức mạnh, vẻ đẹp và tham vọng tìm kiếm tín hiệu chân thực — nhưng con đường chúng tôi lựa chọn là khoa học thực nghiệm, minh bạch và kỷ luật, kiên quyết từ chối những lời hứa hẹn viển vông.
- **Nút hành động (CTA):**
  - Nhãn nút: **Vào dashboard demo**
  - Chú thích: *Không cần tài khoản*
  - Đích đến: `/dashboard`

## Phân đoạn 2 — Thách thức: Biến động & Nhiễu loạn
- **Thẻ định danh (Tag):** Thách thức thực nghiệm
- **Tiêu đề:** Thị trường có thể đổi hướng chỉ sau một tin tức.
- **Nội dung:**
  Những lời quảng cáo "tỷ lệ thắng 80–90%" trên thị trường bán lẻ hầu hết là ảo ảnh sinh ra từ việc rò rỉ dữ liệu tương lai (lookahead bias) và khớp tham số quá mức. Thực tế là thị trường Bitcoin spot vận hành gần với hiệu quả thông tin. Một tin tức vĩ mô hay một dòng lệnh lớn có thể bẻ gãy mọi quy luật kỹ thuật trong chớp mắt.

## Phân đoạn 3 — Giải pháp: Đặt dự đoán cạnh bằng chứng
- **Thẻ định danh (Tag):** Nền tảng nghiên cứu
- **Tiêu đề:** Một nơi để đặt dự đoán cạnh bằng chứng.
- **Nội dung:**
  ShootingStar xây dựng cơ sở hạ tầng thực nghiệm độc lập: dự đoán xác suất hướng giá trong 30 phút kế tiếp dựa trên nến đã đóng tại thời điểm $t$. Dự đoán được ghi nhận bất biến vào sổ dữ liệu tại mốc phát sinh và đối chiếu sòng phẳng với kết quả thị trường sau khi đủ thời gian. Không làm tròn, không vẽ lại lịch sử.

## Phân đoạn 4 — Tham vọng: Kỹ thuật · Tin tức · Con người
- **Thẻ định danh (Tag):** Định hướng phát triển
- **Tiêu đề:** Kỹ thuật · Tin tức · Con người.
- **Cấu trúc 3 trụ cột (Gần 90% là mục tiêu chưa đạt):**
  - **Kỹ thuật (Đang thử nghiệm):** Mô hình định lượng xác suất và phòng thí nghiệm mẫu hình nến (Pattern Lab) tuân thủ chặt chẽ việc loại trừ rò rỉ dữ liệu.
  - **Tin tức (Mục tiêu chưa đạt):** Tích hợp phân tích luồng tin tức vĩ mô và sự kiện tức thời vào bộ lọc dự đoán (Định hướng phát triển tương lai).
  - **Con người (Mục tiêu chưa đạt):** Cơ chế giám sát phản biện và thẩm định độc lập từ chuyên gia trước các quyết định rủi ro.

## Phân đoạn 5 — Kỷ luật: Nguyên tắc & Giới hạn nghiên cứu
- **Thẻ định danh (Tag):** Cam kết trung thực
- **Tiêu đề:** Minh bạch phương pháp trước mọi con số.
- **Các nguyên tắc bất biến:**
  - **Chống rò rỉ dữ liệu:** Mọi đặc trưng tại $t$ chỉ dùng nến đã đóng với độ trễ ghi nhận tối thiểu 1000ms.
  - **Không giả lập phí bằng 0:** Chi phí giao dịch Binance Spot 0.20% roundtrip cùng mô hình trượt giá (slippage) bắt buộc phải được tính vào mọi bài toán.
  - **Trạng thái GATED:** Toàn bộ chỉ số P&L ròng và chính sách hành động tự động `NO_TRADE` theo chi phí hiện chưa được mở khóa cho đến khi hoàn thành thẩm định độc lập.

## Phân đoạn 6 — Kêu gọi hành động (Demo Access)
- **Tiêu đề:** Sẵn sàng kiểm chứng dữ liệu thực nghiệm?
- **Nội dung ngắn:** Khám phá cấu trúc dữ liệu nến, các thực nghiệm walk-forward và nhật ký tín hiệu trực tiếp trên hệ thống cục bộ.
- **Nút hành động:**
  - Nhãn: **Vào dashboard demo**
  - Chú thích: *Không cần tài khoản*
  - Liên kết phụ: *Xem phương pháp nghiên cứu (/about)*
