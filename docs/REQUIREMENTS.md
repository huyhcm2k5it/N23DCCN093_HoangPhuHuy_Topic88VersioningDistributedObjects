# DISTRIBUTED DATABASE PROJECT REQUIREMENTS
# YÊU CẦU ĐỒ ÁN MÔN HỆ CƠ SỞ DỮ LIỆU PHÂN TÁN

---

## I. Final Deliverables / Yêu cầu nộp bài cuối kỳ

| # | English | Tiếng Việt |
|---|---------|------------|
| 1 | Project proposal (based on the template) | Báo cáo đề xuất dự án (dựa trên mẫu Template) |
| 2 | A 2-page design document | Tài liệu thiết kế hệ thống (dài 2 trang) |
| 3 | The Code: GitHub/GitLab repository with clear README | Mã nguồn: Link GitHub/GitLab kèm hướng dẫn (README) |
| 4 | Analysis report justifying design choices using Özsu & Valduriez theory | Báo cáo phân tích: Biện luận lý thuyết CSDL phân tán |
| 5 | Screen-recording (3-5 mins) showing the system handling a specific scenario | Video demo (3-5 phút) hệ thống xử lý lỗi |

---

## II. Topic 88 Description / Mô tả Chủ đề 88

### 88. Versioning Distributed Objects: "Collaborative Design"
### 88. Quản lý phiên bản cho các đối tượng phân tán: "Thiết kế cộng tác"

| Aspect | English | Tiếng Việt |
|--------|---------|------------|
| **Dataset** | CAD_Model objects (PartID, Geometry, Version) | Các đối tượng CAD_Model (Mã cấu kiện, Hình học, Phiên bản) |
| **The Task** | Allow two sites to check out the same object. If both "Check In" different versions, implement a Conflict Resolution strategy (branching or timestamp-based) | Cho phép hai site "check out" cùng đối tượng. Nếu cùng "Check In", thực thi Giải quyết xung đột (branching hoặc timestamp) |
| **Analysis** | How to store "Object Deltas" across sites to save space? | Lưu trữ "Object Deltas" giữa các sites để tiết kiệm dung lượng? |
| **Metric** | Storage used for 10 versions: "Full Snapshot" vs. "Delta Storage" | Dung lượng cho 10 phiên bản: "Full Snapshot" vs. "Delta Storage" |

---

## III. Project Proposal Template / Mẫu Báo cáo Đề xuất

### 1. Project Identity / Định nghĩa Dự án
- Team Name / Tên đội: [Tên nhóm]
- Team Members / Thành viên: [Tên 1, Tên 2]
- Project Title / Tên dự án: [Tiêu đề mô tả]

### 2. Objective & Problem Statement / Mục tiêu & Phát biểu Bài toán
- The "Why": What distributed database challenge are you solving?
- Core Logic: Primary algorithm or protocol to implement

### 3. Dataset Specification / Đặc tả Dữ liệu
- **Source / Nguồn**: Synthetic CAD dataset (`generate_dataset.py`, seed=42, reproducible)
  - Mô phỏng dự án thiết kế khung gầm xe hơi (vehicle chassis collaborative design)
- **Size / Kích thước**: 300 parts / ~5.8 MB (full_dataset.json)
- **Schema / Lược đồ**:
  | Attribute | Type | Description |
  |-----------|------|-------------|
  | `part_id` | string | Mã linh kiện (VD: ENG-001, CHS-003, INT-007) |
  | `geometry.vertices[]` | [{x,y,z}] | Tọa độ 3D các đỉnh |
  | `geometry.edges[]` | [[i,j]] | Cặp chỉ số đỉnh tạo cạnh |
  | `geometry.faces[]` | [[i,j,k]] | Bộ 3 chỉ số đỉnh tạo mặt tam giác |
  | `geometry.properties` | object | material, weight_kg, tolerance_mm |
  | `version` | int | Số phiên bản (bắt đầu từ 1) |
  | `branch` | string | Nhánh phiên bản (mặc định: "main") |
  | `site_origin` | string | Site tạo ra part (Site-A/B/C) |
- **Fragmentation Strategy / Chiến lược Phân mảnh**: **Horizontal Fragmentation** (Phân mảnh ngang theo category)
  | Site | Category | Predicate | Parts |
  |------|----------|-----------|-------|
  | Site-A | Engine (Động cơ) | `category = 'engine'` | 100 |
  | Site-B | Chassis (Khung gầm) | `category = 'chassis'` | 100 |
  | Site-C | Interior (Nội thất) | `category = 'interior'` | 100 |

  **Lý do**: Mỗi nhóm kỹ sư (powertrain, chassis, interior) làm việc chủ yếu trên data cục bộ → giảm truy vấn liên site. UNION(3 site) = Full Dataset, không trùng lặp.

### 4. System Architecture / Kiến trúc Hệ thống
- Nodes: Min 2, Recommended 3
- Communication Layer / Tầng giao tiếp: (e.g., REST API, WebSockets)
- Storage / Lưu trữ: Physical data location

### 5. Tech Stack & Implementation Plan
- Programming Language / Ngôn ngữ: Python
- Deployment / Triển khai: Localhost processes
- Libraries / Thư viện: Flask, pickle/marshmallow

### 6. Success Metrics & Analysis / Phân tích & Đo lường
- Quantitative Metric / Chỉ số: Storage comparison, query time
- Failure Scenario / Kịch bản lỗi: Node disconnect simulation

### 7. Milestones / Cột mốc
- Milestone 1 (Week 5): Environment setup & data fragmentation
- Milestone 2 (Week 8): Core algorithm operational
- Milestone 3 (Week 12): Failure handling & benchmarking

---

## IV. Grading Criteria - Category 9 / Tiêu chí chấm điểm

| Criteria / Tiêu chí | Excellent (90-100%) | Satisfactory (70-89%) | Developing (<70%) |
|---------------------|--------------------|-----------------------|-------------------|
| **OID Management** / Quản lý mã định danh | Flawless handling of object identity across sites | OIDs work but inefficient or collision-prone | Fails to maintain object identity |
| **Complexity Handling** / Xử lý độ phức tạp | Correctly manages nested objects or class hierarchies | Handles flat objects but struggles with nesting | Only handles primitive types |
| **Network Awareness** / Tính toán mạng | Clearly accounts for "Object Rehydration" cost | Functional but assumes zero-latency fetching | No consideration for network costs |
| **Analysis** / Phân tích | Deep dive into Serialization or Garbage Collection logic | Basic code explanation | No theoretical analysis |

> **Note:** These projects are ideal for students who enjoy Software Engineering and OOP.
> Use Python `pickle` or `marshmallow` libraries for object-to-data transformations.
