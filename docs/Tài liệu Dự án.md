# **🍃 Mint POS \- Ứng dụng Quản lý Bán hàng F\&B (Web-App)**

**Mint POS** là một ứng dụng Web Point-of-Sale (Máy bán hàng) hiện đại, chuyên dụng cho ngành F\&B (Nhà hàng, Quán Cafe, Trà sữa). Hệ thống được xây dựng hoàn toàn bằng HTML, CSS (Bootstrap 5\) và JavaScript thuần, tối ưu hóa trải nghiệm người dùng (UX/UI) trên cả thiết bị di động và máy tính bảng/desktop.

## **🚀 Các Tính năng Nổi bật**

### **1\. Trải nghiệm Giao diện (UI/UX) Hiện đại**

* **Thiết kế Thích ứng (Responsive):** Tự động chuyển đổi bố cục. Trên Desktop là màn hình chia cột tiện lợi; trên Mobile, giỏ hàng được thu gọn thành nút nổi (Floating Button) và vuốt mở dạng Offcanvas cực kỳ mượt mà.  
* **Cá nhân hóa Giao diện (Theming):** Cho phép đổi màu chủ đạo hệ thống chỉ với 1 click (Xanh Mint, Xanh dương, Vàng, Cam, Tím) trong menu tài khoản.  
* **Hiệu ứng Động (Animations):** \* Hiệu ứng "Bay vào giỏ hàng" (Flying animation) sinh động khi click chọn món.  
  * Hiệu ứng nhịp đập (Pulse) cảnh báo bàn đang có khách hoặc có đơn hàng mới.  
  * Hiệu ứng rung chuông (Ringing) khi có thông báo đơn hàng QR.  
* **Chế độ xem Thực đơn:** Hỗ trợ chuyển đổi nhanh giữa dạng Lưới (Grid) và dạng Danh sách (List).

### **2\. Quản lý Thực đơn & Giỏ hàng Thông minh**

* **Tìm kiếm & Lọc:** Lọc nhanh theo danh mục (Tất cả, Đồ ăn, Nước uống, Combo) và tìm kiếm theo tên món theo thời gian thực (Real-time search).  
* **Tùy chọn Size & Topping:** Hỗ trợ thiết lập giá linh hoạt. Tự động tính toán và cộng dồn giá tiền khi khách chọn Size hoặc thêm nhiều loại Topping khác nhau.  
* **Ghi chú Món ăn (Item Notes):** Cho phép ghi chú yêu cầu đặc biệt (VD: ít đá, nhiều đường). Tích hợp sẵn bộ "Ghi chú nhanh" (Quick Notes) để thu ngân thao tác chỉ bằng 1 lượt chạm.  
* **Xử lý Giỏ hàng:** Tách biệt thông minh các món ăn cùng loại nhưng khác Size/Topping. Hỗ trợ nút xóa nhanh từng món hoặc làm sạch toàn bộ giỏ hàng (có hộp thoại xác nhận an toàn).

### **3\. Quản lý Sơ đồ bàn (Table Management)**

* **Sơ đồ Trực quan:** Hiển thị danh sách 10 bàn và 1 luồng "Khách mang về" (Takeaway).  
* **Trạng thái Bàn:** Nhận diện màu sắc rõ ràng:  
  * Bàn trống: Màu xám, viền đứt nét.  
  * Có khách: Màu đỏ, hiện số lượng món và tổng tiền đang sử dụng.  
  * Chờ duyệt QR: Màu cam nhấp nháy, báo hiệu có đơn khách vừa tự đặt.  
* **Đồng bộ Dữ liệu (State Sync):** Tự động lưu và tải lại giỏ hàng tương ứng khi chuyển đổi giữa các bàn, đảm bảo thu ngân có thể xử lý song song nhiều khách hàng cùng lúc mà không mất dữ liệu.

### **4\. Xử lý Đơn hàng Online (QR Order Integration)**

* **Chuông Thông báo (Real-time Notification):** Tích hợp chuông báo rung và đếm số lượng khi có đơn hàng mới gửi về từ khách quét mã QR.  
* **Danh sách Đơn chờ Duyệt:** Quản lý riêng các đơn Online, hiển thị chi tiết bàn đặt, thời gian và danh sách món khách tự chọn.  
* **Quy trình Duyệt/Từ chối:** Thu ngân có thể xem chi tiết đơn, bấm "Duyệt" (hệ thống tự động đẩy món vào bàn của khách) hoặc "Từ chối" (xóa đơn khỏi hàng đợi).  
* **Trình Giả lập (Simulator):** Tích hợp sẵn nút "Giả lập khách quét QR" để demo luồng hoạt động mà không cần kết nối Server.

### **5\. Thanh toán Nhanh & Chính xác**

* **Hộp thoại Thanh toán (Checkout Modal):** Hiển thị chi tiết (Summary) lại toàn bộ món ăn, size, topping, ghi chú và tổng tiền.  
* **Gợi ý Tiền thông minh (Smart Quick Cash):** Tự động tính toán các mốc tiền chẵn dựa trên tổng hóa đơn (VD: Tổng 65k \-\> Gợi ý nút: Vừa đủ, 70k, 100k, 500k).  
* **Định dạng Tiền tệ:** Ô nhập tiền của khách tự động phân cách hàng nghìn (100.000) giúp tránh gõ sai số 0\.  
* **Tự động tính tiền thừa:** Hiển thị tức thời số tiền cần thối lại (màu xanh) hoặc cảnh báo số tiền khách đưa còn thiếu (màu đỏ).

## **🛠 Công nghệ Sử dụng**

* **Giao diện (Frontend):** HTML5, CSS3.  
* **Framework UI:** Bootstrap 5.3 (Sử dụng hệ thống Grid, Offcanvas, Modals, Toasts, Badges).  
* **Logic (Scripting):** Vanilla JavaScript (ES6+), thao tác DOM trực tiếp, quản lý State trên RAM trình duyệt.  
* **Icons:** FontAwesome 6 (CDN).  
* **Placeholder Images:** Unsplash Source & UI Avatars API.

## **💡 Hướng dẫn Trải nghiệm (Demo)**

1. **Thêm món:** Nhấn vào món ăn bất kỳ để đưa vào giỏ hàng. Thử chọn các món có Size hoặc Topping (như *Trà Sữa Trân Châu*) để xem bảng tùy chọn nâng cao.  
2. **Ghi chú món:** Nhấn vào icon Cây bút ở từng món trong giỏ hàng để ghi chú nhanh.  
3. **Đổi Bàn:** Chọn tab Sơ đồ bàn, nhấp vào một bàn trống (VD: Bàn 01\) và thử order.  
4. **Trải nghiệm QR Order:** Nhấp vào nút Giả lập khách quét QR (màu cam) trên thanh Menu trên cùng. Nhìn chuông thông báo và Sơ đồ bàn để thấy cảnh báo, sau đó vào tab Đơn Online (QR) để duyệt đơn.  
5. **Thanh toán:** Nhấn nút Thanh toán ở giỏ hàng, thử nhập số tiền hoặc bấm vào các nút gợi ý tiền mặt thông minh để hệ thống tự động tính tiền thừa.