# 6) Test va smoke checklist

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

## Manual smoke (core)

### A. POS topping + payment
1. Chon mon co topping, them gio.
2. Thu cash thieu/du tien.
3. Thu card.

### B. Save-to-table
1. Tao gio takeaway.
2. Bam Luu ban, chon ban.
3. Verify item/topping sang cart ban.

### C. QR staff
1. Tao pending QR qua public API.
2. Approve/reject trong tab Don QR.
3. Verify table state + cart.

### D. QR customer UI
1. Mo `/<slug>/qr/?table_code=&token=`.
2. Tao don pending.
3. Sua don pending.
4. Huy don pending.
5. Verify polling 5s khi staff approve/reject.

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
