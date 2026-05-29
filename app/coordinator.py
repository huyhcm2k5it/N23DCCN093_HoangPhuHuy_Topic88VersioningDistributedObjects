"""
Coordinator metadata service.
Coordinator stores only metadata (no full CAD geometry payloads).
"""

import json
import os
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS


class CoordinatorMetadataStore:
    def __init__(self, db_path=None):
        default_db = os.path.join(os.path.dirname(__file__), "db", "Coordinator-Meta.db")
        self.db_path = db_path or default_db
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_schema()

    def _conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(self._schema_sql())
        conn.commit()
        return conn

    def _init_schema(self):
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            conn.executescript(self._schema_sql())
            conn.commit()

    def _schema_sql(self):
        return """
        CREATE TABLE IF NOT EXISTS oid_registry (
            part_id TEXT PRIMARY KEY,
            oid TEXT NOT NULL UNIQUE,
            created_site TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS version_graph (
            part_id TEXT NOT NULL,
            oid TEXT NOT NULL,
            version INTEGER NOT NULL,
            branch TEXT NOT NULL,
            checksum TEXT,
            parent_version INTEGER,
            parent_branch TEXT,
            site_id TEXT,
            created_at TEXT,
            PRIMARY KEY (part_id, version, branch)
        );

        CREATE TABLE IF NOT EXISTS branch_heads (
            part_id TEXT NOT NULL,
            branch TEXT NOT NULL,
            head_version INTEGER NOT NULL,
            oid TEXT,
            checksum TEXT,
            site_id TEXT,
            updated_at TEXT,
            PRIMARY KEY (part_id, branch)
        );

        CREATE TABLE IF NOT EXISTS conflicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id TEXT NOT NULL,
            oid TEXT,
            site_id TEXT,
            base_version INTEGER,
            conflict_branch TEXT,
            detail TEXT,
            timestamp TEXT
        );

        CREATE TABLE IF NOT EXISTS site_health (
            site_id TEXT PRIMARY KEY,
            network_online INTEGER,
            status TEXT,
            outbox_json TEXT,
            updated_at TEXT
        );
        """

    def _now(self):
        return datetime.now().isoformat()

    def register_object(self, payload):
        part_id = payload["part_id"]
        oid = payload["oid"]
        site_id = payload.get("site_id", "")

        with self._conn() as conn:
            row = conn.execute(
                "SELECT oid FROM oid_registry WHERE part_id=?",
                (part_id,),
            ).fetchone()
            if row and row[0] != oid:
                return {
                    "success": False,
                    "error": "OID_MISMATCH",
                    "message": f"part_id {part_id} already mapped to different oid",
                }

            conn.execute(
                """INSERT OR IGNORE INTO oid_registry(part_id, oid, created_site, created_at)
                   VALUES (?, ?, ?, ?)""",
                (part_id, oid, site_id, self._now()),
            )
            conn.commit()

        return {
            "success": True,
            "part_id": part_id,
            "oid": oid,
            "site_id": site_id,
        }

    def update_head(self, payload):
        part_id = payload["part_id"]
        oid = payload["oid"]
        version = int(payload["version"])
        branch = payload.get("branch") or "main"
        checksum = payload.get("checksum")
        parent_version = payload.get("parent_version")
        parent_branch = payload.get("parent_branch")
        site_id = payload.get("site_id", "")
        now = self._now()

        self.register_object(payload)

        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO version_graph
                   (part_id, oid, version, branch, checksum, parent_version, parent_branch, site_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    part_id,
                    oid,
                    version,
                    branch,
                    checksum,
                    parent_version,
                    parent_branch,
                    site_id,
                    now,
                ),
            )

            existing = conn.execute(
                "SELECT head_version FROM branch_heads WHERE part_id=? AND branch=?",
                (part_id, branch),
            ).fetchone()
            should_update_head = (not existing) or version >= int(existing[0])
            if should_update_head:
                conn.execute(
                    """INSERT OR REPLACE INTO branch_heads
                       (part_id, branch, head_version, oid, checksum, site_id, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (part_id, branch, version, oid, checksum, site_id, now),
                )
            conn.commit()

        return {
            "success": True,
            "part_id": part_id,
            "oid": oid,
            "branch": branch,
            "version": version,
            "site_id": site_id,
        }

    def record_conflict(self, payload):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO conflicts
                   (part_id, oid, site_id, base_version, conflict_branch, detail, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    payload.get("part_id"),
                    payload.get("oid"),
                    payload.get("site_id"),
                    payload.get("base_version"),
                    payload.get("conflict_branch"),
                    payload.get("detail"),
                    payload.get("timestamp") or self._now(),
                ),
            )
            conn.commit()
        return {"success": True}

    def update_site_health(self, payload):
        site_id = payload["site_id"]
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO site_health
                   (site_id, network_online, status, outbox_json, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    site_id,
                    1 if payload.get("network_online", True) else 0,
                    payload.get("status", "unknown"),
                    json.dumps(payload.get("outbox", {}), ensure_ascii=False),
                    payload.get("timestamp") or self._now(),
                ),
            )
            conn.commit()
        return {"success": True, "site_id": site_id}

    def get_version_graph(self, part_id):
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT part_id, oid, version, branch, checksum, parent_version, parent_branch, site_id, created_at
                   FROM version_graph
                   WHERE part_id=?
                   ORDER BY version ASC, branch ASC""",
                (part_id,),
            ).fetchall()

        nodes = []
        for row in rows:
            nodes.append(
                {
                    "part_id": row[0],
                    "oid": row[1],
                    "version": row[2],
                    "branch": row[3],
                    "checksum": row[4],
                    "parent_version": row[5],
                    "parent_branch": row[6],
                    "site_id": row[7],
                    "created_at": row[8],
                }
            )

        return {
            "part_id": part_id,
            "nodes": nodes,
            "source": "coordinator",
        }

    def list_sites(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT site_id, network_online, status, outbox_json, updated_at FROM site_health ORDER BY site_id"
            ).fetchall()
        return [
            {
                "site_id": row[0],
                "network_online": bool(row[1]),
                "status": row[2],
                "outbox": json.loads(row[3]) if row[3] else {},
                "updated_at": row[4],
            }
            for row in rows
        ]


