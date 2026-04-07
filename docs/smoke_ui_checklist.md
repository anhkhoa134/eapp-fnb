# Smoke UI Checklist (POS + QR Public + Quản lý QR)

> **Hướng dẫn chi tiết (từng bước, nút, thông báo):** `docs/testing/trang_ban_hang.md` (POS) và `docs/testing/trang_quan_ly.md` (Quản lý). File này giữ vai trò tóm tắt nhanh.

## 1) Chuẩn bị

### 1.1 Môi trường
```bash
cd /Users/anhkhoa/Downloads/Project_django/eapp-fnb
source /Users/anhkhoa/Downloads/Project_django/env_10_web/bin/activate
python manage.py migrate
python manage.py seed_initial_data --tenant-slug demo --tenant-name "Demo FNB" --seed-qr-pending
python manage.py runserver 127.0.0.1:8000
```

Lưu ý:
- Không dùng `--noasgi`.
- Nếu cần WS đầy đủ, mở Redis local: `redis-server`.

### 1.2 Tài khoản test
- Staff POS: `demo_nhanvien_1 / 123456`
- Manager: `demo_quanly / 123456`

### 1.3 URL
- POS: `http://127.0.0.1:8000/`
- Quản lý QR bàn: `http://127.0.0.1:8000/quanly/qr-tables/`
- Public QR: `http://127.0.0.1:8000/demo/qr/?table_code=<CODE>&token=<TOKEN>`

---

## 2) Checklist theo luồng

## A. POS topping + checkout
1. Chọn món có topping, thêm vào giỏ.
2. Verify topping hiện trong cart + tổng tiền đúng.
3. Thử checkout cash (fail/pass) và card.

## B. Takeaway / table cart (POS)
1. Tạo takeaway cart, **chọn bàn** — verify món **không mất**, import vào cart bàn.
2. (Tùy chọn) Khi đang **ở bàn**, bấm **Tạo đơn mang về** (nút trái footer) để mở đơn mang về mới; sau đó bấm **Quay lại bàn** để quay lại bàn đang phục vụ.
3. **Đổi sang mang về** — verify giỏ bàn trên server **rỗng** (DELETE items), giỏ trên màn hình vẫn có món (mang về).
4. **Mobile:** mở giỏ (offcanvas) → **Chọn bàn** — offcanvas **đóng**, thấy lưới bàn.

## C. QR staff approve/reject
1. Tạo pending QR (bằng API public hoặc trang public QR).
2. Vào tab Đơn QR trên POS.
3. Approve 1 đơn, reject 1 đơn.
4. Verify status bàn và cart.

## D. Public QR full flow
1. Mở trang QR public hợp lệ (có table_code+token).
2. Tạo đơn pending.
3. Sửa đơn pending (PATCH).
4. Hủy đơn pending (CANCELLED).
5. Verify WebSocket realtime cập nhật status sau khi staff xử lý.
6. Nếu WS mất kết nối, verify fallback polling 15s vẫn cập nhật.

## E. Quản lý QR bàn
1. Tạo/sửa/xóa bàn QR.
2. Reset token.
3. Tải PNG QR từng bàn.
4. Chọn một cửa hàng và in PDF khổ lớn (15 bàn/trang).
5. Verify tên/mã bàn nằm gần QR, không có URL text trong từng ô.

## F. Phân trang danh sách (Quản lý + đơn trong ngày)
1. Quản lý: `/quanly/stores/` hoặc `categories/` / `products/` / `staffs/` — nếu >20 dòng, Trang trước/sau; URL có `?page=`.
2. QR bàn: `?store=<id>&page=` — giữ `store` khi đổi trang.
3. Toppings: hai bảng — `page` và `mpage` độc lập.
4. Đơn trong ngày: `/orders/today/?page=` — KPI (tổng đơn, doanh thu) không đổi khi chỉ đổi trang bảng.

---

## 3) Mẫu ghi nhận kết quả

| Step | Result | Evidence | Note |
|---|---|---|---|
| A | PASS/FAIL | Screenshot/Video/Network | |
| B | PASS/FAIL | Screenshot/Video/Network | |
| C | PASS/FAIL | Screenshot/Video/Network | |
| D | PASS/FAIL | Screenshot/Video/Network | |
| E | PASS/FAIL | Screenshot/Video/PDF file | |
| F | PASS/FAIL | Screenshot/URL query | |

---

## 4) Cleanup __pycache__ fallback

### 4.1 Kiểm tra
```bash
git status --short
```

### 4.2 Xóa untracked cache
```bash
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

### 4.3 Xác nhận
```bash
git ls-files | rg "(__pycache__/|\\.pyc$)"
```
Kỳ vọng: không có output.
