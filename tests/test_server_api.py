import os
import unittest
from datetime import datetime

from app.models import CADModel, Delta, Geometry
from app.server import create_app
from app.site_node import SiteNode
from app.storage import _get_db_path, _initialized_dbs


def make_model(part_id="ENG-API", version=1, oid=None):
    geometry = Geometry(
        vertices=[{"x": 1.0, "y": 2.0, "z": 3.0}],
        edges=[],
        faces=[],
        type="Polygon",
    )
    return CADModel(part_id, geometry, version=version, oid=oid, branch="main", site_origin="Site-A")


class TestServerApi(unittest.TestCase):
    def setUp(self):
        self.site_id = "Site-Api-Test"
        self.db_path = _get_db_path(self.site_id)
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass
        _initialized_dbs.discard(self.site_id)

        self.site = SiteNode(self.site_id, coordinator_url=None)
        self.client = create_app(self.site).test_client()

    def tearDown(self):
        _initialized_dbs.discard(self.site_id)
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass

    def test_rehydrate_endpoint_accepts_part_id_and_oid(self):
        model_v1 = make_model()
        model_v2 = make_model(version=2, oid=model_v1.oid)
        model_v2.geometry.vertices.append({"x": 4.0, "y": 5.0, "z": 6.0})

        self.site.snapshot_store.save(model_v1)
        self.site.snapshot_store.save(model_v2)
        self.site.delta_store.save_base(model_v1)
        self.site.delta_store.save_delta(Delta.compute(model_v1, model_v2, self.site_id))

        by_part_id = self.client.post("/rehydrate", json={"part_id": model_v1.part_id, "target_version": 2})
        self.assertEqual(by_part_id.status_code, 200)
        payload = by_part_id.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["metrics"]["part_id"], model_v1.part_id)
        self.assertEqual(payload["metrics"]["rehydration_steps"], 1)
        self.assertTrue(payload["checksum_match"])

        by_oid = self.client.post("/rehydrate", json={"oid": model_v1.oid, "target_version": 2})
        self.assertEqual(by_oid.status_code, 200)
        self.assertEqual(by_oid.get_json()["model"]["part_id"], model_v1.part_id)

    def test_checkouts_endpoint_returns_json_serializable_models(self):
        model = make_model()
        self.site.checkout_store.save(model.part_id, "user1", 1, model, datetime.now().isoformat())

        response = self.client.get("/checkouts")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["checkouts"]), 1)
        checkout = payload["checkouts"][0]
        self.assertEqual(checkout["part_id"], model.part_id)
        self.assertEqual(checkout["model"]["part_id"], model.part_id)


if __name__ == "__main__":
    unittest.main()
