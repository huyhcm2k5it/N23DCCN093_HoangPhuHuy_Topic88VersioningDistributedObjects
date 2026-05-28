"""
Module: main.py
Mo ta: Diem vao duy nhat de chay server, benchmark, demo va clean DB.

Cach chay:
    python main.py --benchmark    Chay so sanh Snapshot vs Delta
    python main.py --servers      Khoi dong 3 site API servers
    python main.py --demo         Chay demo day du (de quay video)
    python main.py --clean        Xoa toan bo DB (reset)
"""

import os
import json
import sys
import threading
import time

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.models import Geometry, CADModel
from app.site_node import SiteNode
from app.server import create_app
from app.coordinator import create_coordinator_app
from scripts.benchmark import run_benchmark
from scripts.demo import run_full_backend_demo

BANNER = """
+==============================================================+
|  Topic 88: Versioning Distributed Objects                    |
|  "Collaborative Design" - Distributed CAD Versioning         |
|  CSDL Phan Tan - Do an cuoi ky                               |
+==============================================================+
"""

BASE_DIR = os.path.dirname(__file__)
DB_DIR = os.path.join(BASE_DIR, "app", "db")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
DATASET_FILES = {
    "Site-A": os.path.join(BASE_DIR, "dataset", "site_a_engine.json"),
    "Site-B": os.path.join(BASE_DIR, "dataset", "site_b_chassis.json"),
    "Site-C": os.path.join(BASE_DIR, "dataset", "site_c_interior.json"),
}
USAGE = (
    "Cach su dung:\n"
    "  python main.py --benchmark\n"
    "  python main.py --servers\n"
    "  python main.py --demo\n"
    "  python main.py --clean\n"
    "  python main.py --help"
)


def is_runtime_db_file(filename):
    return filename.endswith((".db", ".db-wal", ".db-shm", "_wal.json"))


def clean_databases():
    """Xoa runtime SQLite files va cac file ket qua benchmark trong results/."""
    # 1. Xoa runtime DB files
    if os.path.exists(DB_DIR):
        deleted_db = []
        skipped_db = []
        for filename in os.listdir(DB_DIR):
            if not is_runtime_db_file(filename):
                continue
            try:
                os.remove(os.path.join(DB_DIR, filename))
                deleted_db.append(filename)
            except PermissionError:
                skipped_db.append(filename)
        
        if deleted_db:
            print(f"  Da xoa DB: {', '.join(deleted_db)}")
        if skipped_db:
            print(f"  Khong xoa duoc DB (dang bi lock): {', '.join(skipped_db)}")
    else:
        print("  Khong co thu muc DB.")

    # 2. Xoa cac file ket qua benchmark
    if os.path.exists(RESULTS_DIR):
        deleted_res = []
        skipped_res = []
        for filename in os.listdir(RESULTS_DIR):
            file_path = os.path.join(RESULTS_DIR, filename)
            if os.path.isdir(file_path):
                continue
            try:
                os.remove(file_path)
                deleted_res.append(filename)
            except Exception:
                skipped_res.append(filename)
        
        if deleted_res:
            print(f"  Da xoa file ket qua: {', '.join(deleted_res)}")
        if skipped_res:
            print(f"  Khong xoa duoc file ket qua: {', '.join(skipped_res)}")
    else:
        print("  Khong co thu muc ket qua results/.")

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
    for part in parts:
        geo = Geometry(**part["geometry"])
        model = CADModel(
            part_id=part["part_id"],
            geometry=geo,
            version=part.get("version", 1),
            site_origin=part.get("site_origin", site.site_id),
            branch=part.get("branch", "main"),
        )
        site.snapshot_store.save(model)
        site.delta_store.save_base(model)
        site.notify_register_object(model)
        site.notify_update_head(model, parent_version=None, parent_branch=None)
    return len(parts)

def start_site_server(site, port):
    app = create_app(site)
    print(f"  [{site.site_id}] API running at http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def start_coordinator_server(port=5000):
    app = create_coordinator_app()
    print(f"  [Coordinator] API running at http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def cmd_benchmark():
    run_benchmark(num_versions=10, complexity=5)
    print("\n  Dang tao bieu do...")
    try:
        from scripts.visualize import generate_all_charts
        generate_all_charts()
    except Exception as exc:
        print(f"  (Bo qua bieu do: {exc})")


def cmd_servers():
    missing = [site_id for site_id, path in DATASET_FILES.items() if not os.path.exists(path)]
    if missing:
        print(f"  [!] Thieu dataset: {missing}. Chay 'python scripts/generate_dataset.py' truoc.")
        return

    coordinator_thread = threading.Thread(target=start_coordinator_server, args=(5000,), daemon=True)
    coordinator_thread.start()
    time.sleep(0.8)

    print("\n  Khoi dong 3 site phan tan (Horizontal Fragmentation)...\n")
    site_a = SiteNode("Site-A", strategy="branching")
    site_b = SiteNode("Site-B", strategy="branching")
    site_c = SiteNode("Site-C", strategy="branching")

    na = load_fragment_into_site(site_a, DATASET_FILES["Site-A"])
    nb = load_fragment_into_site(site_b, DATASET_FILES["Site-B"])
    nc = load_fragment_into_site(site_c, DATASET_FILES["Site-C"])

    print(f"\n  Phan manh hoan tat: A={na}, B={nb}, C={nc} parts. UNION = {na+nb+nc}")

    threads = [
        threading.Thread(target=start_site_server, args=(site_a, 5001), daemon=True),
        threading.Thread(target=start_site_server, args=(site_b, 5002), daemon=True),
        threading.Thread(target=start_site_server, args=(site_c, 5003), daemon=True),
    ]
    for thread in threads:
        thread.start()
        time.sleep(0.5)

    print("\n  API Endpoints:")
    print("    Coordinator (Metadata):      http://127.0.0.1:5000")
    print("    Site-A (Engine/Branching): http://127.0.0.1:5001")
    print("    Site-B (Chassis/Branching): http://127.0.0.1:5002")
    print("    Site-C (Interior/Branching): http://127.0.0.1:5003")
    print("  Nhan Ctrl+C de dung.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Dang tat servers...")


def cmd_demo():
    run_full_backend_demo()


def main():
    print(BANNER)
    if len(sys.argv) < 2:
        print(USAGE)
        return

    cmd = sys.argv[1]
    commands = {
        "--benchmark": cmd_benchmark,
        "--servers": cmd_servers,
        "--demo": cmd_demo,
        "--clean": clean_databases,
        "--help": lambda: print(__doc__),
    }
    handler = commands.get(cmd)
    if not handler:
        print(f"Lenh khong hop le: {cmd}")
        print(USAGE)
        return
    handler()


if __name__ == "__main__":
    main()
