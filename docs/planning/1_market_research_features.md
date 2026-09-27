# 1) Nghiên cứu thị trường — Tính năng của các phần mềm POS F&B tương tự

**Cập nhật:** 27/09/2026 · **Mục đích:** so sánh eApp FnB với các sản phẩm trên thị trường, tìm khoảng trống tính năng để đưa vào `docs/backlog/`.

## 1. Đối thủ tham chiếu

| Sản phẩm | Thị trường | Định vị | Ghi chú |
|---|---|---|---|
| KiotViet FnB | Việt Nam | Quán nhỏ → chuỗi, giá rẻ (gói cơ bản ~200.000đ/tháng, 3 user) | Tích hợp GrabFood/ShopeeFood, VietQR, kho theo gram |
| Sapo FnB | Việt Nam | Nhà hàng, quán nước, chuỗi | QR tại bàn, bếp, GrabFood/ShopeeFood/Xanh SM Ngon, hoá đơn điện tử, offline mode |
| MISA CukCuk | Việt Nam | Nhà hàng, cafe vừa và nhỏ | Mạnh về kế toán, CRM khách hàng, hệ sinh thái MISA (meInvoice) |
| iPOS.vn | Việt Nam | Nhà hàng vừa → chuỗi lớn | Quản lý từ xa, báo cáo |
| Toast | Mỹ | Nhà hàng full-service & chuỗi | Trợ lý AI "Toast IQ" (hỏi đáp + thao tác), Guest CRM, quản lý đa chi nhánh |
| Square for Restaurants | Mỹ/Quốc tế | Quán nhỏ, setup nhanh | Gói miễn phí, KDS, online ordering, đồng bộ realtime |
| Lightspeed Restaurant | Quốc tế | Nhà hàng vừa → chuỗi | Kho, online ordering, offline, AI dự báo nhu cầu |

## 2. Ma trận tính năng: thị trường vs eApp FnB

Ký hiệu: ✅ có · 🟡 có một phần · ❌ chưa có.

### 2.1 Bán hàng tại quầy / tại bàn
| Tính năng | Phổ biến ở | eApp FnB | Ghi chú |
|---|---|---|---|
| Sơ đồ bàn, trạng thái bàn | Tất cả | ✅ | Lưới bàn theo store |
| Chuyển bàn | Tất cả | ✅ | `cart/move-to/` |
| **Gộp bàn / tách bàn** | KiotViet, Sapo, CukCuk | ❌ | Phổ biến với nhóm khách đông |
| **Tách hoá đơn / gộp hoá đơn** (split check) | Sapo, Toast, Lightspeed, Square | ❌ | Chia theo món hoặc chia đều |
| Size / unit, topping, ghi chú món | Tất cả | ✅ | |
| **Combo / set menu** | KiotViet, Sapo, Toast | ❌ | |
| **Món theo khung giờ** (menu sáng/trưa/tối, happy hour) | Toast, Lightspeed | ❌ | |
| Hết món nhanh ("86") | Toast, Square, Sapo | 🟡 | Có `StoreProduct.is_available`, chưa có thao tác nhanh từ POS |
| **Phí dịch vụ / phụ thu** | Sapo, Toast | ❌ | Có `tax_rate`, chưa có service charge |
| **In hoá đơn / in phiếu bếp** (máy in nhiệt, ESC/POS) | Tất cả (VN) | ❌ | Rất quan trọng với quán VN |
| **Đặt bàn trước** (reservation) | KiotViet, Toast | ❌ | |
| **Offline mode** (bán khi mất mạng, đồng bộ sau) | Sapo, Lightspeed | 🟡 | PWA chỉ có trang offline, chưa bán offline |

### 2.2 Thanh toán
| Tính năng | Phổ biến ở | eApp FnB | Ghi chú |
|---|---|---|---|
| Tiền mặt, thẻ, QR tĩnh | Tất cả | ✅ | QR thanh toán upload ảnh theo store |
| **VietQR động** (số tiền + nội dung theo đơn) | KiotViet, Sapo (Techcombank VietQR Pro) | ❌ | |
| **Tự xác nhận chuyển khoản** (webhook ngân hàng / đọc thông báo) | KiotViet, Sapo | ❌ | Giảm thất thoát, giảm thao tác |
| **Khách thanh toán tại bàn qua QR** | Toast, Square | ❌ | Mở rộng luồng QR hiện có |
| Thanh toán nhiều phương thức cho 1 đơn | Toast, Lightspeed | ❌ | |

