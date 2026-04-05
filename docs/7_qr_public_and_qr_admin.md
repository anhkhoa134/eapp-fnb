# 7) QR public ordering và QR table admin

## Public QR ordering flow

### URL vào trang khách
- `/<public_slug>/qr/?table_code=<CODE>&token=<TOKEN>`

### Hành vi chính
- Hiện menu đúng theo store của bàn.
- Cho chọn unit, topping, note, quantity.
- Gửi đơn tạo `QROrder.PENDING`.
- WebSocket realtime để cập nhật trạng thái đơn.
- Nếu mất kết nối WebSocket, fallback polling 15s.
- Cho `edit/cancel` chỉ khi đơn còn `PENDING`.
- Lưu `active_qr_order_id` theo `table_code` trong localStorage.

### POS realtime liên quan
- POS mở socket theo `store_id` để nhận signal đơn QR mới.
- Khi nhận signal, POS refetch `qr/orders` + `tables` và cập nhật badge/chuông.

### Trạng thái đơn
- `PENDING`: chờ staff duyệt.
- `APPROVED`: đã duyệt, merge vào cart bàn.
- `REJECTED`: staff từ chối.
- `CANCELLED`: khách hủy.

## Public QR API nhanh
- `POST /api/public/qr/orders/`
- `GET /api/public/qr/orders/<id>/?table_code=&token=`
- `PATCH /api/public/qr/orders/<id>/`
- `POST /api/public/qr/orders/<id>/cancel/`

## WebSocket endpoints
- `ws://<host>/ws/pos/store/<store_id>/`
- `ws://<host>/ws/public/qr/order/<order_id>/?table_code=<CODE>&token=<TOKEN>`

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
