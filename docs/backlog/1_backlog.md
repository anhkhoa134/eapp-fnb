# 1) Backlog & checklist tính năng

**Cập nhật:** 27/09/2026 · Nguồn: rà soát code hiện tại + `docs/planning/1_market_research_features.md`.

## Quy ước
- **Ưu tiên:** `P0` chặn release / rủi ro bảo mật · `P1` nên làm ngay phase kế · `P2` có giá trị, lên lịch sau · `P3` ý tưởng dài hạn.
- **Size:** `S` ≤ 2 ngày · `M` ≤ 1 tuần · `L` ≤ 3 tuần · `XL` > 3 tuần.
- **Trạng thái:** `[ ]` chưa làm · `[~]` đang làm · `[x]` xong.
- Mỗi hạng mục có **tiêu chí nghiệm thu** dạng checklist. Khi xong: đánh `[x]`, cập nhật `docs/setup/1_features.md` và tài liệu phase tương ứng.

## Tổng quan
| ID | Hạng mục | Nhóm | Ưu tiên | Size | Phase | Trạng thái |
|---|---|---|---|---|---|---|
| BL-001 | Chặn tenant ngừng hoạt động / hết hạn gói | Bảo mật / SaaS | P0 | S | 4 | [ ] |
| BL-002 | Chống brute-force đăng nhập | Bảo mật | P0 | S | 4 | [ ] |
| BL-003 | Rate limit API public QR | Bảo mật | P1 | S | 4 | [ ] |
| BL-004 | Bắt buộc đổi mật khẩu lần đầu | Bảo mật | P1 | S | 4 | [ ] |
| BL-005 | Nâng cấp Django 5.0 → 5.2 LTS | Nợ kỹ thuật | P1 | M | 4 | [ ] |
| BL-006 | CI pipeline (check + test) | DevOps | P1 | S | 4 | [ ] |
| BL-007 | Content-Security-Policy | Bảo mật | P2 | S | 4 | [ ] |
| BL-008 | Pin dependency trong `requirements.txt` | Nợ kỹ thuật | P1 | S | — | [x] |
| BL-009 | In hoá đơn + in phiếu bếp | Bán hàng | P1 | M | 4 | [ ] |
| BL-010 | VietQR động + tự xác nhận chuyển khoản | Thanh toán | P1 | L | 4 | [ ] |
| BL-011 | Ca làm việc, chốt ca, két tiền | Vận hành | P1 | L | 4 | [ ] |
| BL-012 | Huỷ / hoàn tiền đơn đã thanh toán | Vận hành | P1 | M | 4 | [ ] |
| BL-013 | Nhật ký thao tác (audit log) | Vận hành / Bảo mật | P1 | M | 4 | [ ] |
| BL-014 | Hoá đơn điện tử từ máy tính tiền | Pháp lý | P1 | XL | 5 | [ ] |
| BL-015 | Tách / gộp hoá đơn, gộp bàn | Bán hàng | P2 | L | 5 | [ ] |
| BL-016 | Phí dịch vụ / phụ thu | Bán hàng | P2 | S | 5 | [ ] |
| BL-017 | Hết món nhanh từ POS | Bán hàng | P2 | S | 4 | [ ] |
| BL-018 | Kho nguyên liệu + định lượng | Kho | P1 | XL | 4 | [ ] |
| BL-019 | Báo cáo theo món / giờ / nhân viên + xuất Excel | Báo cáo | P2 | M | 5 | [ ] |
| BL-020 | Đổi điểm + voucher mã code | Khách hàng | P2 | M | 5 | [ ] |
| BL-021 | Phân quyền chi tiết (thu ngân, phục vụ, bếp) | Nền tảng | P2 | M | 5 | [ ] |
| BL-022 | Bếp: định tuyến theo trạm + cảnh báo món chậm | Bếp | P2 | M | 5 | [ ] |
| BL-023 | Trang QR: gọi phục vụ, yêu cầu thanh toán, tra điểm | QR | P2 | M | 5 | [ ] |
| BL-024 | Web order mang về / giao hàng | Kênh online | P2 | L | 5 | [ ] |
| BL-025 | Combo / set menu, menu theo khung giờ | Catalog | P2 | M | 5 | [ ] |
| BL-026 | Đặt bàn trước | Bán hàng | P3 | M | 6 | [ ] |
| BL-027 | Bán offline (PWA) + đồng bộ | Nền tảng | P3 | XL | 6 | [ ] |
| BL-028 | Đồng bộ GrabFood / ShopeeFood | Kênh online | P3 | XL | 6 | [ ] |
| BL-029 | Zalo ZNS / SMS: hoá đơn, sinh nhật, khuyến mãi | Marketing | P3 | M | 6 | [ ] |
| BL-030 | Tự đăng ký dùng thử + thanh toán gói | SaaS | P3 | L | 6 | [ ] |
| BL-031 | Trợ lý AI báo cáo + dự báo nhập hàng | AI | P3 | L | 6 | [ ] |
| BL-032 | Kiosk tự gọi món | Kênh | P3 | M | 6 | [ ] |
| BL-033 | Kịch bản QA cho bếp, khách hàng, khuyến mãi | QA | P2 | S | — | [~] |

