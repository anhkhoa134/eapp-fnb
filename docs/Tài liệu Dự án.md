# eApp FnB - Tai lieu du an (ban cap nhat)

## 1) Gioi thieu
`eApp FnB` la he thong POS multi-tenant cho F&B, xay dung bang Django 5.0 + Bootstrap 5.3.

He thong tach 3 khong gian:
- POS cho nhan vien (`/`)
- Quan ly tenant (`/quanly/`)
- Public tenant (`/<public_slug>/`) va public QR ordering (`/<public_slug>/qr/`)

## 2) Tinh nang chinh dang co

### POS staff
- Ban hang takeaway + table.
- Chon size/topping/note.
- Thanh toan cash/card.
- Tab Don QR de duyet/tu choi don khach.

### Public QR ordering
- Khach vao link QR theo ban (`table_code + token`).
- Tao don pending, theo doi status realtime (polling 5s).
- Cho sua/huy khi don con pending.
- Trang thai: `PENDING`, `APPROVED`, `REJECTED`, `CANCELLED`.

### Quan ly
- Dashboard doanh thu + lich su don.
- CRUD danh muc/san pham/topping/nhan vien.
- Quan ly QR ban:
  - Tao/sua/xoa ban.
  - Reset token.
  - Tai PNG QR tung ban.
  - In PDF A3 theo cua hang (15 ban/trang).

## 3) Model cot loi
- Tenant/Store/User/UserStoreAccess.
- Category/Product/ProductUnit/Topping/ProductTopping.
- DiningTable/QROrder/QROrderItem/QROrderItemTopping.
- TableCartItem/TableCartItemTopping.
- Order/OrderItem/OrderItemTopping.

## 4) API QR public
- `POST /api/public/qr/orders/`
- `GET /api/public/qr/orders/<id>/?table_code=&token=`
- `PATCH /api/public/qr/orders/<id>/`
- `POST /api/public/qr/orders/<id>/cancel/`

## 5) Van hanh nhanh
```bash
source /Users/anhkhoa/Downloads/Project_django/env_10_web/bin/activate
python manage.py migrate
python manage.py seed_initial_data --reset-passwords --default-password 123456 --seed-qr-pending
python manage.py runserver 127.0.0.1:8000
```

## 6) Out-of-scope hien tai
- Inventory
- Shift
- Refund
