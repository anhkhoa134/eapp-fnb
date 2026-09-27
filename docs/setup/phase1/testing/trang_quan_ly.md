# Kiểm thử — Trang Quản lý (`/quanly/`)

**Điều kiện:** Đăng nhập tài khoản **Quản lý** (manager). Nhân viên thường **không** vào được các URL dưới đây (kiểm tra: truy cập trực tiếp `/quanly/` → redirect hoặc 403 theo thiết kế).

**Thông báo:** Nhiều thao tác dùng **toast** góc màn hình (Quản lý) hoặc **django messages** — ghi lại nội dung toast/alert để đối chiếu.

---

## 0. Đăng nhập và vào khu vực Quản lý

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 0.1 | Đăng nhập user **quản lý** | Thành công |
| 0.2 | Truy cập `http://127.0.0.1:8000/quanly/` | Mở **Dashboard** (hoặc trang chủ quản lý), không lỗi 403 (nếu đúng quyền) |

---

## 1. Thanh navbar (mọi trang con)

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 1.1 | **Desktop (rộng):** bấm nút **Thu nhỏ menu** (mũi tên đôi) cạnh logo | Sidebar thu gọn chỉ icon; bấm lại **Mở rộng menu** → hiện đủ chữ |
| 1.2 | **Mobile / cửa sổ hẹp:** bấm **Menu** (icon list) | Offcanvas trượt **từ trái**; có tiêu đề *Menu quản lý* và nút đóng (X) |
| 1.3 | Trong offcanvas: bấm một mục (ví dụ **Cửa hàng**) | Panel đóng; chuyển đúng URL |
| 1.4 | Menu avatar (góc phải) — xem thông tin / đăng xuất (theo quyền) | Giống `base.html` (đổi mật khẩu nếu có mục) |

---

## 1A. Phân trang danh sách (bảng CRUD)

**Quy ước:** 20 dòng/trang; thanh *Trước* / *Sau* và chữ *Trang n/tổng* chỉ hiện khi có từ 2 trang trở lên. **Lịch sử đơn** (`/quanly/orders/`) đã có phân trang từ trước (cùng kiểu URL `?page=`). **Dashboard — Đơn gần nhất** không dùng phân trang (danh sách cố định).

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 1A.1 | Vào **Cửa hàng** / **Danh mục** / **Sản phẩm** / **Nhân viên** — nếu tenant có >20 bản ghi | Cuối khối bảng có điều hướng phân trang |
| 1A.2 | Bấm **Sau** (hoặc gõ tay `?page=2` trên URL) | Bảng chỉ hiển thị đúng trang 2 |
| 1A.3 | **QR bàn** — chọn cửa hàng trong dropdown (GET `store`) rồi chuyển trang | Tham số `store` vẫn còn trên URL cùng `page` |
| 1A.4 | **Topping** — có hai bảng | Bảng *Danh sách topping* dùng `page`; bảng *Cơ cấu topping* dùng `mpage`; đổi trang một bảng không xóa số trang của bảng kia |

---

## 2. Dashboard

**URL:** `http://127.0.0.1:8000/quanly/`

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 2.1 | Quan sát nội dung trang (số liệu, thẻ, biểu đồ — theo bản hiện tại) | Dữ liệu tải; không 500 |
| 2.2 | **Khoảng thời gian nhanh** — chọn 7 / 30 ngày, tháng hiện tại, tháng trước, năm hiện tại, năm trước | Trang tải lại; chip kỳ và KPI/biểu đồ khớp khoảng; ô *Từ/Đến* điền sẵn (readonly khi dùng mốc nhanh) |
| 2.3 | **Tùy chỉnh** — chọn *Tùy chỉnh*, nhập *Từ ngày* / *Đến ngày*, bấm **Lọc** | KPI và biểu đồ theo đúng hai ngày; có thể kết hợp **Cửa hàng** |
| 2.4 | Bảng **Đơn gần nhất** (nếu có) | Danh sách ngắn cố định — **không** có phân trang `page` (khác các trang CRUD) |
| 2.5 | Bấm từng link trong **sidebar** (desktop) hoặc offcanvas (mobile) sang các module dưới | Điều hướng đúng URL |

