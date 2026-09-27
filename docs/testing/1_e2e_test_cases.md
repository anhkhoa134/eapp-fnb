# 1) Bộ test case End-to-End — eApp FnB

**Cập nhật:** 27/09/2026 · **Phạm vi:** toàn bộ luồng người dùng qua giao diện + API + WebSocket, trên môi trường chạy thật (ASGI + Redis).

Tài liệu liên quan:
- Kịch bản click-by-click: `docs/setup/phase1/testing/trang_ban_hang.md`, `docs/setup/phase1/testing/trang_quan_ly.md`
- Smoke rút gọn: `docs/setup/phase1/6_smoke_ui_checklist.md`
- Route / API: `docs/setup/phase1/3_routes_permissions_api.md`

---

## 0. Chuẩn bị

### 0.1 Môi trường
```bash
source /Users/anhkhoa/Downloads/Project_django/env_10_web/bin/activate
python manage.py migrate
python manage.py seed_initial_data --reset-passwords --default-password 123456 --seed-qr-pending
redis-server                                  # terminal riêng
python manage.py runserver 127.0.0.1:8000     # KHÔNG dùng --noasgi
```

### 0.2 Dữ liệu & tài khoản
| Ký hiệu | Tài khoản / dữ liệu | Ghi chú |
|---|---|---|
| `MGR` | `demo_quanly / 123456` | Manager tenant `demo` |
| `STF1` | `demo_nhanvien_1 / 123456` | Staff, có quyền store theo seed |
| `STF2` | `demo_nhanvien_2 / 123456` | Staff thứ hai (test realtime 2 máy) |
| `SA` | Superadmin (`python manage.py createsuperuser`) | Vào `/<REAL_ADMIN_PATH>/` |
| `T2` | Tenant thứ hai tạo bằng `SA` trong admin | Dùng test cô lập tenant + giới hạn gói (mặc định 1 store / 12 bàn / 2 nhân viên) |
| Store | CN Trung Tâm (mặc định), CN Thủ Đức, CN Gò Vấp | Tenant `demo` không giới hạn gói |
| Bàn | 12 bàn / store, mã `<3 ký tự slug store>-01` … `-12` | Lấy `table_code` + `token` tại `/quanly/qr-tables/` |
| Món có topping | Trà Sữa Trân Châu, Cà phê Sữa đá… | Topping: Trân châu trắng, Thạch phô mai… |

Thiết bị: 1 desktop Chrome (POS), 1 cửa sổ ẩn danh / điện thoại (khách QR), 1 tab `/kitchen/`.

### 0.3 Quy ước
- **ID:** `E2E-<MODULE>-<số>`.
- **Ưu tiên:** `P0` luồng tiền / bảo mật — chạy mọi release · `P1` luồng chính · `P2` biên / phụ.
- **Loại:** ✅ happy path · ❌ negative · 🔒 phân quyền / bảo mật · ⚡ realtime.
- Kết quả ghi vào bảng mẫu ở mục 16.

---

## 1. Xác thực & phiên (AUTH)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-AUTH-01 | ✅ | Staff đăng nhập | `/accounts/login/` → `STF1` | Chuyển về POS `/` | P0 |
| E2E-AUTH-02 | ✅ | Manager đăng nhập | Login `MGR` | Vào POS `/`; mở được `/quanly/` | P0 |
| E2E-AUTH-03 | ❌ | Sai mật khẩu | Login `STF1` với mật khẩu sai | Ở lại trang login, báo lỗi, không tạo phiên | P0 |
| E2E-AUTH-04 | 🔒 | Truy cập khi chưa login | Mở `/`, `/quanly/`, `/orders/today/`, `/kitchen/` | Redirect `/accounts/login/?next=…` | P0 |
| E2E-AUTH-05 | 🔒 | Logout chỉ POST | Gọi `GET /accounts/logout/` | 405; phiên vẫn còn | P1 |
| E2E-AUTH-06 | ✅ | Logout | Bấm Đăng xuất (POST) | Về trang login; `/` yêu cầu login lại | P1 |
| E2E-AUTH-07 | ✅ | Đổi mật khẩu | `/quanly/account/` → đổi mật khẩu hợp lệ | Thông báo *Đã đổi mật khẩu.*, phiên hiện tại vẫn giữ; login lại bằng mật khẩu mới OK | P1 |
| E2E-AUTH-08 | ❌ | Đổi mật khẩu yếu / sai mật khẩu cũ | Nhập `123` hoặc sai mật khẩu cũ | Báo lỗi validator, mật khẩu không đổi | P2 |
| E2E-AUTH-09 | 🔒 | Tài khoản `is_active=False` | `SA` khoá `STF2` → login | Không đăng nhập được | P1 |
| E2E-AUTH-10 | ✅ | Cập nhật thông tin tài khoản | `MGR` → `/quanly/account/` → sửa họ tên, email, tên doanh nghiệp → Lưu | *Đã cập nhật thông tin tài khoản.*; tên doanh nghiệp mới hiện ở sidebar | P1 |
| E2E-AUTH-11 | 🔒 | Staff dùng trang Tài khoản | `STF1` → avatar → *Thông tin tài khoản* | Sửa được họ tên/email/mật khẩu; không sửa được tên doanh nghiệp; sidebar chỉ có mục staff được phép | P1 |

