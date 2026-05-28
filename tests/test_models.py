import unittest
from app.models import CADModel, Geometry, CADModelSchema

class TestModels(unittest.TestCase):
    def test_cad_model_creation(self):
        geom = Geometry(vertices=[{"x": 0.0, "y": 0.0, "z": 0.0}], edges=[], faces=[], type="Polygon")
        model = CADModel("ENG-001", geom, version=1, branch="main", site_origin="Site-A", locked_by="test")
        self.assertEqual(model.part_id, "ENG-001")
        self.assertEqual(model.version, 1)
        self.assertEqual(model.branch, "main")
        self.assertEqual(model.site_origin, "Site-A")
        self.assertIsNotNone(model.oid)
        self.assertEqual(model.geometry.type, "Polygon")
        self.assertEqual(len(model.geometry.vertices), 1)

    def test_schema_serialization(self):
        geom = Geometry(vertices=[{"x": 1.0, "y": 2.0, "z": 3.0}], edges=[], faces=[], type="Polygon")
        model = CADModel("ENG-002", geom, version=2, branch="feature-branch", site_origin="Site-B", locked_by="user2")
        
        schema = CADModelSchema()
        data = schema.dump(model)
        
        self.assertEqual(data["part_id"], "ENG-002")
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["branch"], "feature-branch")
        self.assertEqual(data["geometry"]["type"], "Polygon")
        self.assertEqual(data["geometry"]["vertices"][0]["x"], 1.0)

    def test_schema_deserialization(self):
        data = {
            "part_id": "ENG-003",
            "version": 3,
            "branch": "main",
            "oid": "test-oid-123",
            "site_origin": "Site-C",
            "geometry": {
                "type": "Line",
                "vertices": [{"x": 0.0, "y": 0.0, "z": 0.0}, {"x": 1.0, "y": 1.0, "z": 1.0}],
                "edges": [],
                "faces": []
            },
            "created_at": "2023-01-01T00:00:00",
            "modified_at": "2023-01-01T00:00:00",
            "locked_by": None
        }
        schema = CADModelSchema()
        model = schema.load(data)
        
        self.assertEqual(model.part_id, "ENG-003")
        self.assertEqual(model.version, 3)
        self.assertEqual(model.oid, "test-oid-123")
        self.assertIsInstance(model.geometry, Geometry)
        self.assertEqual(model.geometry.type, "Line")
        self.assertEqual(len(model.geometry.vertices), 2)

if __name__ == '__main__':
    unittest.main()
