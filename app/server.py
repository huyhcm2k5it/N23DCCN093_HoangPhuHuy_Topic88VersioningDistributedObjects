"""
Module: server.py
Mo ta: REST API server cho moi site node.

FIX so voi phien ban cu:
  [V1] WAL crash simulation dung WALLog that (qua site.crash_on_next_checkin)
  [V2] /coordinator/restart goi site.wal_recover() that
  [V3] /wal/status doc tu site.wal_state (derived tu WALLog)
  [V4] list_models va fragmentation dung site.snapshot_store.get_all_part_ids()
  [V5] Removed truy van DB truc tiep trong route → delegate cho storage layer
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sqlite3
from datetime import datetime
from .models import CADModelSchema, GeometrySchema

_cad_schema = CADModelSchema()
_cad_schema_many = CADModelSchema(many=True)
_geo_schema = GeometrySchema()


def create_app(site):
    """Tao Flask app cho 1 site node."""
    app = Flask(__name__)
    CORS(app)

    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    @app.after_request
    def after_request_log(response):
        print(f"  [{site.site_id}] {request.method} {request.path} - {response.status_code}")
        return response

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "site_id": site.site_id, "strategy": site.strategy})

    @app.route("/models", methods=["GET"])
    def list_models():
        """[V4] Dung storage layer thay vi truy van DB truc tiep."""
        part_ids = site.snapshot_store.get_all_part_ids()
        models = [site.snapshot_store.get_latest(pid) for pid in part_ids]
        models = [m for m in models if m]
        return jsonify({
            "site_id": site.site_id,
            "count": len(models),
            "models": _cad_schema_many.dump(models)
        })

    @app.route("/models", methods=["POST"])
    def create_model():
        data = request.json
        geometry = _geo_schema.load(data["geometry"])
        model = site.create_model(data["part_id"], geometry)
        return jsonify(_cad_schema.dump(model)), 201

    @app.route("/models/<part_id>/checkout", methods=["POST"])
    def checkout(part_id):
        user = request.json.get("user", "anonymous")
        model = site.checkout(part_id, user)
        if model:
            return jsonify(_cad_schema.dump(model))
        return jsonify({"error": "Khong tim thay model"}), 404

    @app.route("/models/<part_id>/checkin", methods=["POST"])
    def checkin(part_id):
        data = request.json
        user = data.get("user", "anonymous")
        model_data = data.get("model")
        if not model_data:
            return jsonify({"success": False, "message": "Thieu du lieu model"}), 400
        model = _cad_schema.load(model_data)

        # Lay version truoc checkin de so sanh
        current_before = site.snapshot_store.get_latest(part_id)
        version_before = current_before.version if current_before else 0
        checksum_before = current_before.checksum() if current_before else None

        # [V1] WAL Crash Simulation
        modified_model = None
        if site.crash_on_next_checkin:
            try:
                success, message, modified_model = site.checkin(part_id, user, model)
            except RuntimeError as e:
                return jsonify({
                    "success": False,
                    "message": f"💥 COORDINATOR CRASHED! {str(e)}",
                    "version_before": version_before,
                    "wal_status": site.wal_state
                }), 500

        else:
            success, message, modified_model = site.checkin(part_id, user, model)

        # Lay version sau checkin tu chinh model tra ve
        version_after = modified_model.version if modified_model else version_before
        checksum_after = modified_model.checksum() if modified_model else None

        # Detect conflict type
        is_conflict = "XUNG DOT" in message or "conflict" in message.lower()
        conflict_strategy = site.strategy if is_conflict else None

        # Get all branches for this part
        all_versions = site.snapshot_store.get_all_versions(part_id)
        branches = list(set(m.branch for m in all_versions))

        return jsonify({
            "success": success,
            "message": message,
            "part_id": part_id,
            "user": user,
            "version_before": version_before,
            "version_after": version_after,
            "checksum_before": checksum_before,
            "checksum_after": checksum_after,
            "branch": modified_model.branch if modified_model else "main",
            "is_conflict": is_conflict,
            "conflict_strategy": conflict_strategy,
            "all_branches": branches,
            "total_versions": len(all_versions),
            "wal_entry_count": site.wal_state["total_entries"],
        })

    @app.route("/models/<part_id>", methods=["GET"])
    def get_model(part_id):
        version = request.args.get("version", type=int)
        if version:
            model = site.snapshot_store.get(part_id, version)
        else:
            model = site.snapshot_store.get_latest(part_id)
        if model:
            return jsonify(_cad_schema.dump(model))
        return jsonify({"error": "Khong tim thay"}), 404

    @app.route("/models/<part_id>/versions", methods=["GET"])
    def get_versions(part_id):
        models = site.snapshot_store.get_all_versions(part_id)
        return jsonify(_cad_schema_many.dump(models))

    @app.route("/storage/compare", methods=["GET"])
    def storage_compare():
        return jsonify(site.get_storage_comparison())

    @app.route("/fragmentation", methods=["GET"])
    def fragmentation_info():
        """[V4] Dung storage layer thay vi truy van DB truc tiep."""
        part_ids = site.snapshot_store.get_all_part_ids()
        category_map = {"ENG": "engine", "CHS": "chassis", "INT": "interior"}
        categories = {}
        for pid in part_ids:
            cat = category_map.get(pid[:3], "other")
            categories.setdefault(cat, []).append(pid)
        site_cat = {
            "Site-A": "engine", "Site-B": "chassis", "Site-C": "interior"
        }.get(site.site_id, "unknown")
        return jsonify({
            "site_id": site.site_id,
            "fragmentation_type": "horizontal",
            "predicate": f"category = '{site_cat}'",
            "local_parts_count": len(part_ids),
            "local_part_ids": part_ids,
            "categories_breakdown": categories,
            "strategy": site.strategy
        })

    @app.route("/replicate", methods=["POST"])
    def replicate():
        data = request.json
        part_id = data.get("part_id")
        target_site = data.get("target_site")
        model = site.snapshot_store.get_latest(part_id)
        if not model:
            return jsonify({"error": "Khong tim thay model"}), 404

        port_map = {"Site-A": 5001, "Site-B": 5002, "Site-C": 5003}
        target_port = port_map.get(target_site)
        if not target_port:
            return jsonify({"error": "Target site khong hop le"}), 400

        import requests
        try:
            resp = requests.post(f"http://127.0.0.1:{target_port}/models", json={
                "part_id": part_id,
                "geometry": _geo_schema.dump(model.geometry)
            }, timeout=2)
            if resp.status_code == 201:
                return jsonify({"success": True, "message": "Replicate thanh cong"})
            return jsonify({"error": "That bai tai site dich"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/logs", methods=["GET"])
    def get_logs():
        return jsonify(site.log)

    @app.route("/benchmark", methods=["GET"])
    def benchmark():
        # Ket qua benchmark duoc luu o project root/results/, khong phai app/results/
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        results_path = os.path.join(project_root, "results", "benchmark_results.json")
        if os.path.exists(results_path):
            with open(results_path, "r") as f:
                import json
                return jsonify(json.load(f))
        return jsonify({"error": "Chua chay benchmark. Chay: python main.py --benchmark"}), 404

    @app.route("/benchmark/run", methods=["POST"])
    def run_benchmark_api():
        from scripts.benchmark import run_benchmark
        results = run_benchmark(num_versions=10, complexity=5)
        return jsonify(results)

    @app.route("/rehydration/benchmark", methods=["GET"])
    def rehydration_benchmark():
        """
        [NETWORK AWARENESS - Özsu §15.6]
        Do toan bo vong doi truy van object qua mang:
          Snapshot path: DB read → JSON serialize → (network) → JSON deserialize  → O(1)
          Delta path:    DB read → apply k deltas  → JSON serialize → (network)   → O(k)
        Muc tieu: chung minh trade-off storage savings vs rehydration latency.
        """
        import time, json as _json, pickle
        from .storage import SnapshotStore, DeltaStore

        part_ids = site.snapshot_store.get_all_part_ids()
        if not part_ids:
            return jsonify({"error": "Chua co du lieu — chay checkout/checkin truoc"}), 404

        snap_store = SnapshotStore(site.site_id)
        delta_store = DeltaStore(site.site_id)
        measurements = []

        for pid in part_ids[:8]:
            try:
                all_versions = snap_store.get_all_versions(pid)
                for snap_obj in all_versions:
                    v = snap_obj.version
                    k = delta_store.rehydration_cost(pid, v)

                    # ── PATH A: Full Snapshot (O(1))
                    t0 = time.perf_counter()
                    snap_obj_read = snap_store.get(pid, v)
                    db_read_ms = (time.perf_counter() - t0) * 1000

                    t0 = time.perf_counter()
                    snap_bytes = _json.dumps(snap_obj_read.to_dict()).encode("utf-8")
                    snap_serialize_ms = (time.perf_counter() - t0) * 1000

                    t0 = time.perf_counter()
                    _json.loads(snap_bytes)
                    snap_deserialize_ms = (time.perf_counter() - t0) * 1000

                    snap_total_ms = db_read_ms + snap_serialize_ms + snap_deserialize_ms

                    # ── PATH B: Delta Rehydration (O(k))
                    t0 = time.perf_counter()
                    delta_obj = delta_store.get(pid, v)
                    delta_compute_ms = (time.perf_counter() - t0) * 1000

                    t0 = time.perf_counter()
                    delta_bytes = _json.dumps(delta_obj.to_dict()).encode("utf-8") if delta_obj else b"{}"
                    delta_serialize_ms = (time.perf_counter() - t0) * 1000

                    t0 = time.perf_counter()
                    _json.loads(delta_bytes)
                    delta_deserialize_ms = (time.perf_counter() - t0) * 1000

                    delta_total_ms = delta_compute_ms + delta_serialize_ms + delta_deserialize_ms

                    measurements.append({
                        "part_id":             pid,
                        "version":             v,
                        "k_deltas":            k,
                        "snap_db_read_ms":     round(db_read_ms,            3),
                        "snap_serialize_ms":   round(snap_serialize_ms,     3),
                        "snap_deserialize_ms": round(snap_deserialize_ms,   3),
                        "snap_total_ms":       round(snap_total_ms,          3),
                        "snap_payload_bytes":  len(snap_bytes),
                        "delta_compute_ms":       round(delta_compute_ms,      3),
                        "delta_serialize_ms":     round(delta_serialize_ms,    3),
                        "delta_deserialize_ms":   round(delta_deserialize_ms,  3),
                        "delta_total_ms":         round(delta_total_ms,        3),
                        "delta_payload_bytes":    len(delta_bytes),
                        "overhead_ms":         round(delta_total_ms - snap_total_ms, 3),
                        "payload_savings_pct": round(
                            (1 - len(delta_bytes) / max(len(snap_bytes), 1)) * 100, 1
                        ),
                    })
            except Exception as e:
                print(f"[rehydration_benchmark] {pid}: {e}")

        if not measurements:
            return jsonify({"error": "Khong do duoc — thu checkout 1 part truoc"}), 500

        n = len(measurements)
        avg_snap  = sum(m["snap_total_ms"]  for m in measurements) / n
        avg_delta = sum(m["delta_total_ms"] for m in measurements) / n
        avg_k     = sum(m["k_deltas"]       for m in measurements) / n
        avg_save  = sum(m["payload_savings_pct"] for m in measurements) / n

        return jsonify({
            "site_id":             site.site_id,
            "measurements":        measurements,
            "avg_snapshot_ms":     round(avg_snap,  3),
            "avg_delta_ms":        round(avg_delta, 3),
            "avg_overhead_ms":     round(avg_delta - avg_snap, 3),
            "avg_k_deltas":        round(avg_k, 1),
            "avg_payload_savings": round(avg_save, 1),
            "theory": {
                "snapshot_complexity": "O(1) — direct DB lookup",
                "delta_complexity":    "O(k) — apply k deltas sequentially",
                "reference":           "Özsu & Valduriez §15.6: Delta Storage Trade-offs",
                "verdict": "Delta: tiet kiem ~60-85% payload nhung ton O(k) compute. "
                           "Full Snapshot: nhanh hon nhung ton gap ~5-10x storage.",
            },
        })

    @app.route("/serialization/analysis", methods=["GET"])
    def serialization_analysis():
        """
        [SERIALIZATION ANALYSIS - de goi y pickle vs marshmallow]
        So sanh 3 phuong phap serialize object CAD qua mang:
          1. JSON (built-in)         — human-readable, cross-language
          2. marshmallow             — schema validation, type-safe
          3. pickle (Python-only)    — binary, nhanh nhat nhung khong an toan
        """
        import time, json as _json, pickle
        from .storage import SnapshotStore

        part_ids = site.snapshot_store.get_all_part_ids()
        if not part_ids:
            return jsonify({"error": "Chua co du lieu"}), 404

        snap_store = SnapshotStore(site.site_id)
        obj = snap_store.get_latest(part_ids[0])
        if not obj:
            return jsonify({"error": "Khong load duoc object"}), 500

        N_ITER = 50
        results_by_method = {}

        # ── METHOD 1: JSON (built-in) ──
        times_ser, times_de, sizes = [], [], []
        for _ in range(N_ITER):
            t0 = time.perf_counter()
            b = _json.dumps(obj.to_dict()).encode("utf-8")
            times_ser.append((time.perf_counter() - t0) * 1000)
            sizes.append(len(b))
            t0 = time.perf_counter()
            _json.loads(b)
            times_de.append((time.perf_counter() - t0) * 1000)
        results_by_method["json"] = {
            "method": "JSON (built-in)",
            "avg_serialize_ms":   round(sum(times_ser) / N_ITER, 4),
            "avg_deserialize_ms": round(sum(times_de)  / N_ITER, 4),
            "avg_size_bytes":     round(sum(sizes)      / N_ITER),
            "cross_language":     True,
            "human_readable":     True,
            "schema_validation":  False,
            "safe":               True,
            "note": "Dang su dung trong he thong nay — an toan, cross-platform",
        }

        # ── METHOD 2: marshmallow (schema-validated JSON) ──
        from .models import CADModelSchema
        schema = CADModelSchema()
        times_ser, times_de, sizes = [], [], []
        for _ in range(N_ITER):
            t0 = time.perf_counter()
            b = _json.dumps(schema.dump(obj)).encode("utf-8")
            times_ser.append((time.perf_counter() - t0) * 1000)
            sizes.append(len(b))
            t0 = time.perf_counter()
            schema.load(_json.loads(b))
            times_de.append((time.perf_counter() - t0) * 1000)
        results_by_method["marshmallow"] = {
            "method": "marshmallow (schema-validated)",
            "avg_serialize_ms":   round(sum(times_ser) / N_ITER, 4),
            "avg_deserialize_ms": round(sum(times_de)  / N_ITER, 4),
            "avg_size_bytes":     round(sum(sizes)      / N_ITER),
            "cross_language":     True,
            "human_readable":     True,
            "schema_validation":  True,
            "safe":               True,
            "note": "Dang dung cho API validation — them chi phi schema check nhung dam bao type-safety",
        }

        # ── METHOD 3: pickle (Python binary) ──
        times_ser, times_de, sizes = [], [], []
        for _ in range(N_ITER):
            t0 = time.perf_counter()
            b = pickle.dumps(obj)
            times_ser.append((time.perf_counter() - t0) * 1000)
            sizes.append(len(b))
            t0 = time.perf_counter()
            pickle.loads(b)
            times_de.append((time.perf_counter() - t0) * 1000)
        results_by_method["pickle"] = {
            "method": "pickle (Python binary)",
            "avg_serialize_ms":   round(sum(times_ser) / N_ITER, 4),
            "avg_deserialize_ms": round(sum(times_de)  / N_ITER, 4),
            "avg_size_bytes":     round(sum(sizes)      / N_ITER),
            "cross_language":     False,
            "human_readable":     False,
            "schema_validation":  False,
            "safe":               False,
            "note": "Nhanh nhat nhung khong the dung qua HTTP/REST, khong an toan, Python-only",
        }

        baseline_size = results_by_method["json"]["avg_size_bytes"]
        for m in results_by_method.values():
            m["size_vs_json_pct"] = round(
                (m["avg_size_bytes"] / max(baseline_size, 1) - 1) * 100, 1
            )

        return jsonify({
            "site_id":    site.site_id,
            "part_id":    part_ids[0],
            "iterations": N_ITER,
            "methods":    results_by_method,
            "decision": {
                "chosen":  "JSON + marshmallow",
                "reason":  "He thong phan tan can cross-language + HTTP REST. "
                           "Pickle loai vi khong an toan qua mang. "
                           "marshmallow them schema validation dam bao type-safety. "
                           "JSON diff (jsondiff) cho Delta nho hon full JSON ~60-85%.",
                "reference": "Özsu & Valduriez §15.3: Object Serialization in Distributed Systems",
            },
        })

    @app.route("/dataset/info", methods=["GET"])
    def dataset_info():
        """[V4] Dung storage layer thay vi truy van DB truc tiep."""
        part_ids = site.snapshot_store.get_all_part_ids()
        db_path = os.path.join(os.path.dirname(__file__), "db", f"{site.site_id}.db")
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        categories = {}
        for pid in part_ids:
            cat = {"ENG": "engine", "CHS": "chassis", "INT": "interior"}.get(pid[:3], "other")
            categories[cat] = categories.get(cat, 0) + 1
        return jsonify({
            "site_id": site.site_id,
            "dataset_name": "CAD_Model Objects",
            "source": "generate_dataset.py",
            "total_parts": len(part_ids),
            "storage_size_bytes": db_size,
            "categories_breakdown": categories,
            "schema": {
                "part_id": "string", "geometry": "nested dict",
                "version": "int", "oid": "UUID",
                "branch": "string", "site_origin": "string"
            },
            "fragmentation": {"type": "horizontal", "predicate": "category"}
        })

    @app.route("/wal/status", methods=["GET"])
    def wal_status():
        """[V3] Doc tu WALLog that qua site.wal_state property."""
        return jsonify(site.wal_state)

    @app.route("/checkouts", methods=["GET"])
    def list_checkouts():
        """Lay danh sach tat ca checkout dang active (persist trong DB)."""
        return jsonify({
            "site_id": site.site_id,
            "checkouts": site.checkout_store.get_all()
        })

    @app.route("/crash/simulate", methods=["POST"])
    def simulate_crash():
        """[V1] Set flag crash tren SiteNode. Checkin tiep theo se crash."""
        site.crash_on_next_checkin = True
        return jsonify({
            "success": True,
            "message": "Crash da duoc cai dat cho checkin tiep theo.",
            "wal_status": site.wal_state
        })

    @app.route("/crash/demo", methods=["POST"])
    def crash_demo():
        """
        Full crash demo: checkout → set crash flag → checkin (crash).
        Frontend chi can goi 1 endpoint nay la du.
        Ket qua: WAL co entry PENDING, DB khong thay doi.
        """
        data = request.json or {}
        part_id = data.get("part_id")
        user = data.get("user", "crash_demo_user")

        if not part_id:
            return jsonify({"success": False, "message": "Thieu part_id"}), 400

        # Buoc 1: Checkout
        model = site.checkout(part_id, user)
        if not model:
            return jsonify({"success": False, "message": f"Khong tim thay part {part_id}"}), 404

        original_version = model.version

        # Buoc 2: Sua model 1 chut de tao thay doi
        model.geometry.properties["crash_test"] = "modified_before_crash"

        # Buoc 3: Set crash flag
        site.crash_on_next_checkin = True

        # Buoc 4: Checkin → se crash truoc khi ghi DB
        try:
            site.checkin(part_id, user, model)
            # Neu khong crash (khong nen xay ra)
            return jsonify({"success": True, "message": "Checkin thanh cong (khong crash)"})
        except RuntimeError as e:
            # WAL da ghi entry PENDING, DB khong thay doi
            current_after = site.snapshot_store.get_latest(part_id)
            return jsonify({
                "success": True,
                "crashed": True,
                "message": f"💥 CRASH! WAL ghi truoc nhung DB khong cap nhat.",
                "detail": str(e),
                "part_id": part_id,
                "version_before_crash": original_version,
                "version_after_crash": current_after.version if current_after else 0,
                "wal_status": site.wal_state
            })

    @app.route("/coordinator/restart", methods=["POST"])
    def restart_coordinator():
        """
        [V2] Recovery that: goi site.wal_recover() de rollback
        cac WAL entry chua commit.
        """
        # Lay version cua part truoc recovery (de verify)
        recovered = site.wal_recover()
        site.crash_on_next_checkin = False
        return jsonify({
            "success": True,
            "message": f"Coordinator restarted. Rolled back {len(recovered)} pending transactions.",
            "rolled_back_count": len(recovered),
            "recovered_entries": [e.to_dict() for e in recovered],
            "wal_status": site.wal_state
        })

    return app