## 2. Phân quyền & cô lập tenant (SEC)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-SEC-01 | 🔒 | Staff vào trang quản lý | Login `STF1` → `/quanly/`, `/quanly/products/` | 403 | P0 |
| E2E-SEC-02 | 🔒 | Staff truy cập store không được cấp | `STF1` gọi `GET /api/pos/tables/?store_id=<store không có quyền>` | 403 *Store không hợp lệ hoặc không có quyền truy cập.* | P0 |
| E2E-SEC-03 | 🔒 | Thao tác bàn của store khác | `POST /api/pos/tables/<id bàn store khác>/cart/items/` | 403 *Không có quyền truy cập bàn này.* | P0 |
| E2E-SEC-04 | 🔒 | Cô lập tenant — quản lý | Login manager `T2` → mở `/quanly/products/<id sản phẩm demo>/edit/` | 404 / không thấy dữ liệu tenant `demo` | P0 |
| E2E-SEC-05 | 🔒 | Cô lập tenant — API | Manager `T2` gọi `POST /api/pos/qr/orders/<id đơn QR demo>/approve/` | 403 / 404, đơn không đổi trạng thái | P0 |
| E2E-SEC-06 | 🔒 | Cô lập tenant — WebSocket | Staff `T2` mở `ws://…/ws/pos/store/<store demo>/` | Kết nối bị đóng | P0 |
| E2E-SEC-07 | 🔒 | Token QR sai | Mở `/demo/qr/?table_code=<CODE>&token=sai` | Không hiện menu đặt món; API trả 403 *QR không hợp lệ hoặc đã hết hiệu lực.* | P0 |
| E2E-SEC-08 | 🔒 | Thiếu `table_code` / `token` | Gọi `POST /api/public/qr/orders/` thiếu tham số | 400 *Thiếu table_code hoặc token.* | P1 |
| E2E-SEC-09 | 🔒 | Đọc đơn QR bàn khác | `GET /api/public/qr/orders/<id đơn bàn A>/?table_code=<bàn B>&token=<token B>` | 403 / 404, không lộ dữ liệu | P0 |
| E2E-SEC-10 | 🔒 | Reserved slug | `SA` tạo tenant slug `admin` / `api` / `quanly` | Form báo lỗi, không tạo | P1 |
| E2E-SEC-11 | 🔒 | Header bảo mật | Xem response header trang bất kỳ | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` | P2 |
| E2E-SEC-12 | 🔒 | CSRF | POST form `/quanly/…` không có CSRF token | 403 | P1 |
| E2E-SEC-13 | 🔒 | Tenant ngừng hoạt động (public) | `SA` tắt `is_active` tenant `demo` → mở `/demo/`, `/demo/qr/…` | Không truy cập được | P1 |

> Lưu ý: POS / quản lý hiện **chưa** chặn tenant `is_active=False` hoặc hết hạn gói — xem `docs/backlog/1_backlog.md` BL-001. Khi làm xong, bổ sung test case tương ứng.

## 3. POS — Bán mang về (POS)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-POS-01 | ✅ | Tải thực đơn | Login `STF1` → tab **Thực đơn** | Hiện danh mục + món đang bật của store hiện tại | P0 |
| E2E-POS-02 | ✅ | Đổi cửa hàng | Menu avatar → chọn store khác | Món / bàn / đơn QR tải lại theo store mới | P1 |
| E2E-POS-03 | ✅ | Tìm món | Gõ "trà" vào **Tìm món…** | Chỉ còn món khớp | P2 |
| E2E-POS-04 | ✅ | Lọc danh mục | Bấm một danh mục | Chỉ hiện món thuộc danh mục | P2 |
| E2E-POS-05 | ✅ | Thêm món có size + topping + ghi chú | Chọn Trà Sữa → size L → 2 topping → ghi chú "ít đá" → thêm | Giỏ hiện đúng size, topping, ghi chú; thành tiền = (giá size + tổng topping) × SL | P0 |
| E2E-POS-06 | ✅ | Tăng / giảm / xoá dòng | +, −, xoá trong giỏ | Tổng tiền cập nhật đúng; SL về 0 thì mất dòng | P1 |
| E2E-POS-07 | ✅ | Món giống nhau khác topping | Thêm 2 lần cùng món, khác topping | Tách 2 dòng riêng | P1 |
| E2E-POS-08 | ✅ | Món ẩn theo store | Manager tắt món ở store A → POS store A tải lại | Món không còn trên POS store A; store B vẫn có | P1 |
| E2E-POS-09 | ✅ | Giá theo store | Đặt giá riêng cho unit ở store B | POS store B hiển thị và tính giá riêng | P1 |

## 4. Thanh toán (PAY)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-PAY-01 | ✅ | Tiền mặt đủ | Giỏ 55.000 → Tiền mặt, khách đưa 100.000 | Tạo `Order` (kênh *mang về*), tiền thối 45.000, giỏ trống | P0 |
| E2E-PAY-02 | ❌ | Tiền mặt thiếu | Khách đưa 50.000 cho đơn 55.000 | 400 *Khách đưa chưa đủ tiền.*; không tạo đơn | P0 |
| E2E-PAY-03 | ✅ | Thẻ / QR, khách đưa 0 | Chọn Card/QR, không nhập tiền | Đơn tạo, `customer_paid` = tổng tiền | P0 |
| E2E-PAY-04 | ❌ | Giỏ trống | Bấm thanh toán khi giỏ rỗng | 400 *Giỏ hàng trống.* | P1 |
| E2E-PAY-05 | ✅ | QR thanh toán store | Manager upload ảnh QR ở `/quanly/payment-qr/` → POS chọn Card/QR | Hiển thị đúng ảnh QR của store hiện tại | P1 |
| E2E-PAY-06 | ✅ | Khuyến mãi % có trần | KM 10%, trần 20.000; đơn 300.000 | Giảm 20.000; `discount_source=promotion` | P0 |
| E2E-PAY-07 | ❌ | Khuyến mãi chưa đủ điều kiện | KM tối thiểu 200.000; đơn 100.000 | KM không xuất hiện / 400 *Khuyến mãi không hợp lệ hoặc không đủ điều kiện áp dụng.* | P1 |
| E2E-PAY-08 | ❌ | Khuyến mãi hết hạn / sai store | KM `valid_to` hôm qua hoặc không gán store hiện tại | Không hiện trong POS | P1 |
| E2E-PAY-09 | ✅ | Ưu đãi hạng khách | Khách hạng Silver (3%) → đơn 100.000, không chọn KM | Giảm 3.000; `discount_source=tier` | P0 |
| E2E-PAY-10 | ✅ | Không cộng dồn KM + hạng | Khách Gold (5%) + KM 10.000 cho đơn 100.000 | Chỉ áp mức lớn hơn (10.000, nguồn *promotion*) | P0 |
| E2E-PAY-11 | ✅ | Tích điểm | Khách mua 125.000 | +12 điểm (1 điểm / 10.000đ); `total_spent` tăng; lên hạng nếu vượt ngưỡng | P1 |
| E2E-PAY-12 | ✅ | Tạo khách nhanh tại POS | Nhập tên + SĐT mới khi thanh toán; thử lại với SĐT đã có | SĐT mới: tạo khách và gắn vào đơn. SĐT đã có: trả khách cũ, báo *Khách hàng đã tồn tại.* | P2 |
| E2E-PAY-13 | ❌ | Tạo khách thiếu SĐT | Chỉ nhập tên | 400 *Vui lòng nhập số điện thoại khách hàng.* | P2 |
| E2E-PAY-14 | ✅ | Đơn trong ngày | Sau các đơn trên → `/orders/today/` | Đơn mới hiện đủ; KPI tổng đơn / doanh thu khớp | P1 |

## 5. Bán tại bàn (TBL)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-TBL-01 | ✅ | Mở bàn, thêm món | Tab **Chọn bàn** → Bàn 01 → thêm 2 món | Giỏ lưu server; bàn chuyển trạng thái *đang phục vụ* | P0 |
| E2E-TBL-02 | ✅ | Giỏ bàn bền vững | Reload trang / mở POS trên máy khác → Bàn 01 | Món vẫn còn | P0 |
| E2E-TBL-03 | ✅ | Chọn bàn khi đang có giỏ mang về | Giỏ mang về có 2 món → chọn Bàn 02 | Món **không mất**, được import lên giỏ Bàn 02 | P0 |
| E2E-TBL-04 | ✅ | Đổi sang mang về | Đang ở Bàn 02 → **Đổi sang mang về** | Giỏ bàn trên server rỗng; giỏ mang về trên màn hình giữ món; Bàn 02 trống | P1 |
| E2E-TBL-05 | ✅ | Tạo đơn mang về khi đang ở bàn | Ở Bàn 01 → **Tạo đơn mang về** → bán → **Quay lại bàn** | Giỏ Bàn 01 nguyên vẹn | P1 |
| E2E-TBL-06 | ✅ | Chuyển bàn | Bàn 01 → chuyển sang Bàn 05 (trống) | Món chuyển sang Bàn 05, Bàn 01 trống | P0 |
| E2E-TBL-07 | ❌ | Chuyển sang chính nó | `move-to` với `to_table_id` = bàn hiện tại | 400 *Bàn đích phải khác bàn hiện tại.* | P2 |
| E2E-TBL-08 | ❌ | Chuyển khác cửa hàng | `move-to` sang bàn store khác | 400 *Không thể chuyển giỏ giữa hai cửa hàng khác nhau.* | P1 |
| E2E-TBL-09 | ✅ | Thanh toán bàn | Bàn 05 → thanh toán tiền mặt | `Order` kênh *tại quán*; giỏ bàn xoá; bàn trống | P0 |
| E2E-TBL-10 | ❌ | Thanh toán bàn trống | `POST tables/<id>/checkout/` bàn không món | 400 *Bàn này chưa có món để thanh toán.* | P2 |
| E2E-TBL-11 | ✅ | Hai nhân viên cùng bàn | `STF1` thêm món Bàn 03; `STF2` mở Bàn 03 | `STF2` thấy món của `STF1` | P1 |
| E2E-TBL-12 | ✅ | Mobile: chọn bàn từ giỏ | Màn hình < 768px → mở giỏ (offcanvas) → **Chọn bàn** | Offcanvas đóng, thấy lưới bàn | P2 |

## 6. Gọi món QR — Khách (QRC)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-QRC-01 | ✅ | Mở trang QR hợp lệ | Điện thoại mở `/demo/qr/?table_code=<CODE>&token=<TOKEN>` | Hiện tên bàn + menu đúng store của bàn | P0 |
| E2E-QRC-02 | ✅ | Gửi đơn | Chọn món, size, topping, ghi chú → gửi | Đơn `PENDING`; màn hình theo dõi trạng thái | P0 |
| E2E-QRC-03 | ✅ | Nhớ đơn đang chờ | Reload trang | Vẫn thấy đơn đang chờ (localStorage theo `table_code`) | P1 |
| E2E-QRC-04 | ✅ | Sửa đơn chờ | Đổi SL / thêm món / sửa ghi chú → lưu | Đơn cập nhật; POS nhận thay đổi | P1 |
| E2E-QRC-05 | ✅ | Huỷ đơn chờ | Bấm Huỷ | Trạng thái `CANCELLED`; POS mất đơn khỏi danh sách chờ | P1 |
| E2E-QRC-06 | ❌ | Sửa / huỷ đơn đã xử lý | Sau khi staff duyệt → gọi PATCH / cancel | 400 *Quán đã xử lý đơn nên không thể sửa nữa.* / *Quán đã xử lý đơn nên không thể hủy.* | P0 |
| E2E-QRC-07 | ❌ | Token đã reset | Manager reset token bàn → khách dùng link cũ | 403, không đặt được | P0 |
| E2E-QRC-08 | ❌ | Bàn bị tắt | Manager tắt bàn → mở link QR | Không đặt được | P1 |
| E2E-QRC-09 | ✅ | Món hết / ẩn | Manager tắt món ở store của bàn | Món không hiện trên trang QR | P2 |
| E2E-QRC-10 | ✅ | Menu online khi tắt QR | Tắt **QR bàn / gọi món QR** → mở `/demo/` | Chỉ hiện thực đơn, không có nút **+** / giỏ; dòng *Quán hiện chưa nhận đặt món online…* | P2 |
| E2E-QRC-11 | ✅ | Không lộ từ kỹ thuật | Mở trang QR hợp lệ | Không có chữ *WebSocket*, *fallback*, *Mobile-first*; trạng thái hiện *Tự động cập nhật* | P2 |
| E2E-QRC-12 | ✅ | Thêm món khi đơn đang chờ | Đơn `PENDING` → bấm **+** ở một món | Tự vào chế độ *Đang sửa đơn #…*, giỏ có món cũ + món mới, nút *Cập nhật đơn* | P1 |
| E2E-QRC-13 | ✅ | Giữ giỏ nháp | Thêm 2 món, chưa gửi → reload | Giỏ còn nguyên | P2 |

## 7. Gọi món QR — Nhân viên (QRS)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-QRS-01 | ⚡ | Nhận đơn mới realtime | POS đang mở tab bất kỳ; khách gửi đơn | Trong ~1–2s: chuông / badge tăng, âm báo, đơn hiện trong tab **Đơn QR**, bàn đổi màu *có đơn QR* | P0 |
| E2E-QRS-02 | ✅ | Duyệt đơn | Tab Đơn QR → Duyệt | Đơn `APPROVED`; món merge vào giỏ bàn (giữ topping / ghi chú); khách thấy *đã duyệt* | P0 |
| E2E-QRS-03 | ✅ | Duyệt vào bàn đang có món | Bàn đã có 2 món → duyệt đơn QR 1 món | Giỏ bàn còn đủ 3 dòng / cộng SL đúng | P1 |
| E2E-QRS-04 | ✅ | Từ chối có lý do | Từ chối, chọn / nhập lý do | `REJECTED`; lý do lưu và hiển thị cho khách + lịch sử | P0 |
| E2E-QRS-05 | ❌ | Từ chối không lý do | Để trống lý do | 400 *Vui lòng chọn hoặc nhập lý do từ chối.* | P1 |
| E2E-QRS-06 | ❌ | Lý do > 500 ký tự | Nhập 501 ký tự | 400 *Lý do không được quá 500 ký tự.* | P2 |
| E2E-QRS-07 | ❌ | Duyệt đơn khách vừa huỷ | Khách huỷ trong lúc POS còn hiển thị → bấm Duyệt | 400 *Đơn đã bị khách hủy nên không thể duyệt.* | P0 |
| E2E-QRS-08 | ❌ | Hai staff xử lý cùng đơn | `STF1` duyệt; `STF2` (chưa refresh) bấm Từ chối | 400 *Đơn đã được duyệt nên không thể từ chối.* | P0 |
| E2E-QRS-09 | ✅ | Lọc theo trạng thái | `GET /api/pos/qr/orders/?store_id=&status=approved` | Chỉ trả đơn đúng trạng thái | P2 |

## 7b. Menu online — Đặt món mang đi (TKW)
Tiền điều kiện: cờ **QR bàn / gọi món QR** bật, gói còn hạn. Chi tiết: `docs/setup/phase2/4_online_takeaway_ordering.md`.

| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-TKW-01 | ✅ | Đặt mang đi | Mở `/demo/` trên điện thoại → thêm món → nhập tên + SĐT → **Đặt món mang đi** | 201; thẻ theo dõi *Đang chờ quán xác nhận*; `QROrder.order_type = TAKEAWAY`, `table` trống | P0 |
| E2E-TKW-02 | ❌ | Thiếu tên / SĐT sai | Để trống tên hoặc nhập `12ab` | Ô báo đỏ + toast; API trả 400 | P1 |
| E2E-TKW-03 | ⚡ | POS nhận đơn | Khách gửi đơn | Tab Đơn QR hiện thẻ icon túi + tên khách; modal có SĐT, ghi chú | P0 |
| E2E-TKW-04 | ⚡ | Duyệt → báo bếp | POS **Duyệt** | Khách thấy *Quán đã nhận đơn* không cần reload; `/kitchen/` có phiếu *Mang đi · <tên>* nguồn *Mang về*; giỏ bàn không đổi | P0 |
| E2E-TKW-05 | ✅ | Thu tiền | Mục *Mang đi · chờ khách tới lấy* → **Thu tiền** → thanh toán | `Order` tạo; `QROrder.sale_order` gán; không có phiếu bếp thứ hai; khách thấy *Bạn đã nhận món* | P0 |
| E2E-TKW-06 | ❌ | Thu tiền 2 lần | Gọi lại `POST /api/pos/checkout/` với cùng `qr_order_id` | 400 *Đơn mang đi không hợp lệ hoặc đã được thu tiền.* | P0 |
| E2E-TKW-07 | 🔒 | Sai `access_key` | `GET /api/public/qr/orders/<id>/?access_key=sai` | 404, không lộ dữ liệu | P0 |
| E2E-TKW-08 | 🔒 | Giới hạn tần suất | Gửi 11 đơn trong 30 phút từ cùng IP | Đơn thứ 11 → 429 *Bạn đặt quá nhiều đơn…* | P1 |
| E2E-TKW-09 | ✅ | Khách huỷ / bị từ chối | Huỷ đơn chờ; hoặc POS từ chối có lý do | Trạng thái tương ứng; đơn từ chối hiện lý do cho khách | P1 |
| E2E-TKW-10 | ✅ | Nhớ thông tin khách | Đặt xong, reload, thêm món mới | Tên + SĐT điền sẵn; thẻ đơn cũ vẫn hiển thị tới khi bấm *Đã hiểu* | P2 |
| E2E-TKW-11 | ✅ | Nhiều cửa hàng | Chọn cửa hàng khác ở góc phải | Menu + đơn theo dõi theo cửa hàng mới | P2 |

## 8. Realtime WebSocket (WS)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-WS-01 | ⚡ | Kết nối POS | DevTools → Network → WS | `ws://…/ws/pos/store/<id>/` trạng thái 101, không lặp lỗi | P1 |
| E2E-WS-02 | ⚡ | Khách nhận trạng thái | Staff duyệt / từ chối | Trang khách đổi trạng thái không cần reload | P0 |
| E2E-WS-03 | ⚡ | Fallback polling khi Redis tắt | Dừng `redis-server` → khách gửi đơn | POS vẫn nhận đơn trong ≤ 15s; không crash UI | P1 |
| E2E-WS-04 | ⚡ | Tự phục hồi | Bật lại Redis | WS kết nối lại, realtime hoạt động lại | P2 |
| E2E-WS-05 | ⚡ | Đổi store trên POS | Đổi từ store A sang B | Socket chuyển sang group store B; không nhận đơn store A | P1 |