### 2.3 Tuân thủ pháp lý (Việt Nam)
| Tính năng | Phổ biến ở | eApp FnB | Ghi chú |
|---|---|---|---|
| **Hoá đơn điện tử khởi tạo từ máy tính tiền** | Sapo, MISA, KiotViet (qua nhà cung cấp HĐĐT) | ❌ | Xem mục 3 — **bắt buộc** với nhiều khách hàng mục tiêu |
| Hỗ trợ kê khai thuế hộ kinh doanh | Sapo | ❌ | |

### 2.4 Bếp & vận hành
| Tính năng | Phổ biến ở | eApp FnB | Ghi chú |
|---|---|---|---|
| Màn hình bếp (KDS) | Sapo, Square, Toast | ✅ | Phase 3 |
| **Định tuyến theo trạm** (bếp / quầy bar) | Toast, Lightspeed | ❌ | Tất cả món về 1 màn hình |
| **Theo dõi thời gian chế biến**, cảnh báo món chậm | Toast, Square | 🟡 | Có `started_at` / `done_at`, chưa có báo cáo / cảnh báo |
| Âm báo đơn mới | Tất cả | ✅ | `static/sounds/co-don-moi.mp3` |

### 2.5 Kho & giá vốn
| Tính năng | Phổ biến ở | eApp FnB | Ghi chú |
|---|---|---|---|
| **Kho nguyên liệu, định lượng (recipe)** | KiotViet (theo gram), Sapo, Lightspeed | ❌ | Phase 4 |
| Cảnh báo sắp hết nguyên liệu | Sapo | ❌ | |
| Nhập hàng, nhà cung cấp, công nợ | KiotViet, Sapo | ❌ | |
| **Báo cáo giá vốn / lãi gộp theo món** | KiotViet, Sapo, Lightspeed | ❌ | Cần định lượng |

### 2.6 Nhân sự
| Tính năng | Phổ biến ở | eApp FnB | Ghi chú |
|---|---|---|---|
| **Ca làm việc, chốt ca, két tiền** | Tất cả | ❌ | Phase 4 |
| Chấm công, tính lương | Sapo, Toast | ❌ | |
| **Phân quyền chi tiết** (thu ngân, phục vụ, bếp) | Tất cả | 🟡 | Chỉ có MANAGER / STAFF |
| Nhật ký thao tác (huỷ món, giảm giá, xoá đơn) | Toast, KiotViet | ❌ | Chống gian lận |

### 2.7 Khách hàng & marketing
| Tính năng | Phổ biến ở | eApp FnB | Ghi chú |
|---|---|---|---|
| Hồ sơ khách, tích điểm, hạng | CukCuk, Toast | ✅ | Phase 3 |
| **Đổi điểm lấy ưu đãi** | CukCuk, Toast | ❌ | Hiện chỉ tích điểm |
| Voucher / mã giảm giá | Tất cả | 🟡 | Có khuyến mãi hoá đơn, chưa có mã code |
| Ưu đãi sinh nhật, gửi tin Zalo/SMS | CukCuk, Sapo | ❌ | Zalo ZNS phổ biến ở VN |
| Khách tự tra điểm | Toast | ❌ | Có thể gắn vào trang QR |

### 2.8 Kênh bán online
| Tính năng | Phổ biến ở | eApp FnB | Ghi chú |
|---|---|---|---|
| QR gọi món tại bàn | Sapo, Toast | ✅ | Phase 2 |
| **Web order mang về / giao hàng** (link chia sẻ Zalo, Messenger) | Sapo, Square | 🟡 | Có catalog public, chưa đặt hàng online |
| **Đồng bộ GrabFood / ShopeeFood / Xanh SM Ngon** | KiotViet, Sapo | ❌ | Cần hợp đồng đối tác API |
| Giao hàng GrabExpress / AhaMove | Sapo | ❌ | |
| Kiosk tự gọi món | Toast, GRUBBRR | ❌ | Có thể tái dùng trang QR |