---

## 3. Cửa hàng

**URL:** `http://127.0.0.1:8000/quanly/stores/`

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 3.1 | Bấm **Thêm cửa hàng** | Modal *Thêm cửa hàng* mở |
| 3.2 | Điền **Tên**, **Địa chỉ**, **Số điện thoại** (tuỳ chọn), tick/bỏ **Đang hoạt động**, **Cửa hàng mặc định** → bấm **Tạo cửa hàng** | Toast/message thành công; dòng mới trong bảng; slug tự sinh |
| 3.3 | Trên dòng: bấm **Sửa** | Modal *Sửa cửa hàng* điền sẵn dữ liệu (name, address, phone, …) |
| 3.4 | Đổi số điện thoại → **Cập nhật** | Thông báo thành công; cột *Điện thoại* đúng |
| 3.5 | **Sửa** — nhập SĐT quá ngắn / ký tự lạ (nếu test validation) | Lỗi field hoặc message rõ ràng |
| 3.6 | Bấm **Xóa** → xác nhận trong modal | Xóa thành công **hoặc** lỗi ràng buộc (đơn hàng, …) — đọc nội dung thông báo |

---

## 4. Lịch sử đơn

**URL:** `http://127.0.0.1:8000/quanly/orders/`

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 4.1 | Chọn cửa hàng / bộ lọc thời gian (nếu có trên UI) | Danh sách đơn thay đổi theo bộ lọc |
| 4.2 | Mở chi tiết một đơn (nếu có link) | Hiển thị đúng món, tổng tiền |
| 4.3 | Bấm **Xóa** đơn (nếu có) | Xác nhận → thành công hoặc bị chặn |

---

## 5. Danh mục

**URL:** `http://127.0.0.1:8000/quanly/categories/`

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 5.1 | Bấm **Thêm danh mục** (hoặc tương đương) | Modal tạo mở |
| 5.2 | Điền form → **Lưu danh mục** | Thành công; dòng mới trong bảng |
| 5.3 | **Sửa** → **Cập nhật** | Dữ liệu cập nhật |
| 5.4 | **Xóa** → modal xác nhận → **Xóa** | Danh mục biến mất hoặc lỗi ràng buộc |
| 5.5 | **Tải mẫu Excel** (nút *Tải file mẫu* / link template) | File tải về |
| 5.6 | **Import Excel** — chọn file hợp lệ → **Tải lên** / **Import** | Thông báo số dòng thành công / lỗi |

---

## 6. Sản phẩm & đơn vị

**URL:** `http://127.0.0.1:8000/quanly/products/`, sửa đơn vị: `/quanly/units/<id>/edit/`, …

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 6.1 | **Thêm sản phẩm** — điền tên, danh mục, giá, đơn vị, ảnh (nếu có) → Lưu | Thành công; sản phẩm xuất hiện trên POS sau khi gán cửa hàng (nếu có bước gán) |
| 6.2 | **Sửa** / **Xóa** sản phẩm | Tương tự pattern CRUD; kiểm tra thông báo |
| 6.3 | Thêm **đơn vị** từ trang sản phẩm (**Thêm đơn vị** nếu có) | Form đơn vị lưu được |
| 6.4 | Sửa/xóa đơn vị tại URL edit | Không phá vỡ sản phẩm đang dùng đơn vị (hoặc báo lỗi hợp lệ) |

---

## 7. Topping & gán sản phẩm

**URL:** `http://127.0.0.1:8000/quanly/toppings/`, `http://127.0.0.1:8000/quanly/product-toppings/` (có thể redirect)

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 7.1 | CRUD topping (Thêm / Sửa / Xóa) | Thông báo thành công/lỗi |
| 7.2 | Gán topping cho sản phẩm — lưu | Trên POS, món đó có topping khi thêm vào giỏ |

