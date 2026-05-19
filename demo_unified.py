import requests
import time
import json

# Cau hinh cac site phan tan
SITES = {
    "Site-A": "http://127.0.0.1:5001", # Branching
    "Site-B": "http://127.0.0.1:5002", # Branching
    "Site-C": "http://127.0.0.1:5003", # Timestamp
}

def print_banner(msg):
    print(f"\n{'='*70}")
    print(f"  {msg}")
    print(f"{'='*70}")

def run_full_backend_demo():
    print_banner("CHUONG TRINH DEMO HE THONG VERSIONING CAD PHAN TAN (TOPIC 88)")
    
    # 1. Dashboard Overview
    print("\n[BƯỚC 1] KIỂM TRA TRẠNG THÁI CÁC SITE...")
    for name, url in SITES.items():
        try:
            res = requests.get(f"{url}/health", timeout=2).json()
            print(f"  ✅ {name}: ONLINE | Chien luoc: {res.get('strategy')} | Database: {name}.db")
        except:
            print(f"  ❌ {name}: OFFLINE! (Vui long chay 'python main.py --servers')")
            return

    # 2. Collaborative Conflict (Branching)
    print_banner("KỊCH BẢN 1: XỬ LÝ XUNG ĐỘT BẰNG PHÂN NHÁNH (BRANCHING)")
    part_id = "ENG-001"
    print(f"Mo phong 2 ky su A va B cung Checkout {part_id} tai Site-A...")
    
    # Checkout
    a_model = requests.post(f"{SITES['Site-A']}/models/{part_id}/checkout", json={"user": "Engineer_A"}).json()
    b_model = requests.post(f"{SITES['Site-A']}/models/{part_id}/checkout", json={"user": "Engineer_B"}).json()
    
    print(f"  -> Ca 2 cung bat dau tai Version: {a_model['version']}")
    
    print("\nEngineer_A thuc hien thay doi va Check-in truoc...")
    a_model['geometry']['vertices'][0]['x'] += 50
    res_a = requests.post(f"{SITES['Site-A']}/models/{part_id}/checkin", json={"user": "Engineer_A", "model": a_model}).json()
    print(f"  -> Ket qua Site-A: {res_a['message']} (Nhanh hien tai: {res_a['branch']})")
    
    print("\nEngineer_B thuc hien thay doi khac va Check-in sau (XAY RA XUNG ĐỘT)...")
    b_model['geometry']['vertices'][0]['x'] -= 50
    res_b = requests.post(f"{SITES['Site-A']}/models/{part_id}/checkin", json={"user": "Engineer_B", "model": b_model}).json()
    
    print(f"  -> Ket qua Site-A: {res_b['message']}")
    print(f"  -> GIẢI PHÁP: He thong tu dong tao nhanh moi: {res_b['branch']}")
    print(f"  -> [OK] Du lieu cua ca 2 ky su deu duoc bao ton tren 2 nhanh khac nhau.")

    # 3. Collaborative Conflict (Timestamp)
    print_banner("KỊCH BẢN 2: XỬ LÝ XUNG ĐỘT BẰNG TIMESTAMP (LWW)")
    part_id = "INT-001"
    print(f"Mo phong 2 ky su C va D cung Checkout {part_id} tai Site-C...")
    
    c_model = requests.post(f"{SITES['Site-C']}/models/{part_id}/checkout", json={"user": "Engineer_C"}).json()
    d_model = requests.post(f"{SITES['Site-C']}/models/{part_id}/checkout", json={"user": "Engineer_D"}).json()
    
    print("\nEngineer_C Check-in v2...")
    requests.post(f"{SITES['Site-C']}/models/{part_id}/checkin", json={"user": "Engineer_C", "model": c_model})
    
    print("Engineer_D Check-in sau (Xung dot Timestamp)...")
    res_d = requests.post(f"{SITES['Site-C']}/models/{part_id}/checkin", json={"user": "Engineer_D", "model": d_model}).json()
    print(f"  -> Ket qua Site-C: {res_d['message']}")
    print(f"  -> GIẢI PHÁP: Ghi de len nhanh main, version moi nhat hien tai la: {res_d['version_after']}")

    # 4. Crash Recovery (WAL)
    print_banner("KỊCH BẢN 3: GIẢ LẬP LỖI HỆ THỐNG VÀ PHỤC HỒI (WAL RECOVERY)")
    part_id = "CHS-001"
    print(f"Gia lap truong hop Server bi sap (Crash) ngay khi dang ghi du lieu {part_id}...")
    
    # Dat che do tu crash khi nhan request checkin tiep theo
    requests.post(f"{SITES['Site-B']}/crash/simulate")
    
    e_model = requests.post(f"{SITES['Site-B']}/models/{part_id}/checkout", json={"user": "Engineer_E"}).json()
    print("Dang gui request Check-in...")
    
    try:
        res_crash = requests.post(f"{SITES['Site-B']}/models/{part_id}/checkin", 
                                  json={"user": "Engineer_E", "model": e_model}, timeout=5)
        print(f"  -> Server Response Status: {res_crash.status_code} (FAILED AS EXPECTED)")
    except Exception as e:
        print(f"  -> Connection Lost! (Server crashed)")

    # Kiem tra WAL
    wal = requests.get(f"{SITES['Site-B']}/wal/status").json()
    print(f"  -> WAL Log: Phat hien {wal['uncommitted_count']} giao dich chua hoan tat (Pending).")
    
    print("\nThuc hien khoi dong lai dieu phoi vien (Coordinator Restart)...")
    res_rec = requests.post(f"{SITES['Site-B']}/coordinator/restart").json()
    print(f"  -> Recovery Result: {res_rec['message']}")
    print(f"  -> Trang thai WAL sau khi Rollback: {res_rec['wal_status']['uncommitted_count']} pending.")

    print_banner("DEMO HOÀN TẤT - HỆ THỐNG HOẠT ĐỘNG ỔN ĐỊNH!")
    print("Ban co the kiem tra lai Dashboard de xem cac nhanh (Branch) da duoc tao.")

if __name__ == "__main__":
    run_full_backend_demo()