### 2.9 Báo cáo & AI
| Tính năng | Phổ biến ở | eApp FnB | Ghi chú |
|---|---|---|---|
| Dashboard doanh thu | Tất cả | ✅ | |
| **Báo cáo theo món, giờ cao điểm, nhân viên** | Tất cả | 🟡 | Dashboard có tổng quan |
| **Xuất báo cáo Excel/PDF** | Tất cả | ❌ | Chỉ có import/export catalog |
| App quản lý từ xa trên điện thoại | iPOS, Sapo | 🟡 | `/quanly/` responsive + PWA |
| **Trợ lý AI** (hỏi đáp doanh thu, gợi ý hành động) | Toast IQ, Lightspeed | ❌ | Xu hướng 2025–2026 |
| **Dự báo nhu cầu / gợi ý nhập hàng** | Lightspeed | ❌ | Cần dữ liệu kho |

### 2.10 Nền tảng SaaS
| Tính năng | Phổ biến ở | eApp FnB | Ghi chú |
|---|---|---|---|
| Đa chi nhánh, menu tập trung | Toast, KiotViet | ✅ | Giá theo store, bật/tắt món theo store |
| Gói dịch vụ + giới hạn | Tất cả | 🟡 | Có giới hạn, **chưa chặn khi hết hạn gói** |
| Tự đăng ký dùng thử, thanh toán gói online | KiotViet, Sapo | ❌ | Hiện superadmin tạo tenant thủ công |
| Open API / webhook | Toast, Square | ❌ | |

## 3. Quy định hoá đơn điện tử từ máy tính tiền (Việt Nam)
- **Nghị định 70/2025/NĐ-CP**, hiệu lực **01/06/2025**, sửa đổi Nghị định 123/2020.
- Đối tượng: doanh nghiệp, hộ kinh doanh bán lẻ trực tiếp cho người tiêu dùng — **bao gồm nhà hàng, dịch vụ ăn uống**; hộ kinh doanh có doanh thu năm từ **1 tỷ đồng** trở lên bắt buộc dùng.
- Hoá đơn có mã của cơ quan thuế, khởi tạo trên máy POS / máy tính / điện thoại, **không bắt buộc chữ ký số**, ký hiệu chữ **"M"** (Thông tư 32/2025/TT-BTC).
- Dữ liệu bắt buộc: tên, địa chỉ, MST người bán; tên hàng hoá, đơn giá, số lượng, thành tiền; thời điểm lập; mã cơ quan thuế.
- Dữ liệu phải chuyển đến cơ quan thuế (ngay hoặc định kỳ); không chuyển dữ liệu có thể bị phạt hành chính.

**Tác động đến eApp FnB:** là rào cản lớn nhất khi bán cho quán có doanh thu > 1 tỷ/năm. Hướng khả thi: tích hợp API của một nhà cung cấp HĐĐT đã được Tổng cục Thuế chấp thuận (MISA meInvoice, Viettel S-Invoice, VNPT, BKAV eHoadon, FPT…) thay vì tự kết nối cơ quan thuế.

## 4. Xu hướng công nghệ 2026
1. **Nền tảng hợp nhất:** POS + online ordering + giao hàng + kho + loyalty trên một hệ thống, dữ liệu đồng bộ realtime thay vì nhiều công cụ rời rạc.
2. **Tự phục vụ:** kiosk, QR tại bàn, thanh toán tại bàn — tăng giá trị đơn nhờ gợi ý bán thêm tự động.
3. **AI trong POS:** trợ lý hỏi đáp doanh thu/nhân sự/menu và **thực hiện thao tác** (Toast IQ), dự báo nhu cầu, gợi ý nhập hàng (Lightspeed).
4. **Kho realtime gắn định lượng** để kiểm soát food cost và giảm hao hụt.
5. **Loyalty tích hợp mọi kênh** (tại quầy, QR, online) để thu thập dữ liệu khách.

