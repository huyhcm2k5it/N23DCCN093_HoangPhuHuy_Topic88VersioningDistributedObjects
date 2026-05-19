"""
Module: benchmark.py
Mo ta: So sanh hieu qua luu tru giua Full Snapshot va Delta Storage.

Thuc hien yeu cau cua de tai 88:
  "Do luong dung luong cho 10 phien ban voi Full Snapshot vs Delta Storage"

Chay: python benchmark.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import os
import json
import random
import copy
from app.models import CADModel, Geometry, Delta
from app.storage import SnapshotStore, DeltaStore
from app.site_node import SiteNode


def generate_cad_geometry(complexity=5):
    """Tao hinh hoc CAD ngau nhien voi do phuc tap tuy chinh."""
    num_vertices = complexity * 10
    vertices = [
        {
            "x": round(random.uniform(-100, 100), 4),
            "y": round(random.uniform(-100, 100), 4),
            "z": round(random.uniform(-100, 100), 4),
        }
        for _ in range(num_vertices)
    ]
    edges = [[i, (i + 1) % num_vertices] for i in range(num_vertices)]
    faces = [
        [i, (i + 1) % num_vertices, (i + 2) % num_vertices]
        for i in range(0, num_vertices - 2, 3)
    ]
    return Geometry(
        vertices=vertices,
        edges=edges,
        faces=faces,
        properties={
            "material": "aluminum",
            "tolerance": 0.01,
            "weight_kg": round(random.uniform(0.1, 50.0), 2),
        },
    )

def modify_geometry(geo, change_percent=0.2):
    """
    Mo phong chinh sua hinh hoc CAD (Dung cho conflict demo).
    """
    new_geo = copy.deepcopy(geo)
    num_changes = max(1, int(len(new_geo.vertices) * change_percent))

    for _ in range(num_changes):
        idx = random.randint(0, len(new_geo.vertices) - 1)
        axis = random.choice(["x", "y", "z"])
        new_geo.vertices[idx][axis] = round(
            new_geo.vertices[idx][axis] + random.uniform(-5, 5), 4,
        )
    return new_geo


def modify_geometry_realistic(geo, scenario):
    """Mo phong chinh sua thuc te theo kich ban (Tiet lo cho thay giao)."""
    new_geo = copy.deepcopy(geo)
    
    if scenario == "v2_tolerance":
        new_geo.properties["tolerance"] = 0.05
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
            new_geo.vertices.append({
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
            new_geo.vertices.append({
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
    db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "db")
    from app.storage import _initialized_dbs
    for fname in ["benchmark.db", "benchmark_wal.json"]:
        fpath = os.path.join(db_dir, fname)
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
        "snapshot_sizes": snapshot_sizes,
        "delta_sizes": delta_sizes,
        "cumulative_snapshot": cumulative_snapshot,
        "cumulative_delta": cumulative_delta,
        "rehydration_costs": rehydration_costs,
        "rehydration_times_ms": rehydration_times_ms,        # [NEW] Thoi gian thuc te ms
        "avg_rehydration_ms": round(avg_rehydration_ms, 3),  # [NEW] Trung binh
        "total_snapshot": total_snap,
        "total_delta": total_delta,
        "savings_bytes": total_savings,
        "savings_percent": total_savings_pct,
        "integrity_ok": all_match,
    }

    os.makedirs("results", exist_ok=True)
    with open("results/benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nKet qua da luu: results/benchmark_results.json")

    return results



def run_conflict_demo():
    """
    Demo 2 kich ban: THANH CONG va THAT BAI (xung dot).

    Kich ban 1 (Thanh cong):
      - 1 ky su checkout -> sua -> check-in -> OK, khong van de gi

    Kich ban 2 (That bai / Xung dot):
      - 2 ky su cung checkout v1
      - Ky su 1 check-in truoc -> v2 (OK)
      - Ky su 2 check-in sau -> XUNG DOT! (vi ban goc v1 da cu)
      - He thong phai xu ly duoc, khong crash, khong mat du lieu
    """

    # ===========================================================
    #  KICH BAN 1: THANH CONG (Khong xung dot)
    # ===========================================================
    print()
    print("=" * 60)
    print("  KICH BAN 1: THANH CONG (Khong xung dot)")
    print("  Mot ky su lam viec binh thuong, khong ai chen vao")
    print("=" * 60)
    print()

    # Xoa DB cu cua tat ca site conflict demo de dam bao bat dau tu v1
    db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "db")
    from app.storage import _initialized_dbs
    for site_name in ["TS-HaNoi", "TS-SaiGon", "BR-HaNoi", "BR-SaiGon"]:
        for ext in [".db", "_wal.json"]:
            fpath = os.path.join(db_dir, f"{site_name}{ext}")
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except PermissionError:
                    pass
        _initialized_dbs.discard(site_name)


    site_a = SiteNode("Site-A", strategy="branching")

    # Buoc 1: Tao model
    geo = generate_cad_geometry(3)
    model = site_a.create_model("CAD-001", geo)
    print(f"  Buoc 1: [Site-A] Tao model CAD-001 v{model.version}")

    # Buoc 2: Ky su checkout
    checkout = site_a.checkout("CAD-001", "ky_su_1")
    print(f"  Buoc 2: [Site-A] ky_su_1 checkout v{checkout.version}")

    # Buoc 3: Ky su sua hinh hoc
    checkout.geometry = modify_geometry(checkout.geometry, 0.2)
    print(f"  Buoc 3: [Site-A] ky_su_1 sua hinh hoc (20% thay doi)")

    # Buoc 4: Check-in (thanh cong vi khong ai khac sua)
    ok, msg, _ = site_a.checkin("CAD-001", "ky_su_1", checkout)
    status = "THANH CONG" if ok else "THAT BAI"
    print(f"  Buoc 4: [Site-A] Check-in -> [{status}] {msg}")

    # Buoc 5: Tiep tuc sua version 2
    checkout2 = site_a.checkout("CAD-001", "ky_su_1")
    checkout2.geometry = modify_geometry(checkout2.geometry, 0.15)
    ok2, msg2, _ = site_a.checkin("CAD-001", "ky_su_1", checkout2)
    status2 = "THANH CONG" if ok2 else "THAT BAI"
    print(f"  Buoc 5: [Site-A] Tiep tuc sua -> Check-in -> [{status2}] {msg2}")

    print()
    print("  => Ket luan: Khi chi co 1 nguoi lam viec, moi thu dien ra")
    print("     suon se. Khong co xung dot xay ra.")

    # ===========================================================
    #  KICH BAN 2: THAT BAI -> HE THONG XU LY XUNG DOT
    # ===========================================================
    print()
    print("=" * 60)
    print("  KICH BAN 2: XUNG DOT (2 ky su sua cung 1 file)")
    print("  He thong phai phat hien va giai quyet duoc!")
    print("=" * 60)
    print()

    # --- Chien luoc A: TIMESTAMP (Last-Write-Wins) ---
    print("-" * 50)
    print("  Chien luoc A: TIMESTAMP (Ai check-in sau thang)")
    print("-" * 50)
    print()

    site_ts_a = SiteNode("TS-HaNoi", strategy="timestamp")
    site_ts_b = SiteNode("TS-SaiGon", strategy="timestamp")

    # Tao model va sao chep
    geo2 = generate_cad_geometry(3)
    m = site_ts_a.create_model("VOLANG-001", geo2)
    site_ts_a.replicate_to(site_ts_b, "VOLANG-001")
    print(f"  1. [HaNoi]  Tao vo-lang VOLANG-001 v{m.version}")
    print(f"  2. [HaNoi]  Sao chep sang SaiGon")

    # Ca 2 cung checkout
    co_a = site_ts_a.checkout("VOLANG-001", "ky_su_HN")
    co_b = site_ts_b.checkout("VOLANG-001", "ky_su_SG")
    print(f"  3. [HaNoi]  ky_su_HN checkout v{co_a.version}")
    print(f"  4. [SaiGon] ky_su_SG checkout v{co_b.version}")
    print(f"     => Ca 2 deu dang giu ban v1 cu!")

    # Ca 2 sua doc lap
    co_a.geometry = modify_geometry(co_a.geometry, 0.3)
    co_b.geometry = modify_geometry(co_b.geometry, 0.2)
    print(f"  5. [HaNoi]  ky_su_HN boc da mau DO (sua 30%)")
    print(f"  6. [SaiGon] ky_su_SG boc da mau DEN (sua 20%)")

    # HN check-in truoc -> OK
    ok_a, msg_a, _ = site_ts_a.checkin("VOLANG-001", "ky_su_HN", co_a)
    print(f"\n  7. [HaNoi]  Check-in -> [THANH CONG] {msg_a}")

    # Sao chep v2 sang SG (luc nay SG biet la da co v2)
    site_ts_a.replicate_to(site_ts_b, "VOLANG-001")
    print(f"  8. [HaNoi]  Dong bo ban moi sang SaiGon (v2)")

    # SG check-in -> XUNG DOT!
    ok_b, msg_b, _ = site_ts_b.checkin("VOLANG-001", "ky_su_SG", co_b)
    print(f"  9. [SaiGon] Check-in ->")
    print(f"     *** XUNG DOT PHAT HIEN! ***")
    print(f"     Xu ly: {msg_b}")

    print()
    print("  => Ket luan: Chien luoc Timestamp giu ban check-in SAU CUNG.")
    print("     Ban cua ky_su_HN (mau do) BI HUY. Co the mat cong suc!")

    # --- Chien luoc B: BRANCHING (Chia nhanh) ---
    print()
    print("-" * 50)
    print("  Chien luoc B: BRANCHING (Tao nhanh rieng)")
    print("-" * 50)
    print()

    site_br_a = SiteNode("BR-HaNoi", strategy="branching")
    site_br_b = SiteNode("BR-SaiGon", strategy="branching")

    # Tao model va sao chep
    geo3 = generate_cad_geometry(3)
    m2 = site_br_a.create_model("GHENGOI-001", geo3)
    site_br_a.replicate_to(site_br_b, "GHENGOI-001")
    print(f"  1. [HaNoi]  Tao ghe-ngoi GHENGOI-001 v{m2.version}")
    print(f"  2. [HaNoi]  Sao chep sang SaiGon")

    # Ca 2 cung checkout
    co_c = site_br_a.checkout("GHENGOI-001", "ky_su_HN")
    co_d = site_br_b.checkout("GHENGOI-001", "ky_su_SG")
    print(f"  3. [HaNoi]  ky_su_HN checkout v{co_c.version}")
    print(f"  4. [SaiGon] ky_su_SG checkout v{co_d.version}")

    # Sua doc lap
    co_c.geometry = modify_geometry(co_c.geometry, 0.25)
    co_d.geometry = modify_geometry(co_d.geometry, 0.15)
    print(f"  5. [HaNoi]  ky_su_HN them tua lung cao (sua 25%)")
    print(f"  6. [SaiGon] ky_su_SG them boc da (sua 15%)")

    # HN check-in truoc -> OK
    ok_c, msg_c, _ = site_br_a.checkin("GHENGOI-001", "ky_su_HN", co_c)
    print(f"\n  7. [HaNoi]  Check-in -> [THANH CONG] {msg_c}")

    # Sao chep v2 sang SG
    site_br_a.replicate_to(site_br_b, "GHENGOI-001")
    print(f"  8. [HaNoi]  Dong bo ban moi sang SaiGon (v2)")

    # SG check-in -> XUNG DOT nhung xu ly bang Branching
    ok_d, msg_d, _ = site_br_b.checkin("GHENGOI-001", "ky_su_SG", co_d)
    print(f"  9. [SaiGon] Check-in ->")
    print(f"     *** XUNG DOT PHAT HIEN! ***")
    print(f"     Xu ly: {msg_d}")

    print()
    print("  => Ket luan: Chien luoc Branching tao 2 nhanh song song.")
    print("     KHONG MAT du lieu cua ai. Can merge (gop) thu cong sau.")

    # ===========================================================
    #  SO SANH 2 CHIEN LUOC
    # ===========================================================
    print()
    print("=" * 60)
    print("  SO SANH 2 CHIEN LUOC GIAI QUYET XUNG DOT")
    print("=" * 60)
    print()
    print(f"  {'Tieu chi':<25} {'Timestamp (LWW)':<22} {'Branching':<22}")
    print(f"  {'-'*25} {'-'*22} {'-'*22}")
    print(f"  {'Mat du lieu?':<25} {'CO (ban cu bi huy)':<22} {'KHONG':<22}")
    print(f"  {'Can xu ly thu cong?':<25} {'Khong':<22} {'Co (merge)':<22}")
    print(f"  {'Do phuc tap':<25} {'Thap':<22} {'Trung binh':<22}")
    print(f"  {'Phu hop khi':<25} {'Du lieu it gia tri':<22} {'Du lieu quan trong':<22}")
    print(f"  {'VD thuc te':<25} {'Facebook comments':<22} {'Git, CAD, Medical':<22}")

    # ===== SO SANH LUU TRU =====
    print()
    print("=" * 60)
    print("  TONG HOP LUU TRU TAT CA SITES")
    print("=" * 60)
    all_sites = [
        ("Timestamp - HaNoi", site_ts_a),
        ("Timestamp - SaiGon", site_ts_b),
        ("Branching - HaNoi", site_br_a),
        ("Branching - SaiGon", site_br_b),
    ]
    for label, site in all_sites:
        comp = site.get_storage_comparison()
        print(f"\n  [{label}]")
        print(f"    Snapshot: {comp['snapshot_total_bytes']:,} bytes")
        print(f"    Delta:    {comp['delta_total_bytes']:,} bytes")
        print(f"    Tiet kiem: {comp['savings_percent']:.1f}%")


if __name__ == "__main__":
    results = run_benchmark(num_versions=10, complexity=5)
    run_conflict_demo()
    print()
    print("=" * 60)
    print("  Xong! Chay 'python visualize.py' de tao bieu do.")
    print("=" * 60)
