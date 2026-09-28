# 2) Kiến trúc và data model

## Multi-tenant theo path
- Tenant được định danh bằng `Tenant.public_slug`.
- Public route: `/<public_slug>/` (menu online, đặt món mang đi).
- Public QR route: `/<public_slug>/qr/`.
- Reserved slug đã chặn (`RESERVED_PUBLIC_SLUGS`): `admin`, `accounts`, `api`, `quanly`, `kitchen`, `shifts`, `orders`, `tables`, `static`, `media`, `offline`, `favicon.ico`. Thêm route một cấp mới ở gốc (`/<x>/…`) thì phải thêm `x` vào danh sách này.

## Doanh nghiệp (`Tenant`)
- Cờ tính năng `show_*_feature`, gói cước `subscription_plan`, giới hạn `max_*`, thời hạn gói: `phase3/2_feature_settings_and_plan_limits.md`.
- `tax_percent`: mức thuế (%) cộng vào hoá đơn, server tính khi checkout.
- Helper: `feature_enabled(field)` (cờ bật và gói cho phép), `customer_feature_enabled`, `promotion_feature_enabled`, `recipe_feature_enabled`, `tax_rate` (dạng thập phân), `is_ordering_open()` (nhận đơn QR / mang đi online: bật QR + đang hoạt động + gói còn hạn).

## User và phân quyền
- `User.role`: `MANAGER` / `STAFF`.
- Mỗi tenant tối đa 1 manager (`uq_manager_per_tenant`).
- Tài khoản thuộc tenant không có `is_staff` (không vào Django Admin); chỉ superuser quản trị hệ thống.
- Quyền store theo `UserStoreAccess`.
- Mỗi user tối đa 1 store mặc định (`uq_default_store_per_user`).

## Catalog
- `Category`, `Product`, `ProductUnit`.
- `Topping` tenant-level.
- `ProductTopping` để đặt giá topping theo từng product.
- `StoreCategory` và `StoreProduct` để bật/tắt hiển thị theo store.

## Sales/QR core models
- `DiningTable(tenant, store, code, qr_token, is_active, display_order)`.
- `QROrder(order_type=DINE_IN|TAKEAWAY, status=PENDING|APPROVED|REJECTED|CANCELLED, resolved_at, ...)`.
  - `table` nullable: bắt buộc với `DINE_IN`, để trống với `TAKEAWAY`.
  - Đơn mang đi: `customer_name`, `customer_phone`, `access_key` (khách tra cứu đơn), `sale_order` (OneToOne `Order` khi đã thu tiền).
  - `display_label`: tên bàn hoặc `"Mang đi · <tên khách>"`.
- `QROrderItem` + `QROrderItemTopping` (snapshot).
- `TableCartItem` + `TableCartItemTopping`.
- `Order` + `OrderItem` + `OrderItemTopping`.
- `Order.sale_channel`: `dine_in` (tại quán) / `takeaway` (mang về) — gán lúc checkout POS; dùng hiển thị loại đơn (lịch sử, đơn trong ngày).
- `Customer`: hồ sơ khách hàng theo tenant, tích điểm và hạng thành viên theo tổng chi tiêu.
- `Promotion`: khuyến mãi giảm hóa đơn theo % hoặc số tiền; POS nhân viên chọn khi thanh toán.
- `Order.discount_amount` và snapshot khuyến mãi lưu lại số tiền giảm đã áp dụng tại thời điểm checkout.
- `QROrder.rejection_reason`: lý do từ chối (text, tùy chọn) khi staff reject đơn QR.
- `Order.tax_rate` / `tax_amount`: mức thuế (0.08 = 8%) và tiền thuế lúc bán, lấy từ `Tenant.tax_percent`.
- `Order.client_request_id`: mã POS sinh cho mỗi lần bấm thanh toán, unique theo tenant (`uq_order_tenant_client_request`) — gửi lại cùng mã thì server trả đơn đã tạo, không tạo đơn trùng.
- `Order.status`: `completed` · `cancelled` · `refunded` (đã hoàn đủ tiền). `Order.refunded_amount` (tổng đã hoàn), `Order.table_name` (tên bàn lúc thanh toán, in trên hoá đơn), `Order.print_count` (số lần in hoá đơn). Doanh thu thuần = `total_amount − refunded_amount`.
- `Refund(order, amount, method, reason, is_full, created_by)`: mỗi lần hoàn tiền. Chi tiết: `docs/setup/phase4/2_shifts_and_refunds.md`.
- `Shift(store, status=OPEN|CLOSED, opening_cash, …số liệu chốt ca)`: tối đa 1 ca mở / cửa hàng. Chi tiết: `docs/setup/phase4/2_shifts_and_refunds.md`.
- `KitchenTicket.print_count`: số lần in phiếu bếp.

## Nhật ký thao tác
- `App_Core.AuditLog(tenant, store, user, username, action, object_type, object_repr, message, extra, ip_address, created_at)`.
- Ghi thủ công bằng `App_Core.audit.log_action()` cho nghiệp vụ nhạy cảm; ghi tự động (signal) khi sửa dữ liệu danh mục / cấu hình trong request của người đã đăng nhập. Chi tiết: `docs/setup/phase4/3_audit_log.md`.

## Lifecycle QR
1. Khách gọi món QR (public API) → `QROrder.PENDING`.
2. Nhân viên duyệt → merge vào table cart, order thành `APPROVED`.
3. Nhân viên từ chối → `REJECTED`.
4. Khách hủy đơn pending → `CANCELLED`.
5. Terminal states: `APPROVED/REJECTED/CANCELLED` (không cho sửa/hủy tiếp).

## Lifecycle đơn mang đi (menu online)
1. Khách đặt ở `/<public_slug>/` → `QROrder(order_type=TAKEAWAY, table=None).PENDING`.
2. Nhân viên duyệt → `APPROVED`, tạo phiếu bếp `TAKEAWAY` (nếu bật bếp), không đụng giỏ bàn.
3. Khách tới lấy → POS **Thu tiền** → `POST /api/pos/checkout/` kèm `qr_order_id` → tạo `Order`, gán `QROrder.sale_order`, phiếu bếp cũ gắn `order` (không tạo phiếu mới).
4. Từ chối / huỷ như đơn QR tại bàn.

Chi tiết: `docs/setup/phase2/4_online_takeaway_ordering.md`.

## Realtime QR architecture
- ASGI stack: `Django + Channels + Daphne`.
- Channel layer: Redis (`REDIS_URL`).
- WS group:
  - POS theo store: `pos_store_<store_id>`.
  - Public theo order: `public_qr_order_<order_id>`.
- Event mode: WS chỉ push signal, frontend refetch lại REST API hiện có.
- Fallback: khi WS disconnect, frontend polling 15s.

## Quản lý QR bàn
- Manager CRUD bàn QR trong `/quanly/qr-tables/`.
- Có reset token, tải PNG QR từng bàn.
- Có in PDF khổ lớn theo store (15 bàn/trang).
