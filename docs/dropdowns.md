# Dropdown dùng chung

Dùng lại `static/css/dropdowns.css` và `static/js/dropdowns.js` từ eApp POS.
`static/css/dropdowns-fnb.css` nối màu dropdown với theme FnB (`--primary-color`,
`--primary-hover`) và catalog (`--od-primary`), đồng thời ẩn popup khi in.

Include `App_Core/_dropdown_assets.html` được nạp ở base quản lý, POS,
base đặt món công khai và base in. Select và input có datalist tự khởi tạo,
bao gồm control thêm qua AJAX. Không thay đổi name/value, validation, reset,
hoặc các sự kiện input/change dùng để gửi form và cập nhật nghiệp vụ.

- Select có từ 8 lựa chọn tự thêm ô tìm kiếm không dấu.
- `data-dropdown-search="true|false"` bật/tắt tìm kiếm trên select.
- `data-swatch="<màu CSS>"` trên `<option>` hiện chấm màu trước nhãn trong popup
  (VD chọn màu giao diện POS). Giá trị không phải màu CSS hợp lệ thì bỏ qua.
- Datalist đơn vị nguyên liệu vẫn cho nhập đơn vị tự do.
- Tìm khách qua API giữ logic tìm/chọn riêng, dùng chung lớp
  `eapp-dropdown-menu`, `eapp-dropdown-suggestions`, `eapp-dropdown-option`.
- Menu khuyến mãi vẫn dùng Bootstrap và logic tính tiền hiện có.
- `data-dropdown-native` bỏ qua widget do thư viện khác quản lý.
- Select multiple/size > 1 giữ hành vi listbox.
- `EAPPDropdowns.init(root)` khởi tạo chủ động; `EAPPDropdowns.close()` đóng menu.

Kiểm thử: `python3 scripts/tests/dropdowns_browser.py` (Python Playwright và
Chromium; có thể đặt `CHROMIUM_EXECUTABLE`). Test không cần server/database.
Các tình huống FnB cần kiểm tra: tạo/sửa nguyên liệu, sửa sản phẩm, lọc lịch sử
đơn, đổi theme/cửa hàng, chuyển bàn, tìm/chọn khách và khuyến mãi, chọn cửa hàng
ở catalog, chọn khổ giấy in.
