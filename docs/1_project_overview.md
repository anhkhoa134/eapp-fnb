# 1) Tổng quan project eApp FnB

## Mục tiêu
- Xây dựng hệ thống POS multi-tenant theo path-based tenancy.
- Nhân viên thao tác bán hàng tại `/`.
- Quản lý thao tác CRUD + dashboard tại `/quanly/`.
- Khách xem catalog public tại `/<public_slug>/`.
- Khách đặt món QR full flow tại `/<public_slug>/qr/?table_code=...&token=...`.

## Công nghệ
- Python 3.10
- Django 5.0
- Django Channels (ASGI/WebSocket)
- Bootstrap 5.3
- SQLite mặc định, có cấu hình PostgreSQL qua env.
- Redis cho realtime WebSocket channel layer.

## Kiến trúc app
- `App_Core`: tiện ích dùng chung, context processor, seed command.
- `App_Accounts`: custom user, login/logout, password change.
- `App_Tenant`: tenant, store, user-store access.
- `App_Catalog`: category, product, unit, topping, mapping theo store.
- `App_Sales`: POS APIs, table cart, QR approve/reject, checkout.
- `App_Quanly`: dashboard, order history, CRUD, quản lý QR bàn + in QR.
- `App_Public`: public catalog, public QR ordering UI + public QR APIs.

## Trạng thái hiện tại
- Đã có: POS takeaway/table, topping full-stack, QR flow staff, QR flow khách (create/edit/cancel/status), quản lý QR bàn (PNG/PDF 15 bàn/trang).
- POS: chọn bàn từ **mang về** có món thì tự động **import** lên cart bàn (`import-takeaway`); **Đổi sang mang về** thì **xóa hết** cart bàn trên server rồi giữ món trên giỏ mang về; trên **mobile**, mở offcanvas giỏ rồi chọn tab/icon **Chọn bàn** thì offcanvas đóng để không che lưới bàn.
- Quản lý: CRUD cửa hàng (có số điện thoại từng cửa hàng), QR thanh toán POS (upload/xóa ảnh), giao diện responsive (menu mobile offcanvas); **phân trang** các bảng danh sách CRUD + trang **Đơn trong ngày** (`/orders/today/`) — 20 dòng/trang, partial `App_Quanly/_list_pagination.html`; trang **Topping** có hai bộ phân trang (`page` / `mpage`). **Dashboard** — bảng *Đơn gần nhất* không phân trang (giới hạn cố định).
- Đơn POS: trường `Order.sale_channel` (tại quán / mang về); đơn QR từ chối có lưu `QROrder.rejection_reason` (hiển thị lịch sử / dashboard theo thiết kế UI).
- QR realtime đã dùng WebSocket cho POS + Public QR, có fallback polling 15s khi WS mất kết nối.
- Superadmin tạo tenant trong Django Admin/Jazzmin sẽ tự bootstrap dữ liệu mặc định:
  1 quản lý, 2 nhân viên, 1 store, 12 bàn có QR token, 2 category, 4 product có unit.
- Chưa làm: inventory, shift, refund.

## Danh sách tài liệu theo thứ tự
1. `docs/1_project_overview.md`
2. `docs/2_setup_and_run.md`
3. `docs/3_architecture_and_data_model.md`
4. `docs/4_routes_permissions_api.md`
5. `docs/5_seed_demo_data.md`
6. `docs/6_testing_and_smoke.md`
7. `docs/7_qr_public_and_qr_admin.md`
8. `docs/8_websocket_realtime.md`
9. `docs/9_deploy_production.md`
10. `docs/10_pwa.md`

## Tài liệu kiểm thử (QA / tester)

- Trang bán hàng (POS): `docs/testing/trang_ban_hang.md`
- Trang quản lý: `docs/testing/trang_quan_ly.md`
