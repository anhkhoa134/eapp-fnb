# 6) Test va smoke checklist

## Automated test

### Chay check
```bash
python manage.py check
```

### Chay toan bo test
```bash
python manage.py test --keepdb
```

### Chay nhanh theo module
```bash
python manage.py test App_Accounts.tests App_Quanly.tests --keepdb
```

## Manual smoke checklist

### A. Topping
1. Login staff vao POS.
2. Chon mon co topping, tick topping, them vao gio.
3. Xac nhan cart hien topping va tong tien tang dung.

### B. Save-to-table
1. Tao gio takeaway.
2. Bam `Luu ban`.
3. Chon ban trong tab `Chon ban`.
4. Xac nhan cart ban da nhan item, giu dung topping/note/so luong.

### C. Payment cash/card
1. Cash: thu case thieu tien (fail) va du tien (pass).
2. Card: thanh toan khong can nhap tien mat.
3. Xac nhan payload gui `payment_method` dung gia tri.

### D. QR approve topping
1. Tao pending QR qua `POST /api/public/qr/orders`.
2. Duyet trong tab `Don QR`.
3. Mo ban va kiem tra item/topping da merge.
4. Checkout ban va kiem tra cart ban da clear.

## Regression diem nhay cam can luon test lai
- Logout chi chap nhan `POST`.
- `/quanly/product-toppings/` redirect ve `/quanly/toppings/`.
- Lich su don (`/quanly/orders/`) loc + phan trang + row chi tiet topping.

## Repo hygiene
```bash
git ls-files | rg "(__pycache__/|\\.pyc$)"
```
- Ky vong: khong co ket qua nao.