## 5. Đề xuất ưu tiên cho eApp FnB
Tiêu chí: giá trị cho quán nhỏ/vừa tại Việt Nam × chi phí phát triển × tận dụng nền tảng sẵn có.

| Ưu tiên | Tính năng | Lý do |
|---|---|---|
| 1 | In hoá đơn + in phiếu bếp | Kỳ vọng mặc định của mọi quán VN, thiếu là rào cản bán hàng |
| 2 | VietQR động + tự xác nhận chuyển khoản | Thanh toán chuyển khoản chiếm tỷ trọng lớn, giảm thất thoát |
| 3 | Chốt ca + két tiền, nhật ký thao tác, huỷ/hoàn đơn | Chống thất thoát, đã có trong Phase 4 |
| 4 | Hoá đơn điện tử từ máy tính tiền (qua nhà cung cấp) | Bắt buộc pháp lý với quán > 1 tỷ/năm |
| 5 | Tách / gộp hoá đơn, gộp bàn, phí dịch vụ | Nghiệp vụ nhà hàng cơ bản còn thiếu |
| 6 | Kho + định lượng + báo cáo lãi gộp | Khác biệt với đối thủ giá rẻ, cần cho chuỗi |
| 7 | Đổi điểm, voucher mã code, Zalo ZNS | Tận dụng module khách hàng sẵn có |
| 8 | Web order mang về, gọi phục vụ/thanh toán từ trang QR | Mở rộng luồng QR sẵn có với chi phí thấp |
| 9 | Đồng bộ GrabFood / ShopeeFood | Giá trị cao nhưng phụ thuộc hợp đồng đối tác |
| 10 | Trợ lý AI báo cáo, dự báo | Khác biệt hoá, làm sau khi dữ liệu kho/ca đủ |

Backlog chi tiết: `docs/backlog/1_backlog.md`.

## Nguồn tham khảo
- [TOP 7 phần mềm bán hàng quán giải khát 2026 — CukCuk](https://www.cukcuk.vn/34501/phan-mem-ban-hang-quan-giai-khat/)
- [Top 5 phần mềm quản lý nhà hàng 2026 — MISA AMIS](https://amis.misa.vn/236515/phan-mem-quan-ly-nha-hang/)
- [Phần mềm quản lý nhà hàng — Sapo](https://www.sapo.vn/phan-mem-quan-ly-nha-hang.html)
- [KiotViet FnB tích hợp GrabFood và ShopeeFood](https://www.kiotviet.vn/kiotviet-fnb-tich-hop-grabfood-va-shopeefood-quan-ly-tinh-gon-but-pha-doanh-thu/)
- [Hoá đơn khởi tạo từ máy tính tiền: quy định mới nhất 2026 — xCyber](https://xcyber.vn/hoa-don-khoi-tao-tu-may-tinh-tien/)
- [Triển khai HĐĐT từ máy tính tiền theo NĐ 70/2025 — Cổng TTĐT TP Thanh Hoá](https://tpthanhhoa.thanhhoa.gov.vn/web/trang-chu/tin-tuc/trien-khai-hoa-don-dien-tu-khoi-tao-tu-may-tinh-tien-theo-nghi-dinh-70-2025-nd-cp-bat-dau-tu-ngay-01-6-2025.html)
- [Hộ kinh doanh trên 1 tỷ/năm phải xuất hoá đơn máy tính tiền — MISA eShop](https://www.misaeshop.vn/28175/ho-kinh-doanh-tren-1-ty-phai-xuat-hoa-don-may-tinh-tien/)
- [9 Best POS Systems for Restaurants 2026 — Owner.com](https://www.owner.com/blog/best-pos-system-for-restaurants)
- [Best AI Features in Restaurant POS 2026 — RestaurantTools.ai](https://restauranttools.ai/blog/best-restaurant-pos-with-ai-features-2026)
- [Lightspeed Restaurant — Capterra](https://www.capterra.com/p/211849/Lightspeed-Resturant/)
- [Restaurant Technology Trends 2026 — Sauce](https://www.getsauce.com/post/restaurant-technology-trends)
- [Intelligent Self-Service Kiosks 2026 — GRUBBRR](https://grubbrr.com/intelligent-self-service-kiosks-restaurants-2026/)