## 9. Màn hình bếp (KIT)
Tiền điều kiện: `MGR` bật **Màn hình bếp** tại `/quanly/settings/features/`.

| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-KIT-01 | 🔒 | Tính năng tắt | Tắt cờ → mở `/kitchen/`; gọi `POST tables/<id>/kitchen/send/` | 403 / *Tính năng màn hình bếp đang tắt.*; POS không có nút **Báo bếp** | P0 |
| E2E-KIT-02 | ⚡ | Báo bếp từ bàn | Bàn 01 có 2 món → **Báo bếp** | 201 + `ticket_id`; `/kitchen/` hiện phiếu mới realtime (nguồn *Tại bàn*) | P0 |
| E2E-KIT-03 | ✅ | Báo bếp lần 2 chỉ gửi phần mới | Thêm 1 món + tăng SL món cũ → Báo bếp | Phiếu mới chỉ chứa phần chưa gửi; không có món mới → 200 + `ticket_id: null` | P0 |
| E2E-KIT-04 | ⚡ | Cập nhật trạng thái món | Bếp: Chờ làm → Đang làm → Đã xong | Trạng thái đổi; POS nhận `kitchen.changed` | P1 |
| E2E-KIT-05 | ✅ | Hoàn tất phiếu | Bấm xong cả phiếu | Phiếu chuyển sang *đã xong hôm nay* | P1 |
| E2E-KIT-06 | ✅ | Giảm SL món đã báo | Giảm SL món đã báo bếp (chưa làm xong) | Phần tương ứng trên bếp bị huỷ | P0 |
| E2E-KIT-07 | ✅ | Đổi topping / ghi chú món đã báo | Sửa ghi chú món đã báo | Phần chưa xong bị huỷ; món trở thành *chưa báo* để báo lại | P1 |
| E2E-KIT-08 | ✅ | Chuyển bàn khi có phiếu mở | Bàn 01 có phiếu đang làm → chuyển sang Bàn 06 | Phiếu hiển thị tên bàn mới | P1 |
| E2E-KIT-09 | ✅ | Duyệt đơn QR tạo phiếu | Duyệt đơn QR | Phiếu nguồn *Gọi món QR* | P1 |
| E2E-KIT-10 | ✅ | Thanh toán mang về tạo phiếu | Bán mang về + thanh toán | Phiếu nguồn *Mang về* | P1 |
| E2E-KIT-11 | ✅ | Thanh toán bàn còn món chưa báo | Bàn có món chưa báo → thanh toán | Phiếu tự tạo cho phần chưa báo | P1 |
| E2E-KIT-12 | 🔒 | Bếp store khác | Staff gọi `POST kitchen/items/<id item store khác>/status/` | 403 *Không có quyền cập nhật phiếu bếp của cửa hàng này.* | P1 |
| E2E-KIT-13 | ❌ | Trạng thái không hợp lệ | Body `{"status":"FOO"}` | 400 *Trạng thái không hợp lệ.* | P2 |
| E2E-KIT-14 | ✅ | Thanh công cụ | Bấm Chuông, Tự in phiếu, Toàn màn hình, đổi Đang chờ / Đã xong | Nút đổi trạng thái (màu mint + công tắc); tắt/bật giữ sau reload; icon toàn màn hình đổi | P2 |
| E2E-KIT-15 | ✅ | Thời gian chờ dài | Phiếu mở > 60 phút | Hiện dạng `1g05'`, thẻ viền đỏ | P2 |

