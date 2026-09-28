# 4) Lộ trình dự án (Roadmap)

Mốc thời gian lấy theo lịch sử commit (ngày file / model đầu tiên xuất hiện). Phase là cách nhóm theo chủ đề, không phải release riêng — một số hạng mục được làm song song.

## Tổng quan
| Phase | Chủ đề | Thời gian | Trạng thái | Thư mục |
|---|---|---|---|---|
| 1 | Nền tảng POS multi-tenant + Quản lý | 03/2026 | ✅ Hoàn thành | `phase1/` |
| 2 | Gọi món QR + Realtime WebSocket + PWA | 03/2026 – 04/2026 | ✅ Hoàn thành | `phase2/` |
| 3 | Vận hành nâng cao (khách hàng, khuyến mãi, bếp, cấu hình tính năng) | 04/2026 – 09/2026 | ✅ Hoàn thành | `phase3/` |
| 4 | Vận hành hằng ngày: in phiếu, ca làm việc, hoàn tiền, nhật ký thao tác, tồn kho | 09/2026 – | 🚧 Đang làm | `phase4/` |

## Phase 1 — Nền tảng POS multi-tenant + Quản lý
**Mục tiêu:** một tenant có thể đăng nhập, bán hàng tại POS và quản lý danh mục/đơn.

Phạm vi:
- Multi-tenant theo path, `User.role` MANAGER/STAFF, `UserStoreAccess`.
- Catalog: category, product, unit, topping, bật/tắt theo store; import Excel.
- POS: mang về + bàn, table cart, checkout cash/card, QR thanh toán.
- Quản lý: dashboard, lịch sử đơn, CRUD, phân trang.
- Seed demo + auto bootstrap tenant mới.

Tiêu chí hoàn thành:
- [x] `python manage.py test` pass cho App_Accounts, App_Tenant, App_Catalog, App_Sales, App_Quanly.
- [x] Smoke A, B, F trong `phase1/6_smoke_ui_checklist.md` pass.

Tài liệu: `phase1/0_overview.md`.

## Phase 2 — Gọi món QR + Realtime + PWA
**Mục tiêu:** khách tự gọi món tại bàn, nhân viên nhận đơn tức thì, cài app trên điện thoại.

| Mốc | Hạng mục |
|---|---|
| 13/03/2026 | `DiningTable.qr_token`, luồng QR khách (polling) |
| 03/04/2026 | WebSocket (Channels + Redis), fallback polling 15s |
| 04/04/2026 | PWA: manifest, service worker, trang offline |
| 27/09/2026 | Làm lại giao diện gọi món của khách; menu online cho đặt món mang đi, POS thu tiền đơn mang đi (`phase2/4_online_takeaway_ordering.md`) |

Tiêu chí hoàn thành:
- [x] `App_Sales.tests_ws`, `App_Public.tests_ws` pass.
- [x] Smoke C, D, E pass (kể cả khi tắt Redis → fallback polling).

Tài liệu: `phase2/0_overview.md`.

## Phase 3 — Vận hành nâng cao
**Mục tiêu:** hỗ trợ quán có bếp riêng, chương trình khách hàng thân thiết, và bán theo gói tính năng.

| Mốc | Hạng mục |
|---|---|
| 04/04/2026 | Giới hạn gói: `max_stores`, `max_dining_tables`, `max_staff_users` |
| 18/05/2026 | Khách hàng (tích điểm, hạng), khuyến mãi |
| 27/09/2026 | Màn hình bếp (`/kitchen/`), trang Cấu hình tính năng, cờ `show_store_feature`; làm lại thanh công cụ + nút màn hình bếp |

Tiêu chí hoàn thành:
- [x] `App_Sales.tests_kitchen` pass.
- [ ] Kịch bản QA màn hình bếp trong `phase1/testing/` (chưa viết).

Tài liệu: `phase3/0_overview.md`.

## Phase 4 — Vận hành cửa hàng hằng ngày
**Mục tiêu:** đủ nghiệp vụ vận hành cửa hàng hằng ngày.

| Mốc | Hạng mục |
|---|---|
| 27/09/2026 | In hoá đơn / tạm tính / phiếu bếp / báo cáo ca (`phase4/1_printing.md`) |
| 27/09/2026 | Ca làm việc + chốt ca, hoàn tiền toàn bộ / một phần (`phase4/2_shifts_and_refunds.md`) |
| 27/09/2026 | Nhật ký thao tác (`phase4/3_audit_log.md`); hộp thoại dùng chung thay `alert` / `confirm` (`phase4/4_shared_dialog.md`) |
| 27/09/2026 | Định mức nguyên liệu, thành phẩm (`phase4/5_recipes.md`) |
| 28/09/2026 | Rà soát toàn app + sửa lỗi (BL-036): thuế cấu hình theo doanh nghiệp, chặn tính năng theo gói ở server, chống đơn trùng, giới hạn đầu vào, XSS menu public, WebSocket kiểm tra Origin |

Còn lại:
- [x] In phiếu từ trình duyệt (BL-009 bước 1). · [ ] In thẳng máy in nhiệt ESC/POS (bước 2).
- [x] Ca làm việc, chốt ca, đối soát tiền mặt. · [ ] Thu/chi trong ca, báo cáo ca trên `/quanly/`.
- [x] Hoàn tiền / huỷ đơn đã thanh toán (theo số tiền). · [ ] Hoàn theo món.
- [x] Nhật ký thao tác.
- [ ] Tồn kho nguyên liệu / thành phẩm.
- [ ] CI/CD tự động (xem `6_production_env.md` mục 14).

Tiêu chí hoàn thành (phần đã làm):
- [x] `App_Sales.tests_ops` pass.
- [ ] Chạy tay case PRN / SHF / RFD / AUD trên máy in nhiệt thật.

Tài liệu: `phase4/0_overview.md`. Backlog chi tiết (Phase 4, 5, 6+): `docs/backlog/1_backlog.md` · nghiên cứu thị trường: `docs/planning/1_market_research_features.md`.

## Quy trình thêm phase mới
1. Tạo `docs/setup/phaseN/0_overview.md` (mục tiêu, phạm vi, tiêu chí hoàn thành).
2. Thêm dòng vào bảng tổng quan ở trên và vào `1_features.md`.
3. Model/route mới: cập nhật `phase1/2_architecture_and_data_model.md` và `phase1/3_routes_permissions_api.md`.
4. Cập nhật cây trong `3_file_structure.md`.
