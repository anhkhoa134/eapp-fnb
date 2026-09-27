# 5) Định mức nguyên liệu, thành phẩm

Backlog: BL-018 (phần định mức + giá vốn; chưa có tồn kho).

## Bật tính năng
- Cờ `Tenant.show_recipe_feature` — mặc định **tắt**. Manager bật tại `/quanly/settings/features/` (mục *Định mức nguyên liệu, thành phẩm*).
- Gắn với gói cước: `SubscriptionPlan.feature_recipe`. Gói *Miễn phí*, *Cơ bản* không có; *Chuyên nghiệp*, *Doanh nghiệp* có. Gói không có thì công tắc bị khoá (*Cần nâng cấp gói*).
- Quyền thực tế dùng `Tenant.recipe_feature_enabled`: phải bật cờ tenant **và** được gói cho phép. Kiểm tra cả sidebar, trang xem, lưu/xoá và sắp xếp; cờ tenant còn bật sau khi thay đổi quyền gói không mở được tính năng.
- Muốn đổi quyền của gói đã tồn tại: sửa `feature_recipe` trong Django admin. Không sửa migration đã chạy để thay đổi dữ liệu hiện tại.
- Khi tắt: các trang `/quanly/ingredients/…`, `/quanly/recipes/…` trả 403; ẩn mục *Định mức NVL* ở sidebar. Dữ liệu nguyên liệu, định mức được giữ nguyên.
- Bỏ chọn mọi công tắc rồi lưu vẫn hoạt động, kể cả POST rỗng. Quy tắc không được tắt nhiều chi nhánh khi còn nhiều cửa hàng hoạt động vẫn áp dụng.
- Chỉ manager dùng được. Tính năng **không** ảnh hưởng tới POS / checkout.

## Model (`App_Catalog`)
- `Ingredient(tenant, name, unit, cost_per_unit, is_active, display_order)` — tên duy nhất trong tenant (`uq_ingredient_tenant_name`, form so khớp không phân biệt hoa thường). `cost_per_unit` là giá vốn cho **1 đơn vị tính** (VD: cà phê 350.000 đ/kg, đơn vị `g` → 350).
- Trang quản lý không cho đổi đơn vị của nguyên liệu đang có trong định mức, tránh diễn giải `18 g` thành `18 kg`. Muốn đổi: tạo nguyên liệu với đơn vị mới rồi cập nhật lượng trong từng định mức. Vẫn sửa được giá vốn, tên và trạng thái.
- `RecipeItem(product_unit | topping, ingredient, quantity)` — lượng nguyên liệu cho 1 thành phẩm. Đúng 1 trong `product_unit` / `topping` (`ck_recipe_item_single_target`); mỗi nguyên liệu xuất hiện 1 lần / thành phẩm. `ingredient` là `PROTECT`: nguyên liệu đang dùng trong định mức không xoá được (chỉ tắt *Đang hoạt động*).
- Model validation (bao gồm form Django admin) chặn lượng ≤ 0 và nguyên liệu khác tenant của thành phẩm. `save_recipe()` kiểm tra tenant của cả thành phẩm và nguyên liệu, kiểm tra lượng trước khi thay định mức, dùng transaction và khoá bản ghi thành phẩm khi lưu.
- Migration: `App_Catalog/0011_recipe_feature`, `App_Tenant/0017_recipe_feature`.

## Trang quản lý
| URL | Nội dung |
|---|---|
| `/quanly/ingredients/` | CRUD nguyên liệu (tìm theo tên, kéo thả sắp xếp qua `reorder/ingredients/`), số thành phẩm đang dùng |
| `/quanly/recipes/` | Mỗi món → từng đơn vị bán: định mức, **giá vốn**, giá bán, **lãi gộp** (đ và %). Lọc món theo tên, danh mục, *Món còn thiếu định mức*. Có bảng topping khi bật `show_topping_feature`; bộ lọc thiếu định mức cũng loại topping đã có định mức |
| `POST /quanly/recipes/<unit|topping>/<id>/` | Lưu các trường lặp tên `ingredient_id` và `quantity` (đọc bằng `getlist`; nhận `0,5` hoặc `0.5`). Lượng từ `0.001` đến `999999999.999`, tối đa 3 số lẻ, không âm thầm làm tròn. Hai danh sách phải có cùng số dòng. Thay toàn bộ định mức cũ; gửi toàn dòng trống hoặc bỏ hết dòng = xoá định mức. Dữ liệu lỗi giữ nguyên định mức cũ. Ghi nhật ký thao tác |
| `/quanly/ingredients/usage/` | Tiêu hao nguyên liệu lý thuyết theo cửa hàng + khoảng ngày (mặc định 7 ngày gần nhất), tổng giá vốn, danh sách thành phẩm đã bán nhưng chưa có định mức. Chọn được cửa hàng ngưng hoạt động để xem lịch sử. Ngày sai/đảo ngược về 7 ngày gần nhất; cửa hàng sai/khác tenant về tất cả cửa hàng của tenant, có thông báo |

