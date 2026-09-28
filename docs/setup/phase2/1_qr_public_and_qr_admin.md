# 1) QR public ordering và QR table admin

## Public QR ordering flow

### URL vào trang khách
- `/<public_slug>/qr/?table_code=<CODE>&token=<TOKEN>`

### Hành vi chính
- Hiện menu đúng theo store của bàn.
- Cho chọn unit, topping, note, quantity.
- Gửi đơn tạo `QROrder(order_type=DINE_IN, status=PENDING)`.
- WebSocket realtime để cập nhật trạng thái đơn.
- Nếu mất kết nối WebSocket, fallback polling 15s.
- Cho `edit/cancel` chỉ khi đơn còn `PENDING`. Khách bấm thêm món khi đơn đang chờ → tự vào chế độ sửa đơn.
- Lưu id đơn đang theo dõi theo `table_code` trong localStorage (`eapp_qr_active_order::<slug>::<table_code>`); giỏ nháp cũng được giữ khi tải lại trang.
- Trên giao diện khách không dùng thuật ngữ kỹ thuật: trạng thái kết nối hiện là *"Tự động cập nhật"*.

### Giao diện (làm lại 27/09/2026)
Dùng chung khung với menu online mang đi: `templates/App_Public/_ordering_base.html` + `_ordering_app.html`, `qr_ordering.html` chỉ đặt `mode = "dine_in"`. Mô tả đầy đủ (hiệu ứng lấy theo POS, khung chọn món, thẻ theo dõi đơn): `4_online_takeaway_ordering.md` mục *Giao diện khách*.

Lỗi mở trang (thiếu / sai token, tính năng tắt, gói của quán đã hết hạn) hiện một thẻ thông báo kèm nút **Xem thực đơn của quán** dẫn về menu online. API tạo / sửa đơn cũng trả 403 trong các trường hợp này (`Tenant.is_ordering_open()`); khách vẫn huỷ được đơn đang chờ.

Giới hạn đầu vào: tối đa 100 dòng món, mỗi dòng 1–999 (400 khi vượt). Chưa có rate limit cho QR tại bàn (BL-003).

### POS realtime liên quan
- POS mở socket theo `store_id` để nhận signal đơn QR mới.
- Khi nhận signal, POS refetch `qr/orders` + `tables` và cập nhật badge/chuông.

### Trạng thái đơn
- `PENDING`: chờ staff duyệt.
- `APPROVED`: đã duyệt, merge vào cart bàn (đơn mang đi: báo bếp, chờ thu tiền — xem `4_online_takeaway_ordering.md`).
- `REJECTED`: staff từ chối.
- `CANCELLED`: khách hủy.

## Public QR API nhanh
- `POST /api/public/qr/orders/`
- `GET /api/public/qr/orders/<id>/?table_code=&token=` (đơn mang đi: `?access_key=`)
- `POST /api/public/takeaway/orders/` — tạo đơn mang đi từ menu online
- `PATCH /api/public/qr/orders/<id>/`
- `POST /api/public/qr/orders/<id>/cancel/`

## WebSocket endpoints
- `ws://<host>/ws/pos/store/<store_id>/`
- `ws://<host>/ws/public/qr/order/<order_id>/?table_code=<CODE>&token=<TOKEN>`
- `ws://<host>/ws/public/qr/order/<order_id>/?access_key=<KEY>` (đơn mang đi)

## Quản lý QR bàn

### Chức năng
- CRUD bàn QR theo tenant.
- Reset token QR.
- Copy link QR.
- Tải PNG QR cho từng bàn.
- In PDF A3 theo store, 15 bàn/trang.

### Routes
- `/quanly/qr-tables/`
- `/quanly/qr-tables/<id>/edit/`
- `/quanly/qr-tables/<id>/reset-token/`
- `/quanly/qr-tables/<id>/png/`
- `/quanly/qr-tables/print-pdf/?store=<id>`

## Vận hành nhanh
1. Manager tạo bàn trong `/quanly/qr-tables/`.
2. Copy link QR hoặc tải PNG để in dán bàn.
3. Nếu in hàng loạt, lọc store rồi bấm **In PDF khổ lớn**.
4. Khi lộ token, dùng **Reset token** và in lại QR.
