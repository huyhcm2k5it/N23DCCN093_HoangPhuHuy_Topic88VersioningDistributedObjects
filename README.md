<p align="center">
  <h1 align="center">🗄️ Topic 88 — Versioning Distributed Objects</h1>
  <p align="center"><strong>Hệ thống Quản lý Phiên bản Đối tượng CAD Phân tán</strong></p>
  <p align="center"><em>"Collaborative Design" — Distributed CAD Versioning System</em></p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Flask-REST%20API-000000?logo=flask" alt="Flask"/>
  <img src="https://img.shields.io/badge/SQLite-Persistent-003B57?logo=sqlite" alt="SQLite"/>
  <img src="https://img.shields.io/badge/React-Vite-61DAFB?logo=react" alt="React"/>
  <img src="https://img.shields.io/badge/License-Academic-green" alt="License"/>
</p>

> **Đồ án Cuối kỳ · Cơ sở Dữ liệu Phân tán · Học kỳ II — 2025–2026**
> Cơ sở lý thuyết: *Özsu & Valduriez — Principles of Distributed Database Systems, 4th Edition, Chapter 15: Distributed Object Database Management*

---

## 📋 Mục lục

1. [Giới thiệu bài toán](#1-giới-thiệu-bài-toán)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [Cơ sở lý thuyết áp dụng](#3-cơ-sở-lý-thuyết-áp-dụng)
4. [Cấu trúc thư mục](#4-cấu-trúc-thư-mục)
5. [Hướng dẫn cài đặt & chạy](#5-hướng-dẫn-cài-đặt--chạy)
6. [Các tính năng chính](#6-các-tính-năng-chính)
7. [API Endpoints](#7-api-endpoints)
8. [Kết quả thực nghiệm](#8-kết-quả-thực-nghiệm)
9. [Công nghệ sử dụng](#9-công-nghệ-sử-dụng)

---

## 1. Giới thiệu bài toán

Trong ngành công nghiệp cơ khí và thiết kế (ô tô, hàng không), các bản vẽ 3D (CAD Models) là đối tượng dữ liệu **phức tạp** và **rất lớn**. Quá trình thiết kế đòi hỏi sự cộng tác của nhiều kỹ sư phân bố ở **nhiều khu vực địa lý khác nhau**.

**Bài toán đặt ra:**

| Thách thức | Mô tả |
|:---|:---|
| **Cộng tác phân tán** | Nhiều kỹ sư ở các Site khác nhau (Hà Nội, TP.HCM, Đà Nẵng) cùng truy cập và chỉnh sửa bản vẽ đồng thời |
| **Xung đột dữ liệu** | Khi hai người cùng sửa một linh kiện, hệ thống phải đảm bảo không làm mất dữ liệu của bất kỳ ai |
| **Chi phí lưu trữ** | Mỗi bản vẽ trải qua hàng nghìn phiên bản, việc lưu toàn bộ gây lãng phí đĩa cứng và băng thông mạng |
| **Kháng lỗi** | Hệ thống phải tự phục hồi nếu một Node bị sập nguồn giữa lúc đang ghi dữ liệu |

**Giải pháp:** Xây dựng một hệ Quản trị CSDL Phân tán thu nhỏ với 3 Node độc lập, triển khai đầy đủ các cơ chế: **Delta Storage** (lưu trữ vi sai), **Optimistic Concurrency Control** (OCC), **Conflict Resolution** (Branching/Timestamp), và **Write-Ahead Logging** (WAL Crash Recovery).

---

## 2. Kiến trúc hệ thống

```
                    ┌──────────────────────────────────┐
                    │      React Dashboard (Vite)      │
                    │      http://localhost:3000        │
                    └──────────┬───────────────────────┘
                               │ HTTP REST API (JSON)
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
     │   Site-A    │  │   Site-B    │  │   Site-C    │
     │  Port 5001  │  │  Port 5002  │  │  Port 5003  │
     ├─────────────┤  ├─────────────┤  ├─────────────┤
     │ Flask API   │  │ Flask API   │  │ Flask API   │
     │ SiteNode    │  │ SiteNode    │  │ SiteNode    │
     │ OCC Engine  │  │ OCC Engine  │  │ OCC Engine  │
     ├─────────────┤  ├─────────────┤  ├─────────────┤
     │ Snapshot DB │  │ Snapshot DB │  │ Snapshot DB │
     │ Delta DB    │  │ Delta DB    │  │ Delta DB    │
     │ WAL Log     │  │ WAL Log     │  │ WAL Log     │
     ├─────────────┤  ├─────────────┤  ├─────────────┤
     │ SQLite-A.db │  │ SQLite-B.db │  │ SQLite-C.db │
     │ Engine (10) │  │ Chassis(10) │  │Interior(10) │
     │  Branching  │  │  Branching  │  │  Timestamp  │
     └─────────────┘  └─────────────┘  └─────────────┘
```

### Phân mảnh ngang (Horizontal Fragmentation)

Tập dữ liệu gồm **30 linh kiện CAD** được phân mảnh theo vị từ thuộc tính `category`:

| Site | Vị trí giả lập | Phân mảnh | Số linh kiện | Chiến lược xung đột |
|:---|:---|:---|:---:|:---|
| **Site-A** | Hà Nội | `category = 'engine'` (Động cơ) | 10 | Branching |
| **Site-B** | TP.HCM | `category = 'chassis'` (Khung gầm) | 10 | Branching |
| **Site-C** | Đà Nẵng | `category = 'interior'` (Nội thất) | 10 | Timestamp |

- Ba tập dữ liệu hoàn toàn **rời rạc** (Disjointness), tuân thủ nguyên tắc `UNION(A ∪ B ∪ C) = Full Dataset`.
- Mỗi Site sở hữu **CSDL vật lý riêng biệt** (SQLite) → giả lập đúng khái niệm **Local Autonomy** trong CSDL phân tán.

---

## 3. Cơ sở lý thuyết áp dụng

Toàn bộ hệ thống được xây dựng bám sát **Chương 15: Distributed Object Database Management** của giáo trình Özsu & Valduriez.

| # | Khái niệm lý thuyết | Mục giáo trình | Hiện thực trong code |
|:---:|:---|:---:|:---|
| 1 | **Object Identity (OID)** — Định danh bất biến toàn cục | §15.1.1, §15.4.1 | `CADModel.oid` dùng UUID v4, không thay đổi khi đối tượng được sửa, rẽ nhánh, hay nhân bản xuyên Site |
| 2 | **Complex Objects** — Đối tượng phức hợp lồng ghép | §15.1.3 | `CADModel` chứa đối tượng con `Geometry` (vertices, edges, faces, properties) — cấu trúc phân cấp đặc thù CAD |
| 3 | **Serialization / Marshalling** — Tuần tự hóa qua mạng | §15.3 | Thư viện `marshmallow` với `CADModelSchema` + `@post_load` để chuyển đổi Object ↔ JSON khi truyền qua HTTP |
| 4 | **Object Versioning** — Quản lý phiên bản tuyến tính & rẽ nhánh | §15.1 | Thuộc tính `version` (tăng dần) + `branch` (main / Site-X/vN) hỗ trợ Linear & Branched versioning |
| 5 | **Horizontal Fragmentation** — Phân mảnh ngang | §15.2.1 | Phân mảnh theo predicate `category` → 3 Site rời rạc, tối ưu Localization of Reference |
| 6 | **Delta Storage** — Lưu trữ vi sai | §15.5 | `DeltaStore` chỉ lưu diff (jsondiff), tiết kiệm ~62–88% dung lượng. Thuật toán Rehydration O(k) |
| 7 | **Optimistic Concurrency Control** — Điều khiển đồng thời lạc quan | §15.3.2 | Không khóa tài nguyên khi Checkout. Phát hiện xung đột tại thời điểm Checkin (`base_version < current_version`) |
| 8 | **WAL & Crash Recovery** — Đảm bảo Atomicity | §15.7 | Write-Ahead Logging ghi `PENDING` trước khi ghi SQLite. Hàm `wal_recover()` tự động Rollback khi khởi động lại |

---

## 4. Cấu trúc thư mục

```
Topic88_VersioningDistributedObjects/
│
├── main.py                     # Điểm vào chính — điều phối toàn hệ thống
├── demo_unified.py             # Script demo tự động (quay video bảo vệ)
│
├── app/                        # Package lõi logic hệ thống phân tán
│   ├── __init__.py
│   ├── config.py               # Cấu hình IP/Port/Strategy cho 3 Sites
│   ├── models.py               # Data Models: Geometry, CADModel, Delta, WALEntry, WALLog
│   ├── storage.py              # Storage Engines: SnapshotStore + DeltaStore (SQLite)
│   ├── site_node.py            # Business Logic: Checkout, Checkin, OCC, WAL Recovery
│   └── server.py               # Flask REST API Server & Cross-site Replication
│
├── scripts/                    # Các kịch bản bổ trợ
│   ├── generate_dataset.py     # Sinh dữ liệu CAD 3D ban đầu (30 linh kiện)
│   └── benchmark.py            # Đo lường hiệu năng: Snapshot vs Delta, Conflict Demo
│
├── tests/                      # Bộ kiểm thử tự động
│   └── test_integration.py     # Integration tests: OCC, WAL Recovery, Branching
│
├── dataset/                    # Dữ liệu phân mảnh JSON (sinh bởi generate_dataset.py)
│   ├── site_a_engine.json      # 10 linh kiện động cơ → Site-A
│   ├── site_b_chassis.json     # 10 linh kiện khung gầm → Site-B
│   └── site_c_interior.json    # 10 linh kiện nội thất → Site-C
│
├── db/                         # CSDL vật lý SQLite + WAL logs (tự tạo khi chạy)
│   ├── Site-A.db / Site-B.db / Site-C.db
│   └── Site-A_wal.json / ...   # Write-Ahead Log files
│
├── results/                    # Kết quả benchmark & biểu đồ
│   ├── benchmark_results.json
│   └── chart_*.png             # Biểu đồ so sánh Snapshot vs Delta
│
└── giaodien/                   # React Frontend Dashboard (Vite)
    └── src/
        ├── App.jsx             # Layout chính với Tab Navigation
        ├── api.js              # API Bridge → Backend endpoints
        └── components/
            ├── TabDashboard.jsx        # Tổng quan trạng thái 3 Sites
            ├── TabWorkspace.jsx        # Checkout / Checkin + SHA-256 Audit Trail
            ├── TabOverview.jsx         # Tổng quan & Kết quả Benchmark
            ├── TabConflict.jsx         # Demo Conflict Resolution (5 bước)
            ├── TabCoordinatorCrash.jsx # Demo WAL Crash & Recovery (5 bước)
            ├── TabParts.jsx            # Quản lý danh sách linh kiện
            ├── TabStorage.jsx          # Thống kê dung lượng lưu trữ
            └── TabLogs.jsx             # Nhật ký WAL & Activity Log
```

---

## 5. Hướng dẫn cài đặt & chạy

### Yêu cầu hệ thống

| Thành phần | Phiên bản tối thiểu |
|:---|:---|
| Python | ≥ 3.10 |
| Node.js | ≥ 18 |
| pip | Đi kèm Python |
| npm | Đi kèm Node.js |

### Bước 1 — Cài đặt thư viện Python

```bash
pip install -r requirements.txt
```

Các thư viện chính: `flask`, `flask-cors`, `marshmallow`, `jsondiff`, `requests`.

### Bước 2 — Sinh dữ liệu phân mảnh (chỉ cần chạy 1 lần)

```bash
python scripts/generate_dataset.py
```

Script này tạo ra 30 linh kiện CAD 3D ngẫu nhiên (vertices, edges, faces) và phân mảnh vào 3 file JSON trong thư mục `dataset/`.

### Bước 3 — Khởi động 3 API Servers phân tán

```bash
python main.py --servers
```

| Site | URL | Danh mục | Chiến lược xung đột |
|:---|:---|:---|:---|
| Site-A | `http://127.0.0.1:5001` | Engine (ENG-*) | Branching |
| Site-B | `http://127.0.0.1:5002` | Chassis (CHS-*) | Branching |
| Site-C | `http://127.0.0.1:5003` | Interior (INT-*) | Timestamp (Last-Write-Wins) |

### Bước 4 — Khởi động giao diện React Dashboard

Mở **terminal thứ hai**:

```bash
cd giaodien
npm install        # Chỉ cần chạy lần đầu
npm run dev
```

Mở trình duyệt tại: **http://localhost:3000**

### Các lệnh CLI khác

```bash
python main.py --benchmark   # Chạy đo lường Snapshot vs Delta (10 versions)
python main.py --demo        # Chạy demo tự động toàn bộ luồng (không cần UI)
python main.py --clean       # Xóa toàn bộ DB + WAL logs (reset hệ thống)
python main.py --help        # Xem hướng dẫn
```

---

## 6. Các tính năng chính

### 6.1. Dual Storage Engine — Lưu trữ kép

Hệ thống triển khai **2 Engine** chạy song song trên SQLite để đối chiếu thực nghiệm:

| Engine | Cơ chế | Ưu điểm | Nhược điểm |
|:---|:---|:---|:---|
| **SnapshotStore** | Lưu toàn bộ Geometry tại mỗi version | Đọc nhanh O(1) | Tốn dung lượng |
| **DeltaStore** | Lưu Base v1 + chuỗi diff (jsondiff) | Tiết kiệm 62–88% dung lượng | Đọc tốn O(k) — Rehydration |

**Thuật toán Rehydration:** Để lấy version `v_k`, hệ thống lấy Base `v1` rồi áp dụng lần lượt `k-1` bản vá Delta → tái tạo đối tượng hoàn chỉnh.

### 6.2. Optimistic Concurrency Control (OCC)

- **Checkout:** Không khóa CSDL. Ghi thông tin người dùng vào RAM/DB cục bộ.
- **Checkin:** So sánh `base_version` (phiên bản lúc checkout) với `current_version` (phiên bản hiện tại trên DB). Nếu `base < current` → **Xung đột**.

### 6.3. Conflict Resolution — Giải quyết xung đột

| Chiến lược | Cơ chế | Khi nào dùng |
|:---|:---|:---|
| **Branching** | Tạo nhánh phụ (VD: `Site-A/v3`) — không mất dữ liệu | Linh kiện quan trọng, cần review thủ công |
| **Timestamp** | Last-Write-Wins — ghi đè lên nhánh `main` | Linh kiện ít quan trọng, ưu tiên tốc độ |

### 6.4. WAL Crash Recovery — Kháng lỗi

1. **Trước khi ghi SQLite:** Ghi log trạng thái `PENDING` vào file `_wal.json`
2. **Sau khi ghi thành công:** Đổi trạng thái thành `COMMITTED`
3. **Nếu Crash xảy ra giữa chừng:** Khi Node khởi động lại, hàm `wal_recover()` quét file WAL → tìm log `PENDING` → **Rollback** tự động → CSDL trở về trạng thái nhất quán

### 6.5. SHA-256 Audit Trail

Mỗi lần Checkin, Frontend tính mã băm SHA-256 của dữ liệu Geometry để xác minh tính toàn vẹn dữ liệu (Data Integrity) xuyên suốt quá trình truyền tải qua mạng.

---

## 7. API Endpoints

Mỗi Site cung cấp các endpoint REST sau:

| Method | Endpoint | Mô tả |
|:---|:---|:---|
| `GET` | `/health` | Kiểm tra trạng thái kết nối Site |
| `GET` | `/models` | Danh sách tất cả linh kiện trên Site |
| `GET` | `/models/<id>` | Chi tiết một linh kiện (Geometry + metadata) |
| `POST` | `/models/<id>/checkout` | Checkout linh kiện — ghi nhận người đang giữ |
| `POST` | `/models/<id>/checkin` | Checkin — tạo version mới + lưu Delta + kiểm tra xung đột |
| `GET` | `/models/<id>/versions` | Lịch sử toàn bộ phiên bản của linh kiện |
| `GET` | `/storage/compare` | So sánh dung lượng Snapshot vs Delta |
| `GET` | `/fragmentation` | Thông tin phân mảnh ngang của Site |
| `POST` | `/crash/demo` | Giả lập Crash — ghi PENDING vào WAL rồi dừng đột ngột |
| `POST` | `/coordinator/restart` | Trigger Recovery — đọc WAL và Rollback giao dịch lỗi |
| `GET` | `/wal/status` | Trạng thái WAL (số giao dịch pending) |
| `GET` | `/benchmark` | Đọc kết quả benchmark từ file JSON |

---

## 8. Kết quả thực nghiệm

### Benchmark: Snapshot vs Delta Storage (10 phiên bản)

| Version | Snapshot (Bytes) | Delta (Bytes) | Tiết kiệm | Chi phí Rehydration |
|:---:|---:|---:|:---:|:---:|
| v1 (Base) | 3,306 | 3,306 | 0% | 0 bước |
| v2 | 3,306 | 1,389 | **58.0%** | 1 bước |
| v5 | 3,307 | 385 | **88.4%** | 4 bước |
| v10 | 3,307 | 496 | **85.0%** | 9 bước |
| **Tổng** | **33,055** | **12,477** | **62.3%** | — |

**Nhận xét:**
- Delta Storage tiết kiệm trung bình **62.3%** dung lượng đĩa và băng thông mạng.
- Ở các phiên bản thay đổi nhỏ (v5), mức tiết kiệm lên đến **88.4%**.
- **Trade-off:** Đọc version `v10` từ DeltaStore cần 9 phép toán Rehydration — đây là sự đánh đổi giữa **không gian lưu trữ** và **tốc độ đọc**.
- Tính toàn vẹn: SHA-256 checksum xác nhận **100%** dữ liệu phục hồi từ Delta trùng khớp chính xác với Snapshot.

---

## 9. Công nghệ sử dụng

### Backend

| Công nghệ | Vai trò |
|:---|:---|
| **Python 3.10+** | Ngôn ngữ chính |
| **Flask** | REST API framework — giao tiếp giữa các Site qua HTTP |
| **Flask-CORS** | Cho phép Frontend (React) gọi API xuyên origin |
| **SQLite** | CSDL vật lý cục bộ cho mỗi Site (Local DBMS) |
| **marshmallow** | Object Serialization / Deserialization (Object ↔ JSON) |
| **jsondiff** | Thuật toán tính Delta (diff) giữa 2 phiên bản Geometry |
| **hashlib (SHA-256)** | Mã băm xác minh tính toàn vẹn dữ liệu |

### Frontend

| Công nghệ | Vai trò |
|:---|:---|
| **React 18** | UI Framework |
| **Vite** | Build tool & Dev server |
| **Tailwind CSS** | Styling |
| **Web Crypto API** | SHA-256 Audit Trail phía client |

---

## 📚 Tài liệu tham khảo

1. M. Tamer Özsu, Patrick Valduriez — *Principles of Distributed Database Systems*, 4th Edition, Springer, 2020. **Chapter 15: Distributed Object Database Management**.
2. ODMG Standard — Object Data Management Group (Object Model, ODL, OQL).

---

> **Đồ án môn Cơ sở Dữ liệu Phân tán — Học kỳ II, Năm học 2025–2026**
