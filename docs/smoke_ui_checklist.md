# Smoke UI Checklist (POS Multi-tenant)

## 1) Chuẩn bị

### 1.1 Môi trường
```bash
cd /Users/anhkhoa/Downloads/Project_django/eapp-fnb
source /Users/anhkhoa/Downloads/Project_django/env_10_web/bin/activate
python manage.py migrate
python manage.py seed_initial_data --tenant-slug demo --tenant-name "Demo FNB" --seed-qr-pending
python manage.py runserver 127.0.0.1:8000
```

### 1.2 Tài khoản test
- POS staff: `demo_nhanvien_1 / 123456`
- POS manager (nếu cần kiểm tra quanly): `demo_quanly / 123456`

### 1.3 URL
- POS: `http://127.0.0.1:8000/`
- Login: `http://127.0.0.1:8000/accounts/login/`

---

## 2) Checklist smoke theo luồng

## A. Topping (POS staff)
1. Login bằng staff và vào tab `Thực đơn`.
2. Chọn 1 món có topping (ví dụ: `Trà Sữa Trân Châu`), mở modal tùy chọn.
3. Tick 1-2 topping, bấm `Thêm vào giỏ hàng`.
4. Quan sát giỏ hàng.

Expected:
- Có block `TOPPING THÊM` trong options modal.
- Giá ở nút xác nhận tăng đúng theo topping đã chọn.
- Cart item hiển thị danh sách topping đã chọn.
- Tổng tiền item và tổng hóa đơn tăng đúng.

Pass/Fail:
- `PASS` nếu cả UI hiển thị + tính tiền đúng.
- `FAIL` nếu thiếu block topping, không lưu topping, hoặc giá sai.

---

## B. SaveToTable thật (không còn placeholder)
1. Ở mode `Khách mang về`, thêm 2 món (ít nhất 1 món có topping).
2. Bấm `Lưu bàn`.
3. Chuyển sang tab `Sơ đồ bàn` và chọn 1 bàn trống.
4. Quay lại giỏ hàng bàn vừa chọn.

Expected:
- Không còn toast kiểu placeholder.
- Giỏ takeaway được import vào cart của bàn.
- Trạng thái bàn chuyển `occupied` và có tổng tiền.
- Món trong bàn giữ đúng topping/note/số lượng.

Gợi ý verify API (Network tab):
- `POST /api/pos/tables/<table_id>/cart/import-takeaway/`

---

## C. Thanh toán Cash/Card
### C1. Cash fail + pass
1. Với cart có sẵn item, mở modal thanh toán.
2. Chọn `Tiền mặt`.
3. Nhập số tiền nhỏ hơn tổng -> bấm `Hoàn tất thanh toán`.
4. Nhập số tiền đủ/lớn hơn tổng -> thanh toán lại.

Expected:
- Case thiếu tiền: bị chặn, có thông báo lỗi.
- Case đủ tiền: thanh toán thành công, hiển thị order code.
- Tiền thừa hiển thị đúng khi cash > total.

### C2. Card pass
1. Tạo lại cart mới.
2. Mở modal thanh toán, chọn `Thẻ/QR`.
3. Bấm `Hoàn tất thanh toán` (không cần nhập tiền mặt).

Expected:
- Form cash/change được ẩn hoặc không bắt buộc.
- Thanh toán thành công.
- Payload gửi `payment_method=card`.

Gợi ý verify API (Network tab):
- Takeaway: `POST /api/pos/checkout/`
- Table: `POST /api/pos/tables/<table_id>/checkout/`

---

## D. QR approve có topping
### D1. Tạo pending QR bằng API
1. Lấy `table_code` + `qr_token` từ DB/admin (bàn thuộc store staff có quyền).
2. Gửi API public:

```bash
curl -X POST "http://127.0.0.1:8000/api/public/qr/orders/" \
  -H "Content-Type: application/json" \
  -d '{
    "table_code": "XXX-01",
    "token": "TABLE_QR_TOKEN",
    "note": "Khach goi mon QR",
    "items": [
      {
        "product_id": 1,
        "unit_id": 1,
        "quantity": 1,
        "note": "it da",
        "topping_ids": [1]
      }
    ]
  }'
```

### D2. Duyệt đơn trên POS
1. Trong POS staff, mở tab `Đơn Online (QR)`.
2. Mở đơn vừa tạo, bấm `Duyệt`.
3. Mở bàn tương ứng để kiểm tra cart.
4. Thực hiện checkout bàn.

Expected:
- Sau approve: đơn pending biến mất khỏi tab online.
- Cart bàn có item từ QR và giữ đúng topping.
- Checkout bàn thành công và bàn được clear cart.

Gợi ý verify API (Network tab):
- `POST /api/pos/qr/orders/<id>/approve/`

---

## 3) Mẫu ghi nhận kết quả

## 3.1 Bảng test nhanh
| Step | Result | Evidence | Note |
|---|---|---|---|
| A. Topping | PASS/FAIL | Screenshot/Video/Network |  |
| B. SaveToTable | PASS/FAIL | Screenshot/Video/Network |  |
| C1. Cash | PASS/FAIL | Screenshot/Video/Network |  |
| C2. Card | PASS/FAIL | Screenshot/Video/Network |  |
| D. QR approve topping | PASS/FAIL | Screenshot/Video/Network |  |

## 3.2 Mẫu bug chuẩn hóa
```text
[Bug Title]
- Môi trường: local / branch / commit (nếu có)
- Mô tả: lỗi gì, ảnh hưởng gì
- Bước tái hiện:
  1) ...
  2) ...
  3) ...
- Kỳ vọng: ...
- Thực tế: ...
- Bằng chứng: screenshot/video/log/network request-response
```

---

## 4) One-time cleanup `__pycache__` (fallback)

## 4.1 Kiểm tra
```bash
git status --short
```

## 4.2 Nếu có file `__pycache__` tracked bị modified
```bash
git status --short | awk '/__pycache__/ && $1=="M" {print $2}' | xargs -r git checkout --
```

## 4.3 Nếu có file `__pycache__`/`.pyc` untracked
```bash
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

## 4.4 Xác nhận cuối
```bash
git status --short
```

Expected:
- Không còn entry `__pycache__` hoặc `.pyc` trong `git status`.
