# 6) Test và smoke checklist

## Tài liệu kiểm thử chi tiết (QA)

Hai file hướng dẫn tester theo từng click / thông báo:

- **`docs/testing/trang_ban_hang.md`** — POS (`/`)
- **`docs/testing/trang_quan_ly.md`** — Quản lý (`/quanly/`)

## Automated

### Check
```bash
python manage.py check
```

### Full test
```bash
python manage.py test --keepdb
```

### Nhóm test thường dùng
```bash
python manage.py test App_Public.tests App_Sales.tests App_Quanly.tests --keepdb
```

### Nhóm test WebSocket
```bash
python manage.py test App_Sales.tests_ws App_Public.tests_ws
```

## Manual smoke (core)

### A. POS topping + payment
1. Chọn món có topping, thêm vào giỏ.
2. Thử cash thiếu/đủ tiền.
3. Thử card.

### B. Save-to-table + takeaway / table cart (POS)
1. Tạo giỏ takeaway, **chọn bàn** — verify món **không mất**, import lên cart bàn (`import-takeaway`).
2. (Tùy chọn) Khi đang **ở bàn**, bấm **Tạo đơn mang về** (nút trái footer) để mở đơn mang về mới; sau đó bấm **Quay lại bàn** để quay lại bàn đang phục vụ.
3. Verify item/topping trên cart bàn sau khi chọn bàn.
4. Bấm Đổi sang mang về — verify DELETE từng dòng cart bàn trên API, giỏ client là mang về (món vẫn hiện), bàn trống trên UI.
5. Mobile: mở offcanvas giỏ, bấm Chọn bàn — offcanvas đóng, thấy lưới bàn.

### C. QR staff
1. Tạo pending QR qua public API.
2. Approve/reject trong tab Đơn QR.
3. Verify table state + cart.

### D. QR customer UI
1. Mở `/<slug>/qr/?table_code=&token=`.
2. Tạo đơn pending.
3. Sửa đơn pending.
4. Hủy đơn pending.
5. Verify WebSocket realtime khi staff approve/reject.
6. Tắt Redis/chặn WS để verify fallback polling 15s vẫn cập nhật.
7. Mở DevTools, đảm bảo không còn loop lỗi kết nối WS khi server chạy ASGI.

### E. Quanly QR tables
1. Tạo/sửa/xóa bàn QR.
2. Reset token.
3. Tải PNG từng bàn.
4. In PDF theo cửa hàng (15 bàn/trang).

### F. Phân trang danh sách (server-rendered)
1. Quản lý: mở `/quanly/stores/` (hoặc categories/products/staffs) — nếu đủ >20 dòng, có liên kết Trang trước/sau; `?page=2` load đúng trang.
2. QR bàn: lọc `?store=<id>` rồi chuyển trang — tham số `store` vẫn giữ trong URL.
3. Toppings: đổi `page` và `mpage` — hai bảng không reset lẫn nhau.
4. `/orders/today/?page=2` (có nhiều đơn trong ngày): KPI tổng đơn / doanh thu không chỉ còn 20 dòng của bảng; bảng chi tiết theo trang.

## Regression cần giữ
- Logout chỉ POST.
- `/quanly/product-toppings/` redirect về `/quanly/toppings/`.
- QROrder terminal states không cho sửa/hủy/approve/reject sai luật.

## Repo hygiene
```bash
git ls-files | rg "(__pycache__/|\\.pyc$)"
```
Kỳ vọng: không có kết quả.
