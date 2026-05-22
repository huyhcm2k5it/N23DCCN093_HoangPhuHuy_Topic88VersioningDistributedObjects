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
import hashlib
import json
from datetime import datetime
from marshmallow import ValidationError
from .models import CADModelSchema, GeometrySchema

_cad_schema = CADModelSchema()
_cad_schema_many = CADModelSchema(many=True)
_geo_schema = GeometrySchema()
_SITE_PORT_MAP = {"Site-A": 5001, "Site-B": 5002, "Site-C": 5003}


def create_app(site):
    """Tao Flask app cho 1 site node."""
    app = Flask(__name__)
    CORS(app)

    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    def _json_payload():
        payload = request.get_json(silent=True)
        return payload if isinstance(payload, dict) else {}

    def _request_hash(payload):
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @app.after_request
    def after_request_log(response):
        print(f"  [{site.site_id}] {request.method} {request.path} - {response.status_code}")
        return response

    @app.before_request
    def reject_when_network_disconnected():
        """Gia lap node disconnect: chi chan request lien-site, van cho local write."""
        is_inter_site = (
            request.path.startswith("/replication/incoming")
            or bool(request.headers.get("X-Replication-Source"))
        )
        if not site.network_online and is_inter_site:
            return jsonify({
                "success": False,
                "error": "NODE_DISCONNECTED",
                "message": f"{site.site_id} dang bi ngat ket noi lien-site; local transaction van hoat dong.",
                "site_id": site.site_id,
                "network_status": site.network_state,
            }), 503

    @app.route("/health", methods=["GET"])
    def health():
        site.push_site_health()
        return jsonify({
            "status": "ok" if site.network_online else "disconnected",
            "site_id": site.site_id,
            "strategy": site.strategy,
            "network_online": site.network_online,
            "mode": site.network_state["mode"],
            "outbox": site.replication_outbox.summary(),
        })

    @app.route("/network/status", methods=["GET"])
    def network_status():
        return jsonify(site.network_state)

    @app.route("/network/disconnect", methods=["POST"])
    def network_disconnect():
        return jsonify({
            "success": True,
            "message": f"{site.site_id} da bi ngat ket noi mang.",
            "network_status": site.disconnect_network(),
        })

    @app.route("/network/reconnect", methods=["POST"])
    def network_reconnect():
        network = site.reconnect_network()
        pending_ops = site.replication_outbox.pending()
        replay_results = [_attempt_replication_delivery(op) for op in pending_ops]
        delivered = sum(1 for result in replay_results if result["delivered"])
        return jsonify({
            "success": True,
            "message": f"{site.site_id} da ket noi lai mang.",
            "network_status": network,
            "auto_replay": {
                "attempted": len(replay_results),
                "delivered": delivered,
                "still_pending": len(replay_results) - delivered,
                "results": replay_results,
            },
        })

    def _attempt_replication_delivery(op, failure_mode=None):
        """
        Deliver 1 outbox operation sang target.
        Idempotent theo op_id: neu source timeout sau khi target commit,
        replay lai cung op_id se duoc target ACK duplicate thay vi ghi sai.
        """
        if not op:
            return {
                "delivered": False,
                "message": "Outbox operation khong ton tai.",
                "outbox_entry": None,
            }
        if op.get("status") == "ACKED":
            return {
                "delivered": True,
                "message": "Operation da ACK truoc do.",
                "outbox_entry": op,
            }
        if not site.network_online:
            failed = site.replication_outbox.mark_failed(op["op_id"], "SOURCE_SITE_OFFLINE")
            return {
                "delivered": False,
                "message": "Source site dang local-only; operation giu trong outbox.",
                "error": "SOURCE_SITE_OFFLINE",
                "outbox_entry": failed,
            }

        target_site = op["target_site"]
        target_port = _SITE_PORT_MAP.get(target_site)
        if not target_port:
            failed = site.replication_outbox.mark_failed(op["op_id"], "INVALID_TARGET_SITE")
            return {
                "delivered": False,
                "message": "Target site khong hop le.",
                "error": "INVALID_TARGET_SITE",
                "outbox_entry": failed,
            }

        import requests
        try:
            response = requests.post(
                f"http://127.0.0.1:{target_port}/replication/incoming",
                json={
                    "op_id": op["op_id"],
                    "source_site": site.site_id,
                    "target_site": target_site,
                    "model": op["payload"],
                    "failure_mode": failure_mode,
                },
                headers={
                    "X-Replication-Source": site.site_id,
                    "X-Replication-Op-Id": op["op_id"],
                },
                timeout=2,
            )
            try:
                target_payload = response.json()
            except ValueError:
                target_payload = {"raw_response": response.text}

            if response.status_code in (200, 201):
                acked = site.replication_outbox.mark_delivered(op["op_id"])
                return {
                    "delivered": True,
                    "message": "Replicate thanh cong va da ACK.",
                    "target_status_code": response.status_code,
                    "target_response": target_payload,
                    "outbox_entry": acked,
                }

            failed = site.replication_outbox.mark_failed(
                op["op_id"],
                f"HTTP {response.status_code}: {response.text}",
            )
            return {
                "delivered": False,
                "message": "Target chua ACK; operation giu trong outbox de retry.",
                "error": "TARGET_NOT_ACKED",
                "target_status_code": response.status_code,
                "target_response": target_payload,
                "outbox_entry": failed,
            }
        except Exception as exc:
            failed = site.replication_outbox.mark_failed(op["op_id"], exc)
            return {
                "delivered": False,
                "message": "Network timeout/disconnect; operation giu trong outbox de retry.",
                "error": "NODE_DISCONNECT_OR_TIMEOUT",
                "target_site": target_site,
                "detail": str(exc),
                "outbox_entry": failed,
            }

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
        data = _json_payload()
        if not data:
            return jsonify({
                "success": False,
                "error": "INVALID_JSON_PAYLOAD",
                "message": "Body JSON khong hop le hoac dang rong.",
            }), 400

        is_import = "model" in data or {"oid", "version", "branch"}.intersection(data.keys())
        replicated = bool(data.get("replicated")) or bool(request.headers.get("X-Replication-Source"))
        candidate = data.get("model", data)
        incoming_part_id = candidate.get("part_id") if isinstance(candidate, dict) else None

        if incoming_part_id and not replicated and not site.accepts_local_part(incoming_part_id):
            expected_prefix = site.expected_fragment_prefix()
            expected_category = site.expected_fragment_category()
            return jsonify({
                "success": False,
                "error": "FRAGMENTATION_CONSTRAINT_VIOLATION",
                "message": (
                    f"{site.site_id} chi quan ly fragment {expected_category} "
                    f"voi part_id prefix {expected_prefix}-."
                ),
                "site_id": site.site_id,
                "part_id": incoming_part_id,
                "expected_prefix": expected_prefix,
                "expected_category": expected_category,
                "hint": "Dung /replicate de sao chep object hop le giua cac site.",
            }), 400

        try:
            if "model" in data:
                model = _cad_schema.load(data["model"])
                model = site.import_model(model, source_site=request.headers.get("X-Replication-Source"))
            elif is_import:
                model = _cad_schema.load(data)
                model = site.import_model(model, source_site=request.headers.get("X-Replication-Source"))
            else:
                part_id = data.get("part_id")
                geometry_payload = data.get("geometry")
                if not part_id or geometry_payload is None:
                    return jsonify({
                        "success": False,
                        "error": "MISSING_REQUIRED_FIELDS",
                        "message": "Can co day du 'part_id' va 'geometry' khi tao model local.",
                    }), 400
                geometry = _geo_schema.load(geometry_payload)
                model = site.create_model(part_id, geometry)
        except ValidationError as err:
            return jsonify({
                "success": False,
                "error": "SCHEMA_VALIDATION_ERROR",
                "details": err.messages,
            }), 400

        return jsonify(_cad_schema.dump(model)), 201

    @app.route("/models/<part_id>/checkout", methods=["POST"])
    def checkout(part_id):
        payload = _json_payload()
        user = payload.get("user", "anonymous")
        model = site.checkout(part_id, user)
        if model:
            return jsonify(_cad_schema.dump(model))
        return jsonify({"error": "Khong tim thay model"}), 404

    @app.route("/models/<part_id>/checkin", methods=["POST"])
    def checkin(part_id):
        data = _json_payload()
        user = data.get("user", "anonymous")
        model_data = data.get("model")
        if not model_data:
            return jsonify({"success": False, "message": "Thieu du lieu model"}), 400
        try:
            model = _cad_schema.load(model_data)
        except ValidationError as err:
            return jsonify({
                "success": False,
                "message": "Model payload khong hop le",
                "details": err.messages,
            }), 400

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
        conflict_strategy = "branching" if is_conflict else None

        # Get all branches for this part
        all_versions = site.snapshot_store.get_all_versions(part_id)
        branches = list(set(m.branch for m in all_versions))

        response_body = {
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
        }
        if success:
            return jsonify(response_body), 200
        lowered = (message or "").lower()
        if "chua checkout" in lowered:
            return jsonify(response_body), 409
        if "khong khop" in lowered or "thieu" in lowered:
            return jsonify(response_body), 400
        return jsonify(response_body), 500

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

    @app.route("/models/<part_id>/version-graph", methods=["GET"])
    def get_version_graph(part_id):
        return jsonify(site.get_version_graph(part_id))

    @app.route("/storage/compare", methods=["GET"])
    def storage_compare():
        return jsonify(site.get_storage_comparison())

    @app.route("/rehydrate", methods=["POST"])
    def rehydrate_object():
        data = _json_payload()
        oid = data.get("oid")
        target_version = data.get("target_version")
        branch = data.get("branch", "main")
        if not oid or target_version is None:
            return jsonify({
                "success": False,
                "error": "MISSING_REQUIRED_FIELDS",
                "message": "Can co 'oid' va 'target_version'.",
            }), 400
        try:
            target_version = int(target_version)
        except Exception:
            return jsonify({
                "success": False,
                "error": "INVALID_TARGET_VERSION",
            }), 400

        model, meta = site.delta_store.rehydrate(oid, target_version, branch=branch)
        if not model:
            return jsonify({
                "success": False,
                **meta,
            }), 404

        snapshot_model = site.snapshot_store.get_exact(meta["part_id"], target_version, branch) or site.snapshot_store.get(meta["part_id"], target_version, branch)
        snapshot_checksum = snapshot_model.checksum() if snapshot_model else None
        rehydrated_checksum = model.checksum()

        return jsonify({
            "success": True,
            "site_id": site.site_id,
            "model": _cad_schema.dump(model),
            "metrics": meta,
            "rehydrated_checksum": rehydrated_checksum,
            "snapshot_checksum": snapshot_checksum,
            "checksum_match": bool(snapshot_checksum and snapshot_checksum == rehydrated_checksum),
        })

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
        data = _json_payload()
        part_id = data.get("part_id")
        target_site = data.get("target_site")
        if not part_id or not target_site:
            return jsonify({
                "success": False,
                "error": "MISSING_REQUIRED_FIELDS",
                "message": "Can co 'part_id' va 'target_site'.",
            }), 400
        if target_site == site.site_id:
            return jsonify({
                "success": False,
                "error": "INVALID_TARGET_SITE",
                "message": "Khong duoc replicate vao chinh site nguon.",
            }), 400
        model = site.snapshot_store.get_latest(part_id)
        if not model:
            return jsonify({"error": "Khong tim thay model"}), 404
        if target_site not in _SITE_PORT_MAP:
            return jsonify({"success": False, "error": "Target site khong hop le"}), 400

        op = site.replication_outbox.enqueue_model(target_site, model)
        failure_mode = data.get("failure_mode")
        if not failure_mode and data.get("simulate_timeout_after_commit"):
            failure_mode = "after_commit_ack_lost"
        result = _attempt_replication_delivery(
            op,
            failure_mode=failure_mode,
        )
        status_code = 200 if result["delivered"] else 202
        return jsonify({
            "success": result["delivered"],
            "queued": not result["delivered"],
            "message": result["message"],
            "part_id": part_id,
            "target_site": target_site,
            "failure_mode": failure_mode,
            "op_id": op["op_id"],
            "outbox_entry": result["outbox_entry"],
            "delivery": result,
        }), status_code

    @app.route("/replication/incoming", methods=["POST"])
    def replication_incoming():
        data = _json_payload()
        model_data = data.get("model")
        if not model_data:
            return jsonify({"success": False, "error": "Thieu model"}), 400

        source_site = data.get("source_site") or request.headers.get("X-Replication-Source")
        op_id = data.get("op_id") or request.headers.get("X-Replication-Op-Id")
        if not source_site or not op_id:
            return jsonify({
                "success": False,
                "error": "MISSING_REPLICATION_METADATA",
                "message": "Replication incoming yeu cau source_site va op_id.",
            }), 400
        if source_site not in _SITE_PORT_MAP:
            return jsonify({
                "success": False,
                "error": "INVALID_SOURCE_SITE",
                "message": "source_site khong hop le.",
            }), 400
        if source_site == site.site_id:
            return jsonify({
                "success": False,
                "error": "INVALID_SOURCE_SITE",
                "message": "source_site khong duoc trung voi target site.",
            }), 400
        try:
            incoming = _cad_schema.load(model_data)
        except ValidationError as err:
            return jsonify({
                "success": False,
                "error": "SCHEMA_VALIDATION_ERROR",
                "details": err.messages,
            }), 400

        failure_mode = data.get("failure_mode")
        if failure_mode not in (None, "", "before_commit", "after_commit_ack_lost"):
            return jsonify({
                "success": False,
                "error": "INVALID_FAILURE_MODE",
                "message": "failure_mode hop le: before_commit | after_commit_ack_lost",
            }), 400

        idempotency_payload = {
            "source_site": source_site,
            "target_site": site.site_id,
            "model": incoming.to_dict(),
        }
        request_hash = _request_hash(idempotency_payload)
        inbox_entry, claimed, _ = site.replication_inbox.claim_or_get(
            op_id=op_id,
            request_payload=idempotency_payload,
            source_site=source_site,
            model=incoming,
        )

        if not claimed:
            if inbox_entry["request_hash"] != request_hash:
                return jsonify({
                    "success": False,
                    "error": "IDEMPOTENCY_HASH_CONFLICT",
                    "message": "Cung op_id nhung payload khac. Tu choi de tranh duplicate side-effect.",
                    "op_id": op_id,
                    "stored_request_hash": inbox_entry["request_hash"],
                    "incoming_request_hash": request_hash,
                }), 409

            if inbox_entry["stored_response_json"] is not None:
                stored = dict(inbox_entry["stored_response_json"])
                stored["idempotent_duplicate"] = True
                stored["op_id"] = op_id
                stored["source_site"] = source_site
                stored["target_site"] = site.site_id
                return jsonify(stored), 200

            return jsonify({
                "success": False,
                "error": "IDEMPOTENCY_IN_PROGRESS",
                "message": "Operation dang duoc xu ly, vui long retry.",
                "op_id": op_id,
            }), 409

        if failure_mode == "before_commit":
            response_body = {
                "success": False,
                "message": "SIMULATED_BEFORE_COMMIT_FAILURE: target chua ghi DB.",
                "op_id": op_id,
                "source_site": source_site,
                "target_site": site.site_id,
                "failure_mode": "before_commit",
            }
            site.replication_inbox.delete(op_id)
            return jsonify(response_body), 503

        requested = {
            "version": incoming.version,
            "branch": incoming.branch or "main",
            "checksum": incoming.checksum(),
            "oid": incoming.oid,
        }

        existing = site.snapshot_store.get_exact(incoming.part_id, incoming.version, incoming.branch or "main")
        idempotent_duplicate = bool(
            existing
            and existing.oid == incoming.oid
            and existing.checksum() == incoming.checksum()
        )

        imported = site.import_model(incoming, source_site=source_site)
        conflict_resolved = (
            imported.version != requested["version"]
            or (imported.branch or "main") != requested["branch"]
        )
        response_body = {
            "success": True,
            "message": (
                "Replication duplicate da ACK idempotent"
                if idempotent_duplicate
                else "Replication imported"
            ),
            "op_id": op_id,
            "source_site": source_site,
            "target_site": site.site_id,
            "idempotent_duplicate": idempotent_duplicate,
            "conflict_resolved": conflict_resolved,
            "requested": requested,
            "stored": {
                "part_id": imported.part_id,
                "oid": imported.oid,
                "version": imported.version,
                "branch": imported.branch,
                "checksum": imported.checksum(),
            },
        }
        site.replication_inbox.store_response(op_id, response_body, status="PROCESSED")

        if failure_mode == "after_commit_ack_lost":
            return jsonify({
                "success": False,
                "message": "SIMULATED_ACK_LOSS_AFTER_COMMIT: target da commit, source se retry bang op_id.",
                "op_id": op_id,
                "source_site": source_site,
                "target_site": site.site_id,
                "failure_mode": "after_commit_ack_lost",
            }), 504

        return jsonify(response_body), 200 if idempotent_duplicate else 201

    @app.route("/replication/outbox", methods=["GET"])
    def replication_outbox():
        return jsonify({
            "site_id": site.site_id,
            "summary": site.replication_outbox.summary(),
            "entries": site.replication_outbox.list(
                status=request.args.get("status"),
                target_site=request.args.get("target_site"),
            ),
        })

    @app.route("/replication/inbox", methods=["GET"])
    def replication_inbox():
        return jsonify({
            "site_id": site.site_id,
            "entries": site.replication_inbox.list(status=request.args.get("status")),
        })

    @app.route("/replication/replay", methods=["POST"])
    def replication_replay():
        data = _json_payload()
        target_site = data.get("target_site")
        if target_site and target_site not in _SITE_PORT_MAP:
            return jsonify({
                "success": False,
                "error": "INVALID_TARGET_SITE",
                "message": "target_site khong hop le.",
            }), 400
        limit = data.get("limit", 200)
        try:
            limit = max(1, min(int(limit), 1000))
        except Exception:
            return jsonify({
                "success": False,
                "error": "INVALID_LIMIT",
                "message": "limit phai la so nguyen trong khoang 1..1000.",
            }), 400
        pending = site.replication_outbox.pending(target_site=target_site)
        selected = pending[:limit]
        results = [_attempt_replication_delivery(op) for op in selected]
        delivered = sum(1 for result in results if result["delivered"])
        return jsonify({
            "success": True,
            "message": f"Replay complete: {delivered}/{len(results)} operations ACKED.",
            "site_id": site.site_id,
            "target_site": target_site,
            "attempted": len(results),
            "delivered": delivered,
            "still_pending": len(results) - delivered,
            "remaining_queue": max(len(pending) - len(selected), 0),
            "outbox": site.replication_outbox.summary(),
            "results": results,
        })

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
                    full_snapshot_bytes = len(snap_bytes)
                    delta_patch_bytes = delta_store.delta_patch_bytes(pid, v, branch=snap_obj.branch or "main")
                    saving_percent = round(
                        (1 - delta_patch_bytes / max(full_snapshot_bytes, 1)) * 100, 1
                    )

                    measurements.append({
                        "part_id":             pid,
                        "version":             v,
                        "rehydration_steps":   k,
                        "snap_db_read_ms":     round(db_read_ms,            3),
                        "snap_serialize_ms":   round(snap_serialize_ms,     3),
                        "snap_deserialize_ms": round(snap_deserialize_ms,   3),
                        "snap_total_ms":       round(snap_total_ms,          3),
                        "full_snapshot_bytes": full_snapshot_bytes,
                        "delta_compute_ms":       round(delta_compute_ms,      3),
                        "delta_serialize_ms":     round(delta_serialize_ms,    3),
                        "delta_deserialize_ms":   round(delta_deserialize_ms,  3),
                        "delta_total_ms":         round(delta_total_ms,        3),
                        "delta_patch_bytes":      delta_patch_bytes,
                        "rehydrated_object_bytes": len(delta_bytes),
                        "overhead_ms":         round(delta_total_ms - snap_total_ms, 3),
                        "saving_percent":      saving_percent,
                    })
            except Exception as e:
                print(f"[rehydration_benchmark] {pid}: {e}")

        if not measurements:
            return jsonify({"error": "Khong do duoc — thu checkout 1 part truoc"}), 500

        n = len(measurements)
        avg_snap  = sum(m["snap_total_ms"]  for m in measurements) / n
        avg_delta = sum(m["delta_total_ms"] for m in measurements) / n
        avg_k     = sum(m["rehydration_steps"] for m in measurements) / n
        avg_save  = sum(m["saving_percent"] for m in measurements) / n

        return jsonify({
            "site_id":             site.site_id,
            "measurements":        measurements,
            "avg_snapshot_ms":     round(avg_snap,  3),
            "avg_delta_ms":        round(avg_delta, 3),
            "avg_overhead_ms":     round(avg_delta - avg_snap, 3),
            "avg_rehydration_steps": round(avg_k, 1),
            "avg_payload_savings": round(avg_save, 1),
            "theory": {
                "snapshot_complexity": "O(1) — direct DB lookup",
                "delta_complexity":    "O(k) — apply k deltas sequentially",
                "reference":           "Özsu & Valduriez §15.6: Delta Storage Trade-offs",
                "metric_note": "Storage bytes la logical JSON payload bytes, khong phai physical SQLite file size.",
                "verdict": "Delta: tiet kiem payload nhung ton O(k) compute. "
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
                "part_id": "string", "category": "string",
                "geometry": "nested dict",
                "geometry.properties.tolerance_mm": "float",
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
