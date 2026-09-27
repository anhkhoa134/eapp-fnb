# Phase 1 — Nền tảng POS multi-tenant + Quản lý

**Thời gian:** 03/2026 · **Trạng thái:** ✅ Hoàn thành · Roadmap: `docs/setup/4_project_roadmap.md`

## Mục tiêu
Một tenant đăng nhập được, bán hàng tại POS (mang về + tại bàn) và quản lý danh mục, nhân viên, đơn hàng.

## Phạm vi
- Multi-tenant theo path (`Tenant.public_slug`), vai trò `MANAGER` / `STAFF`, quyền theo store.
- Catalog: category, product, unit, topping, bật/tắt theo store; import Excel.
- POS: mang về, table cart lưu server, chuyển bàn, checkout cash/card, QR thanh toán.
- Quản lý `/quanly/`: dashboard, lịch sử đơn, CRUD, phân trang 20 dòng/trang.
- Seed demo (`seed_initial_data`) và auto bootstrap khi superadmin tạo tenant.

## Tài liệu trong phase
| File | Nội dung |
|---|---|
| `1_setup_and_run.md` | Cài môi trường local, env, migrate, chạy server |
| `2_architecture_and_data_model.md` | Kiến trúc multi-tenant, model, lifecycle QR *(tham chiếu chung — cập nhật tiếp ở phase sau)* |
| `3_routes_permissions_api.md` | Web route, POS/Public API, WebSocket, phân trang *(tham chiếu chung)* |
| `4_seed_demo_data.md` | Lệnh seed, dữ liệu được tạo, tài khoản demo |
| `5_testing_and_smoke.md` | Lệnh test tự động + smoke thủ công |
| `6_smoke_ui_checklist.md` | Checklist smoke UI rút gọn + mẫu ghi kết quả |
| `testing/trang_ban_hang.md` | Kịch bản QA chi tiết trang POS |
| `testing/trang_quan_ly.md` | Kịch bản QA chi tiết trang Quản lý |

## Tiêu chí hoàn thành
- [x] `python manage.py test` pass.
- [x] Smoke A, B, F trong `6_smoke_ui_checklist.md` pass.
