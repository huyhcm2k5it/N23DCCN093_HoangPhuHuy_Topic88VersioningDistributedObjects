"""Flask routes for one distributed CAD site."""

import hashlib
import json
import os

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from marshmallow import ValidationError

from .models import CADModelSchema, GeometrySchema


_cad_schema = CADModelSchema()
_cad_many = CADModelSchema(many=True)
_geo_schema = GeometrySchema()
_SITE_PORT_MAP = {"Site-A": 5001, "Site-B": 5002, "Site-C": 5003}


def create_app(site):
    app = Flask(__name__)
    CORS(app)

    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    def payload():
        return request.get_json(silent=True) or {}

    def request_hash(data):
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def error(message, status=400, **extra):
        return jsonify({"success": False, "message": message, **extra}), status

    @app.after_request
    def quiet(response):
        return response

    @app.before_request
    def block_inter_site_when_offline():
        inter_site = request.path.startswith("/replication/incoming") or request.headers.get("X-Replication-Source")
        if inter_site and not site.network_online:
            return error(
                f"{site.site_id} dang bi ngat ket noi lien-site.",
                503,
                error="NODE_DISCONNECTED",
                site_id=site.site_id,
                network_status=site.network_state,
            )

    @app.get("/health")
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

    @app.get("/network/status")
    def network_status():
        return jsonify(site.network_state)

    @app.post("/network/disconnect")
    def network_disconnect():
        return jsonify({"success": True, "network_status": site.disconnect_network()})

    @app.post("/network/reconnect")
    def network_reconnect():
        network = site.reconnect_network()
        results = [deliver(op) for op in site.replication_outbox.pending()]
        delivered = sum(1 for item in results if item["delivered"])
        return jsonify({
            "success": True,
            "network_status": network,
            "auto_replay": {
                "attempted": len(results),
                "delivered": delivered,
                "still_pending": len(results) - delivered,
                "results": results,
            },
        })

    def deliver(op, failure_mode=None):
        if not op:
            return {"delivered": False, "message": "Outbox operation khong ton tai.", "outbox_entry": None}
        if op.get("status") == "ACKED":
            return {"delivered": True, "message": "Operation da ACK truoc do.", "outbox_entry": op}
        if not site.network_online:
            failed = site.replication_outbox.mark_failed(op["op_id"], "SOURCE_SITE_OFFLINE")
            return {"delivered": False, "message": "Source offline; operation giu trong outbox.", "outbox_entry": failed}

        port = _SITE_PORT_MAP.get(op["target_site"])
        if not port:
            failed = site.replication_outbox.mark_failed(op["op_id"], "INVALID_TARGET_SITE")
            return {"delivered": False, "message": "Target site khong hop le.", "outbox_entry": failed}

        try:
            response = requests.post(
                f"http://127.0.0.1:{port}/replication/incoming",
                json={
                    "op_id": op["op_id"],
                    "source_site": site.site_id,
                    "target_site": op["target_site"],
                    "model": op["payload"],
                    "failure_mode": failure_mode,
                },
                headers={"X-Replication-Source": site.site_id, "X-Replication-Op-Id": op["op_id"]},
                timeout=2,
            )
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            if response.status_code in (200, 201):
                return {
                    "delivered": True,
                    "message": "Replicate thanh cong va da ACK.",
                    "target_response": body,
                    "outbox_entry": site.replication_outbox.mark_delivered(op["op_id"]),
                }
            failed = site.replication_outbox.mark_failed(op["op_id"], f"HTTP {response.status_code}: {response.text}")
            return {"delivered": False, "message": "Target chua ACK; se retry.", "target_response": body, "outbox_entry": failed}
        except Exception as exc:
            failed = site.replication_outbox.mark_failed(op["op_id"], exc)
            return {"delivered": False, "message": "Network error; se retry.", "detail": str(exc), "outbox_entry": failed}

    @app.get("/models")
    def list_models():
        models = [site.snapshot_store.get_latest(pid) for pid in site.snapshot_store.get_all_part_ids()]
        models = [model for model in models if model]
        return jsonify({"site_id": site.site_id, "count": len(models), "models": _cad_many.dump(models)})

    @app.post("/models")
    def create_model():
        data = payload()
        candidate = data.get("model", data)
        part_id = candidate.get("part_id") if isinstance(candidate, dict) else None
        replicated = bool(data.get("replicated")) or bool(request.headers.get("X-Replication-Source"))
        is_import = "model" in data or {"oid", "version", "branch"}.intersection(data.keys())

        if part_id and not replicated and not site.accepts_local_part(part_id):
            return error(
                f"{site.site_id} chi quan ly prefix {site.expected_fragment_prefix()}-.",
                400,
                error="FRAGMENTATION_CONSTRAINT_VIOLATION",
                expected_category=site.expected_fragment_category(),
            )
        try:
            if is_import:
                model = site.import_model(_cad_schema.load(candidate), source_site=request.headers.get("X-Replication-Source"))
            else:
                if not data.get("part_id") or data.get("geometry") is None:
                    return error("Can co 'part_id' va 'geometry'.", 400, error="MISSING_REQUIRED_FIELDS")
                model = site.create_model(data["part_id"], _geo_schema.load(data["geometry"]))
        except ValidationError as exc:
            return error("Payload khong dung schema.", 400, error="SCHEMA_VALIDATION_ERROR", details=exc.messages)
        return jsonify(_cad_schema.dump(model)), 201

    @app.get("/models/<part_id>")
    def get_model(part_id):
        version = request.args.get("version", type=int)
        model = site.snapshot_store.get(part_id, version) if version else site.snapshot_store.get_latest(part_id)
        return jsonify(_cad_schema.dump(model)) if model else error("Khong tim thay model.", 404)

    @app.get("/models/<part_id>/versions")
    def get_versions(part_id):
        return jsonify(_cad_many.dump(site.snapshot_store.get_all_versions(part_id)))

    @app.post("/models/<part_id>/checkout")
    def checkout(part_id):
        model = site.checkout(part_id, payload().get("user", "anonymous"))
        return jsonify(_cad_schema.dump(model)) if model else error("Khong tim thay model.", 404)

    @app.post("/models/<part_id>/checkin")
    def checkin(part_id):
        data = payload()
        if not data.get("model"):
            return error("Thieu du lieu model.", 400)
        try:
            model = _cad_schema.load(data["model"])
        except ValidationError as exc:
            return error("Model payload khong hop le.", 400, details=exc.messages)

        before = site.snapshot_store.get_latest(part_id)
        ok, message, checked_in = site.checkin(part_id, data.get("user", "anonymous"), model)
        versions = site.snapshot_store.get_all_versions(part_id)
        body = {
            "success": ok,
            "message": message,
            "part_id": part_id,
            "version_before": before.version if before else 0,
            "version_after": checked_in.version if checked_in else (before.version if before else 0),
            "checksum_before": before.checksum() if before else None,
            "checksum_after": checked_in.checksum() if checked_in else None,
            "branch": checked_in.branch if checked_in else "main",
            "is_conflict": "XUNG DOT" in (message or "") or "conflict" in (message or "").lower(),
            "conflict_strategy": "branching" if checked_in and checked_in.branch != "main" else None,
            "all_branches": sorted({model.branch for model in versions}),
            "total_versions": len(versions),
        }
        if ok:
            return jsonify(body)
        status = 409 if "chua checkout" in (message or "").lower() else 400
        return jsonify(body), status

    @app.get("/storage/compare")
    def storage_compare():
        return jsonify(site.get_storage_comparison())

    @app.get("/fragmentation")
    def fragmentation_info():
        part_ids = site.snapshot_store.get_all_part_ids()
        categories = {}
        for part_id in part_ids:
            category = {"ENG": "engine", "CHS": "chassis", "INT": "interior"}.get(part_id[:3], "other")
            categories.setdefault(category, []).append(part_id)
        site_category = {"Site-A": "engine", "Site-B": "chassis", "Site-C": "interior"}.get(site.site_id, "unknown")
        return jsonify({
            "site_id": site.site_id,
            "fragmentation_type": "horizontal",
            "predicate": f"category = '{site_category}'",
            "local_parts_count": len(part_ids),
            "local_part_ids": part_ids,
            "categories_breakdown": categories,
            "strategy": site.strategy,
        })

    @app.post("/replicate")
    def replicate():
        data = payload()
        part_id, target_site = data.get("part_id"), data.get("target_site")
        if not part_id or not target_site:
            return error("Can co 'part_id' va 'target_site'.", 400, error="MISSING_REQUIRED_FIELDS")
        if target_site == site.site_id or target_site not in _SITE_PORT_MAP:
            return error("Target site khong hop le.", 400, error="INVALID_TARGET_SITE")
        model = site.snapshot_store.get_latest(part_id)
        if not model:
            return error("Khong tim thay model.", 404)

        op = site.replication_outbox.enqueue_model(target_site, model)
        failure_mode = data.get("failure_mode") or ("after_commit_ack_lost" if data.get("simulate_timeout_after_commit") else None)
        result = deliver(op, failure_mode=failure_mode)
        return jsonify({
            "success": result["delivered"],
            "queued": not result["delivered"],
            "message": result["message"],
            "part_id": part_id,
            "target_site": target_site,
            "op_id": op["op_id"],
            "outbox_entry": result["outbox_entry"],
            "delivery": result,
        }), 200 if result["delivered"] else 202

    @app.post("/replication/incoming")
    def replication_incoming():
        data = payload()
        source_site = data.get("source_site") or request.headers.get("X-Replication-Source")
        op_id = data.get("op_id") or request.headers.get("X-Replication-Op-Id")
        if not source_site or not op_id or not data.get("model"):
            return error("Replication can source_site, op_id va model.", 400, error="MISSING_REPLICATION_METADATA")
        if source_site not in _SITE_PORT_MAP or source_site == site.site_id:
            return error("source_site khong hop le.", 400, error="INVALID_SOURCE_SITE")

        try:
            incoming = _cad_schema.load(data["model"])
        except ValidationError as exc:
            return error("Model replication khong dung schema.", 400, error="SCHEMA_VALIDATION_ERROR", details=exc.messages)
        failure_mode = data.get("failure_mode")
        if failure_mode not in (None, "", "before_commit", "after_commit_ack_lost"):
            return error("failure_mode khong hop le.", 400, error="INVALID_FAILURE_MODE")

        idem_payload = {"source_site": source_site, "target_site": site.site_id, "model": incoming.to_dict()}
        inbox_entry, claimed, _ = site.replication_inbox.claim_or_get(op_id, idem_payload, source_site, incoming)
        if not claimed:
            if inbox_entry["request_hash"] != request_hash(idem_payload):
                return error("Cung op_id nhung payload khac.", 409, error="IDEMPOTENCY_HASH_CONFLICT")
            if inbox_entry["stored_response_json"] is not None:
                stored = dict(inbox_entry["stored_response_json"])
                stored["idempotent_duplicate"] = True
                return jsonify(stored)
            return error("Operation dang xu ly, vui long retry.", 409, error="IDEMPOTENCY_IN_PROGRESS")
        if failure_mode == "before_commit":
            site.replication_inbox.delete(op_id)
            return error("SIMULATED_BEFORE_COMMIT_FAILURE", 503, op_id=op_id)
        existing = site.snapshot_store.get_exact(incoming.part_id, incoming.version, incoming.branch or "main")
        duplicate = bool(existing and existing.oid == incoming.oid and existing.checksum() == incoming.checksum())
        imported = site.import_model(incoming, source_site=source_site)
        body = {
            "success": True,
            "message": "Replication duplicate da ACK idempotent" if duplicate else "Replication imported",
            "op_id": op_id,
            "idempotent_duplicate": duplicate,
            "stored": {"part_id": imported.part_id, "oid": imported.oid, "version": imported.version, "branch": imported.branch},
        }
        site.replication_inbox.store_response(op_id, body)
        if failure_mode == "after_commit_ack_lost":
            return error("SIMULATED_ACK_LOSS_AFTER_COMMIT", 504, op_id=op_id)
        return jsonify(body), 200 if duplicate else 201

    @app.get("/replication/outbox")
    def replication_outbox():
        entries = site.replication_outbox.list(status=request.args.get("status"), target_site=request.args.get("target_site"))
        return jsonify({"site_id": site.site_id, "summary": site.replication_outbox.summary(), "entries": entries})

    @app.post("/replication/replay")
    def replication_replay():
        data = payload()
        target_site = data.get("target_site")
        if target_site and target_site not in _SITE_PORT_MAP:
            return error("target_site khong hop le.", 400, error="INVALID_TARGET_SITE")
        pending = site.replication_outbox.pending(target_site=target_site)[: int(data.get("limit", 200))]
        results = [deliver(op) for op in pending]
        delivered = sum(1 for item in results if item["delivered"])
        return jsonify({
            "success": True, "message": f"Replay complete: {delivered}/{len(results)} operations ACKED.",
            "site_id": site.site_id, "target_site": target_site, "attempted": len(results),
            "delivered": delivered, "still_pending": len(results) - delivered,
            "outbox": site.replication_outbox.summary(), "results": results,
        })

    @app.get("/benchmark")
    def benchmark():
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "benchmark_results.json")
        if not os.path.exists(path):
            return error("Chua chay benchmark. Chay: python main.py --benchmark", 404)
        with open(path, "r", encoding="utf-8") as file:
            return jsonify(json.load(file))

    @app.post("/benchmark/run")
    def run_benchmark_api():
        from scripts.benchmark import run_benchmark
        return jsonify(run_benchmark(num_versions=10, complexity=5))

    @app.post("/rehydrate")
    def rehydrate_object():
        data = payload()
        oid = data.get("oid")
        target_version = data.get("target_version")
        branch = data.get("branch", "main")
        if not oid or target_version is None:
            return error("Can co 'oid' va 'target_version'.", 400, error="MISSING_REQUIRED_FIELDS")
        try:
            target_version = int(target_version)
        except Exception:
            return error("Vui long nhap target_version la so nguyen.", 400, error="INVALID_TARGET_VERSION")

        model, meta = site.delta_store.rehydrate(oid, target_version, branch=branch)
        if not model:
            return error("Khong tim thay target version.", 404, **meta)

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

    @app.get("/replication/inbox")
    def replication_inbox():
        return jsonify({
            "site_id": site.site_id,
            "entries": site.replication_inbox.list(status=request.args.get("status")),
        })

    @app.get("/logs")
    def get_logs():
        return jsonify(site.log)

    @app.get("/dataset/info")
    def dataset_info():
        part_ids = site.snapshot_store.get_all_part_ids()
        db_path = os.path.join(os.path.dirname(__file__), "db", f"{site.site_id}.db")
        categories = {}
        for part_id in part_ids:
            category = {"ENG": "engine", "CHS": "chassis", "INT": "interior"}.get(part_id[:3], "other")
            categories[category] = categories.get(category, 0) + 1
        return jsonify({
            "site_id": site.site_id,
            "dataset_name": "CAD_Model Objects",
            "total_parts": len(part_ids),
            "storage_size_bytes": os.path.getsize(db_path) if os.path.exists(db_path) else 0,
            "categories_breakdown": categories,
            "schema": {"part_id": "string", "geometry": "nested dict", "version": "int", "oid": "UUID", "branch": "string"},
            "fragmentation": {"type": "horizontal", "predicate": "category"},
        })

    @app.get("/checkouts")
    def list_checkouts():
        return jsonify({
            "site_id": site.site_id,
            "checkouts": site.checkout_store.get_all(),
        })

    return app
