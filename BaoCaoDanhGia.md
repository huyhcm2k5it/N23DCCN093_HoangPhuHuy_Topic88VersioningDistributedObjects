# 📊 Báo Cáo Đánh Giá Chất Lượng Đồ Án (Topic 88 — Versioning Distributed Objects)

> **Hệ thống Quản lý Phiên bản Đối tượng CAD Phân tán · Học kỳ II — 2025–2026**
> *Tham chiếu lý thuyết: Özsu & Valduriez — Principles of Distributed Database Systems, 4th Edition*

---

## 1. Kết Quả Kiểm Tra Sức Khỏe Dự Án (Project Health Check)

Hệ thống đã được chạy thử nghiệm thực tế toàn bộ các tầng logic (Backend, Frontend, Tests, Benchmark) và đạt kết quả xuất sắc:

### 🧪 Integration Tests (Bộ Kiểm Thử Tích Hợp)
Chạy bộ test tích hợp toàn diện gồm 3 kịch bản cốt lõi:
- **Test 1**: Timestamp Conflict Resolution (LWW) trên Site-C.
- **Test 2**: Branching Conflict Resolution trên Site-A.
- **Test 3**: WAL Crash & Recovery (Rollback transaction pending) trên Site-A.

**Kết quả:** **3/3 Tests Passed (100% Thành công)** trong `3.319s`.

### 📊 Benchmark & Charts Generation (Đo Lường Hiệu Năng & Biểu Đồ)
Chạy script đo lường so sánh hiệu năng giữa hai động cơ lưu trữ `SnapshotStore` (Lưu toàn bộ) và `DeltaStore` (Lưu vi sai) với 10 phiên bản.
- **Kết quả:**
  - Tiết kiệm dung lượng trung bình đạt **từ 54.7% đến 94.7%** tùy thuộc vào mức độ thay đổi hình học giữa các phiên bản.
  - Thư viện `matplotlib` đã sinh thành công **3 biểu đồ trực quan hóa dữ liệu** tại thư mục `results/`:
    1. `version_sizes.png` (Kích thước file từng phiên bản).
    2. `cumulative_storage.png` (Dung lượng tích lũy cộng dồn).
    3. `rehydration_latency.png` (Thời gian khôi phục O(k) CPU Penalty).
  - Tích hợp tính toán mã băm **SHA-256** hoạt động ổn định, đảm bảo tính toàn vẹn dữ liệu (Integrity) đạt 100% khớp tuyệt đối sau khi Rehydrate.

### 🖥️ React Frontend Dashboard (Giao Diện Người Dùng)
Chạy quy trình biên dịch tối ưu cho sản phẩm (production build) bằng Vite & Tailwind CSS.
- **Kết quả:** **Build thành công 100%** không xảy ra bất kỳ cảnh báo (warning) hay lỗi biên dịch nào. Bản phân phối `dist/` được tạo hoàn chỉnh (`index-*.js` ~`251.57 KB`).

---

## 2. Các Điểm Sáng Nổi Bật (Key Strengths)

Hệ thống được thiết kế cực kỳ thông minh, bám sát các nguyên lý phân tán nâng cao:
1. **Local Autonomy (Tự trị cục bộ)**: Mỗi Site hoạt động độc lập trên cơ sở dữ liệu SQLite vật lý riêng biệt (`Site-A.db`, `Site-B.db`, `Site-C.db`) và có chiến lược giải quyết xung đột riêng.
2. **Dual Storage Engine (Lưu trữ kép)**: Hiện thực hóa chính xác lý thuyết về Delta Storage (Özsu §15.6) so sánh trực quan với Full Snapshot.
3. **Write-Ahead Logging (WAL)**: Ghi nhật ký phục hồi lỗi trước khi ghi dữ liệu thật, có khả năng tự động khôi phục (Self-healing) khi điều phối viên khởi động lại.
4. **Persisted Checkouts**: Trạng thái checkout được lưu vào SQLite (`checkouts`) giúp hệ thống giữ nguyên ngữ cảnh ngay cả khi tiến trình API Server bị sập.

---

## 3. Các Điểm Hạn Chế Lý Thuyết & Đề Xuất Cải Tiến (Potential Enhancements)

Dù đồ án hoạt động hoàn hảo và không có lỗi runtime (bugs), để bài báo cáo và buổi bảo vệ đạt điểm tối đa từ Hội đồng chuyên môn, bạn có thể chú ý đến **3 điểm hạn chế mang tính học thuật** sau đây:

