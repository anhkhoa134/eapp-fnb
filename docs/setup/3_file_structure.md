# 3) Cấu trúc thư mục dự án

Bỏ qua: `__pycache__/`, `migrations/` (chỉ ghi khi cần), file build/cache trong `.gitignore`.

## Cây thư mục toàn dự án
```
eapp-fnb/
├── manage.py
├── requirements.txt
├── db.sqlite3                          # DB dev (SQLite), không dùng cho prod
│
├── Project/                            # Cấu hình Django
│   ├── settings.py                     # Đọc env từ Project/.env, DB, Channels, security, logging
│   ├── urls.py                         # Root URLconf (PWA, admin, accounts, api, quanly, POS, public)
│   ├── asgi.py                         # ASGI app (HTTP + WebSocket)
│   ├── routing.py                      # Gộp WebSocket routes
│   ├── wsgi.py                         # WSGI app (Gunicorn)
│   └── .env                            # Biến môi trường (không commit)
│
├── App_Core/                           # Tiện ích dùng chung
│   ├── views.py                        # PWA manifest / sw.js / offline, 404 redirect
│   ├── middleware.py                   # NotFoundRedirectMiddleware
│   ├── context_processors.py
│   ├── admin_views.py                  # Phục hồi dữ liệu demo từ admin
│   ├── seed_initial_data_runner.py     # Logic seed demo
│   ├── tenant_media_paths.py           # Đường dẫn media theo tenant
│   ├── templatetags/number_format.py
│   └── management/commands/seed_initial_data.py
│
├── App_Accounts/                       # Custom User, login/logout, đổi mật khẩu
│   ├── models.py                       # User (role MANAGER / STAFF)
│   ├── permissions.py                  # Decorator phân quyền
│   ├── forms.py · views.py · urls.py
│   └── tests.py
│
├── App_Tenant/                         # Tenant, Store, UserStoreAccess, cờ tính năng, giới hạn gói
│   ├── models.py
│   ├── services.py                     # Store truy cập được + bootstrap tenant mới (provision_tenant_default_setup)
│   ├── admin.py
│   └── tests.py
│
├── App_Catalog/                        # Category, Product, ProductUnit, Topping, mapping theo store
│   ├── models.py · services.py
│   ├── product_image_utils.py
│   └── tests.py
│
├── App_Sales/                          # POS, giỏ bàn, checkout, QR staff, bếp, khách hàng, khuyến mãi
│   ├── models.py                       # Order, DiningTable, QROrder, TableCartItem, KitchenTicket, Customer, Promotion…
│   ├── views.py · urls.py              # /, /orders/today/, /kitchen/
│   ├── api_urls.py                     # /api/pos/…
│   ├── services.py                     # Giá theo store, hạng khách hàng, khuyến mãi, tính tổng đơn
│   ├── kitchen.py                      # Nghiệp vụ phiếu bếp
│   ├── realtime.py                     # Push event qua channel layer
│   ├── consumers.py · ws_urls.py       # WebSocket POS theo store
│   └── tests.py · tests_kitchen.py · tests_ws.py
│
├── App_Quanly/                         # Trang quản lý /quanly/
│   ├── views.py · urls.py · forms.py   # Dashboard, CRUD, QR bàn, cấu hình tính năng
│   ├── catalog_excel.py                # Import Excel danh mục / sản phẩm
│   └── tests.py
│
├── App_Public/                         # Catalog public + gọi món QR của khách
│   ├── views.py · urls.py              # /<public_slug>/, /<public_slug>/qr/
│   ├── api_urls.py                     # /api/public/…
│   ├── consumers.py · ws_urls.py       # WebSocket trạng thái đơn QR
│   └── tests.py · tests_ws.py
│
├── templates/
│   ├── offline.html                    # Trang PWA offline
│   ├── App_Core/                       # base.html, _pwa_head.html, _pwa_register.html
│   ├── App_Accounts/                   # login.html, password_change.html
│   ├── App_Sales/                      # index.html (POS), orders_today.html, kitchen.html
│   ├── App_Quanly/                     # _layout, _sidebar_nav, _list_pagination, dashboard, CRUD…
│   ├── App_Public/                     # catalog.html, qr_ordering.html
│   └── admin/app_core/                 # Template xác nhận phục hồi demo
│
├── static/
│   ├── images/logo/
│   ├── pwa/icons/ · pwa/screenshots/
│   ├── sounds/co-don-moi.mp3           # Âm báo đơn QR mới
│   ├── css/ · js/
│
├── media/tenant_<id>/                  # File upload theo tenant (ảnh sản phẩm, QR thanh toán)
├── logs/recent-errors.log
├── backup/                             # Tài liệu / cấu hình cũ (tham khảo, không dùng runtime)
├── scripts/
│   ├── run/                            # 1_reset_project.py, 2_git_clean_cached.py, print_secret_key.py
│   ├── pipeline.txt
│   └── run.txt
│
└── docs/                               # Xem cây chi tiết bên dưới
    ├── setup/                          # Tổng quan + tài liệu theo phase
    ├── planning/                       # Nghiên cứu thị trường, định hướng
    ├── backlog/                        # Backlog + checklist tính năng
    └── testing/                        # Test case E2E
```