---

## A. Bảo mật & nợ kỹ thuật (hiện tại)

### BL-001 · Chặn tenant ngừng hoạt động / hết hạn gói — P0
**Hiện trạng:** `Tenant.is_active` chỉ được kiểm tra ở trang public / WebSocket public. POS, `/quanly/`, POS API **không** kiểm tra `is_active` hay `subscription_ends_on`.
- [ ] Middleware hoặc decorator chặn user thuộc tenant `is_active=False` (logout + thông báo).
- [ ] Hết hạn gói: chặn POS/API ghi dữ liệu, cho phép xem `/quanly/account/` để gia hạn.
- [ ] WebSocket POS từ chối kết nối khi tenant bị chặn.
- [ ] Cảnh báo trước 7 ngày trên `/quanly/` khi gói sắp hết hạn.
- [ ] Test cho cả 3 trường hợp: tenant tắt, hết hạn, sắp hết hạn.

### BL-002 · Chống brute-force đăng nhập — P0
- [ ] Khoá tạm theo username + IP sau N lần sai (ví dụ `django-axes`) hoặc `limit_req` Nginx cho `/accounts/login/`.
- [ ] Thông báo lỗi không tiết lộ username có tồn tại hay không.
- [ ] Superadmin mở khoá được trong admin.

### BL-003 · Rate limit API public QR — P1
- [ ] Giới hạn tần suất `POST/PATCH /api/public/qr/orders/` theo IP + bàn.
- [ ] Giới hạn số đơn `PENDING` đồng thời trên một bàn.
- [ ] Trả `429` kèm thông báo tiếng Việt, trang QR hiển thị thân thiện.

### BL-004 · Bắt buộc đổi mật khẩu lần đầu — P1
- [ ] Cờ `must_change_password` cho tài khoản bootstrap / seed / reset bởi quản lý.
- [ ] Sau login, chuyển thẳng đến trang đổi mật khẩu cho đến khi đổi xong.

### BL-005 · Nâng cấp Django 5.2 LTS — P1
Django 5.0 đã hết hỗ trợ bảo mật.
- [ ] Nâng `Django`, kiểm tra tương thích `channels`, `daphne`, `django-jazzmin`.
- [ ] `python manage.py check --deploy`, full test pass.
- [ ] Cập nhật `requirements.txt` và `docs/setup/2_tech_stack.md`.

### BL-006 · CI pipeline — P1
- [ ] Workflow chạy `check`, `makemigrations --check --dry-run`, `test` (kèm Redis service) trên mỗi PR.
- [ ] Badge / trạng thái bắt buộc pass trước khi merge `main`.
- Tham chiếu: `docs/setup/6_production_env.md` mục 13.

### BL-007 · Content-Security-Policy — P2
- [ ] Header CSP whitelist `cdn.jsdelivr.net`, `cdnjs.cloudflare.com`; hoặc tự host static.
- [ ] Kiểm tra POS, bếp, trang QR, dashboard ECharts không vỡ.

### BL-008 · Pin dependency — ✅ xong 27/09/2026
- [x] `requirements.txt` khai báo đủ gói đang dùng với phiên bản cố định.

### BL-033 · Kịch bản QA còn thiếu — P2
- [x] Bộ test case E2E tổng hợp: `docs/testing/1_e2e_test_cases.md`.
- [ ] Kịch bản QA chi tiết từng click cho `/kitchen/`, khách hàng, khuyến mãi, cấu hình tính năng (theo format `docs/setup/phase1/testing/`).

