# 2) Ca làm việc (chốt ca) và hoàn tiền

Backlog: BL-011 (ca làm việc), BL-012 (hoàn tiền).

## Ca làm việc

### Bật tính năng
- Cờ `Tenant.show_shift_feature` — mặc định **tắt**. Manager bật tại `/quanly/settings/features/`.
- Gắn với gói cước: `SubscriptionPlan.feature_shift`. Gói *Miễn phí* không có; *Cơ bản*, *Chuyên nghiệp*, *Doanh nghiệp* có. Gói không có thì công tắc bị khoá (*Cần nâng cấp gói*). Xem `phase3/2_feature_settings_and_plan_limits.md`.
- Khi tắt: `/shifts/`, `/shifts/<id>/print/` trả 403; `GET /api/pos/shifts/current/` trả 403; ẩn mục *Ca làm việc* ở sidebar, menu tài khoản POS, trang Đơn trong ngày. Dữ liệu ca (kể cả ca đang mở) được giữ nguyên, bật lại dùng tiếp.
- Bán hàng **không bắt buộc** phải mở ca. Ca chỉ dùng để đối soát tiền mặt.

### Lối vào
- POS: menu tài khoản → **Ca làm việc** (badge *Đang mở* / *Chưa mở ca* theo cửa hàng đang chọn).
- Quản lý: sidebar, nhóm con dưới **Cấu hình tính năng** (manager).
- Trang Đơn trong ngày: nút **Ca làm việc**.

### Model `Shift`
`Shift(tenant, store, status=OPEN|CLOSED, opened_by, opened_at, opening_cash, closed_by, closed_at, note, …)`
- Mỗi cửa hàng tối đa **1 ca đang mở** (`uq_open_shift_per_store`). Ca gắn theo cửa hàng (một két tiền), không theo nhân viên.
- Khi chốt, số liệu được **chụp lại** vào ca: `order_count`, `gross_sales`, `cash_sales`, `card_sales`, `discount_total`, `refund_total`, `cash_refunds`, `expected_cash`, `counted_cash`, `cash_difference`. Sau đó sửa / xoá đơn không làm đổi báo cáo ca đã chốt.

### Cách tính (`App_Sales/shifts.py`)
- Đơn thuộc ca: `Order` của cửa hàng có `created_at` trong `[opened_at, closed_at]` (ca đang mở: tới hiện tại), trừ đơn `cancelled`. Đơn đã hoàn tiền vẫn tính vào doanh thu ca; phần hoàn tính riêng.
- Hoàn tiền thuộc ca: `Refund` của cửa hàng có `created_at` trong khoảng ca (có thể là hoàn cho đơn của ca trước).
- **Tiền mặt dự kiến** = tiền đầu ca + thu tiền mặt − hoàn tiền mặt.
- **Chênh lệch** = tiền mặt thực đếm − dự kiến (âm = thiếu, dương = thừa).
- Doanh thu thuần = doanh thu − hoàn tiền.

### Trang `/shifts/`
- `GET ?store_id=` — ca đang mở (KPI trực tiếp) hoặc form mở ca; lịch sử ca các cửa hàng user có quyền (15 dòng/trang, `?page=`).
- `POST action=open` — `store_id`, `opening_cash` (nhận `1.500.000`), `note`. Mở trùng → báo lỗi.
- `POST action=close` — `store_id`, `counted_cash` (bắt buộc), `note`. Trước khi gửi có hộp thoại xác nhận. Chốt xong chuyển về `?store_id=&print_shift=<id>` và tự in báo cáo chốt ca.
- Ô tiền tự định dạng dấu chấm; khi nhập tiền thực đếm, trang hiện ngay *Thừa / Thiếu … đ so với dự kiến*.
- Staff và manager đều mở / chốt ca được (với cửa hàng mình có quyền).

### Báo cáo ca (in)
`/shifts/<id>/print/`: doanh thu (tiền mặt, thẻ/QR), giảm giá, hoàn tiền, doanh thu thuần; tiền mặt trong két (đầu ca, + thu, − hoàn, = dự kiến, thực đếm, chênh lệch); danh sách món bán ra; ghi chú; ô ký Thu ngân / Quản lý. Ca đang mở in bản *BÁO CÁO CA (ĐANG MỞ)* tính tới thời điểm in.

## Hoàn tiền

### Quy tắc
- Chỉ **manager**, tại `/quanly/orders/` → nút hoàn tiền trên đơn → modal: **Hoàn toàn bộ** số còn lại hoặc **Hoàn một phần** (nhập số tiền), hình thức hoàn (tiền mặt / thẻ-QR, mặc định theo đơn), **lý do bắt buộc**, xác nhận qua hộp thoại. Trang Đơn trong ngày có lối tắt (manager) sang Lịch sử đơn đã lọc theo mã đơn.
- Hoàn nhiều lần được, tổng không vượt `total_amount`. Đơn `cancelled` không hoàn được.
- Nghiệp vụ: `create_refund()` trong `App_Sales/services.py` (khoá dòng `Order` bằng `select_for_update`).

### Model
- `Refund(tenant, store, order, amount, method=cash|card, reason, is_full, created_by, created_at)`.
- `Order.refunded_amount` — tổng đã hoàn. Hoàn đủ → `Order.status = refunded` (*Đã hoàn tiền*).
- `Order.refundable_amount`, `Order.net_amount` (property).

### Ảnh hưởng số liệu
| Chỗ | Cách tính |
|---|---|
| Dashboard `/quanly/`, Lịch sử đơn, Đơn trong ngày | Doanh thu **thuần** = `Sum(total_amount − refunded_amount)` (`sum_net_revenue()`); đơn hoàn toàn bộ không còn tính vào số đơn hoàn thành |
| Khách hàng | `total_spent`, điểm, hạng tính lại trên doanh thu thuần (`recompute_customer_stats`) |
| Ca làm việc | Hoàn tiền mặt trừ vào tiền mặt dự kiến của ca đang mở tại thời điểm hoàn |
| Hoá đơn in | Liệt kê các lần hoàn + *Thực thu*; đơn hoàn toàn bộ có dấu *ĐÃ HOÀN TIỀN* |
| Nhật ký | Mỗi lần hoàn ghi `order.refund` kèm số tiền, hình thức, lý do |

Chưa làm (theo BL-011 / BL-012): gắn cứng `Order` với ca, thu/chi ngoài bán hàng trong ca, hoàn theo từng món, quyền hoàn tiền riêng cho nhân viên (BL-021).

## Test
`App_Sales.tests_ops.ShiftTests` (mở / chốt ca, chênh lệch, số liệu chốt không đổi, bật/tắt tính năng, gắn gói cước, slug `shifts` dành riêng) và `RefundTests` (hoàn một phần rồi toàn bộ, vượt số tiền, bắt buộc lý do, chỉ manager, doanh thu thuần).