Ba trang dùng chung thanh pill: tab hiện tại có nền màu chủ đề, `aria-current="page"`, viền focus bàn phím. Màn hình nhỏ xếp icon trên nhãn, giữ đủ ba tab. Ô ngày xếp dọc trên điện thoại; bảng tiêu hao cuộn ngang trong khung khi thiếu chỗ. Modal định mức cuộn phần nội dung khi nhiều dòng và giữ nút lưu có nhãn trong khung nhìn; trình duyệt kiểm tra dòng thiếu lượng/nguyên liệu, lượng ngoài giới hạn và nguyên liệu trùng trước khi gửi.

## Cách tính (`App_Catalog/recipes.py`)
- **Giá vốn thành phẩm** = Σ (định mức × `cost_per_unit`). Lãi gộp tính trên `ProductUnit.price` (giá gốc), chưa trừ khuyến mãi / giá riêng theo cửa hàng.
- **Tiêu hao** = Σ số lượng `OrderItem` đã bán × định mức của `unit`; topping: Σ số lượng món chứa topping (`OrderItemTopping`) × định mức topping. Tính đơn `completed` và `refunded` (món đã làm), bỏ đơn `cancelled`.
- Dùng định mức **hiện tại** (không chụp lại lúc bán): đổi định mức / giá vốn sẽ đổi kết quả của cả các ngày trước.
- Nguyên liệu ngưng hoạt động vẫn được tính nếu còn trong định mức; trạng thái chỉ ẩn khỏi lựa chọn thêm mới. Khoảng ngày tính theo `Order.created_at` trong múi giờ ứng dụng, gồm trọn ngày đầu và ngày cuối.

## Kiểm chứng sau rà soát (27/09/2026)

- `python3 manage.py test App_Quanly.tests_recipes --noinput`: **27 test pass** (bổ sung 11 test và mở rộng các case dữ liệu lỗi/phân quyền).
- `python3 manage.py test --noinput`: **300 test pass**.
- `python3 manage.py makemigrations --check --dry-run`: không có thay đổi schema; bản sửa này không cần migration mới.
- Chromium headless trên máy chủ và database tạm riêng: đăng nhập, tạo nguyên liệu giá lẻ, thêm/xoá dòng định mức, preview giá vốn, lưu/mở lại, chặn nguyên liệu trùng, tiêu hao kèm topping và cảnh báo thiếu định mức đều pass. Không có lỗi JavaScript trong các luồng này.
- Đã chụp và kiểm tra giao diện ở 320, 375, 768 và 1440 px; ba pill đủ nhãn, trang không tràn ngang, modal nhiều dòng cuộn được và footer còn trong khung nhìn. Đây là kiểm thử trên dữ liệu thử riêng, chưa xác nhận dữ liệu tài khoản tại cổng 8000 hay hành vi trên điện thoại thật.
- Checklist giao diện và nghiệp vụ: nhóm `REC` trong `docs/testing/1_e2e_test_cases.md`.

## Còn lại (BL-018)
- Tồn kho theo cửa hàng: nhập kho, kiểm kho, trừ kho khi checkout, hoàn kho khi huỷ; cảnh báo dưới mức tối thiểu.
- Chụp giá vốn vào `OrderItem` lúc bán để báo cáo lãi gộp theo thời gian không đổi khi sửa định mức.
- Bán thành phẩm (nguyên liệu tự chế như cốt cà phê, syrup) làm nguyên liệu của món khác.
