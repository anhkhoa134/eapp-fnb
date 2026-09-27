# 4) Hộp thoại dùng chung (`eappDialog`)

Không dùng `window.alert` / `window.confirm` / `window.prompt` của trình duyệt. Mọi thông báo và xác nhận dùng modal chung `static/js/eapp_dialog.js` (Bootstrap 5).

## Đã nạp sẵn
- `templates/App_Core/base.html` (mọi trang kế thừa: Quản lý, Ca làm việc, Đơn trong ngày, Màn hình bếp…).
- `templates/App_Sales/index.html` (POS), sau `bootstrap.bundle`.
- Trang mới không kế thừa `base.html`: nạp `bootstrap.bundle` rồi `{% static 'js/eapp_dialog.js' %}`.

## Cách dùng
Khai báo trên `<form>` hoặc nút submit, không cần viết JS:
```html
<form method="post" action="..."
      data-confirm="Sau khi chốt, số liệu ca sẽ được khoá lại."
      data-confirm-title="Chốt ca #12?"
      data-confirm-ok="Chốt ca"
      data-confirm-variant="danger">
```
Gọi từ JS (trả Promise):
```js
const ok = await eappDialog.confirm({ title, message, okText, cancelText, variant });
await eappDialog.alert({ title, message, variant });
```
- `variant`: `primary` (mặc định) · `danger` · `warning` · `success` · `info` — đổi icon và màu nút xác nhận.
- `message` hiển thị dạng text (không chèn HTML), giữ xuống dòng `\n`.
- Esc / bấm nền = Huỷ. Nhiều hộp thoại gọi liên tiếp được xếp hàng.
- Mở chồng lên modal Bootstrap khác (ví dụ xác nhận trong modal Hoàn tiền) vẫn nằm trên cùng và trả lại trạng thái cho modal bên dưới khi đóng.

## Nơi đang dùng
| Nơi | Loại |
|---|---|
| Chốt ca (`App_Sales/shifts.html`) | `data-confirm`, `danger` |
| Hoàn tiền (`App_Quanly/order_history.html`) | `data-confirm`, `warning` |
| Xoá gán topping (`App_Quanly/product_toppings.html`) | `data-confirm`, `danger` |
| POS: thay giỏ mang về bằng đơn mang đi của khách | `eappDialog.confirm`, `warning` |
| Màn hình bếp: lỗi cập nhật món | `eappDialog.alert`, `danger` |
| Hướng dẫn cài app trên Safari iOS (dự phòng khi không dựng được modal riêng) | `eappDialog.alert`, `info` |

Thông báo ngắn không cần người dùng bấm (thêm vào giỏ, đã lưu…) vẫn dùng toast của từng trang. `console.warn` giữ nguyên cho lỗi nền chỉ dành cho dev.
