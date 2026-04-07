# Kiểm thử — Trang bán hàng (POS)

**URL:** `http://127.0.0.1:8000/`  
**Điều kiện:** Đăng nhập tài khoản **nhân viên** hoặc **quản lý** (có quyền POS).

Ghi chú cột **Kết quả / Thông báo**: ghi lại toast, `alert`, nội dung lỗi trên màn hình, hoặc hành vi thực tế (ví dụ giỏ trống, modal đóng).

---

## 0. Chuẩn bị

| Bước | Thao tác | Kiểm tra |
|------|----------|----------|
| 0.1 | Mở `/accounts/login/`, đăng nhập user có quyền POS | Chuyển về trang POS `/`, không báo lỗi đăng nhập |
| 0.2 | (Nếu có nhiều cửa hàng) Mở menu avatar góc phải → khu **Cửa hàng** → chọn `<select id="storeSelector">` | Tên cửa hàng đổi; sản phẩm/bàn/đơn QR theo đúng cửa (sau khi tải lại dữ liệu) |

---

## 1. Thanh điều hướng và tab chính

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 1.1 | Bấm tab **Thực đơn** (icon thìa dĩa) | Vùng trái hiển thị danh mục + lưới/list sản phẩm |
| 1.2 | Bấm tab **Chọn bàn** | Hiển thị lưới bàn (trống / đang phục vụ / có đơn QR theo chú thích màu) |
| 1.3 | Bấm tab **Đơn QR** | Tiêu đề *Danh sách đơn QR chờ duyệt*; nếu không có đơn: empty state *Chưa có đơn QR nào* |
| 1.4 | Bấm icon chuông trên navbar | Chuyển sang tab **Đơn QR** (tương đương 1.3) |
| 1.5 | Ô **Tìm món...** — gõ từ khóa có trong tên món | Danh sách sản phẩm lọc theo từ khóa |

---

## 2. Thực đơn: lọc danh mục và dạng xem

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 2.1 | Bấm pill **Tất cả** (nếu có thêm pill theo từng danh mục, bấm từng pill) | Chỉ còn sản phẩm thuộc danh mục đó (hoặc tất cả) |
| 2.2 | Bấm icon **lưới** (grid) trong nhóm Grid/List | Sản phẩm dạng thẻ lưới |
| 2.3 | Bấm icon **danh sách** (list) | Sản phẩm dạng list |

---

## 3. Thêm món vào giỏ (có/không topping)

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 3.1 | Bấm vào một **sản phẩm không có topping/size** | Số lượng trong giỏ tăng; **Tổng tiền** cập nhật; nút **Thanh toán** bật khi giỏ có món |
| 3.2 | Bấm sản phẩm **có topping/size** | Modal tùy chọn mở (chọn size, topping, …) |
| 3.3 | Trong modal: chọn size/topping → bấm nút xác nhận / thêm (theo UI modal) | Modal đóng; dòng món trong giỏ hiển thị đúng topping; tổng tiền đúng |
| 3.4 | Trên **dòng món** trong giỏ: tăng/giảm số lượng (`+` / `-`) | Số lượng và tổng tiền thay đổi; về 0 thì dòng biến mất |
| 3.5 | Bấm **Ghi chú** (nếu có) trên dòng món | Modal **Ghi chú món** — nhập hoặc chọn ghi chú nhanh → lưu → ghi chú hiển thị trên dòng |
| 3.6 | **Mobile:** bấm nút nổi **Giỏ hàng (n)** | Offcanvas giỏ mở từ phải; hiển thị cùng nội dung giỏ |
| 3.7 | **Mobile:** giỏ đang mở → bấm **Chọn bàn** trong khối *Đang phục vụ* | Chuyển tab **Chọn bàn**; offcanvas giỏ **đóng** (không che lưới bàn). Tương tự nếu bấm icon bàn trên navbar khi offcanvas đang mở |

---

## 4. Giỏ hàng: xóa, chọn bàn / mang về

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 4.1 | Đọc dòng **Đang phục vụ:** — mặc định thường là *Khách mang về* khi chưa chọn bàn | Khớp trạng thái hiện tại |
| 4.2 | Bấm **Chọn bàn** (trong giỏ hoặc luồng tương đương) | Chuyển sang tab **Chọn bàn** (`openTableMap`). Trên **mobile**, offcanvas giỏ (nếu đang mở) tự đóng để thấy lưới bàn |
| 4.3 | **Mang về** có món trong giỏ → chọn một **bàn trống** | Món **không mất**: client gọi `POST .../cart/import-takeaway/` rồi tải lại giỏ bàn; *Đang phục vụ* hiển thị tên bàn; có **Đổi sang mang về** |
| 4.4 | Bấm **Đổi sang mang về** (khi đang gắn bàn và giỏ có món đồng bộ từ bàn) | **Toàn bộ dòng giỏ trên bàn** bị xóa trên server (`DELETE` từng `cart/items/<id>/`); giỏ trên màn hình chuyển sang **mang về** (cùng món, không còn liên kết `tableItemId`); bàn trên lưới cập nhật trạng thái trống / tổng. Nếu API lỗi → toast, **vẫn ở chế độ bàn** |
| 4.5 | Bấm **Đổi sang mang về** khi giỏ **trống** | Chỉ đổi nhãn *Khách mang về*; không gọi xóa dòng (hoặc không có dòng để xóa) |
| 4.6 | Bấm **Xóa tất cả** (thùng rác) khi giỏ có món | Giỏ về trống; modal xác nhận (Bootstrap) trước khi thực hiện |
| 4.7 | Khi đang **mang về** có món: bấm **Lưu bàn** | Toast hướng dẫn → chọn bàn → món import vào cart bàn (giống 4.3) |
| 4.8 | Khi đang **ở bàn** (chưa thanh toán): bấm **Tạo đơn mang về** | POS chuyển sang *Khách mang về* với giỏ **trống** (không xóa giỏ bàn trên server); có nút **Quay lại bàn** để tiếp tục bàn cũ |
| 4.9 | Khi đang **ở bàn**: bấm **Chuyển bàn** | Mở modal chọn bàn đích → xác nhận → giỏ bàn hiện tại được chuyển sang bàn mới (bàn cũ rỗng); POS tự chuyển sang bàn đích |

