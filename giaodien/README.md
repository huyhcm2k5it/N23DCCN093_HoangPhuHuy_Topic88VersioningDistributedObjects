# 🖥️ Frontend - Hệ thống Quản lý Phiên bản CAD Phân tán (Vite + React)

> Giao diện điều khiển (Dashboard) cho Đồ án **Topic 88: Versioning Distributed Objects**  
> Môn: Cơ sở dữ liệu phân tán - Kỳ II 2025-2026

---

## 🎯 Tổng quan

Giao diện Web React này đóng vai trò là một **Centralized Dashboard** giúp người dùng (và giáo viên chấm điểm) trực quan hoá toàn bộ các quy trình phức tạp đang diễn ra ngầm bên trong Hệ thống Phân tán (Backend). Thay vì gõ lệnh Terminal khô khan, bạn có thể tương tác với 3 Site phân tán chỉ bằng các cú click chuột.

**Các tính năng "đắt giá" được trực quan hóa:**
- 📡 **Giám sát thời gian thực:** Cập nhật liên tục trạng thái Online/Offline của 3 Site.
- 🛠️ **Làm việc (Workspace):** Trực quan hóa quy trình tải file thiết kế (Checkout), sửa đổi JSON, và lưu file (Check-in) kèm cơ chế tạo mã băm SHA-256 (Audit Trail) để đối chiếu toàn vẹn dữ liệu.
- ⚡ **Mô phỏng Xung đột (Conflict):** Chạy kịch bản 5 bước tuần tự để xem hệ thống xử lý chiến lược rẽ nhánh (Branching - Site A/B) và ghi đè (Timestamp - Site C) như thế nào.
- 💥 **Mô phỏng Crash WAL:** Tính năng cực kỳ nâng cao giúp mô phỏng việc sập nguồn Server (Crash) và tự động phục hồi an toàn tuyệt đối dựa trên WAL log (Atomicity).

---

## 📑 Các Tab Chức Năng Chính

Giao diện được tổ chức thành 5 thẻ (Tabs) riêng biệt, mô phỏng một vòng đời sản xuất phần mềm CAD:

1. **📊 Bảng Điều Khiển (Overview):**
   - Hiển thị biểu đồ đo lường % tiết kiệm dung lượng của thuật toán **Delta Storage** so với Snapshot Storage truyền thống.

2. **📝 Không gian Làm việc (Workspace):**
   - Lựa chọn linh kiện và thực hiện Checkout.
   - Trình chỉnh sửa JSON giả lập phần mềm CAD để kỹ sư tinh chỉnh toạ độ 3D.
   - Khi Check-in, hệ thống sẽ trả về mã Hash SHA-256 mới, chứng minh dữ liệu đã được lưu trữ an toàn xuống Backend.

3. **⚔️ Trình diễn Xung đột (Conflict Demo):**
   - Kịch bản 5 bước hướng dẫn người dùng ép hệ thống sinh ra lỗi Xung đột do 2 kỹ sư sửa chung 1 file cùng lúc.
   - Có thể chọn Demo giữa chiến lược rẽ nhánh (Branching) và chiến lược ưu tiên thời gian (Timestamp).
   - Biểu diễn cây thư mục rẽ nhánh trực quan.

4. **🔥 Demo WAL Crash (Recovery Demo):**
   - Đóng vai "Hacker" chọc thủng hệ thống bằng cách làm sập Server đúng lúc nó đang lưu CSDL.
   - Cung cấp nút hiển thị trực tiếp nội dung file Log cứng `_wal.json` dạng Raw để quan sát cờ `PENDING`.
   - Nút "Trigger Recovery" để khởi động lại Server và kích hoạt tính năng Rollback tự động.

5. **📜 Nhật ký & Kiểm toán (Event Logs):**
   - Danh sách các thao tác `CHECKOUT`, `CHECKIN`, `CONFLICT`, `REPLICATE` chạy liên tục, giúp theo dõi luồng giao tiếp mạng và các thay đổi.

---

## 💻 Công nghệ sử dụng

| Thư viện | Vai trò |
|----------|---------|
| **React 18** | Khung giao diện chính (UI Framework) |
| **Vite** | Trình đóng gói và dev server siêu tốc |
| **Tailwind CSS v3** | Hệ thống tạo kiểu (Styling) dựa trên các utility class |
| **Recharts** | Thư viện biểu đồ (hiển thị so sánh Delta vs Snapshot) |
| **Lucide React** | Bộ icon SVG hiện đại, tinh tế |

---

## 🚀 Hướng dẫn Chạy (Development)

> **Điều kiện tiên quyết:** Phải cài đặt Node.js (phiên bản 18 trở lên).

### Bước 1: Khởi động 3 Servers Backend
Mở một terminal mới (ở thư mục gốc của dự án - `Topic88_VersioningDistributedObjects`):
```bash
python main.py --servers
```
*(Nếu bạn quên bật Backend, giao diện React sẽ báo lỗi 🔴 Offline ở toàn bộ các Site).*

### Bước 2: Khởi động Giao diện Web
Mở một terminal khác, di chuyển vào thư mục `giaodien`:
```bash
cd giaodien
npm install    # Lệnh này chỉ cần chạy 1 lần duy nhất để tải thư viện
npm run dev    # Lệnh bật Server React
```

Mở trình duyệt truy cập vào đường link: **http://localhost:3000** (hoặc port mà Vite cung cấp như 5173).

---

## 📂 Cấu trúc Code Giao diện (Dành cho nhà phát triển)

- `src/App.jsx`: Component gốc chứa Header, thanh điều hướng và logic chuyển đổi qua lại giữa 5 Tab.
- `src/api.js`: Nơi tập trung toàn bộ các lệnh gọi HTTP `fetch()` xuống Backend. Tất cả các cổng (Port 5001, 5002, 5003) được khai báo tại đây. Mọi sự cố CORS đều được bắt lỗi (catch) ở file này.
- `src/components/TabWorkspace.jsx`: Component chứa khung hiển thị mã băm SHA-256 và trình chỉnh sửa JSON.
- `src/components/TabConflict.jsx`: Component chứa máy trạng thái (State Machine) quản lý quy trình 5 bước Demo xung đột.
- `src/components/TabCoordinatorCrash.jsx`: Component xử lý lỗi cố ý (Intentional Crash) và hiện bảng kiểm tra WAL File trực quan.
- `src/index.css`: Cấu hình màu nền Dark Mode và các Class tuỳ chỉnh của Tailwind (ví dụ `.btn-primary`, `.glow-text`).

---

*Giao diện này được phát triển hoàn thiện nhằm hỗ trợ tối đa cho việc Thuyết minh và Bảo vệ Đồ án trước hội đồng.*