## 10. Quản lý — Dashboard & đơn hàng (MGR)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-MGR-01 | ✅ | Dashboard theo kỳ | `/quanly/` → đổi `period`: 7d, 30d, tháng này, tháng trước, năm nay, năm trước | KPI + biểu đồ đổi theo kỳ, không lỗi | P1 |
| E2E-MGR-02 | ✅ | Khoảng ngày tuỳ chọn | Để trống kỳ, nhập `date_from` / `date_to` | Dữ liệu đúng khoảng | P2 |
| E2E-MGR-03 | ✅ | Lọc theo store | Chọn store | KPI chỉ tính store đó | P1 |
| E2E-MGR-04 | ✅ | Đối chiếu doanh thu | Tổng các đơn hôm nay (E2E-PAY) vs dashboard hôm nay | Khớp tuyệt đối (sau giảm giá, thuế) | P0 |
| E2E-MGR-05 | ✅ | Lịch sử đơn | `/quanly/orders/` | Có loại đơn (tại quán / mang về), giảm giá, đơn QR bị từ chối kèm lý do | P1 |
| E2E-MGR-06 | ✅ | Xoá đơn | Xoá một đơn | Đơn biến mất; dashboard cập nhật | P1 |

## 11. Quản lý — Danh mục, sản phẩm, topping, nhân viên, cửa hàng, QR bàn (CRUD)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-CRUD-01 | ✅ | Tạo danh mục → sản phẩm → unit | Tạo mới đủ 3 cấp, upload ảnh JPG/PNG | Món hiện trên POS + menu online; ảnh được chuyển WebP + có thumbnail; form không còn ô Image URL | P0 |
| E2E-CRUD-02 | ✅ | Sửa giá | Sửa giá unit | POS / QR dùng giá mới cho món thêm sau | P1 |
| E2E-CRUD-03 | ✅ | Ngưng bán | Tắt `is_active` sản phẩm | Món biến mất khỏi POS / QR | P1 |
| E2E-CRUD-04 | ✅ | Import Excel | Tải file mẫu (không còn cột `url_hinh`, `thu_tu`) → điền → import | Danh mục / sản phẩm tạo đúng; dòng lỗi được liệt kê | P1 |
| E2E-CRUD-05 | ❌ | Import Excel lỗi | File sai cột / sai giá | Báo lỗi từng dòng, không tạo dữ liệu rác | P2 |
| E2E-CRUD-06 | ✅ | Topping + gán theo sản phẩm | Tạo topping → gán giá cho 1 sản phẩm | POS chỉ hiện topping cho món được gán, đúng giá | P1 |
| E2E-CRUD-07 | ✅ | Phân trang topping 2 bảng | Đổi `page` rồi `mpage` | Hai bảng không reset lẫn nhau | P2 |
| E2E-CRUD-08 | ✅ | Tạo nhân viên + cấp store | Tạo staff mới, cấp 1 store | Login được, POS chỉ thấy store được cấp | P0 |
| E2E-CRUD-09 | ✅ | Reset mật khẩu nhân viên | Manager reset | Nhân viên login bằng mật khẩu mới | P1 |
| E2E-CRUD-10 | ✅ | CRUD cửa hàng | Tạo store mới (có SĐT) | Xuất hiện trong bộ chọn store POS (nếu được cấp quyền) | P1 |
| E2E-CRUD-11 | ✅ | CRUD bàn QR | Tạo / sửa / xoá bàn | Lưới bàn POS cập nhật | P1 |
| E2E-CRUD-12 | ✅ | Reset token | Reset token bàn | Link cũ hỏng (E2E-QRC-07), link mới hoạt động | P0 |
| E2E-CRUD-13 | ✅ | PNG QR | Tải PNG | Quét bằng điện thoại mở đúng trang QR của bàn | P1 |
| E2E-CRUD-14 | ✅ | In PDF A3 | Lọc store → **In PDF khổ lớn** | 15 bàn/trang; tên/mã bàn gần QR; không có URL text | P2 |
| E2E-CRUD-15 | ✅ | Phân trang | Danh sách > 20 dòng → `?page=2`; QR bàn giữ `?store=` | Đúng trang, giữ bộ lọc | P2 |
| E2E-CRUD-17 | ✅ | Kéo thả sắp xếp | Kéo thả đơn vị của 1 sản phẩm, topping, bàn QR → reload | Thứ tự mới được lưu; POS / trang QR hiển thị theo thứ tự mới; mục tạo mới nằm cuối | P1 |
| E2E-CRUD-18 | ❌ | Reorder sai dữ liệu | `POST /quanly/reorder/units/` với id trùng, hoặc id thuộc 2 sản phẩm / tenant khác | 400, thứ tự không đổi | P2 |
| E2E-CRUD-19 | 🔒 | Reorder khi tính năng tắt | Tắt Topping → `POST /quanly/reorder/toppings/` | 403 *Tính năng topping đang tắt.* | P2 |
| E2E-CRUD-16 | ✅ | Redirect cũ | Mở `/quanly/product-toppings/` | Redirect `/quanly/toppings/` | P2 |

