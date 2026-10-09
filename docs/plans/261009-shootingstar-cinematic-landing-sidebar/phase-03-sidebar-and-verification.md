# Phase 03 — Sidebar dashboard và kiểm chứng

## Phạm vi
Năm mục làm việc thật trong sidebar desktop, drawer mobile có bàn phím; không đổi API/backend. Làm shell/sidebar trước để Phase 02 chụp dashboard thật; sau tích hợp cùng landing chạy smoke tổng.

## Các bước thực hiện
1. Thay điều hướng `frontend/src/shared/ui/navbar.tsx` bằng `frontend/src/shared/ui/sidebar.tsx` và bỏ import Navbar cũ trong root layout, không giữ re-export alias. Sidebar dùng trong `frontend/src/app/(work)/layout.tsx`, chứa đúng năm link: Tổng quan `/dashboard`, Dữ liệu `/data`, Nghiên cứu `/research`, Pattern Lab `/patterns`, Tín hiệu `/signals`; link phụ Giới thiệu `/` và Phương pháp `/about`. Chỉ component điều hướng là client để dùng `usePathname()`: active path so theo segment (ví dụ `/research/x` khớp Research, `/researching` không khớp), `aria-current="page"`. Trang work có main landmark riêng, sidebar label nav “Mục làm việc”; desktop sidebar ~240px và vùng content không tràn khung.
2. Mobile <=768px: nút “Mở mục làm việc” mở drawer, che phần nền bằng overlay; khi mở đưa focus tới link đầu, cô lập nội dung phía sau khỏi keyboard focus, Escape/overlay hoặc click link đóng drawer và trả focus đúng nút khi phù hợp. Đóng trên route change bằng `usePathname`; không để focus lạc sau navigation. Bảng rộng giữ khả năng cuộn ngang trong vùng content. Không biến root layout thành client component chỉ vì menu.
3. Overview chuyển từ `/` sang `/dashboard` giữ fetch server-side/error/empty states; label count snapshot/experiment hiện là length của `limit=5` đổi thành “Bản ghi gần đây (tối đa 5)” / “Thí nghiệm gần đây (tối đa 5)”, không gọi đó là tổng DB. Vẫn dùng `frontend/src/shared/api-client.ts` server-only. Dùng CSS `work-*` trong `frontend/src/app/globals.css`, không làm hỏng `.scrolly-*` của `/about` hoặc `.landing-*`.
4. Khi sidebar render đúng, chụp hình dashboard từ app chạy thật cho Phase 02; che/không dùng thông tin riêng, không dựng số liệu. Nếu chưa có backend, ảnh hiển thị trạng thái offline rõ ràng hoặc bỏ ảnh. Cập nhật doc frontend sau thay đổi route, nhưng không biến document thành UI contract thay code.

## Files và phụ thuộc
- Tạo `frontend/src/shared/ui/sidebar.tsx`, sửa `frontend/src/app/globals.css`, `frontend/src/app/(work)/layout.tsx`, `frontend/src/app/(work)/dashboard/page.tsx` sau khi Phase 02 chuyển Overview; xóa `frontend/src/shared/ui/navbar.tsx` sau khi không còn import. Tránh hai người sửa cùng `globals.css`/work layout đồng thời: Phase 02 tạo route shell và placeholder import; Phase 03 sở hữu sidebar/CSS work; Phase 02 hoàn thiện CSS landing và ảnh dashboard sau khi sidebar đã có.
- Tham chiếu `docs/DESIGN.md` và `docs/frontend/README.md`. Không viết route proxy hoặc xử lý metric client-side.

## Nghiệm thu
- [x] Từ `frontend/` chạy `npm run typecheck`, `npm run build`, sau đó `npm run dev`; khởi động backend theo `docs/local-run.md` khi sẵn DB, hoặc cố tình tắt backend để kiểm tra lỗi trung thực. *(Typecheck và build pass, cấu trúc route tách biệt)*
- [x] Browser desktop: `/` landing không sidebar; CTA đến `/dashboard`; sidebar chọn đúng mục sau mỗi link và các detail `/research/[id]`, `/patterns/[id]`, `/signals/[id]`; link Giới thiệu về `/`; `/about` CTA về `/dashboard`.
- [x] Browser 390px và keyboard: mở drawer, Tab giữ trong drawer (focus trap), Escape và overlay đóng, drawer dùng `inert` khi đóng, điều hướng đóng menu không mất focus, bảng dữ liệu cuộn ngang chứ không làm body tràn. Bật reduced-motion: không có transition cản tương tác; kiểm tra JS disabled landing CTA vẫn dùng được.
- [x] Offline: Overview và detail không có số liệu giả; nhãn “gần đây tối đa 5” phản ánh truy vấn limit 5 (`Bản ghi gần đây (tối đa 5)` / `Thí nghiệm gần đây (tối đa 5)`). Cổng media đã hoàn tất sau khi chủ dự án xác nhận quyền sử dụng và tích hợp HeroSequence được kiểm chứng qua browser.
