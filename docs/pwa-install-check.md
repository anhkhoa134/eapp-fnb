# Kiểm tra cài PWA — 2026-10-15

Nút native chỉ hiện khi có beforeinstallprompt; hướng dẫn Safari có nhãn riêng. Bổ sung chống bấm lặp, xử lý lỗi prompt/userChoice và trạng thái đã cài.

## Kiểm thử

- `python scripts/check_pwa_install.py` (Playwright + Google Chrome): sự kiện mô phỏng, không xác nhận cài ứng dụng. Kiểm tra không có prompt, hủy/thử lại, bấm lặp, prompt mới khi yêu cầu cũ đang chờ, lỗi prompt/userChoice, accepted/appinstalled, standalone. FnB/POS/LMS thêm hướng dẫn iPad.
- Kiểm tra website bằng hồ sơ Chrome persistent riêng: manifest hợp lệ và nhận beforeinstallprompt ở FnB/POS/Reader/Prompt/Equiptrack. LMS bản đang chạy chưa có manifest; cần triển khai thay đổi mới.
- Safari/iPad không cung cấp beforeinstallprompt: hướng dẫn Thêm vào Màn hình chính là luồng thủ công, không phải lỗi hộp thoại. Mở bằng biểu tượng đã cài để dùng standalone.

## Triển khai

Thay đổi hiện ở mã nguồn local. Cần triển khai template/Python, chạy collectstatic và cập nhật ứng dụng. Kiểm tra lại bằng hồ sơ trình duyệt thường chưa cài app, chờ sự kiện installable sau tương tác. Không dùng cửa sổ ẩn danh để kết luận app không cài được.

Tham khảo: https://web.dev/learn/pwa/installation-prompt
