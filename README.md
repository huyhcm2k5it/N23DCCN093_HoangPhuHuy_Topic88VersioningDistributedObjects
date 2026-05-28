# Topic 88 – Versioning Distributed Objects

**Distributed CAD Model Versioning for Collaborative Design**

Hệ thống mô phỏng quản lý phiên bản cho các đối tượng CAD phân tán. Nhiều site có thể checkout cùng một object, hệ thống tự động phát hiện conflict khi checkin từ stale base và giải quyết bằng branching. Hỗ trợ so sánh Full Snapshot Storage với Delta Storage, benchmark 10 versions và demo lỗi Node Disconnect bằng Durable Outbox Retry.

**Môn học:** Cơ sở dữ liệu phân tán
**Cơ sở lý thuyết:** Ozsu & Valduriez, *Principles of Distributed Database Systems*, 4th Edition, Chapter 15.

---

## Mục lục

1. [Yêu cầu Topic 88](#1-yêu-cầu-topic-88)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [Dataset và phân mảnh](#3-dataset-và-phân-mảnh)
4. [Chức năng chính](#4-chức-năng-chính)
5. [Cài đặt](#5-cài-đặt)
6. [Cách chạy](#6-cách-chạy)
7. [Frontend Dashboard](#7-frontend-dashboard)
8. [REST API](#8-rest-api)
9. [Benchmark Results](#9-benchmark-results)
10. [Cấu trúc code](#10-cấu-trúc-code)

---

## 1. Yêu cầu Topic 88

Đề bài yêu cầu:

- Dataset là `CAD_Model` objects gồm `PartID`, `Geometry`, `Version`.
- Cho phép hai site checkout cùng một object.
- Nếu hai site checkin các version khác nhau, phải có conflict resolution strategy.
- Phân tích cách lưu `Object Deltas` để tiết kiệm dung lượng.
- Đo metric dung lượng cho 10 versions: Full Snapshot vs Delta Storage.
- Có video 3–5 phút trình diễn hệ thống xử lý một lỗi cụ thể.

Hệ thống hiện thực các yêu cầu trên bằng:

| Yêu cầu             | Hiện thực                                                                                                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CAD_Model objects     | `CADModel` với `part_id`, `oid` (UUID bất biến), `geometry`, `version`, `branch`                                                                     |
| Phân tán            | 3 site + 1 Coordinator, mỗi site có SQLite riêng                                                                                                                 |
| Checkout/Checkin      | Optimistic CC: persist `base_version` vào DB, so sánh khi checkin                                                                                               |
| Conflict resolution   | Tạo conflict branch tự động khi phát hiện stale base                                                                                                          |
| Delta storage         | `DeltaStore`: base v1 + jsondiff compact patches, rehydrate qua chuỗi delta                                                                                      |
| Benchmark 10 versions | `scripts/benchmark.py`: đo `full_snapshot_bytes`, `delta_storage_bytes`, `saving_percent`, `rehydration_steps`, `avg_rehydration_ms`, `integrity_ok` |
| Failure demo          | Node Disconnect + Durable Outbox Retry                                                                                                                              |

---

## 2. Kiến trúc hệ thống

```
                 +-----------------------------+
                 | Coordinator Metadata Server |  :5000
                 | oid_registry, version_graph |
                 | branch_heads, conflicts     |
                 +--------------+--------------+
                                |
        +-----------------------+-----------------------+
        |                       |                       |
+-------v-------+       +-------v-------+       +-------v-------+
| Site-A  :5001 |       | Site-B  :5002 |       | Site-C  :5003 |
| Engine parts  |       | Chassis parts |       | Interior      |
| SQLite DB     |       | SQLite DB     |       | SQLite DB     |
+---------------+       +---------------+       +---------------+
```

**Coordinator** (`app/coordinator.py`):

- SQLite riêng (`app/db/Coordinator-Meta.db`) với 5 bảng: `oid_registry`, `version_graph`, `branch_heads`, `conflicts`, `site_health`.
- Chỉ lưu metadata, không lưu geometry payload.

**Site node** (`app/site_node.py`):

- Mỗi site có SQLite riêng (`app/db/Site-A.db`, `Site-B.db`, `Site-C.db`) với 7 bảng: `snapshots`, `bases`, `deltas`, `checkouts`, `replication_outbox`, `replication_inbox`.
- Write-Ahead Log riêng (`{site_id}_wal.json`) cho crash recovery.

**Giao tiếp:** HTTP/REST (Flask + Requests). Không dùng shared memory hay message broker.

| Service           | URL                       |
| ----------------- | ------------------------- |
| Coordinator       | `http://127.0.0.1:5000` |
| Site-A (Engine)   | `http://127.0.0.1:5001` |
| Site-B (Chassis)  | `http://127.0.0.1:5002` |
| Site-C (Interior) | `http://127.0.0.1:5003` |
| Frontend          | `http://localhost:5173` |

---

## 3. Dataset và phân mảnh

Dataset được sinh bằng `scripts/generate_dataset.py` với `random.seed(42)` (tái lập hoàn toàn).

**Quy mô:** 300 CAD objects (100 × 3 categories), mỗi object gồm 100 vertices, 100 edges, ~33 faces. Tổng dataset ~5.8 MB JSON.

**Phân mảnh ngang (Horizontal Fragmentation, §15.2):**

| Site   | Fragment | Predicate                | File dataset                     | Kích thước |
| ------ | -------- | ------------------------ | -------------------------------- | ------------- |
| Site-A | Engine   | `part_id LIKE 'ENG-%'` | `dataset/site_a_engine.json`   | ~1.9 MB       |
| Site-B | Chassis  | `part_id LIKE 'CHS-%'` | `dataset/site_b_chassis.json`  | ~1.9 MB       |
| Site-C | Interior | `part_id LIKE 'INT-%'` | `dataset/site_c_interior.json` | ~1.9 MB       |

**Schema CADModel:**

```json
{
  "part_id": "ENG-001",
  "oid": "immutable-uuid",
  "version": 1,
  "branch": "main",
  "site_origin": "Site-A",
  "geometry": {
    "type": "Solid",
    "vertices": [{"id": "V1", "x": 0.0, "y": 0.0, "z": 0.0}, ...],
    "edges": [{"id": "E1", "from": "V1", "to": "V2"}, ...],
    "faces": [{"id": "F1", "edges": ["E1", "E2", "E3"]}, ...],
    "properties": {
      "category": "engine",
      "material": "aluminum",
      "tolerance_mm": 0.01,
      "weight_kg": 85.5
    }
  }
}
```

Predicate validation: `SiteNode.accepts_local_part(part_id)` kiểm tra prefix trước khi cho tạo model local. Replication cross-site không bị chặn.

---

## 4. Chức năng chính

### 4.1. Distributed Checkout/Checkin với Conflict Branching

**Luồng chính:**

1. Site-A tạo object `ENG-001` (v1, branch `main`).
2. Site-A replicate object sang Site-B.
3. Site-A và Site-B cùng checkout object: cùng `oid`, cùng `base_version = 1`.
4. Site-A checkin trước → tạo v2 trên `main`.
5. Site-B checkin bản checkout cũ (base_version=1, nhưng latest đã là v2).
6. `SiteNode.checkin()` phát hiện `current.version (2) > checkout_base (1)` → tạo conflict branch:

```
v1 (main)
├── v2 (main)               ← Site-A checkin
└── v2_conflict_SITE_B      ← Site-B checkin, không mất
```

Cả hai nhánh được lưu đầy đủ. Version graph ghi nhận tại Coordinator.

### 4.2. Snapshot vs Delta Storage

Hệ thống lưu song song hai dạng:

| Dạng                                       | Cách lưu                     | Truy vấn           | Dung lượng |
| ------------------------------------------- | ------------------------------ | ------------------- | ------------ |
| **Full Snapshot** (`SnapshotStore`) | Toàn bộ object mỗi version  | O(1)                | Cao          |
| **Delta Storage** (`DeltaStore`)    | Base v1 + jsondiff patch chain | O(k), k = số delta | Thấp        |

**Rehydration:** Để đọc version N từ delta, hệ thống apply tuần tự:

```
base_v1 → delta(v1→v2) → delta(v2→v3) → ... → delta(vN-1→vN)
```

**Integrity:** SHA-256 checksum (`CADModel.checksum()`) xác minh `snapshot == rehydrated`.

### 4.3. Failure Demo – Node Disconnect + Outbox Retry

1. Site-A tạo CAD object.
2. Site-B bị disconnect (`POST /network/disconnect`).
3. Site-A gửi replicate → request thất bại, lưu vào `replication_outbox` (status `PENDING`).
4. Site-B reconnect (`POST /network/reconnect`).
5. Site-A replay outbox (`POST /replication/replay`).
6. Site-B nhận object với cùng `oid`.

Outbox có exponential backoff retry, idempotency check tại inbox (theo `op_id` + `request_hash`), tránh duplicate side-effect.

### 4.4. WAL Crash Recovery

Write-Ahead Log (`WALLog` trong `app/models.py`) ghi nhận mỗi checkin trước khi commit DB:

1. `wal_log.begin("CHECKIN", ...)` → ghi WAL entry `committed=false`.
2. Thực hiện snapshot/delta write.
3. `wal_log.commit(entry_id)` → `committed=true`.

Nếu crash giữa bước 1 và 3, `wal_recover()` rollback các entry uncommitted. Thread-safe bằng `threading.Lock`.

---

## 5. Cài đặt

### Backend

```bash
pip install -r requirements.txt
python scripts/generate_dataset.py
```

Dependencies: `flask>=3.0`, `flask-cors>=4.0`, `marshmallow>=3.20`, `matplotlib>=3.8`, `tabulate>=0.9`, `jsondiff>=2.0`, `requests>=2.31`.

### Frontend

```bash
cd giaodien
npm install
```

Dependencies: React 18, Vite, Tailwind CSS, lucide-react, Recharts.

---

## 6. Cách chạy

### Reset dữ liệu runtime

```bash
python main.py --clean
```

Xóa tất cả SQLite DB, WAL files trong `app/db/` và benchmark results trong `results/`.

### Sinh dataset

```bash
python scripts/generate_dataset.py
```

Tạo 300 objects (seed=42) vào `dataset/`: `site_a_engine.json`, `site_b_chassis.json`, `site_c_interior.json`, `full_dataset.json`.

### Chạy benchmark 10 versions

```bash
python main.py --benchmark
```

Kết quả ghi vào:

```
results/benchmark_results.json
results/version_sizes.png
results/cumulative_storage.png
results/rehydration_latency.png
```

### Chạy backend servers

```bash
python main.py --servers
```

Khởi động 4 service:

- Coordinator ở port 5000.
- Site-A ở port 5001 (load 100 Engine parts).
- Site-B ở port 5002 (load 100 Chassis parts).
- Site-C ở port 5003 (load 100 Interior parts).

Dataset được tự động import vào SQLite khi server khởi động.

### Chạy frontend dashboard

Mở terminal khác:

```bash
cd giaodien
npm run dev
```

Mở URL Vite cung cấp: `http://localhost:5173`

### Chạy demo qua terminal

Khi backend servers đang chạy:

```bash
python main.py --demo
```

Demo terminal (`scripts/demo.py`) chạy tự động:

- Kiểm tra health 3 site + coordinator.
- Checkout cùng object từ 2 site.
- Checkin tạo conflict branch.
- Benchmark snapshot vs delta 10 versions.
- Node disconnect + outbox retry.

---

## 7. Frontend Dashboard

React dashboard gồm 4 tab:

| Tab                                  | Component                    | Chức năng                                                                                               |
| ------------------------------------ | ---------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Overview & Metrics**         | `TabOverview.jsx`          | Kiến trúc hệ thống, dataset info, benchmark Snapshot vs Delta (biểu đồ Recharts), rehydration cost |
| **Distributed Sites**          | `TabDashboard.jsx`         | Trạng thái 3 site, phân mảnh, storage comparison, danh sách models                                   |
| **Conflict Demo**              | `TabConflict.jsx`          | Demo hai site checkout cùng object → checkin → tạo conflict branch, hiển thị version graph          |
| **Failure Demo: Outbox Retry** | `TabNetworkDisconnect.jsx` | Demo Node Disconnect, outbox pending, reconnect, replay, xác nhận `oid` khớp                         |

Frontend gọi backend qua REST API (`src/api.js`). Backend là source of truth cho `oid`, `version`, `branch`, `network_online`, `outbox.status`.

---

## 8. REST API

### Site API (`app/server.py`)

| Method   | Endpoint                            | Mục đích                                              |
| -------- | ----------------------------------- | -------------------------------------------------------- |
| `GET`  | `/health`                         | Trạng thái site, strategy, network, outbox             |
| `GET`  | `/models`                         | Liệt kê latest model của tất cả part_ids            |
| `POST` | `/models`                         | Tạo model mới hoặc import model từ site khác        |
| `GET`  | `/models/<part_id>`               | Lấy latest hoặc version cụ thể (`?version=N`)      |
| `POST` | `/models/<part_id>/checkout`      | Checkout object (ghi `base_version` vào DB)           |
| `POST` | `/models/<part_id>/checkin`       | Checkin object (detect conflict, tạo branch nếu stale) |
| `GET`  | `/models/<part_id>/versions`      | Tất cả versions và branches                           |
| `GET`  | `/models/<part_id>/version-graph` | Version graph từ Coordinator                            |
| `POST` | `/replicate`                      | Replicate object sang site khác qua outbox              |
| `POST` | `/replication/incoming`           | Nhận replication (idempotent theo `op_id`)            |
| `GET`  | `/replication/outbox`             | Xem outbox (filter `?status=`, `?target_site=`)      |
| `GET`  | `/replication/inbox`              | Xem inbox                                                |
| `POST` | `/replication/replay`             | Replay pending outbox operations                         |
| `POST` | `/network/disconnect`             | Giả lập site disconnect (chặn inter-site request)     |
| `POST` | `/network/reconnect`              | Reconnect + auto-replay outbox                           |
| `GET`  | `/network/status`                 | Trạng thái network                                     |
| `GET`  | `/storage/compare`                | So sánh snapshot vs delta bytes                         |
| `POST` | `/rehydrate`                      | Rehydrate object theo OID + version                      |
| `GET`  | `/rehydration/benchmark`          | Đo latency snapshot path vs delta path                  |
| `GET`  | `/fragmentation`                  | Thông tin phân mảnh tại site                         |
| `GET`  | `/benchmark`                      | Đọc benchmark results JSON                             |
| `POST` | `/benchmark/run`                  | Chạy benchmark 10 versions                              |
| `GET`  | `/logs`                           | Event log của site                                      |

### Coordinator API (`app/coordinator.py`)

| Method   | Endpoint                          | Mục đích                                    |
| -------- | --------------------------------- | ---------------------------------------------- |
| `GET`  | `/health`                       | Trạng thái coordinator + danh sách sites    |
| `POST` | `/meta/register-object`         | Đăng ký OID (đảm bảo 1 part_id → 1 oid) |
| `POST` | `/meta/update-head`             | Cập nhật version graph + branch head         |
| `POST` | `/meta/record-conflict`         | Ghi nhận conflict event                       |
| `POST` | `/meta/site-health`             | Site push health status                        |
| `GET`  | `/meta/version-graph/<part_id>` | Xem version graph                              |
| `GET`  | `/meta/branch-heads/<part_id>`  | Xem branch heads                               |
| `GET`  | `/meta/conflicts/<part_id>`     | Xem conflicts                                  |

---

## 9. Benchmark Results

Kết quả benchmark 10 versions (từ `results/benchmark_results.json`):

| Metric               | Giá trị       |
| -------------------- | --------------- |
| Full Snapshot tổng  | 68,361 bytes    |
| Delta Storage tổng  | 10,319 bytes    |
| Tiết kiệm          | **84.9%** |
| Avg rehydration time | 3.924 ms        |
| Integrity (SHA-256)  | ✅ OK           |

Chi tiết theo version:

| Version | Snapshot (bytes) | Delta patch (bytes) | Saving % | Rehydration steps |
| ------- | ---------------- | ------------------- | -------- | ----------------- |
| 1       | 6,126            | 0 (base)            | 0%       | 0                 |
| 2       | 5,873            | 38                  | 99.4%    | 1                 |
| 3       | 5,873            | 40                  | 99.3%    | 2                 |
| 4       | 5,873            | 168                 | 97.1%    | 3                 |
| 5       | 5,873            | 58                  | 99.0%    | 4                 |
| 6       | 7,597            | 1,931               | 74.6%    | 5                 |
| 7       | 7,597            | 193                 | 97.5%    | 6                 |
| 8       | 8,502            | 1,028               | 87.9%    | 7                 |
| 9       | 7,423            | 103                 | 98.6%    | 8                 |
| 10      | 7,624            | 634                 | 91.7%    | 9                 |

Trade-off: Delta storage tiết kiệm ~85% dung lượng nhưng rehydration cost tăng tuyến tính O(k) với k = số delta trong chain.

---

## 10. Cấu trúc code

```
Topic88_VersioningDistributedObjects/
├── app/
│   ├── __init__.py
│   ├── config.py             # Cấu hình ports, benchmark settings
│   ├── coordinator.py        # CoordinatorMetadataStore + Flask app
│   ├── models.py             # Geometry, CADModel, Delta, WALEntry, WALLog + schemas
│   ├── server.py             # Flask REST API routes cho site node
│   ├── site_node.py          # SiteNode: checkout, checkin, conflict, replication
│   ├── storage.py            # SnapshotStore, DeltaStore, CheckoutStore,
│   │                         # ReplicationOutboxStore, ReplicationInboxStore,
│   │                         # TransactionManager
│   └── db/                   # SQLite databases (runtime, gitignored)
├── dataset/
│   ├── full_dataset.json     # 300 objects đầy đủ
│   ├── site_a_engine.json    # Fragment Engine (100 parts)
│   ├── site_b_chassis.json   # Fragment Chassis (100 parts)
│   └── site_c_interior.json  # Fragment Interior (100 parts)
├── giaodien/                 # React frontend
│   └── src/
│       ├── App.jsx           # Layout chính, 4 tab navigation
│       ├── api.js            # REST API client
│       ├── components/
│       │   ├── TabOverview.jsx          # Tab 1: Overview & Metrics
│       │   ├── TabDashboard.jsx         # Tab 2: Distributed Sites
│       │   ├── TabConflict.jsx          # Tab 3: Conflict Demo
│       │   └── TabNetworkDisconnect.jsx # Tab 4: Failure Demo
│       ├── demoGeometry.js   # Geometry mẫu cho demo
│       └── index.css         # Tailwind CSS
├── scripts/
│   ├── generate_dataset.py   # Sinh 300 CAD objects (seed=42)
│   ├── benchmark.py          # Benchmark 10 versions: snapshot vs delta
│   ├── demo.py               # Demo terminal tự động
│   └── visualize.py          # Vẽ chart PNG từ benchmark results
├── results/
│   └── benchmark_results.json
├── main.py                   # Entry point: --servers, --benchmark, --demo, --clean
├── requirements.txt          # Python dependencies
└── README.md
```

---