---

## 5. Thanh toán (Tiền mặt / Thẻ·QR)

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 5.1 | Thêm ít nhất một món → bấm **Thanh toán** | Modal **Thanh toán hóa đơn** mở; *Số tiền cần thanh toán* khớp tổng giỏ |
| 5.2 | Chọn **Tiền mặt** | Hiện *Gợi ý số tiền*, ô **Khách đưa (VNĐ)** và *Tiền thừa trả khách* |
| 5.3 | Nhập số tiền khách đưa **nhỏ hơn** tổng cần thanh toán → bấm **Hoàn tất thanh toán** | Báo lỗi / không hoàn tất (theo logic JS/API) |
| 5.4 | Nhập đủ hoặc thừa → bấm **Hoàn tất thanh toán** | Modal đóng; đơn hoàn tất; giỏ xử lý theo luồng (trống hoặc chuyển trạng thái) — kiểm tra toast hoặc UI |
| 5.5 | Chọn **Thẻ/QR** | Hiện panel *Quét mã QR chuyển khoản* nếu cửa hàng đã cấu hình; nếu chưa: dòng *Chưa cấu hình: Quản lý → QR thanh toán.* |
| 5.6 | **Thẻ/QR** — **Hoàn tất thanh toán** khi đủ điều kiện | Tương tự 5.4 |
| 5.7 | Bấm **Hủy** trên modal | Đóng modal; giỏ không mất (trừ khi đã clear riêng) |

---

## 6. Tab Đơn QR (nhân viên duyệt)

**Chuẩn bị:** Cần ít nhất một đơn **PENDING** từ khách (xem mục 7 hoặc API).

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 6.1 | Vào tab **Đơn QR** | Thẻ đơn chờ hiển thị (nếu có) |
| 6.2 | Bấm vào một đơn chờ | Modal **Chi tiết Đơn QR** — hiển thị bàn, thời gian, món, tổng |
| 6.3 | Bấm **Duyệt đơn & Báo bếp** | Modal đóng; đơn chuyển trạng thái; danh sách cập nhật; có thể có toast |
| 6.4 | Mở đơn khác (hoặc tạo đơn mới) → bấm **Từ chối** | Browser `confirm` *Xác nhận từ chối đơn này?* — OK → đơn bị từ chối; danh sách cập nhật |

---

## 7. (Liên quan) Tạo đơn QR từ phía khách để test mục 6

**URL mẫu:** `http://127.0.0.1:8000/<public_slug>/qr/?table_code=<CODE>&token=<TOKEN>`  
Lấy `table_code`, `token` từ **Quản lý → QR bàn** (hoặc seed).

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 7.1 | Mở URL đúng `table_code` + `token` | Trang đặt món khách load được |
| 7.2 | Thêm món → gửi đơn (theo nút trên UI public) | Đơn ở trạng thái chờ; trên POS tab **Đơn QR** xuất hiện đơn mới (có thể sau vài giây nếu dùng polling) |

---

## 8. Trang phụ: Đơn trong ngày

**URL:** `http://127.0.0.1:8000/orders/today/`  
**Query:** `?store_id=` (lọc cửa hàng), `?page=` (phân trang **bảng** đơn — 20 đơn/trang).

| Bước | Thao tác | Kiểm tra |
|------|----------|----------|
| 8.1 | Mở URL khi đã đăng nhập | Hiển thị KPI (tổng đơn, doanh thu, giá trị đơn TB) và bảng đơn trong ngày (cột loại đơn / thanh toán theo UI hiện tại) |
| 8.2 | (Nhiều cửa hàng) Chọn cửa hàng trong dropdown trên trang | Bảng và KPI chỉ theo cửa đã chọn |
| 8.3 | Khi có hơn 20 đơn trong ngày (sau lọc) | Cuối bảng có *Trước* / *Sau*; `?page=2` chỉ đổi các dòng bảng |
| 8.4 | So sánh KPI trang 1 và trang 2 | **Tổng đơn / Doanh thu / TB đơn** phải **giống nhau** (tính trên toàn bộ đơn đã lọc, không chỉ 20 dòng hiện tại) |

---

## 9. Đăng xuất

| Bước | Thao tác | Kết quả / Thông báo mong đợi |
|------|----------|-------------------------------|
| 9.1 | Avatar → **Đăng xuất** | Modal xác nhận (nếu có) → xác nhận → về trang login; session hết |

---

## Bảng tổng hợp nhanh

| Hạng mục | PASS / FAIL | Ghi chú |
|----------|-------------|---------|
| Tab Thực đơn / Chọn bàn / Đơn QR | | |
| Thêm món, topping, ghi chú | | |
| Giỏ, mobile offcanvas, chọn bàn, mang về ↔ bàn, Lưu bàn | | |
| Thanh toán tiền mặt / Thẻ·QR | | |
| Duyệt / Từ chối đơn QR | | |
| Đơn trong ngày (`/orders/today/`, KPI + phân trang bảng) | | |
