# Yêu cầu nâng cấp / gia hạn gói

Áp dụng cùng hợp đồng nghiệp vụ cho PM, FnB, POS và Photo. Mỗi repo có `App_Billing`; chỉ `adapter.py`, cấu hình tài khoản và migration phụ thuộc khác nhau.

## Sử dụng

- Trang gói mặc định theo tháng. “Chọn gói này” mở form đã chọn đúng gói và kỳ hạn đang xem. Chọn lại gói trả phí hiện tại để gia hạn.
- Yêu cầu lưu gói, kỳ hạn 1/12 tháng (miễn phí: không thời hạn), giá backend tại thời điểm gửi và ghi chú. Khách có thể hủy yêu cầu đang chờ. Mỗi tài khoản/doanh nghiệp chỉ có một yêu cầu chờ xử lý.
- POS/FnB: chỉ quản lý doanh nghiệp đang hoạt động được gửi và xem lịch sử. PM/Photo: theo tài khoản đăng nhập. Người chưa đăng nhập Photo được chuyển đến đăng nhập.
- Django Admin → **Yêu cầu gói dịch vụ** → **Xem và xử lý**. Chỉ superuser được duyệt, từ chối hoặc hủy; duyệt phải xác nhận đã thanh toán/thỏa thuận. Gói liên hệ cần nhập số tiền báo giá; gói niêm yết phải khớp giá đã lưu.
- Cùng gói còn hạn: nối tiếp thời hạn còn lại theo tháng lịch. Đổi gói hoặc gói hết hạn: bắt đầu từ lúc duyệt. Đổi gói không tự tính hoàn tiền/bù trừ; quản trị viên xác nhận thỏa thuận trước khi duyệt.
- Gói miễn phí không có hạn sử dụng. Gói có giá niêm yết: nếu đã bật SePay, khách chuyển khoản qua mã QR và gói tự kích hoạt khi nhận đủ tiền; chưa bật thì quản trị viên duyệt tay. Gói liên hệ luôn duyệt tay.

## Dữ liệu và ranh giới tích hợp

`SubscriptionRequest` giữ mã tham chiếu duy nhất, người gửi, tài khoản, gói/kỳ hạn/giá đã chốt, trạng thái, phản hồi và dấu thời gian. `PaymentAttempt` tách lần thanh toán khỏi yêu cầu; một yêu cầu có thể có nhiều lần thanh toán nhưng chỉ kích hoạt một lần.

`services.py` là nơi duy nhất thực hiện chuyển trạng thái và gọi `adapter.activate`. Việc duyệt, hủy, xác nhận thanh toán đều trong transaction, khóa tài khoản rồi yêu cầu/lần thanh toán theo cùng thứ tự. Ràng buộc DB bảo vệ một yêu cầu chờ, token gửi lại và mã giao dịch của nhà cung cấp. Các bài kiểm thử local dùng SQLite; khóa hàng cần PostgreSQL trong production và cần kiểm thử cạnh tranh trên PostgreSQL trước khi bật webhook.

Giá nhận từ trình duyệt không được sử dụng. `client_token` chống gửi lại khi mất kết nối; gửi lại yêu cầu đã duyệt không gia hạn lần nữa. Lịch sử chỉ truy vấn tài khoản hiện tại, có phân trang 20 dòng và không cache.

## Thanh toán tự động qua SePay (19/11/2026)

Dùng chung tài khoản SePay và tài khoản ngân hàng nhận tiền với `ecom_final` (xem `ecom_final/docs/features/7_sepay_payment_integration.md`). Code giống hệt nhau ở POS, FnB, PM, Photo: `App_Billing/sepay.py`, `views.sepay_webhook`, `services.record_provider_payment`, `tests_sepay.py`. Sửa ở một app thì đồng bộ sang ba app còn lại.

### Luồng

1. Khách gửi yêu cầu gói có giá niêm yết (> 0đ). Lịch sử yêu cầu hiện mã QR `qr.sepay.vn` có sẵn số tiền đã chốt và nội dung `SEVQR <mã yêu cầu>`, ví dụ `SEVQR POS9650D778E31E4917`. `SEVQR` bắt buộc khi tài khoản nhận là VietinBank cá nhân; giữ cho mọi ngân hàng.
2. Khách quét QR và chuyển khoản. SePay gọi `POST /accounts/billing/sepay/webhook/`.
3. Webhook kiểm chữ ký HMAC-SHA256 (`X-SePay-Signature`, `X-SePay-Timestamp`, lệch tối đa 5 phút), rồi kiểm: chiều tiền `in`, số tài khoản nhận (`accountNumber` hoặc `subAccount`) khớp `SEPAY_BANK_ACCOUNT`, có mã giao dịch, số tiền là số nguyên dương, nội dung có mã yêu cầu đúng tiền tố của app (`BILLING_REFERENCE_PREFIX`: `POS`, `FNB`, `PM`, `PHOTO` + 16 ký tự hex; bỏ qua khoảng trắng/dấu chấm ngân hàng chèn vào).
4. `record_provider_payment` tạo `PaymentAttempt(provider='sepay')`, gọi `record_verified_payment` và kích hoạt gói trong cùng transaction. Lịch sử tự làm mới mỗi 8 giây khi còn QR chờ thanh toán.

Gói miễn phí và gói giá liên hệ không có QR, vẫn duyệt tay. Admin vẫn duyệt tay được như cũ; khi đó lần SePay chờ bị hủy.

### Trường hợp đặc biệt