## Cây thư mục tài liệu (`docs/`)
```
docs/
├── planning/
│   └── 1_market_research_features.md   # So sánh đối thủ, xu hướng 2026, đề xuất ưu tiên
├── backlog/
│   └── 1_backlog.md                    # Backlog BL-xxx: ưu tiên, size, checklist nghiệm thu
├── testing/
│   └── 1_e2e_test_cases.md             # Test case E2E theo module + journey
└── setup/
    ├── 1_features.md                       # Danh sách tính năng + trạng thái + cờ tenant
    ├── 2_tech_stack.md                     # Công nghệ & phiên bản
    ├── 3_file_structure.md                 # Cây cấu trúc dự án (file này)
    ├── 4_project_roadmap.md                # Phân chia Phase 1, 2, 3, 4
    ├── 5_security_policy.md                # Tiêu chuẩn bảo mật
    ├── 6_production_env.md                 # Môi trường Production, deploy, CI/CD
    │
    ├── phase1/                             # Nền tảng POS multi-tenant + Quản lý
    │   ├── 0_overview.md
    │   ├── 1_setup_and_run.md
    │   ├── 2_architecture_and_data_model.md
    │   ├── 3_routes_permissions_api.md
    │   ├── 4_seed_demo_data.md
    │   ├── 5_testing_and_smoke.md
    │   ├── 6_smoke_ui_checklist.md
    │   └── testing/
    │       ├── trang_ban_hang.md           # Kịch bản QA trang POS
    │       └── trang_quan_ly.md            # Kịch bản QA trang Quản lý
    │
    ├── phase2/                             # Gọi món QR + Realtime + PWA
    │   ├── 0_overview.md
    │   ├── 1_qr_public_and_qr_admin.md
    │   ├── 2_websocket_realtime.md
    │   └── 3_pwa.md
    │
    ├── phase3/                             # Vận hành nâng cao
    │   ├── 0_overview.md                   # Khách hàng, khuyến mãi, tổng quan phase
    │   ├── 1_kitchen_display.md
    │   └── 2_feature_settings_and_plan_limits.md
    │
    └── phase4/                             # Kế hoạch (chưa làm)
        └── 0_overview.md
```

Quy ước:
- File trong `docs/setup/` và mỗi `phaseN/` đánh số theo thứ tự đọc; `0_overview.md` là điểm vào của mỗi phase.
- Tài liệu tham chiếu dùng chung (data model, route/API) nằm ở `phase1/` và được **cập nhật tiếp** khi phase sau thêm model/route.
- Phase mới: tạo `phaseN/0_overview.md`, thêm dòng vào `4_project_roadmap.md` và `1_features.md`.