---

## 8. QR bàn

**URL:** `http://127.0.0.1:8000/quanly/qr-tables/`

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 8.1 | Chọn **Cửa hàng** (dropdown GET nếu có) | Danh sách bàn theo cửa |
| 8.2 | **Thêm bàn** — điền mã/tên → Lưu | Bàn mới trong list |
| 8.3 | **Sửa** / **Xóa** | CRUD đúng |
| 8.4 | **Reset token** (nút riêng) | Thông báo thành công; URL QR cũ không còn hiệu lực |
| 8.5 | **Tải PNG** / mở link ảnh QR | File ảnh tải về, quét được |
| 8.6 | **In PDF** (chọn cửa hàng) — tải PDF | Nhiều bàn trên trang; layout không vỡ |

---

## 9. QR thanh toán (POS)

**URL:** `http://127.0.0.1:8000/quanly/payment-qr/`

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 9.1 | Chọn cửa hàng ở dropdown phía trên form | Form áp dụng đúng store |
| 9.2 | Xem khối **Ảnh hiện tại** (nếu đã có) | Preview đúng file |
| 9.3 | **Chọn tệp** ảnh mới (PNG/JPG &lt; 2MB) → **Lưu cấu hình** | Toast *Đã cập nhật QR thanh toán...* |
| 9.4 | Tick **Xóa ảnh QR hiện tại** (không chọn file mới) → **Lưu cấu hình** | Ảnh gỡ; không còn preview (hoặc placeholder) |
| 9.5 | Vừa tick **Xóa ảnh** vừa chọn file mới → **Lưu** | Form báo lỗi *Chọn một: tải ảnh mới hoặc xóa...* (alert đỏ hoặc non-field error) |
| 9.6 | Điền **Tên ngân hàng**, **Chủ TK**, **Số TK** → **Lưu** | Reload vẫn giữ giá trị |

---

## 10. Nhân viên

**URL:** `http://127.0.0.1:8000/quanly/staffs/`

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 10.1 | **Thêm nhân viên** — username, mật khẩu, cửa hàng → Lưu | Tạo thành công hoặc đạt giới hạn gói → message lỗi |
| 10.2 | **Sửa** / **Xóa** | CRUD + thông báo |
| 10.3 | **Đặt lại mật khẩu** (URL dạng `/quanly/staffs/<id>/password/`) | Form đổi mật khẩu; đăng nhập lại bằng user nhân viên với mật khẩu mới |

---

## 11. Tài khoản quản lý

**URL:** `http://127.0.0.1:8000/quanly/account/`

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 11.1 | Đọc thông tin doanh nghiệp / gói (nếu hiển thị) | Đúng với tenant |
| 11.2 | Gửi form (nếu có chỉnh sửa được trên trang) | Thông báo lưu thành công |

---

## 12. Import catalog (nếu tách trang)

Nếu import nằm ở `/quanly/catalog-import/upload/`:

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 12.1 | Upload file đúng định dạng | Báo cáo số dòng import |
| 12.2 | Upload file sai | Thông báo lỗi rõ (thiếu cột, sai sheet, …) |

---

## Bảng tổng hợp nhanh

| Module | URL | PASS / FAIL | Ghi chú |
|--------|-----|-------------|---------|
| Navbar / sidebar / offcanvas | | | |
| Phân trang CRUD / Topping (`page`, `mpage`) | (xem mục 1A) | | |
| Dashboard | `/quanly/` | | |
| Cửa hàng | `/quanly/stores/` | | |
| Lịch sử đơn | `/quanly/orders/` | | |
| Danh mục | `/quanly/categories/` | | |
| Sản phẩm | `/quanly/products/` | | |
| Topping | `/quanly/toppings/` | | |
| QR bàn | `/quanly/qr-tables/` | | |
| QR thanh toán | `/quanly/payment-qr/` | | |
| Nhân viên | `/quanly/staffs/` | | |
| Tài khoản | `/quanly/account/` | | |
