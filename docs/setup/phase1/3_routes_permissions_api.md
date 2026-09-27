# 3) Route, permission, API contracts

## Web routes
- `GET /` → POS (staff/manager, login required).
- `GET /orders/today/` → đơn hôm nay (staff/manager, login required).
- `GET /kitchen/` → màn hình bếp (staff/manager, login required; 403 khi tenant tắt `show_kitchen_feature`).
- `GET|POST /shifts/?store_id=` → ca làm việc: mở ca (`action=open`), chốt ca (`action=close`) (staff/manager; 403 khi tenant tắt `show_shift_feature`). Chi tiết: `docs/setup/phase4/2_shifts_and_refunds.md`.
- Trang in (staff/manager có quyền store; `?autoprint=1` để tự mở hộp thoại in và đếm lần in; cho phép nhúng iframe cùng origin):
  - `GET /orders/<order_id>/receipt/` → hoá đơn.
  - `GET /tables/<table_id>/bill/` → phiếu tạm tính của giỏ bàn.
  - `GET /kitchen/tickets/<ticket_id>/print/` → phiếu bếp (403 khi tắt `show_kitchen_feature`).
  - `GET /shifts/<shift_id>/print/` → báo cáo ca (403 khi tắt `show_shift_feature`).
  - Chi tiết: `docs/setup/phase4/1_printing.md`.
- `GET /quanly/*` → manager only.
- `GET /accounts/login/` → login.
- `POST /accounts/logout/` → logout.
- `GET /<public_slug>/` → menu online (xem menu, đặt món mang đi).
- `GET /<public_slug>/qr/?table_code=&token=` → public QR ordering UI.
- `GET /manifest.webmanifest` → Web App Manifest (PWA).
- `GET /sw.js` → service worker (PWA).
- `GET /offline/` → trang fallback khi ngoại tuyến (PWA).

Chi tiết: `docs/setup/phase2/3_pwa.md`.

## Security notes
- `GET /accounts/logout/` ⇒ 405.
- Public QR APIs bắt buộc `table_code + token` hợp lệ; đơn mang đi dùng `access_key` riêng của từng đơn.
- Tạo đơn mang đi giới hạn 10 đơn / 30 phút / IP / tenant (429 khi vượt).
- POS APIs chỉ thao tác trên store user được cấp quyền.
- POS WebSocket cần login + có quyền store.
- Public WebSocket cần `table_code + token` hợp lệ và order thuộc đúng bàn, hoặc `access_key` đúng của đơn mang đi.

## POS API (`/api/pos/`)
- `GET products/?store_id=&q=&category=`
- `POST checkout/` — mang về; tuỳ chọn `qr_order_id` khi thu tiền đơn mang đi khách đặt online (đơn phải `TAKEAWAY` + `APPROVED` + chưa thu; không tạo phiếu bếp lần hai)
- `GET tables/?store_id=`
- `GET tables/<table_id>/cart/`
- `POST tables/<table_id>/cart/items/`
- `PATCH tables/<table_id>/cart/items/<item_id>/`
- `DELETE tables/<table_id>/cart/items/<item_id>/`
- `POST tables/<table_id>/cart/import-takeaway/`
- `POST tables/<table_id>/cart/move-to/` (body: `{ "to_table_id": <id> }`)
- `POST tables/<table_id>/checkout/`
- Response của `checkout/` và `tables/<id>/checkout/` có thêm `kitchen_ticket_id` (phiếu bếp vừa tạo, hoặc `null`) để POS tự in phiếu bếp.
- `GET shifts/current/?store_id=` → `{ "store_id", "shift": null | { "id", "opened_at", "opened_by", "opening_cash" } }` (403 khi tắt `show_shift_feature`)
- `GET qr/orders/?store_id=&status=pending|approved|rejected|cancelled|awaiting_payment` (`awaiting_payment` = đơn mang đi đã duyệt, chưa thu tiền; mỗi dòng có `order_type`, `customer_name`, `customer_phone`)
- `POST qr/orders/<order_id>/approve/` — đơn tại bàn: merge vào giỏ bàn; đơn mang đi: chỉ báo bếp. Response có `order_type`
- `POST qr/orders/<order_id>/reject/`
- `POST tables/<table_id>/kitchen/send/` → báo bếp phần số lượng chưa gửi của giỏ bàn (201 + `ticket_id`, hoặc 200 + `ticket_id: null` khi không có món mới)
- `GET kitchen/tickets/?store_id=&scope=active|done` → phiếu bếp đang chờ / đã xong hôm nay
- `POST kitchen/items/<item_id>/status/` (body: `{ "status": "PENDING|PREPARING|DONE" }`)
- `POST kitchen/tickets/<ticket_id>/complete/` → xong cả phiếu

