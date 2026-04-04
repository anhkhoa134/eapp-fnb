# Smoke UI Checklist (POS + QR Public + Quanly QR)

> **Huong dan chi tiet (tung buoc, nut, thong bao):** `docs/testing/trang_ban_hang.md` (POS) va `docs/testing/trang_quan_ly.md` (Quan ly). File nay giu vai tro tom tat nhanh.

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

## B. Takeaway / table cart (POS)
1. Tao takeaway cart, **chon ban** (co the khong can Bam Luu ban) — verify mon **khong mat**, import vao cart ban.
2. (Tuy chon) Bam **Luu ban** roi chon ban — tuong tu.
3. **Doi sang mang ve** — verify gio ban tren server **rong** (DELETE items), gio tren man hinh van co mon (mang ve).
4. **Mobile:** mo gio (offcanvas) → **Chon ban** — offcanvas **dong**, thay luoi ban.

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
