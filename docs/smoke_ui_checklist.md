# Smoke UI Checklist (POS + QR Public + Quanly QR)

## 1) Chuan bi

### 1.1 Moi truong
```bash
cd /Users/anhkhoa/Downloads/Project_django/eapp-fnb
source /Users/anhkhoa/Downloads/Project_django/env_10_web/bin/activate
python manage.py migrate
python manage.py seed_initial_data --tenant-slug demo --tenant-name "Demo FNB" --seed-qr-pending
python manage.py runserver 127.0.0.1:8000
```

Luu y:
- Khong dung `--noasgi`.
- Neu can WS day du, mo Redis local: `redis-server`.

### 1.2 Tai khoan test
- Staff POS: `demo_nhanvien_1 / 123456`
- Manager: `demo_quanly / 123456`

### 1.3 URL
- POS: `http://127.0.0.1:8000/`
- Quanly QR tables: `http://127.0.0.1:8000/quanly/qr-tables/`
- Public QR: `http://127.0.0.1:8000/demo/qr/?table_code=<CODE>&token=<TOKEN>`

---

## 2) Checklist theo luong

## A. POS topping + checkout
1. Chon mon co topping, them vao gio.
2. Verify topping hien trong cart + tong tien dung.
3. Thu checkout cash (fail/pass) va card.

## B. SaveToTable
1. Tao takeaway cart.
2. Bam Luu ban va chon ban.
3. Verify item/topping import vao cart ban.

## C. QR staff approve/reject
1. Tao pending QR (bang API public hoac trang public QR).
2. Vao tab Don QR tren POS.
3. Approve 1 don, reject 1 don.
4. Verify status ban va cart.

## D. Public QR full flow
1. Mo trang QR public hop le (co table_code+token).
2. Tao don pending.
3. Sua don pending (PATCH).
4. Huy don pending (CANCELLED).
5. Verify WebSocket realtime cap nhat status sau khi staff xu ly.
6. Neu WS mat ket noi, verify fallback polling 15s van cap nhat.

## E. Quanly QR tables
1. Tao/sua/xoa ban QR.
2. Reset token.
3. Tai PNG QR tung ban.
4. Chon 1 store va in PDF kho lon (15 ban/trang).
5. Verify ten/ma ban nam gan QR, khong co URL text trong tung o.

---

## 3) Mau ghi nhan ket qua

| Step | Result | Evidence | Note |
|---|---|---|---|
| A | PASS/FAIL | Screenshot/Video/Network | |
| B | PASS/FAIL | Screenshot/Video/Network | |
| C | PASS/FAIL | Screenshot/Video/Network | |
| D | PASS/FAIL | Screenshot/Video/Network | |
| E | PASS/FAIL | Screenshot/Video/PDF file | |

---

## 4) Cleanup __pycache__ fallback

### 4.1 Kiem tra
```bash
git status --short
```

### 4.2 Xoa untracked cache
```bash
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

### 4.3 Xac nhan
```bash
git ls-files | rg "(__pycache__/|\\.pyc$)"
```
Ky vong: khong co output.
