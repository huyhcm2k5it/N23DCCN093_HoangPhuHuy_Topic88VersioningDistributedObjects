import unittest
import requests
import time

SITE_A = "http://127.0.0.1:5001"  # Branching (Engine)
SITE_C = "http://127.0.0.1:5003"  # Timestamp (Interior)

class TestDistributedVersioning(unittest.TestCase):
    """
    Test Integration E2E cho he thong Versioning Distributed Objects.
    Dam bao API xu ly dung Checkout, Checkin, Xung dot va Crash Recovery.
    """

    def setUp(self):
        # Dam bao cac server dang chay
        try:
            requests.get(f"{SITE_A}/health", timeout=2)
        except requests.exceptions.ConnectionError:
            self.skipTest("Cac server (Site-A, Site-C) chua chay. Vui long chay 'python main.py --servers' truoc.")

    def _modify_geometry(self, geometry):
        """Thay doi nhe geometry de mo phong ky su sua ban ve."""
        geo_copy = dict(geometry)
        if geo_copy['vertices']:
            geo_copy['vertices'][0]['x'] += 10.5
        return geo_copy

    def test_01_timestamp_conflict_resolution(self):
        """
        Kich ban: 2 Ky su cung checkout part o Site-C (Timestamp).
        Ky su 1 checkin thanh cong (v2).
        Ky su 2 checkin cham hon -> Xung dot -> Timestamp tu dong ghi de (v3 tren nhanh main).
        """
        part_id = "INT-001"
        
        # 1. Ca 2 cung checkout version hien tai
        base_res = requests.get(f"{SITE_C}/models/{part_id}").json()
        base_version = base_res['version']

        res1 = requests.post(f"{SITE_C}/models/{part_id}/checkout", json={"user": "KySu_C1"}).json()
        res2 = requests.post(f"{SITE_C}/models/{part_id}/checkout", json={"user": "KySu_C2"}).json()
        
        self.assertEqual(res1['version'], base_version, f"KySu_C1 phai nhan duoc v{base_version}")
        self.assertEqual(res2['version'], base_version, f"KySu_C2 phai nhan duoc v{base_version}")

        # 2. KySu_C1 sua va checkin (Thanh cong -> v+1)
        model1 = dict(res1)
        model1['geometry'] = self._modify_geometry(model1['geometry'])
        ck1 = requests.post(f"{SITE_C}/models/{part_id}/checkin", json={"user": "KySu_C1", "model": model1}).json()
        self.assertTrue(ck1['success'])
        self.assertEqual(ck1['version_after'], base_version + 1)

        # 3. KySu_C2 sua va checkin (Xung dot -> Timestamp resolve -> v+2)
        model2 = dict(res2)
        model2['geometry'] = self._modify_geometry(model2['geometry'])
        ck2 = requests.post(f"{SITE_C}/models/{part_id}/checkin", json={"user": "KySu_C2", "model": model2}).json()
        
        self.assertTrue(ck2['success'], "Phai xu ly duoc xung dot chu khong the fail")
        self.assertTrue(ck2['is_conflict'], "He thong phai nhan dien duoc day la xung dot")
        self.assertEqual(ck2['conflict_strategy'], "timestamp", "Chien luoc phai la timestamp")
        
        # Voi Timestamp, tat ca deu o nhanh 'main' va version tang len
        self.assertEqual(ck2['branch'], "main")
        self.assertEqual(ck2['version_after'], base_version + 2)

    def test_02_branching_conflict_resolution(self):
        """
        Kich ban: 2 Ky su cung checkout part o Site-A (Branching).
        Ky su 1 checkin thanh cong (v2 tren main).
        Ky su 2 checkin cham hon -> Xung dot -> Branching tao nhanh rieng.
        """
        part_id = "ENG-001"
        
        # 1. Ca 2 cung checkout
        res1 = requests.post(f"{SITE_A}/models/{part_id}/checkout", json={"user": "KySu_A1"}).json()
        res2 = requests.post(f"{SITE_A}/models/{part_id}/checkout", json={"user": "KySu_A2"}).json()

        # 2. KySu_A1 checkin (Thanh cong -> v2 main)
        model1 = dict(res1)
        model1['geometry'] = self._modify_geometry(model1['geometry'])
        ck1 = requests.post(f"{SITE_A}/models/{part_id}/checkin", json={"user": "KySu_A1", "model": model1}).json()
        self.assertTrue(ck1['success'])

        # 3. KySu_A2 checkin (Xung dot -> Branching)
        model2 = dict(res2)
        model2['geometry'] = self._modify_geometry(model2['geometry'])
        ck2 = requests.post(f"{SITE_A}/models/{part_id}/checkin", json={"user": "KySu_A2", "model": model2}).json()
        
        self.assertTrue(ck2['success'])
        self.assertTrue(ck2['is_conflict'])
        self.assertEqual(ck2['conflict_strategy'], "branching")
        
        # Kiem tra nhanh moi da duoc tao (VD: Site-A/KySu_A2/v2)
        self.assertNotEqual(ck2['branch'], "main", "Branching khong duoc luu de len main")
        self.assertTrue("KySu_A2" in ck2['branch'], "Ten nhanh phai chua ten user")

    def test_03_crash_recovery(self):
        """
        Kich ban: He thong dang ghi DB thi bi Crash.
        WAL phai luu trang thai, sau do phuc hoi (Rollback) thanh cong.
        """
        part_id = "ENG-002"
        user = "KySu_Crash"

        # 1. Lay version hien tai
        initial_model = requests.get(f"{SITE_A}/models/{part_id}").json()
        initial_version = initial_model['version']

        # 2. Checkout
        res = requests.post(f"{SITE_A}/models/{part_id}/checkout", json={"user": user}).json()
        model = dict(res)
        model['geometry'] = self._modify_geometry(model['geometry'])

        # 3. Gia lap Crash cho Checkin tiep theo
        requests.post(f"{SITE_A}/crash/simulate")

        # 4. Checkin (Se bi CRASH 500)
        crash_res = requests.post(f"{SITE_A}/models/{part_id}/checkin", json={"user": user, "model": model})
        self.assertEqual(crash_res.status_code, 500, "Phai tra ve loi 500 do Crash")
        
        crash_body = crash_res.json()
        self.assertFalse(crash_body['success'])
        self.assertTrue(crash_body['wal_status']['coordinator_crashed'], "WAL phai ghi nhan he thong da crash")
        self.assertGreater(crash_body['wal_status']['uncommitted_count'], 0, "Phai co transaction dang pending trong WAL")

        # 5. Kiem tra DB chua bi thay doi version (Vi chua commit xong)
        current_model = requests.get(f"{SITE_A}/models/{part_id}").json()
        self.assertEqual(current_model['version'], initial_version, "Database khong duoc phep cap nhat khi co crash")

        # 6. Khoi dong lai he thong -> Kich hoat Rollback
        recover = requests.post(f"{SITE_A}/coordinator/restart").json()
        self.assertTrue(recover['success'])
        self.assertEqual(recover['wal_status']['uncommitted_count'], 0, "Tat ca transaction loi phai duoc rollback")

if __name__ == '__main__':
    unittest.main(verbosity=2)
