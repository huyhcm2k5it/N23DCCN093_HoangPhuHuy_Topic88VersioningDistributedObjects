"""
Module: main.py
Mo ta: Diem vao chinh cua chuong trinh.
Mo ta logic backend day du (cac tang, API, WAL): xem docstring dau file demo_unified.py

Cach chay:
    python main.py --benchmark    Chay so sanh Snapshot vs Delta
    python main.py --servers      Khoi dong 3 site API servers
    python main.py --demo         Chay demo day du (de quay video)
    python main.py --clean        Xoa toan bo DB (reset)
"""

import sys
import os
import json
import threading
import time

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try: sys.stdout.reconfigure(encoding="utf-8")
    except: pass

from app.models import Geometry, CADModel
from app.site_node import SiteNode
from app.server import create_app
from scripts.benchmark import run_benchmark, run_conflict_demo
import demo_unified

BANNER = """
+==============================================================+
|  Topic 88: Versioning Distributed Objects                    |
|  "Collaborative Design" - Distributed CAD Versioning         |
|  CSDL Phan Tan - Do an cuoi ky                               |
+==============================================================+
"""

def clean_databases():
    """Xoa toan bo file .db va _wal.json trong thu muc app/db/."""
    db_dir = os.path.join(os.path.dirname(__file__), "app", "db")
    if not os.path.exists(db_dir):
        print("  Khong co DB nao can xoa.")
        return
    deleted = []
    skipped = []
    for f in os.listdir(db_dir):
        if f.endswith(".db") or f.endswith("_wal.json"):
            try:
                os.remove(os.path.join(db_dir, f))
                deleted.append(f)
            except PermissionError:
                skipped.append(f)
    if deleted:
        print(f"  Da xoa: {', '.join(deleted)}")
    if skipped:
        print(f"  Khong xoa duoc (dang bi lock): {', '.join(skipped)}")
    if not deleted and not skipped:
        print("  Khong co file nao.")

    # Reset initialized_dbs cache trong storage module
    from app.storage import _initialized_dbs
    _initialized_dbs.clear()

def load_fragment_into_site(site, json_path):
    """
    Load du lieu tu file JSON fragment vao DB cua site.
    Tuong thich voi schema moi: tach cot rieng biet.
    """
    if not os.path.exists(json_path):
        print(f"  [WARN] Khong tim thay file fragment: {json_path}")
        return 0
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    parts = data.get("parts", [])
    print(f"  [{site.site_id}] Load {len(parts)} parts from {os.path.basename(json_path)}")
    for p in parts:
        geo = Geometry(**p["geometry"])
        model = CADModel(
            part_id=p["part_id"],
            geometry=geo,
            version=p.get("version", 1),
            site_origin=p.get("site_origin", site.site_id),
            branch=p.get("branch", "main"),
        )
        # Luu vao ca 2 store: snapshot (full) va delta (base)
        site.snapshot_store.save(model)
        site.delta_store.save_base(model)
    return len(parts)

def start_site_server(site, port):
    app = create_app(site)
    print(f"  [{site.site_id}] API running at http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

def cmd_benchmark():
    run_benchmark(num_versions=10, complexity=5)
    run_conflict_demo()
    print("\n  Dang tao bieu do...")
    try:
        from visualize import generate_all_charts
        generate_all_charts()
    except ImportError:
        print("  (Bo qua bieu do - pip install matplotlib)")

def cmd_servers():
    base = os.path.dirname(__file__)
    fragment_files = {
        "Site-A": os.path.join(base, "dataset", "site_a_engine.json"),
        "Site-B": os.path.join(base, "dataset", "site_b_chassis.json"),
        "Site-C": os.path.join(base, "dataset", "site_c_interior.json"),
    }
    missing = [k for k, v in fragment_files.items() if not os.path.exists(v)]
    if missing:
        print(f"  [!] Thieu dataset: {missing}. Chay 'python scripts/generate_dataset.py' truoc.")
        return

    print("\n  Khoi dong 3 site phan tan (Horizontal Fragmentation)...\n")
    site_a = SiteNode("Site-A", strategy="branching")
    site_b = SiteNode("Site-B", strategy="branching")
    site_c = SiteNode("Site-C", strategy="timestamp")

    na = load_fragment_into_site(site_a, fragment_files["Site-A"])
    nb = load_fragment_into_site(site_b, fragment_files["Site-B"])
    nc = load_fragment_into_site(site_c, fragment_files["Site-C"])

    print(f"\n  Phan manh hoan tat: A={na}, B={nb}, C={nc} parts. UNION = {na+nb+nc}")

    threads = [
        threading.Thread(target=start_site_server, args=(site_a, 5001), daemon=True),
        threading.Thread(target=start_site_server, args=(site_b, 5002), daemon=True),
        threading.Thread(target=start_site_server, args=(site_c, 5003), daemon=True),
    ]
    for t in threads: t.start(); time.sleep(0.5)

    print("\n  API Endpoints:")
    print("    Site-A (Engine/Branching): http://127.0.0.1:5001")
    print("    Site-B (Chassis/Branching): http://127.0.0.1:5002")
    print("    Site-C (Interior/Timestamp): http://127.0.0.1:5003")
    print("  Nhan Ctrl+C de dung.\n")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Dang tat servers...")

def cmd_demo():
    demo_unified.run_full_backend_demo()

def main():
    print(BANNER)
    if len(sys.argv) < 2:
        print("Cach su dung:\n  python main.py --benchmark\n  python main.py --servers\n  python main.py --demo\n  python main.py --clean\n  python main.py --help")
        return
    cmd = sys.argv[1]
    if cmd == "--benchmark": cmd_benchmark()
    elif cmd == "--servers": cmd_servers()
    elif cmd == "--demo": cmd_demo()
    elif cmd == "--clean": clean_databases()
    elif cmd == "--help": print(__doc__)
    else: print(f"Lenh khong hop le: {cmd}")

if __name__ == "__main__":
    main()