## 12. Khách hàng & khuyến mãi (CUS)
Tiền điều kiện: cờ **Khách hàng** và **Khuyến mãi** bật.

| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-CUS-01 | ✅ | Tạo khách | `/quanly/customers/` → tên + SĐT | Tạo thành công, hạng Member | P1 |
| E2E-CUS-02 | ❌ | Trùng SĐT | `/quanly/customers/` tạo khách thứ hai cùng SĐT | Form báo lỗi trùng, không lỗi 500. **Bug đã biết:** form hiện không kiểm tra trùng → IntegrityError (xem BL-034) | P1 |
| E2E-CUS-03 | ✅ | Lên hạng | Tạo đơn cho khách đến khi `total_spent` ≥ 5.000.000 | Hạng Silver; đơn sau áp 3% | P1 |
| E2E-CUS-04 | ✅ | Sửa ngưỡng hạng | Đổi ngưỡng / % hạng | Checkout sau dùng cấu hình mới | P2 |
| E2E-CUS-05 | ❌ | Khách ngưng hoạt động | Tắt khách → chọn ở POS | 400 *Khách hàng không hợp lệ hoặc đã ngưng hoạt động.* | P2 |
| E2E-CUS-06 | ✅ | Tạo khuyến mãi | `/quanly/promotions/` — %, trần, tối thiểu, thời hạn, store | Hiện ở POS khi đủ điều kiện | P1 |
| E2E-CUS-07 | ✅ | Tắt khuyến mãi | Tắt `is_active` | Không còn ở POS | P2 |

## 13. Cấu hình tính năng & giới hạn gói (FEAT)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-FEAT-01 | 🔒 | Tắt Topping | Tắt cờ → POS, `/quanly/toppings/` | Ẩn topping trên POS / QR; trang topping bị chặn; API thêm topping trả 400 *Tính năng topping đang tắt.* | P1 |
| E2E-FEAT-02 | 🔒 | Tắt QR bàn | Tắt cờ → trang QR khách, `/quanly/qr-tables/`, API public | Bị chặn (403 *Tính năng gọi món QR đang tắt.*); POS ẩn tab Đơn QR | P0 |
| E2E-FEAT-03 | 🔒 | Tắt Khách hàng | Tắt cờ | Ẩn menu Khách hàng; POS không chọn được khách | P1 |
| E2E-FEAT-04 | 🔒 | Tắt Khuyến mãi | Tắt cờ | Ẩn menu + phần chọn KM ở POS | P1 |
| E2E-FEAT-05 | 🔒 | Tắt nhiều cửa hàng | Tenant có > 1 store đang hoạt động → tắt cờ | Không cho tắt, báo lỗi; khi còn 1 store thì tắt được và `/quanly/stores/` trả 403 | P1 |
| E2E-FEAT-06 | ✅ | Bật lại tính năng | Bật lại từng cờ | Dữ liệu cũ vẫn còn, hiển thị lại bình thường | P2 |
| E2E-FEAT-07 | ❌ | Giới hạn cửa hàng | Tenant `T2` (tối đa 1) bật nhiều cửa hàng → tạo store thứ 2 | Báo *Đã đạt giới hạn số cửa hàng (1)…* | P1 |
| E2E-FEAT-08 | ❌ | Giới hạn bàn | `T2` tạo bàn thứ 13 | Báo *Đã đạt giới hạn số bàn (12)…* | P1 |
| E2E-FEAT-09 | ❌ | Giới hạn nhân viên | `T2` tạo nhân viên thứ 3 | Báo *Đã đạt giới hạn số nhân viên (2)…* | P1 |
| E2E-FEAT-10 | ✅ | Không giới hạn | `SA` đặt giới hạn = 0 | Tạo thêm thoải mái | P2 |
| E2E-FEAT-11 | ✅ | Xem mức sử dụng | `/quanly/account/` | Hiện đã dùng / tối đa và ngày hết hạn gói | P2 |
| E2E-FEAT-12 | 🔒 | Tắt / bật Ca làm việc | Tenant mới → kiểm tra mặc định; bật cờ → mở ca; tắt cờ → `/shifts/`, `/shifts/<id>/print/`, `GET /api/pos/shifts/current/` | Mặc định tắt; khi tắt: 403 *Tính năng ca làm việc đang tắt…*, ẩn mục Ca làm việc (sidebar, POS, Đơn trong ngày); bật lại: ca đang mở vẫn còn | P1 |
| E2E-FEAT-13 | 🔒 | Ca làm việc theo gói | Gán gói *Miễn phí* → `/quanly/settings/features/`; gán *Cơ bản* | Miễn phí: cờ bị tắt, công tắc khoá + nhãn *Cần nâng cấp gói*, POST bật bị bỏ qua. Cơ bản: bật được | P1 |
| E2E-FEAT-14 | ✅ | Vị trí mục Ca làm việc | Bật cờ → xem sidebar Quản lý | *Ca làm việc* nằm trong nhóm con dưới *Cấu hình tính năng* | P2 |

