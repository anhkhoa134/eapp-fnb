# 3) Kiến trúc và data model

## Multi-tenant theo path
- Tenant được định danh bằng `Tenant.public_slug`.
- Public route: `/<public_slug>/`.
- Public QR route: `/<public_slug>/qr/`.
- Reserved slug đã chặn: `admin`, `accounts`, `api`, `quanly`, `static`, `media`, `favicon.ico`.

## User và phân quyền
- `User.role`: `MANAGER` / `STAFF`.
- Mỗi tenant tối đa 1 manager (`uq_manager_per_tenant`).
- Quyền store theo `UserStoreAccess`.
- Mỗi user tối đa 1 store mặc định (`uq_default_store_per_user`).

## Catalog
- `Category`, `Product`, `ProductUnit`.
- `Topping` tenant-level.
- `ProductTopping` để đặt giá topping theo từng product.
- `StoreCategory` và `StoreProduct` để bật/tắt hiển thị theo store.

## Sales/QR core models
- `DiningTable(tenant, store, code, qr_token, is_active, display_order)`.
- `QROrder(status=PENDING|APPROVED|REJECTED|CANCELLED, resolved_at, ...)`.
- `QROrderItem` + `QROrderItemTopping` (snapshot).
- `TableCartItem` + `TableCartItemTopping`.
- `Order` + `OrderItem` + `OrderItemTopping`.
- `Order.sale_channel`: `dine_in` (tại quán) / `takeaway` (mang về) — gán lúc checkout POS; dùng hiển thị loại đơn (lịch sử, đơn trong ngày).
- `QROrder.rejection_reason`: lý do từ chối (text, tùy chọn) khi staff reject đơn QR.

## Lifecycle QR
1. Khách gọi món QR (public API) → `QROrder.PENDING`.
2. Nhân viên duyệt → merge vào table cart, order thành `APPROVED`.
3. Nhân viên từ chối → `REJECTED`.
4. Khách hủy đơn pending → `CANCELLED`.
5. Terminal states: `APPROVED/REJECTED/CANCELLED` (không cho sửa/hủy tiếp).

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