---

## B. Phase 4 — Vận hành cửa hàng hằng ngày

### BL-009 · In hoá đơn + in phiếu bếp — P1
- [ ] Mẫu hoá đơn khổ 58mm / 80mm (tên quán, store, bàn, món, topping, giảm giá, thuế, tổng, phương thức thanh toán, QR thanh toán).
- [ ] In từ trình duyệt (`window.print` + CSS print) — bước 1.
- [ ] In phiếu bếp khi báo bếp (tuỳ chọn thay/kèm màn hình bếp).
- [ ] In lại hoá đơn từ lịch sử đơn.
- [ ] (Bước 2) In trực tiếp máy in nhiệt LAN/USB (ESC/POS) qua app cầu nối.

### BL-010 · VietQR động + tự xác nhận chuyển khoản — P1
- [ ] Sinh VietQR theo chuẩn NAPAS với số tiền + nội dung chứa mã đơn; cấu hình ngân hàng/STK theo store.
- [ ] Nhận webhook từ cổng trung gian (payOS / SePay / Casso…) → khớp đơn → tự đánh dấu đã thanh toán.
- [ ] Push realtime cho POS khi nhận tiền (âm báo + toast).
- [ ] Xử lý lệch số tiền / trùng giao dịch; log webhook; xác thực chữ ký webhook.

### BL-011 · Ca làm việc, chốt ca, két tiền — P1
- [ ] Mở ca: tiền đầu ca; mọi `Order` gắn với ca đang mở.
- [ ] Thu/chi ngoài bán hàng trong ca.
- [ ] Chốt ca: tiền mặt kỳ vọng vs thực tế, chênh lệch, người bàn giao.
- [ ] Báo cáo ca trên `/quanly/`.

### BL-012 · Huỷ / hoàn tiền đơn đã thanh toán — P1
- [ ] Huỷ toàn bộ hoặc một phần món, bắt buộc lý do.
- [ ] Chỉ manager (hoặc quyền được cấp) duyệt.
- [ ] Trừ lại điểm / `total_spent` khách hàng, cập nhật hạng.
- [ ] Dashboard và báo cáo trừ doanh thu hoàn.

### BL-013 · Nhật ký thao tác — P1
- [ ] Ghi log: xoá đơn, huỷ món đã báo bếp, giảm giá, hoàn tiền, đổi giá, reset token QR, đổi cấu hình tính năng.
- [ ] Trang tra cứu log theo ngày / nhân viên / loại thao tác cho manager.

### BL-017 · Hết món nhanh từ POS — P2
- [ ] Nhân viên bật/tắt `StoreProduct.is_available` ngay trên thẻ món ở POS.
- [ ] Trang QR khách cập nhật realtime (ẩn / mờ món hết).

### BL-018 · Kho nguyên liệu + định lượng — P1
- [ ] Model nguyên liệu, đơn vị, tồn kho theo store.
- [ ] Định lượng theo `ProductUnit` (+ topping).
- [ ] Trừ kho khi checkout; hoàn kho khi huỷ/hoàn.
- [ ] Nhập kho, kiểm kho, điều chỉnh; cảnh báo dưới mức tối thiểu.
- [ ] Báo cáo giá vốn / lãi gộp theo món.

---

## C. Phase 5 — Mở rộng nghiệp vụ & pháp lý

### BL-014 · Hoá đơn điện tử từ máy tính tiền — P1 (pháp lý)
Theo NĐ 70/2025/NĐ-CP — bắt buộc với nhà hàng / hộ kinh doanh doanh thu ≥ 1 tỷ/năm.
- [ ] Chọn nhà cung cấp HĐĐT có API (MISA meInvoice, Viettel, VNPT, BKAV…).
- [ ] Cấu hình theo tenant: MST, ký hiệu hoá đơn, thông tin kết nối (mã hoá khi lưu).
- [ ] Tự phát hành khi checkout (tuỳ chọn), lưu mã tra cứu + mã CQT trên `Order`.
- [ ] In mã tra cứu / QR tra cứu trên hoá đơn.
- [ ] Hàng đợi gửi lại khi lỗi mạng; điều chỉnh/huỷ hoá đơn khi hoàn tiền.
- [ ] Bật/tắt bằng cờ tenant `show_einvoice_feature`.

