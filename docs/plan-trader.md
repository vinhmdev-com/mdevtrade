# TÀI LIỆU KỸ THUẬT & LẬP TRÌNH: HỆ THỐNG MDEVTRADE (TRADING AGENTS)

Tài liệu này đóng vai trò là kim chỉ nam (Blueprint) chi tiết đến mức độ code-level dành cho các lập trình viên triển khai hệ thống đa tác nhân (Multi-Agent) giao dịch vàng XAUT/USDT trên Binance Spot.

---

## 1. TRIẾT LÝ CỐT LÕI (CORE PHILOSOPHY)
*   **Mục tiêu:** Tích lũy tài sản cứng (Vàng/XAUT) dài hạn (3-5 năm). Tối ưu hóa quá trình gom hàng bằng AI.
*   **Thị trường:** Binance Spot 1:1. Không Margin, không Futures, không phí Funding.
*   **Chiến lược 3 KHÔNG:** 
    1. **KHÔNG CẮT LỖ (No Stop-Loss):** Dù thị trường sập sâu, tuyệt đối không bán lỗ. Chuyển sang trạng thái "Hold to win" và tiếp tục gom hàng giá rẻ.
    2. **KHÔNG ALL-IN:** Luôn chia nhỏ vốn DCA tĩnh ($5.5/lệnh).
    3. **KHÔNG ĐỂ AI NẮM TÀI SẢN:** AI chỉ phân tích vĩ mô, Bot Thực thi (bằng code Python thuần) mới cầm API Key và giữ quyền sinh sát.

---

## 2. KIẾN TRÚC PHÂN RẢ (DECOUPLED ARCHITECTURE)

Hệ thống chia làm 2 cụm Microservices tách biệt hoàn toàn:

### A. CỤM 1: AI BRAIN (`trading_research`)
*   **Đầu vào:** OHLCV (từ yfinance), Technical Indicators (SMA, RSI, MACD), Macro News.
*   **Ngữ cảnh lai (Hybrid Sliding Window):** AI chỉ được cấp lịch sử tóm tắt của 3-5 chu kỳ sóng gần nhất, kèm theo Tổng kết All-time PnL. Không cung cấp dữ liệu rác hàng ngày để tránh ảo giác.
*   **Trạng thái:** "Mù" hoàn toàn. Không biết ví đang có bao nhiêu tiền.
*   **Đầu ra:** Trả về duy nhất 1 tín hiệu mỗi ngày: `TĂNG` / `GIẢM` / `NEUTRAL`.

### B. CỤM 2: EXECUTION HANDS (`trading_binance`)
*   **Đầu vào:** Tín hiệu từ AI Brain, Số dư ví Binance (CCXT), Lịch sử Trade (SQLite).
*   **Nhiệm vụ:** Kiểm tra điều kiện ví, kiểm tra giá vốn (WAC), ra quyết định khớp lệnh cuối cùng.

---

## 3. LOGIC THỰC THI (CODE-LEVEL WORKFLOW)

Logic cốt lõi của Bot Thực thi được viết bằng các lệnh IF/ELSE cứng nhắc, tuyệt đối không dùng AI ở tầng này để đảm bảo an toàn toán học.

**Bước 1: Tính toán Giá vốn trung bình (WAC - Weighted Average Cost)**
*   Mỗi khi mua Vàng, Bot lưu lịch sử vào SQLite. Code sẽ tính WAC:
    `WAC = Tổng chi phí USDT đã mua / Tổng số lượng XAUT đang giữ`

**Bước 2: Xử lý tín hiệu từ AI**
Giả sử Order Size cố định = $5.5 USDT.

*   **Trường hợp 1: AI hô TĂNG (MUA)**
    *   *Kiểm tra Inventory:* USDT trong ví > 5.5$ ?
    *   *Nếu Đủ:* Gọi CCXT bắn lệnh Market Buy XAUT trị giá 5.5$.
    *   *Nếu Thiếu:* Chặn lệnh, ghi log "Hết USDT phòng thủ".

*   **Trường hợp 2: AI hô GIẢM (BÁN CHỐT LỜI)**
    *   Bot tính toán: `Giá Market Hiện Tại` có lớn hơn `Giá vốn trung bình (WAC)` không?
    *   *Nếu Giá Market > WAC (Đang Lãi):* Gọi CCXT bắn lệnh Market Sell lượng XAUT trị giá 5.5$. Khóa lợi nhuận.
    *   *Nếu Giá Market < WAC (Đang Lỗ):* **CHẶN LỆNH!** (Bảo vệ triết lý Không Cắt Lỗ). Ghi log: "Thị trường giảm sâu nhưng đang lỗ, chuyển sang trạng thái Hold, từ chối bán".

*   **Trường hợp 3: AI hô NEUTRAL**
    *   Đứng yên. Không làm gì.

---

## 4. CẤU TRÚC DATABASE (SQLITE)

Database `trading_memory.db` là trái tim của Kế toán hệ thống. Chứa 2 bảng chính:

### Bảng 1: `trade_history` (Sổ phụ giao dịch)
Lưu mọi giao dịch mua bán thành công để tính Giá Vốn (WAC) và theo dõi phí.
*   `id` (PK)
*   `order_id` (String) - Lấy từ Binance.
*   `timestamp` (Datetime)
*   `side` (String) - 'BUY' hoặc 'SELL'.
*   `amount_xaut` (Float) - Số lượng Vàng đã khớp.
*   `price` (Float) - Tỷ giá lúc khớp lệnh.
*   `cost_usdt` (Float) - Số tiền USDT đã tiêu/thu về.
*   `fee_currency` (String) - Đồng tiền trả phí (XAUT/USDT/BNB).
*   `fee_amount` (Float) - Lượng phí bị trừ.

### Bảng 2: `macro_cycles` (Nhật ký Chu kỳ Sóng - Dành cho AI học)
Mỗi khi kết thúc một chu kỳ gom hàng và bắt đầu xả hàng (chốt lời thành công), Bot sẽ ghi lại 1 dòng vào đây.
*   `id` (PK)
*   `cycle_type` (String) - Sóng TĂNG / Sóng GIẢM.
*   `start_date` (Datetime)
*   `end_date` (Datetime)
*   `total_accumulated_usd` (Float)
*   `average_entry_price` (Float) - Giá vốn WAC.
*   `average_exit_price` (Float)
*   `realized_pnl_pct` (Float) - % Lãi thực tế của chu kỳ.

*(Báo cáo từ bảng này sẽ được trích xuất 3 dòng gần nhất để nhồi vào prompt cho AI Brain đọc mỗi ngày).*

---

## 5. THIẾT LẬP MÔI TRƯỜNG VÀ DEPENDENCIES

**File `.env` yêu cầu:**
```env
BINANCE_API_KEY=your_key_here
BINANCE_SECRET_KEY=your_secret_here
ORDER_SIZE_USD=5.5
MAX_XAUT_INVENTORY_USD=1000.0  # Ngưỡng tối đa giới hạn việc gom hàng
```

**Thư viện Python cốt lõi:**
*   `ccxt`: Kết nối Binance Spot (Bật sandbox mode khi test).
*   `sqlite3`: Lưu trữ cục bộ.
*   `langgraph`: Điều phối Workflow.

---
**Tổng kết cho Developer:** Hãy code thật cẩn thận phần tính toán WAC (Giá vốn) và logic chặn lệnh BÁN lỗ. Đó là chốt chặn cuối cùng bảo vệ tài sản của User.