def create_coordinator_app(db_path=None):
    app = Flask(__name__)
    CORS(app)

    store = CoordinatorMetadataStore(db_path=db_path)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "service": "coordinator",
            "sites": store.list_sites(),
        })

    @app.route("/meta/register-object", methods=["POST"])
    def meta_register_object():
        data = request.get_json(silent=True) or {}
        required = ["part_id", "oid", "site_id"]
        if any(k not in data for k in required):
            return jsonify({"success": False, "error": "MISSING_FIELDS", "required": required}), 400
        result = store.register_object(data)
        return jsonify(result), 200 if result.get("success") else 409

    @app.route("/meta/update-head", methods=["POST"])
    def meta_update_head():
        data = request.get_json(silent=True) or {}
        required = ["part_id", "oid", "version", "branch", "site_id"]
        if any(k not in data for k in required):
            return jsonify({"success": False, "error": "MISSING_FIELDS", "required": required}), 400
        result = store.update_head(data)
        return jsonify(result), 200

    @app.route("/meta/record-conflict", methods=["POST"])
    def meta_record_conflict():
        data = request.get_json(silent=True) or {}
        required = ["part_id", "oid", "site_id", "conflict_branch"]
        if any(k not in data for k in required):
            return jsonify({"success": False, "error": "MISSING_FIELDS", "required": required}), 400
        return jsonify(store.record_conflict(data)), 201

    @app.route("/meta/site-health", methods=["POST"])
    def meta_site_health():
        data = request.get_json(silent=True) or {}
        if "site_id" not in data:
            return jsonify({"success": False, "error": "MISSING_FIELDS", "required": ["site_id"]}), 400
        return jsonify(store.update_site_health(data)), 200

    @app.route("/meta/version-graph/<part_id>", methods=["GET"])
    def meta_version_graph(part_id):
        return jsonify(store.get_version_graph(part_id)), 200

    return app
