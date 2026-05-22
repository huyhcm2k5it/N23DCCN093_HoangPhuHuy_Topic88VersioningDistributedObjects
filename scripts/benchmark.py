"""
Module: benchmark.py
Mo ta: So sanh hieu qua luu tru giua Full Snapshot va Delta Storage.

Thuc hien yeu cau cua de tai 88:
  "Do luong dung luong cho 10 phien ban voi Full Snapshot vs Delta Storage"

Chay: python main.py --benchmark
"""
import os
import sys
import json
import random
import copy

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.models import CADModel, Geometry, Delta
from app.storage import SnapshotStore, DeltaStore

DB_DIR = os.path.join(PROJECT_ROOT, "app", "db")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")


def generate_cad_geometry(complexity=5):
    """Tao hinh hoc CAD ngau nhien voi do phuc tap tuy chinh."""
    num_vertices = complexity * 10
    vertices = [
        {
            "id": f"V{i+1}",
            "x": round(random.uniform(-100, 100), 4),
            "y": round(random.uniform(-100, 100), 4),
            "z": round(random.uniform(-100, 100), 4),
        }
        for i in range(num_vertices)
    ]
    edges = [
        {
            "id": f"E{i+1}",
            "from": vertices[i]["id"],
            "to": vertices[(i + 1) % num_vertices]["id"],
        }
        for i in range(num_vertices)
    ]
    faces = [
        {
            "id": f"F{idx + 1}",
            "edges": [edges[i]["id"], edges[(i + 1) % num_vertices]["id"], edges[(i + 2) % num_vertices]["id"]],
        }
        for idx, i in enumerate(range(0, num_vertices - 2, 3))
    ]
    return Geometry(
        type="Solid",
        vertices=vertices,
        edges=edges,
        faces=faces,
        properties={
            "material": "aluminum",
            "tolerance_mm": 0.01,
            "weight_kg": round(random.uniform(0.1, 50.0), 2),
        },
    )


def modify_geometry_realistic(geo, scenario):
    """Mo phong chinh sua thuc te theo kich ban (Tiet lo cho thay giao)."""
    new_geo = copy.deepcopy(geo)
    
    if scenario == "v2_tolerance":
        new_geo.properties["tolerance_mm"] = 0.05
    elif scenario == "v3_material":
        new_geo.properties["material"] = "titanium"
    elif scenario == "v4_merge_ab":
        # Sửa 15%
        num_changes = max(1, int(len(new_geo.vertices) * 0.15))
        for _ in range(num_changes):
            idx = random.randint(0, len(new_geo.vertices) - 1)
            new_geo.vertices[idx]["z"] += 1.5
    elif scenario == "v5_minor":
        # Sửa 5%
        num_changes = max(1, int(len(new_geo.vertices) * 0.05))
        for _ in range(num_changes):
            idx = random.randint(0, len(new_geo.vertices) - 1)
            new_geo.vertices[idx]["x"] += 0.5
    elif scenario == "v6_redesign":
        # Them 60% diem (Kich thuoc file tang vot)
        num_new = max(1, int(len(new_geo.vertices) * 0.60))
        for _ in range(num_new):
            new_id = f"V{len(new_geo.vertices) + 1}"
            new_geo.vertices.append({
                "id": new_id,
                "x": round(random.uniform(-50, 50), 4),
                "y": round(random.uniform(-50, 50), 4),
                "z": round(random.uniform(-50, 50), 4)
            })
    elif scenario == "v7_fix":
        # Sửa 10% sau khi redesign
        num_changes = max(1, int(len(new_geo.vertices) * 0.10))
        for _ in range(num_changes):
            idx = random.randint(0, len(new_geo.vertices) - 1)
            new_geo.vertices[idx]["y"] -= 0.5
    elif scenario == "v8_branch_a":
        # Them 20% (them variant)
        num_new = max(1, int(len(new_geo.vertices) * 0.20))
        for _ in range(num_new):
            new_id = f"V{len(new_geo.vertices) + 1}"
            new_geo.vertices.append({
                "id": new_id,
                "x": round(random.uniform(10, 30), 4),
                "y": round(random.uniform(10, 30), 4),
                "z": round(random.uniform(10, 30), 4)
            })
    elif scenario == "v9_branch_b":
        # Xoa 20% (toi uu vat lieu, giam kich thuoc file)
        num_remove = max(1, int(len(new_geo.vertices) * 0.20))
        new_geo.vertices = new_geo.vertices[:-num_remove]
    elif scenario == "v10_merge":
        # Sửa 30% khi merge 2 branch
        num_changes = max(1, int(len(new_geo.vertices) * 0.30))
        for _ in range(num_changes):
            idx = random.randint(0, len(new_geo.vertices) - 1)
            new_geo.vertices[idx]["x"] += random.uniform(-2, 2)
            
    return new_geo


