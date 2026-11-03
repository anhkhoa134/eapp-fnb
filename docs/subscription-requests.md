# Yêu cầu nâng cấp / gia hạn gói

Áp dụng cùng hợp đồng nghiệp vụ cho PM, FnB, POS và Photo. Mỗi repo có `App_Billing`; chỉ `adapter.py`, cấu hình tài khoản và migration phụ thuộc khác nhau.

## Sử dụng

- Trang gói mặc định theo tháng. “Chọn gói này” mở form đã chọn đúng gói và kỳ hạn đang xem. Chọn lại gói trả phí hiện tại để gia hạn.
- Yêu cầu lưu gói, kỳ hạn 1/12 tháng (miễn phí: không thời hạn), giá backend tại thời điểm gửi và ghi chú. Khách có thể hủy yêu cầu đang chờ. Mỗi tài khoản/doanh nghiệp chỉ có một yêu cầu chờ xử lý.
- POS/FnB: chỉ quản lý doanh nghiệp đang hoạt động được gửi và xem lịch sử. PM/Photo: theo tài khoản đăng nhập. Người chưa đăng nhập Photo được chuyển đến đăng nhập.
- Django Admin → **Yêu cầu gói dịch vụ** → **Xem và xử lý**. Chỉ superuser được duyệt, từ chối hoặc hủy; duyệt phải xác nhận đã thanh toán/thỏa thuận. Gói liên hệ cần nhập số tiền báo giá; gói niêm yết phải khớp giá đã lưu.
- Cùng gói còn hạn: nối tiếp thời hạn còn lại theo tháng lịch. Đổi gói hoặc gói hết hạn: bắt đầu từ lúc duyệt. Đổi gói không tự tính hoàn tiền/bù trừ; quản trị viên xác nhận thỏa thuận trước khi duyệt.
- Gói miễn phí không có hạn sử dụng. Gửi yêu cầu không tự kích hoạt hoặc tự thu tiền.

## Dữ liệu và ranh giới tích hợp

`SubscriptionRequest` giữ mã tham chiếu duy nhất, người gửi, tài khoản, gói/kỳ hạn/giá đã chốt, trạng thái, phản hồi và dấu thời gian. `PaymentAttempt` tách lần thanh toán khỏi yêu cầu; một yêu cầu có thể có nhiều lần thanh toán nhưng chỉ kích hoạt một lần.

`services.py` là nơi duy nhất thực hiện chuyển trạng thái và gọi `adapter.activate`. Việc duyệt, hủy, xác nhận thanh toán đều trong transaction, khóa tài khoản rồi yêu cầu/lần thanh toán theo cùng thứ tự. Ràng buộc DB bảo vệ một yêu cầu chờ, token gửi lại và mã giao dịch của nhà cung cấp. Các bài kiểm thử local dùng SQLite; khóa hàng cần PostgreSQL trong production và cần kiểm thử cạnh tranh trên PostgreSQL trước khi bật webhook.

Giá nhận từ trình duyệt không được sử dụng. `client_token` chống gửi lại khi mất kết nối; gửi lại yêu cầu đã duyệt không gia hạn lần nữa. Lịch sử chỉ truy vấn tài khoản hiện tại, có phân trang 20 dòng và không cache.

## Bổ sung SePay sau này

Tham khảo mô hình mã đơn, lưu tổng tiền và nhận webhook của `ecom_final`, nhưng không thêm endpoint thanh toán hoặc cấu hình SePay trong đợt này. Các kênh tự động mặc định bị tắt.