## 13b. In ấn (PRN)
Tiền điều kiện: máy tính có máy in nhiệt 80mm (hoặc *Save as PDF* để kiểm tra bố cục).

| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-PRN-01 | ✅ | In hoá đơn sau thanh toán | POS thanh toán mang về (tắt *Tự in hoá đơn*) → bấm **In hoá đơn** trên toast | Hộp thoại in mở ngay trên trang POS (không mở tab); hoá đơn đủ tên / địa chỉ / SĐT cửa hàng, số HĐ, món + topping, tổng, khách đưa, tiền thừa | P0 |
| E2E-PRN-02 | ✅ | Tự in hoá đơn | Bật **Tự in hoá đơn** trong menu POS → thanh toán | Hộp thoại in tự mở; tắt/bật giữ sau reload | P1 |
| E2E-PRN-03 | ✅ | Hoá đơn tại bàn | Thanh toán Bàn 01 → in | Có dòng *Bàn: Bàn 01* | P1 |
| E2E-PRN-04 | 🔒 | In lại | In cùng hoá đơn lần 2 từ Đơn trong ngày / Lịch sử đơn | Có dấu *BẢN IN LẠI (lần 2)*; nhật ký có *In lại hoá đơn* | P0 |
| E2E-PRN-05 | ✅ | Phiếu tạm tính | Bàn có món → **In tạm tính** | Món + tạm tính + QR chuyển khoản cửa hàng; ghi *không phải hoá đơn thanh toán* | P1 |
| E2E-PRN-06 | ✅ | Phiếu bếp | Bật *Tự in phiếu bếp* (POS) → **Báo bếp**; thanh toán mang về | Phiếu bếp in tự động; nếu cũng bật tự in hoá đơn thì hai hộp thoại mở lần lượt, không chồng nhau | P1 |
| E2E-PRN-07 | ✅ | Tự in ở màn hình bếp | Mở 2 tab `/kitchen/` cùng bật *Tự in phiếu* → POS báo bếp | Chỉ in 1 lần (phiếu đã in không tự in lại); nút máy in trên thẻ phiếu in lại được | P1 |
| E2E-PRN-08 | ✅ | Khổ 58mm | Trang in → chọn *58 mm* → In; mở trang in khác | Nội dung vừa khổ; lựa chọn được nhớ | P2 |
| E2E-PRN-09 | 🔒 | In đơn cửa hàng khác | Staff mở `/orders/<id đơn store không có quyền>/receipt/` | 403 | P1 |
| E2E-PRN-10 | 🔒 | Phiếu bếp khi tắt bếp | Tắt Màn hình bếp → mở `/kitchen/tickets/<id>/print/` | 403 | P2 |

## 13c. Ca làm việc (SHF)
Tiền điều kiện: tenant gói *Cơ bản* trở lên, `MGR` bật **Ca làm việc** tại `/quanly/settings/features/`.

| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-SHF-01 | ✅ | Mở ca | `STF1`: POS → menu → **Ca làm việc** (badge *Chưa mở ca*) → nhập `500.000` → **Mở ca** | Ca #N đang mở; badge POS *Đang mở* | P0 |
| E2E-SHF-02 | ❌ | Mở ca trùng | Mở ca lần 2 cho cùng cửa hàng (tab khác) | Báo *…đang có ca mở, hãy chốt ca đó trước.* | P1 |
| E2E-SHF-03 | ✅ | Số liệu trực tiếp | Bán 1 đơn tiền mặt 60.000, 1 đơn thẻ 30.000 → reload `/shifts/` | Số đơn 2, doanh thu 90.000, tiền mặt 60.000, thẻ 30.000, dự kiến 560.000 | P0 |
| E2E-SHF-04 | ✅ | Hoàn tiền mặt trong ca | `MGR` hoàn 10.000 tiền mặt đơn trên | Hoàn tiền 10.000; dự kiến 550.000 | P0 |
| E2E-SHF-05 | ✅ | Chốt ca | Nhập thực đếm `540.000` → **Chốt ca** → hộp thoại xác nhận → **Chốt ca** | Gợi ý *Thiếu 10.000 đ* khi nhập; chốt xong tự in báo cáo; lịch sử: chênh lệch **-10.000** (đỏ) | P0 |
| E2E-SHF-06 | ❌ | Chốt thiếu tiền thực đếm | Để trống ô thực đếm → Chốt | Không gửi được (bắt buộc) / báo lỗi; ca vẫn mở | P2 |
| E2E-SHF-07 | ✅ | Huỷ chốt | Bấm **Huỷ** trên hộp thoại xác nhận | Ca vẫn mở | P2 |
| E2E-SHF-08 | ✅ | Số liệu ca đã chốt không đổi | Sau khi chốt, bán thêm / xoá đơn trong ca | Báo cáo ca đã chốt giữ nguyên số | P1 |
| E2E-SHF-09 | ✅ | In báo cáo tạm | Ca đang mở → **In báo cáo tạm** | Tiêu đề *BÁO CÁO CA (ĐANG MỞ)*, có món bán ra | P2 |
| E2E-SHF-10 | 🔒 | Ca cửa hàng khác | Staff chỉ có quyền Store 1 → `/shifts/?store_id=<store 2>`; `/shifts/<id ca store 2>/print/` | Trang hiện Store 1; báo cáo ca Store 2 trả 403 | P1 |

## 13d. Hoàn tiền (RFD)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-RFD-01 | ✅ | Hoàn một phần | `MGR` `/quanly/orders/` → nút hoàn tiền → *Hoàn một phần* 20.000, lý do → xác nhận | Thông báo *Đã hoàn 20.000 đ…*; đơn *Hoàn thành* + *Hoàn 1 phần*; tổng tiền hiện *-20.000 đ hoàn* | P0 |
| E2E-RFD-02 | ✅ | Hoàn phần còn lại | Hoàn *toàn bộ số còn lại* | Trạng thái *Đã hoàn tiền*; nút hoàn tiền biến mất; chi tiết đơn liệt kê 2 lần hoàn | P0 |
| E2E-RFD-03 | ❌ | Vượt số tiền | Hoàn một phần lớn hơn số còn lại | Báo *Số tiền hoàn vượt quá…*; không đổi dữ liệu | P1 |
| E2E-RFD-04 | ❌ | Thiếu lý do | Để trống lý do (gửi bằng API / sửa form) | Báo *Vui lòng nhập lý do hoàn tiền.* | P2 |
| E2E-RFD-05 | 🔒 | Staff hoàn tiền | Staff `POST /quanly/orders/<id>/refund/` | 403 | P0 |
| E2E-RFD-06 | ✅ | Doanh thu thuần | So dashboard, Lịch sử đơn, Đơn trong ngày trước / sau hoàn | Doanh thu giảm đúng số đã hoàn | P0 |
| E2E-RFD-07 | ✅ | Khách hàng | Hoàn đơn có khách thành viên | `total_spent`, điểm, hạng khách giảm tương ứng | P1 |
| E2E-RFD-08 | ✅ | In hoá đơn đã hoàn | In lại hoá đơn đơn đã hoàn | Có các dòng hoàn tiền + *Thực thu*; đơn hoàn đủ có dấu *ĐÃ HOÀN TIỀN* | P2 |