def run_benchmark(num_versions=10, complexity=5):
    """
    Chay benchmark so sanh Full Snapshot vs Delta Storage.

    1. Tao 1 CAD model ban dau
    2. Chinh sua qua num_versions phien ban
    3. Luu song song vao SnapshotStore va DeltaStore
    4. So sanh dung luong va kiem tra toan ven du lieu
    5. [NETWORK AWARENESS] Do thoi gian rehydration O(k) - Özsu §15.6
    """
    import time

    print()
    print("=" * 60)
    print("  BENCHMARK: Full Snapshot vs Delta Storage")
    print(f"  So phien ban: {num_versions} | Do phuc tap: {complexity}")
    print("=" * 60)
    print()

    # Khoi tao 2 store (xoa DB cu neu co de dam bao chain delta sach)
    from app.storage import _initialized_dbs
    for fname in ["benchmark.db", "benchmark_wal.json"]:
        fpath = os.path.join(DB_DIR, fname)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except PermissionError:
                pass
    _initialized_dbs.discard("benchmark")

    snapshot_store = SnapshotStore("benchmark")
    delta_store = DeltaStore("benchmark")

    # Tao model ban dau (version 1)
    base_geo = generate_cad_geometry(complexity)
    base_model = CADModel(
        part_id="BENCH-001",
        geometry=base_geo,
        version=1,
        site_origin="benchmark",
    )

    snapshot_store.save(base_model)
    delta_store.save_base(base_model)

    # Mang luu ket qua
    snapshot_sizes = [base_model.snapshot_size()]
    delta_sizes = [base_model.snapshot_size()]  # Base giong snapshot
    cumulative_snapshot = [snapshot_sizes[0]]
    cumulative_delta = [delta_sizes[0]]
    rehydration_costs = [0]                 # So delta can ap dung (O(k))
    rehydration_times_ms = [0.0]            # Thoi gian thuc te (ms) - Network Awareness

    current_model = base_model

    scenarios = [
        "v1_initial", "v2_tolerance", "v3_material", "v4_merge_ab", 
        "v5_minor", "v6_redesign", "v7_fix", "v8_branch_a", 
        "v9_branch_b", "v10_merge"
    ]

    # Tao cac phien ban tiep theo
    for v in range(2, num_versions + 1):
        scenario_name = scenarios[v - 1]
        print(f"  [{scenario_name.upper()}] Dang tao phien ban {v}...")
        
        new_geo = modify_geometry_realistic(current_model.geometry, scenario_name)
        new_model = CADModel(
            part_id=current_model.part_id,
            geometry=new_geo,
            version=v,
            oid=current_model.oid,
            site_origin="benchmark",
        )

        # Luu vao Snapshot (full copy)
        snap_size = snapshot_store.save(new_model)
        snapshot_sizes.append(snap_size)

        # Tinh va luu Delta (chi phan thay doi)
        delta = Delta.compute(current_model, new_model, "benchmark")
        delta_size = delta_store.save_delta(delta)
        delta_sizes.append(delta_size)

        # Cap nhat tong tich luy thu cong (tranh loi DB bi lock)
        cumulative_snapshot.append(cumulative_snapshot[-1] + snap_size)
        cumulative_delta.append(cumulative_delta[-1] + delta_size)
        rehydration_costs.append(
            delta_store.rehydration_cost("BENCH-001", v),
        )

        # [NETWORK AWARENESS] Do thoi gian rehydrate thuc te tu base + k deltas
        # Day la chi phi O(k) cua Delta Storage - Özsu §15.6
        t0 = time.perf_counter()
        delta_store.get("BENCH-001", v)
        t1 = time.perf_counter()
        rehydration_times_ms.append(round((t1 - t0) * 1000, 3))

        current_model = new_model

    # ===== IN BANG KET QUA =====
    print(
        f"{'Version':<10} {'Snapshot (B)':<15} {'Delta (B)':<15} "
        f"{'Tiet kiem':<12} {'Rehydration':<14} {'Time (ms)':<10}"
    )
    print("-" * 76)

    for i in range(num_versions):
        savings = snapshot_sizes[i] - delta_sizes[i]
        savings_pct = (savings / max(snapshot_sizes[i], 1)) * 100
        print(
            f"v{i + 1:<9} {snapshot_sizes[i]:<15} {delta_sizes[i]:<15} "
            f"{savings_pct:>6.1f}%     {rehydration_costs[i]} deltas"
            f"       {rehydration_times_ms[i]:.2f}ms"
        )

    total_snap = cumulative_snapshot[-1]
    total_delta = cumulative_delta[-1]
    total_savings = total_snap - total_delta
    total_savings_pct = (total_savings / max(total_snap, 1)) * 100
    avg_rehydration_ms = sum(rehydration_times_ms[1:]) / max(len(rehydration_times_ms) - 1, 1)

    per_version_metrics = []
    for i in range(num_versions):
        full_bytes = snapshot_sizes[i]
        delta_patch_bytes = 0 if i == 0 else delta_sizes[i]
        saving_percent = round((1 - delta_patch_bytes / max(full_bytes, 1)) * 100, 1) if i > 0 else 0.0
        per_version_metrics.append({
            "version": i + 1,
            "full_snapshot_bytes": full_bytes,
            "delta_patch_bytes": delta_patch_bytes,
            "rehydrated_object_bytes": full_bytes,
            "rehydration_steps": rehydration_costs[i],
            "saving_percent": saving_percent,
        })

    print()
    print("=" * 76)
    print("TONG KET:")
    print(f"  Full Snapshot: {total_snap:,} bytes")
    print(f"  Delta Storage: {total_delta:,} bytes")
    print(f"  Tiet kiem:     {total_savings:,} bytes ({total_savings_pct:.1f}%)")
    print(f"  Rehydration TB: {avg_rehydration_ms:.3f} ms/version [O(k) deltas]")
    print("=" * 76)

    # ===== KIEM TRA TOAN VEN DU LIEU =====
    print()
    print("Kiem tra toan ven du lieu (SHA-256):")
    all_match = True
    for v in range(1, num_versions + 1):
        snap_model = snapshot_store.get("BENCH-001", v)
        delta_model = delta_store.get("BENCH-001", v)
        match = snap_model.checksum() == delta_model.checksum()
        status = "PASS" if match else "FAIL"
        print(f"  v{v}: [{status}] {'Trung khop' if match else 'LOI!'}")
        if not match:
            all_match = False

    print(f"\nKet qua: {'TAT CA DUNG' if all_match else 'CO LOI'}")

    # ===== LUU KET QUA =====
    results = {
        "num_versions": num_versions,
        "complexity": complexity,
        "per_version_metrics": per_version_metrics,
        "snapshot_sizes": snapshot_sizes,
        "delta_sizes": delta_sizes,
        "cumulative_snapshot": cumulative_snapshot,
        "cumulative_delta": cumulative_delta,
        "full_snapshot_bytes": total_snap,
        "delta_storage_bytes": total_delta,
        "saving_percent": round(total_savings_pct, 2),
        "rehydration_costs": rehydration_costs,
        "rehydration_times_ms": rehydration_times_ms,        # [NEW] Thoi gian thuc te ms
        "avg_rehydration_ms": round(avg_rehydration_ms, 3),  # [NEW] Trung binh
        "total_snapshot": total_snap,
        "total_delta": total_delta,
        "savings_bytes": total_savings,
        "savings_percent": total_savings_pct,
        "integrity_ok": all_match,
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    results_path = os.path.join(RESULTS_DIR, "benchmark_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nKet qua da luu: results/benchmark_results.json")

    return results


if __name__ == "__main__":
    run_benchmark(num_versions=10, complexity=5)
    print()
    print("=" * 60)
    print("  Xong! Chay 'python main.py --benchmark' de sinh kem bieu do.")
    print("=" * 60)
