import unittest
import os
import json
from app.models import CADModel, Geometry
from app.storage import SnapshotStore, DeltaStore, ReplicationOutboxStore

# Helper for test setup
def get_test_model():
    geom = Geometry(vertices=[{"x": 1.0, "y": 2.0, "z": 3.0}], edges=[], faces=[], type="Polygon")
    return CADModel("ENG-TEST", geom, version=1, branch="main", site_origin="Site-A", locked_by="test")

class TestStorage(unittest.TestCase):
    def setUp(self):
        # Ensure clean state for tests
        self.site_id = "Site-Test"
        from app.storage import _get_db_path
        self.db_path = _get_db_path(self.site_id)
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except: pass
            
        self.snapshot_store = SnapshotStore(self.site_id)
        self.delta_store = DeltaStore(self.site_id)
        self.outbox_store = ReplicationOutboxStore(self.site_id)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass # Windows might hold the lock temporarily

    def test_snapshot_store_save_and_get(self):
        model = get_test_model()
        # Mock transaction commit (since it's normally done in TransactionManager)
        from app.storage import _get_conn
        geo_json = json.dumps(model.geometry.to_dict(), ensure_ascii=False)
        with _get_conn(self.site_id) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO snapshots 
                   (part_id, version, branch, oid, site_origin, created_at, modified_at, locked_by, geometry)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (model.part_id, model.version, model.branch, model.oid, model.site_origin, 
                 model.created_at, model.modified_at, model.locked_by, geo_json)
            )
            conn.commit()

        # Retrieve
        retrieved = self.snapshot_store.get_latest("ENG-TEST")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.part_id, "ENG-TEST")
        self.assertEqual(retrieved.version, 1)

    def test_outbox_enqueue_and_pending(self):
        model = get_test_model()
        op = self.outbox_store.enqueue_model("Site-B", model)
        
        self.assertIsNotNone(op)
        self.assertEqual(op["target_site"], "Site-B")
        self.assertEqual(op["status"], "PENDING")
        
        pending_list = self.outbox_store.pending("Site-B")
        self.assertEqual(len(pending_list), 1)
        self.assertEqual(pending_list[0]["op_id"], op["op_id"])

        # Mark delivered
        self.outbox_store.mark_delivered(op["op_id"])
        pending_list_after = self.outbox_store.pending("Site-B")
        self.assertEqual(len(pending_list_after), 0)

    def test_delta_rehydrate_and_checksum(self):
        # 1. Prepare base
        model_v1 = get_test_model()
        self.delta_store.save_base(model_v1)
        
        # 2. Prepare delta (v1 -> v2)
        model_v2 = CADModel("ENG-TEST", Geometry(vertices=[{"x": 1.0, "y": 2.0, "z": 3.0}, {"x": 4.0, "y": 5.0, "z": 6.0}], edges=[], faces=[], type="Polygon"), version=2, branch="main")
        from app.models import Delta
        delta = Delta.compute(model_v1, model_v2, "Site-A")
        self.delta_store.save_delta(delta)
        
        # 3. Rehydrate v2
        rehydrated_v2 = self.delta_store.rehydrate("ENG-TEST", 2)
        
        # 4. Check results
        self.assertIsNotNone(rehydrated_v2)
        self.assertEqual(rehydrated_v2.version, 2)
        self.assertEqual(rehydrated_v2.checksum(), model_v2.checksum())

    def test_checkout_get_all(self):
        from app.storage import CheckoutStore
        from datetime import datetime
        checkout_store = CheckoutStore(self.site_id)
        
        model = get_test_model()
        checkout_store.save("ENG-TEST", "user1", 1, model, datetime.now().isoformat())
        
        all_checkouts = checkout_store.get_all()
        self.assertEqual(len(all_checkouts), 1)
        self.assertEqual(all_checkouts[0]["part_id"], "ENG-TEST")
        self.assertEqual(all_checkouts[0]["user"], "user1")
        self.assertIsInstance(all_checkouts[0]["model"], dict)
        self.assertEqual(all_checkouts[0]["model"]["part_id"], "ENG-TEST")

if __name__ == '__main__':
    unittest.main()
