# 4) Menu online & đặt món mang đi

**Cập nhật:** 27/09/2026 · Backlog: BL-024 (phần mang đi)

Trang menu công khai `/<public_slug>/` (trước đây gọi là *Public catalog*) nay cho khách **đặt món mang đi**: chọn món, để lại tên + SĐT, quán duyệt trên POS và báo bếp, khách ghé lấy và trả tiền tại quầy. Trang dùng chung giao diện với trang gọi món QR tại bàn.

Trên trang Quản lý, liên kết nhanh tới trang này tên là **Menu online**.

## Khi nào khách đặt được
Trang chỉ nhận đặt món khi **cả hai** điều kiện đúng:
- Tenant bật `show_qr_order_feature` (cùng cờ với gọi món QR, vì đơn đi qua tab **Đơn QR** trên POS).
- Gói cước chưa hết hạn (`Tenant.is_subscription_expired()` là `False`).

Nếu không, trang chỉ hiện thực đơn để xem, kèm dòng *"Quán hiện chưa nhận đặt món online…"*. API tạo đơn trả `403`.

## Luồng nghiệp vụ
```
Khách (/<slug>/)           POS (tab Đơn QR)                 Bếp (/kitchen/)
─────────────────          ─────────────────────            ───────────────
Chọn món, nhập tên + SĐT
Gửi đơn ──────────────▶ Đơn chờ duyệt (thẻ túi xanh,
  PENDING                 tên + SĐT khách)
                          Duyệt ───────────────────────▶ Phiếu TAKEAWAY
  APPROVED ◀─────────────  "Mang đi · chờ khách tới lấy"   "Mang đi · <tên>"
                          (khách tới) Thu tiền
                          → món vào giỏ mang về → Thanh toán
  "Đã lấy món" ◀────────  Order tạo, gắn QROrder.sale_order
```
- **Duyệt:** không đụng giỏ bàn. Nếu bật bếp, tạo phiếu `KitchenTicket(source=TAKEAWAY, table_name="Mang đi · <tên>", qr_order=…)` ngay lúc duyệt.
- **Thu tiền:** nút **Thu tiền** đưa món của đơn vào giỏ mang về (thay giỏ hiện tại sau khi hỏi xác nhận nếu giỏ đang có món; đang ở bàn thì tự chuyển sang mang về, vẫn quay lại bàn được). Thanh toán gửi thêm `qr_order_id`.
- **Checkout có `qr_order_id`:** server kiểm tra đơn là `TAKEAWAY` + `APPROVED` + cùng store + chưa thu tiền. Sau khi tạo `Order`: gán `QROrder.sale_order`; nếu đơn đã có phiếu bếp thì **không tạo phiếu mới**, chỉ gắn `KitchenTicket.order`. Thu tiền lần hai cho cùng đơn trả `400`.
- **Từ chối / khách huỷ:** như đơn QR tại bàn.

## Data model (`App_Sales.QROrder`, migration `0012_qr_takeaway`)
| Field | Ý nghĩa |
|---|---|
| `order_type` | `DINE_IN` (tại bàn, mặc định) · `TAKEAWAY` (mang đi) |
| `table` | Nay `null=True`. Bắt buộc với `DINE_IN` (kiểm tra trong `clean()`), để trống với `TAKEAWAY` |
| `customer_name`, `customer_phone` | Người nhận (chỉ đơn mang đi). SĐT được chuẩn hoá bỏ khoảng trắng, `.`, `-`, `()` |
| `access_key` | Khoá ngẫu nhiên (`secrets.token_urlsafe(24)`) để khách xem / sửa / huỷ đơn của mình |
| `sale_order` | `OneToOne → Order`, hoá đơn POS đã thu tiền. `null` = chưa thu |

Thuộc tính: `is_takeaway`, `display_label` (tên bàn, hoặc `"Mang đi · <tên khách>"`). POS, bếp, audit log và lịch sử đơn dùng `display_label`.

## API
### Public (`/api/public/`, không cần đăng nhập, `csrf_exempt`)
| Method | URL | Ghi chú |
|---|---|---|
| `POST` | `takeaway/orders/` | Body: `tenant_slug`, `store_id`, `customer_name`, `customer_phone`, `note`, `items[]` (`product_id`, `unit_id`, `quantity`, `note`, `topping_ids`). Trả `201` + `qr_order_id`, `access_key`, `order` |
| `GET` | `qr/orders/<id>/?access_key=` | Dùng chung endpoint với đơn QR, xác thực bằng `access_key` thay cho `table_code + token` |
| `PATCH` | `qr/orders/<id>/` | Body có `access_key`, chỉ khi còn `PENDING` |
| `POST` | `qr/orders/<id>/cancel/` | Body có `access_key`, chỉ khi còn `PENDING` |