1. Thêm adapter nhà cung cấp và cấu hình secrets ngoài mã nguồn. Thêm tên nhà cung cấp vào `BILLING_PAYMENT_PROVIDERS` chỉ khi tích hợp đã hoàn chỉnh.
2. Gọi `create_payment_attempt(request_id, provider=...)` từ luồng checkout được phân quyền. Service lấy giá đã lưu, chỉ cho yêu cầu còn chờ với giá dương; trả lại lần đang chờ nếu có. Gói liên hệ vẫn xử lý thủ công cho đến khi có quy trình báo giá riêng.
3. Tạo nội dung chuyển khoản/QR gắn với `SubscriptionRequest.reference`. Không lấy số tiền, tài khoản ngân hàng hoặc mã đối soát từ dữ liệu khách tự gửi.
4. Endpoint webhook phải xác thực theo giao thức chính thức của nhà cung cấp tại thời điểm tích hợp, kiểm tra tài khoản nhận, chiều tiền vào, đơn vị tiền và mã yêu cầu. Sau đó mới gọi `record_verified_payment(payment_id, transaction_id=..., amount_vnd=...)`.
5. Service kiểm tra giá đã chốt, số tiền đủ, mã giao dịch chưa dùng và trạng thái; kích hoạt trong cùng transaction. Gọi lại cùng giao dịch thành công trả lại kết quả, không cộng thêm hạn. Thiếu tiền, yêu cầu hủy hoặc đã xử lý không kích hoạt; chuyển các trường hợp cần đối soát vào quy trình hỗ trợ.
6. Bổ sung log webhook, retry/reconciliation, kiểm thử xác thực, sai tài khoản nhận, sai chiều tiền, replay và cạnh tranh duyệt thủ công/webhook trước khi bật thực tế.

Không gọi `record_verified_payment` trực tiếp từ dữ liệu chưa xác thực. Không bật thanh toán tự động bằng cách chỉ tạo bản ghi `PaymentAttempt` trong DB.

## Triển khai và kiểm tra

Sau khi cập nhật mã từng app, chạy `python manage.py migrate --noinput`, `python manage.py collectstatic --noinput` rồi khởi động lại dịch vụ theo quy trình hiện có. Migration chỉ thêm bảng yêu cầu/thanh toán, không sửa gói hay thời hạn của khách hiện tại.

Chạy `python manage.py test App_Billing --noinput`. Bộ test kiểm tra quyền/CSRF, tách tài khoản, giá server, trùng yêu cầu, duyệt/từ chối/hủy, giá liên hệ, tháng lịch, gia hạn giữ phần còn lại, chống kích hoạt lặp, và render trang tài khoản.

## CTA và kỳ hạn hiện tại

- Miễn phí đang dùng: “Đang sử dụng”, vô hiệu hóa ở cả hai tab; không có gia hạn.
- Cùng gói trả phí, cùng kỳ hạn: “Gia hạn gói”. Khác kỳ hạn: “Chuyển sang gói tháng/năm”, ghi lịch sử là “Đổi kỳ hạn”. Việc duyệt vẫn cộng thời hạn mới sau phần còn lại của cùng gói.
- Gói khác: “Chọn gói này”; trả phí → miễn phí: “Chuyển về miễn phí”, form/hồ sơ ghi “Không thời hạn”. Khách chưa đăng nhập: “Bắt đầu miễn phí”.
- Đúng gói/kỳ hạn có yêu cầu chờ: “Đang chờ xử lý”, có thể hủy trong lịch sử.
- Mỗi lần kích hoạt lưu `activation_snapshot` (gói, bản ghi hoặc ngày bắt đầu/kết thúc) trên yêu cầu. Chỉ nhận kỳ hạn từ yêu cầu đã duyệt khớp gói thực tế; thao tác sửa gói thủ công làm snapshot không còn khớp sẽ không giữ nhầm kỳ hạn cũ. Các bản ghi PM/Photo cũ có mã liên kết yêu cầu chính xác vẫn đọc được kỳ hạn. Dữ liệu cũ không đủ thông tin hiển thị “Chưa xác định kỳ hạn” và “Gia hạn theo tháng/năm”; không suy đoán bằng cách chia số ngày còn lại.

CTA dùng màu và icon theo hành động: xanh dương (chọn/đăng ký), xanh lá (gia hạn), tím (đổi kỳ hạn), vàng nhạt (chờ xử lý), xám có dấu kiểm (đang dùng miễn phí), viền xám (chuyển về miễn phí). Nhãn, màu và icon cùng cập nhật khi đổi tab hoặc làm mới lịch sử; nút chờ/đang dùng không có hiệu ứng hover. Có viền focus bàn phím và hỗ trợ giảm chuyển động.