Ghi chú màn hình bếp (chỉ khi tenant bật `show_kitchen_feature`): phiếu bếp (`KitchenTicket`) tạo khi bấm **Báo bếp** ở giỏ bàn, khi duyệt đơn QR (tại bàn hoặc mang đi), khi thanh toán mang về (trừ đơn mang đi online đã báo bếp lúc duyệt), và khi thanh toán bàn còn món chưa báo. `TableCartItem.kitchen_sent_quantity` giữ số đã báo; giảm số lượng / xoá / đổi ghi chú hoặc topping món đã báo sẽ huỷ phần bếp chưa làm xong. Chi tiết: `docs/setup/phase3/1_kitchen_display.md`.

Ghi chú hành vi POS (frontend, `templates/App_Sales/index.html`): chọn bàn khi đang **mang về** có món → `POST .../cart/import-takeaway/` rồi `GET .../cart/`; **Đổi sang mang về** khi đang gắn bàn → `DELETE .../cart/items/<item_id>/` cho từng dòng rồi giữ giỏ trên client dạng mang về.

## Public API (`/api/public/`)
- `POST qr/orders/` → tạo đơn pending tại bàn.
- `POST takeaway/orders/` → tạo đơn mang đi (body `tenant_slug`, `store_id`, `customer_name`, `customer_phone`, `note`, `items`); trả thêm `access_key`.
- `GET qr/orders/<order_id>/?table_code=&token=` (hoặc `?access_key=`) → lấy trạng thái + items.
- `PATCH qr/orders/<order_id>/` → cập nhật đơn pending (replace items + note).
- `POST qr/orders/<order_id>/cancel/` → hủy đơn pending (`CANCELLED`).

Chi tiết đơn mang đi: `docs/setup/phase2/4_online_takeaway_ordering.md`.

## WebSocket routes
- `GET ws://<host>/ws/pos/store/<store_id>/`
- `GET ws://<host>/ws/public/qr/order/<order_id>/?table_code=&token=` (đơn mang đi: `?access_key=`)

## WebSocket message schema
- POS:
  - `{ "type": "qr.changed", "store_id": <id>, "order_id": <id>, "reason": "created|updated|approved|rejected|cancelled", "ts": "<iso>" }`
  - `{ "type": "kitchen.changed", "store_id": <id>, "ticket_id": <id|null>, "reason": "created|status|done|cancelled|moved", "message": "...", "ts": "<iso>" }` (POS và `/kitchen/` dùng chung kênh này)
- Public QR:
  - `{ "type": "qr.order.changed", "order_id": <id>, "status": "PENDING|APPROVED|REJECTED|CANCELLED", "reason": "created|updated|approved|rejected|cancelled|paid", "ts": "<iso>" }`

## Quanly API-like routes (server-rendered)

Tất cả dưới đây yêu cầu **manager** (trừ khi ghi chú khác).

- `GET|POST /quanly/` — dashboard (`GET`: `store`, `period` = `7d` \| `30d` \| `this_month` \| `last_month` \| `this_year` \| `last_year`, hoặc `date_from` / `date_to` khi `period` trống)
- `GET|POST /quanly/stores/` — CRUD cửa hàng (POST tạo; POST edit/delete theo URL riêng). 403 khi tenant tắt `show_store_feature` (mặc định tắt: chỉ 1 cửa hàng)
- `GET|POST /quanly/account/` — trang Tài khoản (**staff + manager**, trang duy nhất trong `/quanly/` staff vào được). POST phân biệt bằng `form_action`:
  - `profile` — cập nhật họ tên (`first_name`), email (`AccountProfileForm`). Manager bắt buộc email (dùng cho Quên mật khẩu) và sửa thêm `tenant_name` (tên doanh nghiệp); staff gửi `tenant_name` bị bỏ qua.
  - `password_change` — đổi mật khẩu (`POSPasswordChangeForm`), giữ phiên hiện tại.
  - Manager thấy thêm bảng *Các gói cước & nâng cấp*. Anchor `#doi-mat-khau` trỏ tới thẻ đổi mật khẩu.
  - Menu avatar (`base.html` và POS): *Thông tin tài khoản* → trang này; `base.html` có *Lịch sử đơn* (manager → `/quanly/orders/`, staff → `/orders/today/`), POS có *Đổi mật khẩu* → `#doi-mat-khau`.
  - Sidebar (`_sidebar_nav.html`) với staff chỉ hiện *Tài khoản* và liên kết nhanh; các mục manager-only bị ẩn. *Ca làm việc* nằm trong nhóm con dưới *Cấu hình tính năng* (manager, khi bật); staff vào ca làm việc từ menu tài khoản POS.
  - `/accounts/password/change/` vẫn còn nhưng không còn menu nào trỏ tới.