## 13e. Nhật ký thao tác (AUD)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-AUD-01 | ✅ | Huỷ món đã báo bếp | Bàn có 3 món đã báo bếp → giảm còn 1 | Nhật ký *Huỷ món*: *Bàn 01: huỷ … x2 (đã báo bếp)*, đúng nhân viên | P0 |
| E2E-AUD-02 | ✅ | Đổi giá | Sửa giá đơn vị 30.000 → 35.000 | *Cập nhật* · *Đơn vị bán*, dòng *Giá: 30.000 → 35.000* | P1 |
| E2E-AUD-03 | ✅ | Các thao tác nhạy cảm | Hoàn tiền, xoá đơn, in lại hoá đơn, chuyển bàn, từ chối QR, mở / chốt ca, reset token QR, đổi cấu hình tính năng | Mỗi thao tác có 1 dòng đúng loại; mật khẩu / token chỉ ghi *đã thay đổi* | P1 |
| E2E-AUD-04 | 🔒 | Đăng nhập sai | Đăng nhập `STF1` sai mật khẩu | Dòng *Đăng nhập thất bại* có IP | P1 |
| E2E-AUD-05 | ✅ | Bộ lọc | Lọc theo nhóm *Bán hàng*, theo người, cửa hàng, ngày, từ khoá | Kết quả đúng; phân trang giữ bộ lọc | P2 |
| E2E-AUD-06 | 🔒 | Phân quyền / cô lập | Staff mở `/quanly/audit-log/`; manager tenant A tìm thao tác của tenant B | Staff 403; không thấy dữ liệu tenant khác | P0 |

## 13f. Hộp thoại dùng chung (DLG)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-DLG-01 | ✅ | Không còn hộp thoại trình duyệt | Chốt ca, hoàn tiền, xoá gán topping, POS thay giỏ mang về bằng đơn khách, lỗi ở màn hình bếp | Luôn là modal của app (icon, tiêu đề, nút Huỷ / xác nhận), không có popup `127.0.0.1 says…` | P1 |
| E2E-DLG-02 | ✅ | Huỷ / Esc / bấm nền | Mở xác nhận → Huỷ; lặp lại với Esc và bấm ra ngoài | Thao tác không thực hiện | P1 |
| E2E-DLG-03 | ✅ | Chồng lên modal | Trong modal Hoàn tiền bấm **Xác nhận hoàn tiền** | Hộp thoại nằm trên modal hoàn tiền, bấm được; Huỷ thì quay lại modal hoàn tiền, trang vẫn khoá cuộn đúng | P2 |

## 13g. Định mức nguyên liệu, thành phẩm (REC)

Chuẩn bị: manager có gói cho phép `feature_recipe`, bật **Định mức nguyên liệu, thành phẩm**. Tài liệu: `docs/setup/phase4/5_recipes.md`.

| ID | Loại | Kịch bản / bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|
| E2E-REC-01 | 🔒 | Staff mở ba trang hoặc POST tạo/sửa/xoá/sắp xếp; manager có gói không cho phép dù cờ tenant còn bật | 403, không đổi dữ liệu; sidebar ẩn mục định mức khi không có quyền gói | P0 |
| E2E-REC-02 | ✅ | Tắt tất cả công tắc tính năng rồi lưu (tenant chỉ có 1 cửa hàng hoạt động); bật định mức lại | Lưu được; định mức cũ còn nguyên | P1 |
| E2E-REC-03 | ✅ | Thêm nguyên liệu g/ml, giá vốn lẻ; mở sửa rồi lưu; kéo thả sắp xếp | Giá và trạng thái giữ đúng; thứ tự vẫn đúng sau reload | P1 |
| E2E-REC-04 | ❌ | Nguyên liệu đang dùng: thử xoá hoặc đổi g thành kg | Báo lỗi, giữ nguyên nguyên liệu và định mức; vẫn sửa được giá vốn/trạng thái | P1 |
| E2E-REC-05 | ✅ | Khai báo size M: 18 g cà phê giá 350/g + 30,5 ml sữa giá 40/ml, bán giá 25.000 | Preview và sau lưu: giá vốn 7.520 đ; lãi gộp 17.480 đ; mở lại đủ hai dòng | P1 |
| E2E-REC-06 | ❌ | Gửi lượng 0/âm/0.0001/NaN, nguyên liệu trùng/khác tenant, hoặc hai danh sách POST lệch số dòng | Không thay định mức cũ; có thông báo validation, không lỗi 500 | P0 |
| E2E-REC-07 | ✅ | Bán 2 size M theo REC-05, mỗi ly thêm topping 40 g giá 50/g; thêm size L chưa có định mức | Tiêu hao 36 g cà phê + 61 ml sữa + 80 g topping; vốn 19.040 đ; cảnh báo size L thiếu định mức | P1 |
| E2E-REC-08 | ✅ | Xem đơn hoàn tiền, đơn huỷ, cửa hàng đã ngưng hoạt động; nhập ngày đảo ngược/cửa hàng không hợp lệ | Gồm đơn hoàn tiền, bỏ đơn huỷ; chọn được cửa hàng ngưng; bộ lọc sai có thông báo và giá trị thay thế rõ ràng | P1 |
| E2E-REC-09 | ✅ | Lọc *Món còn thiếu định mức*, kiểm tra cả bảng topping | Chỉ món có size thiếu định mức; bảng topping không còn topping đã có định mức | P1 |
| E2E-REC-10 | ✅ | Mở ba tab ở desktop và mobile 320/375 px; dùng Tab bàn phím; thêm nhiều dòng trong modal | Một tab active đúng trang; đủ nhãn, không tràn ngang; focus rõ; nội dung modal cuộn, nút lưu còn thấy | P1 |
| E2E-REC-11 | 🔒 | Trong Django admin, tạo định mức với nguyên liệu khác tenant hoặc lượng bằng 0 | Form báo lỗi, không lưu bản ghi sai | P0 |

