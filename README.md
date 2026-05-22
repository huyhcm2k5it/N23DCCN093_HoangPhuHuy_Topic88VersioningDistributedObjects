# Topic 88 - Versioning Distributed Objects

Distributed CAD Model Versioning for Collaborative Design

Đây là đồ án mô phỏng hệ thống quản lý phiên bản cho các đối tượng CAD phân tán. Hệ thống cho phép nhiều site checkout cùng một CAD object, phát hiện conflict khi checkin từ stale base, giải quyết conflict bằng branching, so sánh Full Snapshot Storage với Delta Storage cho 10 versions và trình diễn lỗi Node Disconnect bằng Durable Outbox Retry.

## 1. Yêu cầu Topic 88

Đề bài yêu cầu:

- Dataset là `CAD_Model` objects gồm `PartID`, `Geometry`, `Version`.
- Cho phép hai site checkout cùng một object.
- Nếu hai site checkin các version khác nhau, phải có conflict resolution strategy.
- Phân tích cách lưu `Object Deltas` để tiết kiệm dung lượng.
- Đo metric dung lượng cho 10 versions: Full Snapshot vs Delta Storage.
- Có video 3-5 phút trình diễn hệ thống xử lý một lỗi cụ thể.

Hệ thống hiện thực các yêu cầu trên bằng:

- `CADModel` có `part_id`, `geometry`, `version`, `oid`, `branch`.
- 3 site phân tán: Site-A, Site-B, Site-C.
- Coordinator metadata server.
- Conflict resolution bằng branching.
- Snapshot store và delta store.
- Benchmark 10 versions.
- Failure demo: Site-B disconnect, Site-A giữ request trong outbox, reconnect rồi replay.

## 2. Kiến trúc hệ thống

```text
                 +-----------------------------+
                 | Coordinator Metadata Server |
                 | oid, version graph, heads   |
                 +--------------+--------------+
                                |
        +-----------------------+-----------------------+
        |                       |                       |
+-------v-------+       +-------v-------+       +-------v-------+
| Site-A        |       | Site-B        |       | Site-C        |
| Engine parts  |       | Chassis parts |       | Interior      |
| SQLite DB     |       | SQLite DB     |       | SQLite DB     |
+---------------+       +---------------+       +---------------+
```

Các service mặc định:

| Service | URL |
|---|---|
| Coordinator | `http://127.0.0.1:5000` |
| Site-A | `http://127.0.0.1:5001` |
| Site-B | `http://127.0.0.1:5002` |
| Site-C | `http://127.0.0.1:5003` |
| Frontend | Vite URL, thường là `http://localhost:5173` |

## 3. Dataset và phân mảnh

Dataset được sinh bằng `scripts/generate_dataset.py`.

| Site | Fragment | Predicate | Vai trò |
|---|---|---|---|
| Site-A | Engine | `part_id LIKE 'ENG-%'` | Động cơ |
| Site-B | Chassis | `part_id LIKE 'CHS-%'` | Khung gầm |
| Site-C | Interior | `part_id LIKE 'INT-%'` | Nội thất |

Schema rút gọn:

```json
{
  "part_id": "ENG-001",
  "oid": "immutable-object-id",
  "version": 1,
  "branch": "main",
  "geometry": {
    "type": "Solid",
    "vertices": [],
    "edges": [],
    "faces": [],
    "properties": {
      "material": "steel",
      "tolerance_mm": 0.01,
      "weight_kg": 18.5
    }
  }
}
```

## 4. Chức năng chính

### Distributed checkout/checkin

Luồng chính:

1. Site-A tạo object.
2. Site-A replicate object sang Site-B.
3. Site-A và Site-B checkout cùng object, cùng `oid`, cùng base version.
4. Site-A checkin trước, tạo version mới trên `main`.
5. Site-B checkin bản checkout cũ.
6. Backend phát hiện stale base và tạo conflict branch.

Branching result:

```text
v1 main
├── v2 main
└── v2_conflict_SITE_B
```

### Snapshot vs Delta Storage

Hệ thống lưu song song hai dạng:

- Full Snapshot: lưu toàn bộ object ở mỗi version.
- Delta Storage: lưu base object và diff giữa các version.

Benchmark đo:

- `full_snapshot_bytes`
- `delta_storage_bytes`
- `saving_percent`
- `rehydration_steps`
- `avg_rehydration_ms`
- `integrity_ok`

### Failure demo

Failure scenario chính:

```text
Node Disconnect + Outbox Retry
```

Luồng:

1. Site-A tạo CAD object.
2. Site-B bị disconnect liên-site.
3. Site-A replicate sang Site-B.
4. Target chưa ACK, operation được giữ trong Site-A outbox.
5. Site-B reconnect.
6. Site-A replay outbox.
7. Site-B nhận object với cùng `oid`.

## 5. Cài đặt

### Backend

```bash
pip install -r requirements.txt
python scripts/generate_dataset.py
```

### Frontend

```bash
cd giaodien
npm install
```

## 6. Cách chạy

### Reset dữ liệu runtime

```bash
python main.py --clean
```

### Sinh dataset

```bash
python scripts/generate_dataset.py
```

