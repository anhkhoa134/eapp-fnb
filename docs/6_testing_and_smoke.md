# 6) Test va smoke checklist

## Tai lieu kiem thu chi tiet (QA)

Hai file huong dan tester theo tung click / thong bao:

- **`docs/testing/trang_ban_hang.md`** — POS (`/`)
- **`docs/testing/trang_quan_ly.md`** — Quan ly (`/quanly/`)

## Automated

### Check
```bash
python manage.py check
```

### Full test
```bash
python manage.py test --keepdb
```

### Nhom test thuong dung
```bash
python manage.py test App_Public.tests App_Sales.tests App_Quanly.tests --keepdb
```

### Nhom test WebSocket
```bash
python manage.py test App_Sales.tests_ws App_Public.tests_ws
```

## Manual smoke (core)

### A. POS topping + payment
1. Chon mon co topping, them gio.
2. Thu cash thieu/du tien.
3. Thu card.

### B. Save-to-table + takeaway / table cart (POS)
1. Tao gio takeaway, chon ban (khong can Bam Luu ban) — verify mon khong mat, import len cart ban (`import-takeaway`).
2. (Tuy chon) Bam Luu ban, chon ban — cung ket qua import.
3. Verify item/topping tren cart ban sau khi chon ban.
4. Bam Doi sang mang ve — verify DELETE tung dong cart ban tren API, gio client la mang ve (mon van hien), ban trong tren UI.
5. Mobile: mo offcanvas gio, Bam Chon ban — offcanvas dong, thay luoi ban.

### C. QR staff
1. Tao pending QR qua public API.
2. Approve/reject trong tab Don QR.
3. Verify table state + cart.

### D. QR customer UI
1. Mo `/<slug>/qr/?table_code=&token=`.
2. Tao don pending.
3. Sua don pending.
4. Huy don pending.
5. Verify WebSocket realtime khi staff approve/reject.
6. Tat Redis/chan WS de verify fallback polling 15s van cap nhat.
7. Mo DevTools, dam bao khong con loop loi ket noi WS khi server chay ASGI.

### E. Quanly QR tables
1. Tao/sua/xoa ban QR.
2. Reset token.
3. Tai PNG tung ban.
4. In PDF store (15 ban/trang).

## Regression can giu
- Logout chi POST.
- `/quanly/product-toppings/` redirect ve `/quanly/toppings/`.
- QROrder terminal states khong cho sua/huy/approve/reject sai luat.

## Repo hygiene
```bash
git ls-files | rg "(__pycache__/|\\.pyc$)"
```
Ky vong: khong co ket qua.