### ⚠️ Vấn đề 1: Đồng bộ xuyên Site làm mất định danh OID toàn cục (Replication OID Preservation)
- **Hiện trạng trong code (`app/server.py` dòng 171 - route `/replicate`):**
  Khi replicate một linh kiện từ Site này sang Site khác, endpoint gọi `POST /models` ở Site đích.
  Hàm `create_model` tại Site đích sẽ khởi tạo đối tượng `CADModel` mới, dẫn đến việc sinh một **UUID mới** làm OID (`self.oid = str(uuid.uuid4())`).
- **Lý thuyết đối chiếu (Özsu §15.1.1):**
  *Object Identity (OID) của một đối tượng phức hợp phải là duy nhất toàn cục (globally unique) và bất biến (immutable) xuyên suốt vòng đời của nó, bất kể nó được sao chép hay di chuyển qua bao nhiêu Site.*
- **Đề xuất sửa đổi:**
  Cập nhật route `POST /replicate` để truyền toàn bộ object (bao gồm cả `oid`, `version`, `site_origin`) và lưu trực tiếp qua `snapshot_store.save(model)` ở Site đích, thay vì tạo mới từ đầu.

### ⚠️ Vấn đề 2: Thiếu kiểm tra ràng buộc phân mảnh ngang tại API (Fragmentation Predicate Enforcement)
- **Hiện trạng trong code (`app/server.py` dòng 55 - route `POST /models`):**
  Bất kỳ client nào cũng có thể gọi `POST /models` đến một Site bất kỳ để tạo linh kiện. Ví dụ: Bạn có thể gửi một linh kiện có `part_id = 'INT-001'` (Interior - thuộc Site-C) vào Site-A (`category = 'engine'`). Backend sẽ lưu thành công mà không báo lỗi.
- **Lý thuyết đối chiếu (Özsu §15.2.1):**
  *Phân mảnh ngang (Horizontal Fragmentation) yêu cầu các phân mảnh phải rời rạc (Disjointness) và tuân thủ chặt chẽ vị từ phân mảnh (Predicate). Site-A chỉ được phép quản lý dữ liệu thỏa mãn `category = 'engine'`.*
- **Đề xuất sửa đổi:**
  Thêm bộ lọc kiểm tra vị từ (Predicate Validator) tại API boundary trước khi cho phép insert. Nếu `part_id` không khớp với dải quản lý của Site (ví dụ Site-A nhận `INT-*`), trả về mã lỗi `400 Bad Request (Fragmentation Constraint Violation)`.

### ⚠️ Vấn đề 3: Race Condition khi khôi phục WAL (WAL Concurrency)
- **Hiện trạng trong code:**
  Tiến trình recovery diễn ra qua endpoint `/coordinator/restart`. Hàm `wal_recover()` thực hiện quét các transaction chưa committed và rollback. Nếu trong quá trình này có các yêu cầu checkout/checkin đồng thời khác gửi tới, có thể xảy ra race condition trên database file.
- **Đề xuất cải tiến:**
  Trong quá trình recovery, hệ thống nên thiết lập trạng thái tạm khóa (lock/maintenance mode) đối với các dịch vụ checkin/checkout thường cho tới khi khôi phục trạng thái nhất quán hoàn toàn.

---

## 4. Bí Quyết Bảo Vệ Đồ Án Điểm A+ (Defense Strategy)

Khi thuyết trình trước Hội đồng, bạn hãy nhấn mạnh các từ khóa đắt giá sau:

1. **"Sự đánh đổi Không gian - Thời gian" (Space-Time Trade-off):**
   - Đưa ra con số từ bảng kết quả: *"Delta Storage giúp chúng em tiết kiệm tới hơn 80% dung lượng ổ cứng, nhưng đánh đổi lại bằng CPU chi phí Rehydration tăng dần theo thời gian là O(k) mỗi khi truy xuất phiên bản thứ k."*
2. **"Tự phục hồi không cần 2PC" (Self-Healing Log):**
   - Trình bày kịch bản WAL: *"Thay vì dùng giao thức 2-Phase Commit phức tạp, hệ thống của chúng em sử dụng Write-Ahead Logging (WAL) cục bộ kết hợp với cơ chế Rollback để tự chữa lành dữ liệu nếu node bị sập nguồn đột ngột khi đang ghi."*
3. **"Optimistic Concurrency Control (OCC)":**
   - *"Hệ thống không khóa tài nguyên lúc Checkout, giúp kỹ sư làm việc song song hiệu quả. Chúng em phát hiện xung đột ở pha Checkin bằng cách so sánh số phiên bản nền (base version) và giải quyết linh hoạt bằng Phân nhánh (Branching) hoặc Ghi đè theo thời gian (Timestamp)."*