| Tình huống | Kết quả |
|---|---|
| Giao dịch của app khác, của ecom_final (`DH…`), hoặc không có mã | Bỏ qua, trả 200, log INFO |
| Sai chữ ký / thiếu header / timestamp quá hạn / thiếu secret | 401, log WARNING. SePay sẽ gửi lại |
| Tiền ra, sai tài khoản nhận, số tiền không hợp lệ | Bỏ qua, trả 200, log WARNING |
| Đúng mã nhưng chuyển thiếu, yêu cầu đã hủy/đã duyệt, mã không tồn tại | Không kích hoạt, trả 200, **log ERROR (Sentry báo)**: đối soát tay rồi duyệt hoặc hoàn tiền |
| Chuyển dư | Kích hoạt, lưu số tiền thực nhận trong `PaymentAttempt.received_amount_vnd` |
| SePay gửi lại cùng giao dịch | Không cộng thêm hạn (khóa duy nhất `provider` + `provider_reference`) |

### Bật trên production

Thiếu một trong ba biến đầu thì tính năng tắt hẳn: không hiện QR, webhook trả 404, mọi thứ như trước.

| Biến môi trường | Giá trị |
|---|---|
| `SEPAY_WEBHOOK_HMAC_SECRET` | HMAC Secret Key của webhook **Live** tạo riêng cho app này (không dùng secret Test mode, không dùng chung secret với ecom_final) |
| `SEPAY_BANK_ACCOUNT` | Số tài khoản nhận tiền, giống ecom_final |
| `SEPAY_BANK_CODE` | Mã ngân hàng cho `qr.sepay.vn`, giống ecom_final (vd `vietinbank`) |
| `SEPAY_ACCOUNT_HOLDER` | Tên chủ tài khoản hiển thị dưới QR (tùy chọn) |

Trên `my.sepay.vn/webhooks` (tắt Test mode): tạo webhook mới, sự kiện **Money in**, URL `https://<domain app>/accounts/billing/sepay/webhook/`, bảo mật **HMAC-SHA256**, **không** bật "chỉ gửi khi có mã thanh toán" (mẫu mã thanh toán của công ty đang là `DH` + số cho ecom_final). Thêm 4 biến vào Coolify, redeploy, rồi dùng **Gửi thử** trên SePay: kỳ vọng HTTP 200 `{"success": true}` (payload mẫu không có mã của app nên chỉ bị bỏ qua). Thử thật bằng một yêu cầu gói giá thấp nhất.

Gói FREE của SePay có 50 giao dịch tiền vào mỗi tháng, tính chung cho cả tài khoản (ecom_final + các app).

## Triển khai và kiểm tra

Sau khi cập nhật mã từng app, chạy `python manage.py migrate --noinput`, `python manage.py collectstatic --noinput` rồi khởi động lại dịch vụ theo quy trình hiện có. Migration chỉ thêm bảng yêu cầu/thanh toán, không sửa gói hay thời hạn của khách hiện tại.

Chạy `python manage.py test App_Billing --noinput` (gồm `tests_sepay.py`: chữ ký, replay, sai tài khoản/chiều tiền, thiếu tiền, gửi lại, giao dịch của app khác). Bộ test kiểm tra quyền/CSRF, tách tài khoản, giá server, trùng yêu cầu, duyệt/từ chối/hủy, giá liên hệ, tháng lịch, gia hạn giữ phần còn lại, chống kích hoạt lặp, và render trang tài khoản.

## CTA và kỳ hạn hiện tại

- Miễn phí đang dùng: “Đang sử dụng”, vô hiệu hóa ở cả hai tab; không có gia hạn.
- Cùng gói trả phí, cùng kỳ hạn: “Gia hạn gói”. Khác kỳ hạn: “Chuyển sang gói tháng/năm”, ghi lịch sử là “Đổi kỳ hạn”. Việc duyệt vẫn cộng thời hạn mới sau phần còn lại của cùng gói.
- Gói khác: “Chọn gói này”; trả phí → miễn phí: “Chuyển về miễn phí”, form/hồ sơ ghi “Không thời hạn”. Khách chưa đăng nhập: “Bắt đầu miễn phí”.
- Đúng gói/kỳ hạn có yêu cầu chờ: “Đang chờ xử lý”, có thể hủy trong lịch sử.
- Mỗi lần kích hoạt lưu `activation_snapshot` (gói, bản ghi hoặc ngày bắt đầu/kết thúc) trên yêu cầu. Chỉ nhận kỳ hạn từ yêu cầu đã duyệt khớp gói thực tế; thao tác sửa gói thủ công làm snapshot không còn khớp sẽ không giữ nhầm kỳ hạn cũ. Các bản ghi PM/Photo cũ có mã liên kết yêu cầu chính xác vẫn đọc được kỳ hạn. Dữ liệu cũ không đủ thông tin hiển thị “Chưa xác định kỳ hạn” và “Gia hạn theo tháng/năm”; không suy đoán bằng cách chia số ngày còn lại.

CTA dùng màu và icon theo hành động: xanh dương (chọn/đăng ký), xanh lá (gia hạn), tím (đổi kỳ hạn), vàng nhạt (chờ xử lý), xám có dấu kiểm (đang dùng miễn phí), viền xám (chuyển về miễn phí). Nhãn, màu và icon cùng cập nhật khi đổi tab hoặc làm mới lịch sử; nút chờ/đang dùng không có hiệu ứng hover. Có viền focus bàn phím và hỗ trợ giảm chuyển động.
