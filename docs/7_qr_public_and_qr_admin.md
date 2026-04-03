# 7) QR public ordering va QR table admin

## Public QR ordering flow

### URL vao trang khach
- `/<public_slug>/qr/?table_code=<CODE>&token=<TOKEN>`

### Hanh vi chinh
- Hien menu dung theo store cua ban.
- Cho chon unit, topping, note, quantity.
- Gui don tao `QROrder.PENDING`.
- WebSocket realtime de cap nhat trang thai don.
- Neu mat ket noi WebSocket, fallback polling 15s.
- Cho `edit/cancel` chi khi don con `PENDING`.
- Luu `active_qr_order_id` theo `table_code` trong localStorage.

### Trang thai don
- `PENDING`: cho staff duyet.
- `APPROVED`: da duyet, merge vao cart ban.
- `REJECTED`: staff tu choi.
- `CANCELLED`: khach huy.

## Public QR API nhanh
- `POST /api/public/qr/orders/`
- `GET /api/public/qr/orders/<id>/?table_code=&token=`
- `PATCH /api/public/qr/orders/<id>/`
- `POST /api/public/qr/orders/<id>/cancel/`

## WebSocket endpoints
- `ws://<host>/ws/pos/store/<store_id>/`
- `ws://<host>/ws/public/qr/order/<order_id>/?table_code=<CODE>&token=<TOKEN>`

## Quanly QR ban

### Chuc nang
- CRUD ban QR theo tenant.
- Reset token QR.
- Copy link QR.
- Tai PNG QR cho tung ban.
- In PDF A3 theo store, 15 ban/trang.

### Routes
- `/quanly/qr-tables/`
- `/quanly/qr-tables/<id>/edit/`
- `/quanly/qr-tables/<id>/reset-token/`
- `/quanly/qr-tables/<id>/png/`
- `/quanly/qr-tables/print-pdf/?store=<id>`

## Van hanh nhanh
1. Manager tao ban trong `/quanly/qr-tables/`.
2. Copy link QR hoac tai PNG de in dan ban.
3. Neu in hang loat, loc store roi bam `In PDF kho lon`.
4. Khi lo token, dung `Reset token` va in lai QR.
