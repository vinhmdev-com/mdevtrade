# CHIẾN LƯỢC GIAO DỊCH XAUT/USDT BẰNG AI (TRIAL 30 NGÀY)

## 1. TỔNG QUAN KIẾN TRÚC VÀ NGÂN SÁCH
- **Mục tiêu cốt lõi:** Tích lũy tài sản cứng (Vàng/XAUT) dùng trong tương lai (3-5 năm). Do đó chiến lược mang triết lý **KHÔNG CẮT LỖ (No Stop-Loss)**. Cứ giữ và tích trữ ở đó.
- **Tài sản Giao dịch:** `XAUT/USDT` (Giao ngay - Binance Spot). Sở hữu tài sản thật, không đòn bẩy.
- **Tổng ngân sách:** $200 cho quá trình Trial 30 ngày.
- **Chia Pool Khởi tạo (Cân bằng tĩnh):**
  - ~100$ XAUT (Vàng - mua sẵn để làm vốn bán khi Trend Giảm).
  - ~100$ USDT (Đô la - tiền mặt phòng thủ để mua khi Trend Tăng).
- **Quy mô Lệnh (Order Size):** ~$5.5 / lệnh / ngày.

## 2. KIẾN TRÚC PHÂN RẢ HỆ THỐNG (DECOUPLED ARCHITECTURE)
Hệ thống được chia làm 2 Microservices độc lập, "mù" thông tin lẫn nhau để đảm bảo tính khách quan:

### A. Bot Research (Bộ Não AI - `trading_research`)
- **Nhiệm vụ:** Đọc tin tức, dữ liệu vĩ mô, phân tích kỹ thuật.
- **Đặc tính:** Hoàn toàn "Mù" (Blind). Không biết ví đang có bao nhiêu tiền, không biết giá vốn.
- **Ngữ cảnh (Prompt):** Sử dụng Cửa sổ trượt lai (Hybrid Sliding Window) - chỉ cung cấp 3-5 báo cáo chu kỳ gần nhất và 1 báo cáo tổng All-time để tránh ảo giác.
- **Đầu ra (Output):** Khách quan đánh giá xu hướng vĩ mô: **TĂNG**, **GIẢM** hoặc **NEUTRAL**.

### B. Bot Execution (Đôi Tay Thực Thi - `trading_binance`)
- **Nhiệm vụ:** Nắm API Key, đọc số dư ví (CCXT), đọc lịch sử lệnh (SQLite) để tính **Giá Vốn Trung Bình (WAC)**.
- **Đặc tính:** Có khả năng "Chặn lệnh" (Override) để bảo vệ tài sản, tuyệt đối tuân thủ triết lý Không Cắt Lỗ.

## 3. LOGIC VẬN HÀNH CỐT LÕI (CORE STRATEGY)
Bot Execution sẽ nhận tín hiệu mỗi ngày từ Bot Research và thực hiện logic bảo vệ vốn:

- **Tín hiệu TĂNG (Gom hàng):** Kiểm tra ví, nếu USDT > 5.5$, tiến hành MUA $5.5 XAUT. (Thu gom Vàng).
- **Tín hiệu GIẢM (Chốt lời):** 
  - *Kiểm tra:* Giá thị trường hiện tại CÓ LỚN HƠN Giá vốn trung bình (WAC) không?
  - *Nếu > WAC (Có lãi):* Bán lượng XAUT trị giá $5.5 để chốt lời thu USDT về.
  - *Nếu < WAC (Đang lỗ):* **TỪ CHỐI BÁN**. Ghi log: "Chuyển sang trạng thái Hold tích trữ, không cắt lỗ".
- **Tín hiệu NEUTRAL:** Đứng im, không làm gì.

## 4. QUẢN TRỊ DỮ LIỆU & RÚT KINH NGHIỆM
- **Cơ sở dữ liệu (SQLite):** Hệ thống không dùng ngắt mạch (Circuit Breaker) nữa vì đánh theo trường phái Hold dài hạn. Thay vào đó, SQLite sẽ làm nhiệm vụ **Kế toán (Accounting)**:
  - Bảng `trade_history`: Lưu mọi lệnh Mua/Bán cùng với Phí giao dịch (Fee) bị trừ.
  - Bảng `macro_cycles`: Tổng hợp Lãi/Lỗ của từng chu kỳ để trích xuất gửi cho AI Brain tự rút kinh nghiệm.

*(Lưu ý: Để xem hướng dẫn code chi tiết mức độ Developer, vui lòng tham khảo file `plan-trader.md`)*