### Chạy benchmark 10 versions

```bash
python main.py --benchmark
```

Kết quả được ghi vào:

```text
results/benchmark_results.json
results/version_sizes.png
results/cumulative_storage.png
results/rehydration_latency.png
```

### Chạy backend servers

```bash
python main.py --servers
```

Lệnh này khởi động:

- Coordinator ở port 5000.
- Site-A ở port 5001.
- Site-B ở port 5002.
- Site-C ở port 5003.

### Chạy frontend dashboard

Mở terminal khác:

```bash
cd giaodien
npm run dev
```

Mở URL Vite cung cấp, thường là:

```text
http://localhost:5173
```

### Chạy backend demo bằng terminal

Khi backend servers đang chạy:

```bash
python main.py --demo
```

Demo terminal gồm:

- Kiểm tra 3 site.
- Checkout cùng object.
- Checkin tạo conflict branch.
- Benchmark snapshot vs delta.
- Node disconnect + outbox retry.

## 7. Frontend dashboard

Các tab chính:

| Tab | Mục đích |
|---|---|
| Overview & Metrics | Kiến trúc, dataset, benchmark Snapshot vs Delta, rehydration cost. |
| Distributed Sites | Trạng thái 3 site, phân mảnh, storage. |
| Conflict Demo | Demo hai site checkout cùng object và tạo conflict branch. |
| Failure Demo: Outbox Retry | Demo lỗi Node Disconnect và replay outbox. |

Frontend chỉ hiển thị logic từ backend. Backend là source of truth cho `oid`, `version`, `branch`, `network_online`, `outbox.status`.

## 8. REST API chính

### Site API

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/health` | Kiểm tra trạng thái site. |
| `GET` | `/dataset/info` | Thông tin dataset. |
| `POST` | `/models` | Tạo hoặc import CAD model. |
| `GET` | `/models` | Liệt kê models. |
| `GET` | `/models/<part_id>` | Lấy latest hoặc version cụ thể. |
| `POST` | `/models/<part_id>/checkout` | Checkout object. |
| `POST` | `/models/<part_id>/checkin` | Checkin object. |
| `GET` | `/models/<part_id>/versions` | Lịch sử version và branch. |
| `POST` | `/replicate` | Replicate latest object sang site khác. |
| `GET` | `/replication/outbox` | Xem source outbox. |
| `POST` | `/replication/replay` | Replay pending outbox. |
| `POST` | `/network/disconnect` | Giả lập site disconnect. |
| `POST` | `/network/reconnect` | Kết nối site lại. |
| `GET` | `/storage/compare` | So sánh snapshot và delta. |
| `GET` | `/benchmark` | Đọc benchmark results. |
| `POST` | `/benchmark/run` | Chạy benchmark. |

### Coordinator API

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/health` | Trạng thái coordinator và site health. |
| `POST` | `/meta/register-object` | Đăng ký OID. |
| `POST` | `/meta/update-head` | Cập nhật branch head. |
| `POST` | `/meta/record-conflict` | Ghi nhận conflict. |
| `GET` | `/meta/version-graph/<part_id>` | Xem version graph. |
| `GET` | `/meta/branch-heads/<part_id>` | Xem branch heads. |
| `GET` | `/meta/conflicts/<part_id>` | Xem conflicts. |

## 9. Tài liệu nộp bài

Tất cả tài liệu nộp bài nằm trong thư mục:

```text
docbaocao/
```

Các file:

| File | Nội dung |
|---|---|
| `00_MUC_LUC_NOP_BAI.md` | Mục lục và checklist deliverables. |
| `01_PROPOSAL.md` | Project proposal. |
| `02_DESIGN_DOCUMENT_2_TRANG.md` | Design document khoảng 2 trang. |
| `03_ANALYSIS_REPORT_OZSU_VALDURIEZ.md` | Analysis report gắn với Ozsu & Valduriez. |
| `04_PHAN_TICH_HE_THONG_CHI_TIET.md` | Phân tích hệ thống chi tiết. |

Phần phân tích lý thuyết trong `03_ANALYSIS_REPORT_OZSU_VALDURIEZ.md` ghi rõ nguồn là Ozsu & Valduriez, Principles of Distributed Database Systems, 4th Edition, Chapter 15: Distributed Object Database Management. Báo cáo map cụ thể các phần của hệ thống vào Section 15.1, 15.2, 15.3, 15.4, 15.5, 15.6 và 15.7.

## 10. Cấu trúc code

```text
Topic88_VersioningDistributedObjects/
├── app/
│   ├── coordinator.py
│   ├── models.py
│   ├── server.py
│   ├── site_node.py
│   └── storage.py
├── dataset/
├── docbaocao/
├── docs/
├── giaodien/
├── results/
├── scripts/
├── main.py
├── README.md
└── requirements.txt
```

## 11. Kết luận

Repo này đáp ứng đầy đủ trọng tâm Topic 88: quản lý version cho distributed CAD objects, checkout/checkin nhiều site, conflict resolution bằng branching, delta storage để tiết kiệm dung lượng, benchmark 10 versions và một failure scenario phân tán bằng Node Disconnect + Outbox Retry.
