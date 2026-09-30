# Audit QR / POS — 30/09/2026

## Phạm vi và kết quả

Rà soát đặt QR tại bàn, đặt mang đi, sửa/hủy đơn, duyệt/từ chối, giỏ bàn,
chuyển bàn, báo bếp, thanh toán, hoàn tiền, quyền cửa hàng và thông báo WebSocket.
Bao gồm các bản sửa QR ngay trước đợt audit này.

Kiểm tra trên PostgreSQL **14.18**, Django **5.2.17** trong database tạm riêng;
không sửa dữ liệu VPS hoặc database local đang sử dụng.

- **199 test thành công**: `App_Public App_Sales App_Accounts App_Core`.
- `makemigrations --check --dry-run`: không có thay đổi schema.
- `git diff --check`: không có lỗi khoảng trắng.
- WebSocket dùng Channels InMemoryChannelLayer trong test. Có kiểm tra kết nối,
  quyền, sự kiện và giả lập lỗi backend; không thay thế smoke test Nginx/Redis thật.

## Phát hiện đã sửa

| Mức | Tình huống | Thay đổi |
| --- | --- | --- |
| Cao | PostgreSQL từ chối `FOR UPDATE` trên phía nullable của outer join khi duyệt QR, sửa/hủy đơn mang đi, hoàn tiền | Chỉ khóa dòng đơn bằng `of=('self',)`; với duyệt tại bàn, khóa bàn riêng trước khi gộp giỏ |
| Cao | Các thao tác giỏ bàn không dùng chung khóa với thanh toán: dữ liệu có thể bị đọc cũ hoặc ghi đè khi nhiều máy thao tác | Thêm/sửa/xóa, nhập giỏ mang về, chuyển bàn, báo bếp lấy khóa bàn trong transaction trước khi đọc/ghi giỏ; chuyển bàn khóa hai bàn theo thứ tự ID |
| Cao | Mã thanh toán đã dùng ở cửa hàng khác có thể trả thông tin đơn ngoài phạm vi chi nhánh đang thao tác | Kiểm tra cửa hàng của đơn trước khi trả kết quả thanh toán cũ, ở cả nhánh bình thường và nhánh xử lý trùng khóa |
| Trung bình | Khởi tạo channel layer lỗi làm API trả 500 dù đơn đã lưu | Đưa cả khởi tạo và gửi thông báo vào khối xử lý lỗi; vẫn ghi warning để vận hành phát hiện cấu hình lỗi |
| Trung bình | Tiền khách đưa là `NaN`/`sNaN` gây `decimal.InvalidOperation` | Từ chối số không hữu hạn bằng HTTP 400 trước khi tính tiền/lưu đơn |
| Trung bình | WebSocket đơn mang đi vẫn cho kết nối mới khi cửa hàng ngừng hoạt động | Kiểm tra `store__is_active` giống API HTTP |
| Trung bình, phát hiện thêm khi chạy bộ test tài khoản | Form đăng ký cho tên cửa hàng 150 ký tự trong khi cột DB chỉ chứa 120 | Giới hạn form về 120, trả lỗi form thay vì PostgreSQL 500; giữ test slug dài và bổ sung test vượt giới hạn |

Hai lớp test WebSocket dùng `TransactionTestCase` để phù hợp vòng đời kết nối
database của Channels; tránh việc test trước đóng kết nối của transaction dùng
chung rồi test sau bị `connection already closed` trên PostgreSQL.

## Kiểm tra hồi quy đáng chú ý

- Tạo đơn khi `get_channel_layer()` lỗi vẫn trả 201, lưu đúng một đơn.
- Duyệt đơn → gộp giỏ → báo bếp; duyệt lại không nhân đôi số lượng/phiếu.
- Hai kết nối PostgreSQL duyệt cùng đơn đồng thời: cả hai nhận 200, chỉ một
  phiếu bếp và đúng số món.
- Trong khi thanh toán giữ khóa bàn, request sửa món phải chờ; sau thanh toán,
  request nhận 404, hóa đơn giữ số lượng đã chốt và giỏ không xuất hiện lại.
- Sửa/hủy đơn mang đi không có bàn; kiểm tra access key.
- Hoàn tiền từng phần rồi toàn bộ, kiểm tra doanh thu sau hoàn.
- Quyền nhân viên theo cửa hàng, token QR, quyền WebSocket và kiểm tra Origin.
- Trả 400 với tiền không hữu hạn, không tạo hóa đơn.

Test bổ sung tập trung trong `App_Sales/tests_qr_audit.py`, cùng các test
QR/WebSocket hiện có. Có thể chạy lại bằng:

```bash
python manage.py test App_Public App_Sales App_Accounts App_Core --noinput
```

Chạy với cấu hình PostgreSQL kiểm thử riêng; SQLite không kiểm tra được khóa dòng.
Hai test đồng thời sẽ được bỏ qua trên backend không hỗ trợ `select_for_update`.
Phiên bản môi trường kiểm thử là Django 5.2.17; `requirements.txt` hiện pin 5.0.7.
Đợt audit này không thay đổi dependency hoặc xác minh trên cả hai phiên bản.

## Giới hạn còn lại

- **Đã xử lý tiếp theo yêu cầu sau audit:** tạo đơn QR/mang đi có UUID v4,
  ràng buộc unique và nội dung yêu cầu bất biến để gửi lại sau lỗi mạng/tải lại
  trang. Trang mới luôn gửi mã; API client cũ không gửi mã vẫn không chống trùng.
  Xem `docs/setup/phase2/1_qr_public_and_qr_admin.md`.
- Các test đồng thời tập trung vào duyệt đơn và sửa giỏ khi thanh toán; không phải
  kiểm thử tải hay kiểm chứng mọi tổ hợp thao tác nhiều máy.
- Chưa triển khai hoặc kiểm tra hạ tầng Nginx/Redis trên VPS trong đợt audit này.

## Triển khai

Bản sửa hiện trong workspace, chưa push/deploy. Riêng bản sửa chống trùng bổ sung
sau audit có migration `App_Sales.0014_qr_order_idempotency` và file JS mới.
Sau khi cập nhật mã lên VPS, chạy `migrate`, `collectstatic --noinput`, rồi restart
`gunicorn-eapp-fnb` và `daphne-eapp-fnb`.
Smoke test: đặt QR → duyệt/báo bếp → thanh toán; thử đơn mang đi sửa/hủy;
kiểm tra thông báo ở POS và bếp, đồng thời theo dõi `logs/recent-errors.log`.

Kiểm tra bổ sung chống trùng: **212 test backend qua trên PostgreSQL**, **7 test
JavaScript qua** (gồm thực thi mã trang với DOM giả lập cho cả hai chế độ sau mất
phản hồi và tải lại trang). Trình duyệt tích hợp lỗi khởi tạo trong phiên kiểm thử;
chưa xác minh giao diện bằng trình duyệt thật. Migration đã áp dụng trên SQLite local.