## 14. Superadmin & dữ liệu mẫu (ADM)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-ADM-01 | ✅ | Tạo tenant mới | `SA` tạo Tenant slug `quan-a` | Tự tạo 1 manager `quan-a_quanly`, 2 staff, 1 store, 12 bàn có token, 2 danh mục, 4 món | P0 |
| E2E-ADM-02 | ✅ | Tenant mới dùng được ngay | Login `quan-a_quanly / 123456` | Bán được 1 đơn, mở được trang QR 1 bàn | P0 |
| E2E-ADM-03 | ✅ | Seed idempotent | Chạy `seed_initial_data` 2 lần | Không trùng dữ liệu, không lỗi | P1 |
| E2E-ADM-04 | ✅ | Phục hồi dữ liệu demo | Admin → **Phục hồi dữ liệu demo** → xác nhận | Dữ liệu demo về trạng thái chuẩn | P2 |
| E2E-ADM-05 | 🔒 | Admin path ẩn | Mở `/admin/` khi `REAL_ADMIN_PATH` khác `admin` | Không vào được trang admin | P1 |

## 15. PWA, giao diện & phi chức năng (NFR)
| ID | Loại | Kịch bản | Bước | Kết quả mong đợi | Ưu tiên |
|---|---|---|---|---|---|
| E2E-NFR-01 | ✅ | Cài app (Chrome) | DevTools → Application → Manifest / Service Worker | Manifest hợp lệ, SW active scope `/`, có nút cài | P2 |
| E2E-NFR-02 | ✅ | Trang offline | Đã mở site online → Network Offline → reload | Hiển thị `/offline/` | P2 |
| E2E-NFR-03 | 🔒 | Không cache trang đã đăng nhập | Offline → mở `/quanly/` | Trang offline, không lộ nội dung cũ | P1 |
| E2E-NFR-04 | ✅ | iOS Add to Home Screen | Safari → Share → Add to Home Screen | Đúng tên + icon | P2 |
| E2E-NFR-05 | ✅ | Responsive | POS, `/quanly/`, QR khách ở 375px, 768px, 1366px | Không vỡ layout, không cuộn ngang; menu quản lý dạng offcanvas trên mobile | P1 |
| E2E-NFR-06 | ✅ | 404 thân thiện | Mở URL không tồn tại (trang web) | Redirect trang thân thiện; URL `/api/…` sai vẫn trả JSON 404 | P2 |
| E2E-NFR-07 | ✅ | Hiệu năng POS | Store 200 món, 50 bàn | Tải POS < 3s, thêm món phản hồi < 300ms (mạng LAN) | P2 |
| E2E-NFR-08 | ✅ | Tải đồng thời | 10 khách gửi đơn QR cùng lúc vào 1 store | Không mất đơn, POS nhận đủ | P2 |

---

## 16. Kịch bản xuyên suốt (Journey)
Chạy trước mỗi release, theo thứ tự, trên dữ liệu seed sạch.

### J1 — Một ca bán hàng tại quán (P0)
1. `MGR` bật **Màn hình bếp**. Mở 3 màn hình: POS (`STF1`), `/kitchen/` (`STF2`), điện thoại khách QR Bàn 04.
2. `STF1` bán 1 đơn mang về, tiền mặt → phiếu bếp *Mang về* xuất hiện.
3. `STF1` mở Bàn 01, thêm 3 món → **Báo bếp** → bếp nhận realtime → bếp làm xong 2 món.
4. Khách Bàn 04 gọi 2 món qua QR → POS kêu chuông → `STF1` duyệt → món vào giỏ Bàn 04 + phiếu bếp *Gọi món QR*.
5. Khách Bàn 04 gọi thêm 1 đơn → `STF1` từ chối với lý do "Hết món" → khách thấy lý do.
6. Bàn 01 chuyển sang Bàn 07 → phiếu bếp đang mở đổi tên bàn.
7. Bàn 07 thanh toán Card/QR cho khách thành viên + khuyến mãi → áp mức giảm lớn hơn, khách được cộng điểm.
8. Bàn 04 thanh toán tiền mặt.
9. `MGR` mở `/orders/today/` và `/quanly/` → 4 đơn, doanh thu khớp tổng tiền đã thu.

**Đạt khi:** mọi bước đúng mong đợi, không cần reload thủ công, doanh thu khớp.

### J2 — Mở quán mới trên hệ thống (P0)
1. `SA` tạo tenant `quan-b`.
2. Manager `quan-b` đăng nhập, đổi mật khẩu, tạo danh mục + 3 món + topping, upload QR thanh toán.
3. Tạo nhân viên thứ 3 → bị chặn giới hạn gói; `SA` nâng `max_staff_users` → tạo được.
4. In PDF QR bàn, quét 1 mã bằng điện thoại, đặt thử 1 đơn → staff duyệt → thanh toán.
5. Đăng nhập tenant `demo` → không thấy bất kỳ dữ liệu nào của `quan-b` và ngược lại.

### J3 — Sự cố hạ tầng (P1)
1. Đang có đơn QR chờ → tắt Redis.
2. Khách gửi đơn mới → POS nhận trong ≤ 15s (polling).
3. Staff duyệt → khách thấy trạng thái trong ≤ 15s.
4. Bật lại Redis → realtime tức thì trở lại, không có đơn trùng / mất.

### J4 — Thay đổi cấu hình giữa ca (P1)
1. POS đang mở, giỏ có món có topping.
2. `MGR` tắt Topping, tắt QR bàn.
3. POS reload → không còn chọn topping; tab Đơn QR ẩn; link QR khách bị chặn.
4. `MGR` bật lại → mọi thứ hoạt động lại, dữ liệu cũ còn nguyên.

### J5 — Một ngày có mở / chốt ca (P0)
1. `MGR` bật **Ca làm việc**. `STF1` mở ca với 500.000.
2. Bán vài đơn tiền mặt + thẻ, bật *Tự in hoá đơn*; một bàn **In tạm tính** trước khi thanh toán.
3. `STF1` giảm món đã báo bếp; `MGR` hoàn một phần 1 đơn tiền mặt.
4. Cuối ngày `STF1` đếm két, chốt ca → báo cáo chốt ca in ra.
5. `MGR` đối chiếu: chênh lệch trên báo cáo = thực đếm − (đầu ca + thu tiền mặt − hoàn tiền mặt); doanh thu dashboard = doanh thu ca − hoàn tiền; nhật ký có đủ mở ca, huỷ món, hoàn tiền, chốt ca.

---

## 17. Mẫu ghi nhận kết quả
| ID | Ngày | Người test | Môi trường (dev / staging / prod) | Trình duyệt / thiết bị | Kết quả (PASS / FAIL / BLOCKED) | Bằng chứng | Bug ID / ghi chú |
|---|---|---|---|---|---|---|---|
| E2E-AUTH-01 | | | | | | | |

## 18. Liên kết test tự động
| Module | Test tự động hiện có |
|---|---|
| AUTH, SEC, CRUD, FEAT | `App_Accounts.tests`, `App_Tenant.tests`, `App_Quanly.tests` |
| POS, PAY, TBL, QRS, CUS | `App_Sales.tests` |
| KIT | `App_Sales.tests_kitchen` |
| PRN, SHF, RFD, AUD, FEAT-12/13/14 | `App_Sales.tests_ops` |
| REC | `App_Quanly.tests_recipes` (27 test) |
| QRC, TKW | `App_Public.tests` (`PublicQrApiTests`, `PublicTakeawayApiTests`) |
| WS | `App_Sales.tests_ws`, `App_Public.tests_ws` |

```bash
python manage.py test            # 300 test — pass ngày 27/09/2026
```
Các case có đánh dấu ⚡, NFR và Journey cần kiểm thử thủ công hoặc bằng công cụ E2E trình duyệt (đề xuất Playwright — thêm vào backlog khi cần tự động hoá).