Kiểm tra đầu vào khi tạo đơn:
- Tên bắt buộc. SĐT theo mẫu `^(\+?84|0)\d{8,10}$`.
- Món phải thuộc store, đang bán và danh mục đang hiển thị ở store (giống đơn QR).
- **Giới hạn tần suất:** tối đa **10 đơn / 30 phút / IP / tenant** (`TAKEAWAY_ORDER_LIMIT_PER_IP`, `TAKEAWAY_ORDER_WINDOW` trong `App_Public/views.py`), vượt thì trả `429`. Dùng `App_Accounts.rate_limit` với scope `takeaway_order_ip`; IP lấy qua `get_client_ip` (tôn trọng `LOGIN_TRUST_X_REAL_IP`).

Payload `order` trả về có thêm: `order_type`, `customer_name`, `customer_phone`, `rejection_reason` (khi bị từ chối), `is_paid`. `table` là `null` với đơn mang đi.

### POS (`/api/pos/`)
- `GET qr/orders/?store_id=&status=awaiting_payment`: đơn mang đi đã duyệt, chưa thu tiền. Mỗi dòng có thêm `order_type`, `customer_name`, `customer_phone`; `table_name` = `display_label`.
- `POST qr/orders/<id>/approve/`: response có thêm `order_type`.
- `POST checkout/`: nhận thêm `qr_order_id` (tuỳ chọn).

### WebSocket
- Khách: `ws://<host>/ws/public/qr/order/<id>/?access_key=<KEY>`.
- Sau khi thu tiền, server push `qr.order.changed` với `reason: "paid"` để trang khách chuyển sang *"Bạn đã nhận món"*.

## Giao diện khách (dùng chung QR tại bàn và mang đi)
Template:
- `templates/App_Public/_ordering_base.html`: khung trang độc lập (không dùng `App_Core/base.html`), gồm CSS, header, toast.
- `templates/App_Public/_ordering_app.html`: lưới món, giỏ, khung chọn món, theo dõi đơn, toàn bộ JS.
- `catalog.html` (`mode = "takeaway"`) và `qr_ordering.html` (`mode = "dine_in"`) kế thừa khung trên.

Dữ liệu khởi tạo nằm trong `json_script` id `order-bootstrap-data`, gồm `mode`, `ordering_enabled`, `store`, `categories`, `products` (và `table_code`, `token` với QR).

Hành vi chính:
- Tìm món không phân biệt dấu. Danh mục là các chip cuộn ngang.
- Bấm thẻ món → khung chọn size, topping, ghi chú, số lượng (trượt từ dưới lên trên điện thoại). Nút **+** thêm nhanh nếu món chỉ có 1 size và không có topping.
- Hiệu ứng lấy theo POS: thẻ nổi lên khi hover, thu nhỏ khi bấm, ảnh bay vào giỏ, số lượng giỏ nảy lên.
- Giỏ: thanh nổi ở đáy màn hình điện thoại (mở offcanvas), cột phải trên desktop (`offcanvas-lg`).
- Thẻ theo dõi đơn có thanh tiến trình:
  - Tại bàn: *Đã gửi → Quán xác nhận → Đang chuẩn bị*.
  - Mang đi: thêm bước *Đã lấy món*.
  - Bị từ chối thì hiện lý do. Có chữ *"Tự động cập nhật"* khi đang theo dõi, không dùng thuật ngữ kỹ thuật.
- Đơn đang chờ mà khách bấm thêm món → tự vào chế độ sửa đơn (nạp món của đơn vào giỏ).

localStorage (mọi truy cập đều bọc `try/catch`):
| Key | Nội dung |
|---|---|
| `eapp_qr_active_order::<slug>::<table_code>` | id đơn QR đang theo dõi (giữ tương thích bản cũ) |
| `eapp_takeaway_order::<slug>::store-<id>` | `{id, key}` đơn mang đi đang theo dõi |
| `eapp_order_cart::<mode>::<ngữ cảnh>` | Giỏ nháp; món không còn bán sẽ bị bỏ khi tải lại |
| `eapp_takeaway_customer::<slug>` | Tên + SĐT khách để điền sẵn lần sau |

## Chưa làm (còn trong BL-024)
- Chọn giờ nhận món.
- Giao hàng (địa chỉ, phí ship).
- Thanh toán online trước khi tới lấy (phụ thuộc BL-010).

## Test
```bash
python manage.py test App_Public   # PublicTakeawayApiTests + PublicQrApiTests
```