### BL-015 · Tách / gộp hoá đơn, gộp bàn — P2
- [ ] Gộp giỏ nhiều bàn vào một bàn (giữ phiếu bếp).
- [ ] Tách hoá đơn theo món hoặc chia đều N phần; mỗi phần một `Order`.
- [ ] Thanh toán nhiều phương thức cho một đơn.

### BL-016 · Phí dịch vụ / phụ thu — P2
- [ ] Cấu hình % hoặc số tiền theo store; tuỳ chọn áp dụng cho tại bàn / mang về.
- [ ] Lưu snapshot trên `Order`, hiển thị trên hoá đơn và báo cáo.

### BL-019 · Báo cáo nâng cao + xuất Excel — P2
- [ ] Doanh thu theo món / danh mục, giờ cao điểm (heatmap), nhân viên, kênh bán, khuyến mãi.
- [ ] Xuất Excel / PDF theo bộ lọc.

### BL-020 · Đổi điểm + voucher mã code — P2
- [ ] Quy đổi điểm thành tiền giảm khi checkout (tỷ lệ cấu hình được).
- [ ] Voucher mã code: số lần dùng, hạn, giới hạn mỗi khách.
- [ ] Làm rõ quy tắc cộng dồn với ưu đãi hạng / khuyến mãi hiện tại.

### BL-021 · Phân quyền chi tiết — P2
- [ ] Vai trò: thu ngân, phục vụ, bếp (hoặc quyền theo checkbox).
- [ ] Quyền nhạy cảm tách riêng: giảm giá tay, huỷ món đã báo bếp, hoàn tiền, xem báo cáo.

### BL-022 · Bếp nâng cao — P2
- [ ] Gán danh mục → trạm (bếp / bar); màn hình bếp lọc theo trạm.
- [ ] Đổi màu / cảnh báo phiếu chờ quá X phút; báo cáo thời gian chế biến trung bình.

### BL-023 · Trang QR mở rộng — P2
- [ ] Nút **Gọi phục vụ** và **Yêu cầu thanh toán** → thông báo realtime lên POS.
- [ ] Khách nhập SĐT để tích điểm / tra điểm.
- [ ] Thanh toán tại bàn bằng VietQR động (phụ thuộc BL-010).

### BL-024 · Web order mang về / giao hàng — P2
- [ ] Từ catalog public: giỏ hàng, SĐT, giờ nhận, ghi chú.
- [ ] Đơn vào POS như đơn QR (duyệt / từ chối), realtime.

### BL-025 · Combo, menu theo khung giờ — P2
- [ ] Combo gồm nhiều món/unit với giá combo; trừ kho theo thành phần.
- [ ] Giờ bán cho món / danh mục; khuyến mãi happy hour.

---

## D. Phase 6+ — Tương lai

### BL-026 · Đặt bàn trước — P3
- [ ] Đặt bàn theo giờ, số khách, SĐT; giữ bàn trên sơ đồ; nhắc trước giờ.

### BL-027 · Bán offline — P3
- [ ] POS bán được khi mất mạng (IndexedDB), đồng bộ khi có mạng, xử lý xung đột.

### BL-028 · Đồng bộ GrabFood / ShopeeFood — P3
- [ ] Tìm hiểu điều kiện đối tác API; đồng bộ đơn, menu, trạng thái hết món.

### BL-029 · Zalo ZNS / SMS — P3
- [ ] Gửi hoá đơn, điểm tích luỹ, ưu đãi sinh nhật, khuyến mãi (cần Zalo OA + template duyệt).

### BL-030 · Tự đăng ký + thanh toán gói — P3
- [ ] Đăng ký dùng thử, tự bootstrap tenant, thanh toán gia hạn online (liên quan BL-001).

### BL-031 · Trợ lý AI — P3
- [ ] Hỏi đáp doanh thu / món bán chạy bằng ngôn ngữ tự nhiên trên `/quanly/`.
- [ ] Dự báo doanh thu / gợi ý nhập hàng (sau BL-018).

### BL-032 · Kiosk tự gọi món — P3
- [ ] Chế độ kiosk tái dùng trang QR, thanh toán VietQR, in số thứ tự.