- `GET|POST /quanly/settings/features/` — cấu hình tính năng nâng cao (cửa hàng nhiều chi nhánh, khách hàng, khuyến mãi, topping, QR bàn, màn hình bếp, ca làm việc)
- `GET /quanly/orders/`, `POST /quanly/orders/<id>/delete/` — lịch sử đơn (xoá đơn ghi nhật ký `order.delete`; lọc `status` gồm cả `refunded`)
- `POST /quanly/orders/<id>/refund/` — hoàn tiền: `refund_type=full|partial`, `amount` (khi `partial`), `method=cash|card`, `reason` (bắt buộc), `next`. Chi tiết: `docs/setup/phase4/2_shifts_and_refunds.md`
- `GET /quanly/audit-log/?action=&user=&store=&date_from=&date_to=&q=&page=` — nhật ký thao tác (`action` nhận mã thao tác hoặc `group:<n>`). Chi tiết: `docs/setup/phase4/3_audit_log.md`
- `GET|POST /quanly/categories/`, `.../products/`, `.../toppings/`, ... — catalog CRUD (xem `App_Quanly/urls.py`)
- `POST /quanly/reorder/<units|toppings|tables>/` — lưu thứ tự sau kéo thả, body JSON `{ "ids": [...] }` theo thứ tự mới (400 nếu id trùng / không thuộc cùng danh sách; 403 khi tính năng tương ứng tắt)
- `GET|POST /quanly/payment-qr/` — cấu hình QR thanh toán POS theo cửa hàng
- `GET|POST /quanly/staffs/` — quản lý nhân viên
- `GET|POST /quanly/qr-tables/`
- `GET|POST /quanly/qr-tables/<id>/edit/`
- `POST /quanly/qr-tables/<id>/delete/`
- `POST /quanly/qr-tables/<id>/reset-token/`
- `GET /quanly/qr-tables/<id>/png/`
- `GET /quanly/qr-tables/print-pdf/?store=<id>`

## Phân trang (danh sách render server)

- **Kích thước trang:** 20 bản ghi (cùng mức với lịch sử đơn).
- **Partial dùng chung:** `templates/App_Quanly/_list_pagination.html` — liên kết *Trước* / *Sau* và hiển thị `Trang n/tổng`.
- **Quản lý** — tham số GET `page` trên:
  - `/quanly/stores/`, `/quanly/categories/`, `/quanly/products/`, `/quanly/staffs/`, `/quanly/qr-tables/`
  - Trên **QR bàn**, bộ lọc `?store=<id>` được giữ khi chuyển trang.
- **Quản lý → Topping** (`/quanly/toppings/`): hai bảng độc lập:
  - `page` — danh sách topping;
  - `mpage` — bảng gán topping theo sản phẩm;
  - Link phân trang của mỗi bảng giữ tham số của bảng còn lại (ví dụ đổi trang topping không reset trang gán).
- **Đơn trong ngày** `GET /orders/today/?store_id=&page=`:
  - Các chỉ số KPI (tổng đơn, doanh thu, giá trị đơn trung bình) tính trên **toàn bộ** đơn sau khi lọc cửa hàng;
  - Chỉ **bảng chi tiết** theo từng trang.
- **Đã có từ trước (không đổi):** lịch sử đơn `/quanly/orders/`.
- **Menu online** `/<public_slug>/`: không phân trang server nữa (từ 27/09/2026) — tải toàn bộ món của store, lọc / tìm ở trình duyệt như trang QR.
- **Dashboard** `/quanly/`: khối **Đơn gần nhất** vẫn giới hạn cố định trên server (không dùng tham số `page`).

## Payment rule
- `cash`: `customer_paid >= total_amount`.
- `card`: nếu `customer_paid <= 0` backend set bằng `total_amount`.
