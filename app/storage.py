import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta

from .models import CADModel, Delta, Geometry


_DB_DIR = os.path.join(os.path.dirname(__file__), "db")
_initialized_dbs = set()
_init_lock = threading.Lock()

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS snapshots (part_id TEXT NOT NULL, version INTEGER NOT NULL, branch TEXT NOT NULL DEFAULT 'main', oid TEXT, site_origin TEXT DEFAULT '', created_at TEXT, modified_at TEXT, locked_by TEXT, geometry TEXT NOT NULL, PRIMARY KEY (part_id, version, branch));
CREATE INDEX IF NOT EXISTS idx_snapshots_part ON snapshots(part_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_branch ON snapshots(part_id, branch);
CREATE TABLE IF NOT EXISTS bases (part_id TEXT PRIMARY KEY, version INTEGER NOT NULL DEFAULT 1, oid TEXT, site_origin TEXT DEFAULT '', created_at TEXT, geometry TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS deltas (part_id TEXT NOT NULL, branch TEXT NOT NULL DEFAULT 'main', from_version INTEGER NOT NULL, to_version INTEGER NOT NULL, changes TEXT NOT NULL, timestamp TEXT, author_site TEXT DEFAULT '', PRIMARY KEY (part_id, branch, from_version, to_version));
CREATE INDEX IF NOT EXISTS idx_deltas_part ON deltas(part_id);
CREATE INDEX IF NOT EXISTS idx_deltas_branch ON deltas(part_id, branch);
CREATE TABLE IF NOT EXISTS checkouts (part_id TEXT NOT NULL, user TEXT NOT NULL, base_version INTEGER NOT NULL, checkout_time TEXT, model_json TEXT NOT NULL, PRIMARY KEY (part_id, user));
CREATE TABLE IF NOT EXISTS replication_outbox (op_id TEXT PRIMARY KEY, source_site TEXT NOT NULL, target_site TEXT NOT NULL, part_id TEXT NOT NULL, oid TEXT, version INTEGER NOT NULL, branch TEXT NOT NULL DEFAULT 'main', payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING', attempt_count INTEGER NOT NULL DEFAULT 0, last_error TEXT, next_retry_at TEXT, created_at TEXT, updated_at TEXT, acked_at TEXT);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON replication_outbox(status);
CREATE INDEX IF NOT EXISTS idx_outbox_target ON replication_outbox(target_site, status);
CREATE TABLE IF NOT EXISTS replication_inbox (op_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, source_site TEXT NOT NULL, part_id TEXT NOT NULL, oid TEXT, version INTEGER, branch TEXT NOT NULL DEFAULT 'main', checksum TEXT, status TEXT NOT NULL DEFAULT 'PROCESSED', processed_at TEXT, stored_response_json TEXT, stored_response_hash TEXT);
CREATE INDEX IF NOT EXISTS idx_inbox_source ON replication_inbox(source_site, processed_at);
"""


def _get_db_path(site_id):
    os.makedirs(_DB_DIR, exist_ok=True)
    return os.path.join(_DB_DIR, f"{site_id}.db")


def _get_conn(site_id):
    conn = sqlite3.connect(_get_db_path(site_id), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    with _init_lock:
        if site_id not in _initialized_dbs:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
            _initialized_dbs.add(site_id)
    return conn


def _json_size(value):
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _one(site_id, sql, params=()):
    with _get_conn(site_id) as conn:
        return conn.execute(sql, params).fetchone()


def _all(site_id, sql, params=()):
    with _get_conn(site_id) as conn:
        return conn.execute(sql, params).fetchall()


def _write(site_id, sql, params=()):
    with _get_conn(site_id) as conn:
        conn.execute(sql, params)
        conn.commit()


def _model_from_snapshot(row):
    if not row:
        return None
    return CADModel(
        part_id=row["part_id"],
        version=row["version"],
        branch=row["branch"] or "main",
        oid=row["oid"],
        site_origin=row["site_origin"] or "",
        created_at=row["created_at"],
        modified_at=row["modified_at"],
        locked_by=row["locked_by"],
        geometry=Geometry.from_dict(json.loads(row["geometry"])),
    )


class SnapshotStore:
    def __init__(self, site_id):
        self.site_id = site_id

    def save(self, model):
        _write(
            self.site_id,
            """INSERT OR REPLACE INTO snapshots (part_id, version, branch, oid, site_origin, created_at, modified_at, locked_by, geometry)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (model.part_id, model.version, model.branch or "main", model.oid, model.site_origin, model.created_at, model.modified_at, model.locked_by, json.dumps(model.geometry.to_dict(), ensure_ascii=False)),
        )
        return model.snapshot_size()

    def get(self, part_id, version, branch="main"):
        return self.get_exact(part_id, version, branch)

    def get_exact(self, part_id, version, branch="main"):
        row = _one(self.site_id, "SELECT * FROM snapshots WHERE part_id=? AND version=? AND branch=?", (part_id, version, branch or "main"))
        return _model_from_snapshot(row)

    def get_latest(self, part_id, branch="main"):
        row = _one(self.site_id, "SELECT * FROM snapshots WHERE part_id=? AND branch=? ORDER BY version DESC LIMIT 1", (part_id, branch or "main"))
        return _model_from_snapshot(row)

    def get_all_versions(self, part_id):
        rows = _all(self.site_id, "SELECT * FROM snapshots WHERE part_id=? ORDER BY version ASC, branch ASC", (part_id,))
        return [_model_from_snapshot(row) for row in rows]

    def get_all_part_ids(self):
        rows = _all(self.site_id, "SELECT DISTINCT part_id FROM snapshots ORDER BY part_id")
        return [row["part_id"] for row in rows]

    def total_storage_bytes(self):
        return sum(model.snapshot_size() for part_id in self.get_all_part_ids() for model in self.get_all_versions(part_id))


class DeltaStore:
    def __init__(self, site_id):
        self.site_id = site_id

    def save_base(self, model):
        _write(
            self.site_id,
            "INSERT OR REPLACE INTO bases (part_id, version, oid, site_origin, created_at, geometry) VALUES (?, ?, ?, ?, ?, ?)",
            (model.part_id, model.version, model.oid, model.site_origin, model.created_at, json.dumps(model.geometry.to_dict(), ensure_ascii=False)),
        )
        return model.snapshot_size()

    def save_delta(self, delta):
        _write(
            self.site_id,
            "INSERT OR REPLACE INTO deltas (part_id, branch, from_version, to_version, changes, timestamp, author_site) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (delta.part_id, delta.branch or "main", delta.from_version, delta.to_version, json.dumps(delta.changes, ensure_ascii=False), delta.timestamp, delta.author_site),
        )
        return delta.size_bytes()

    def _base(self, part_id):
        row = _one(self.site_id, "SELECT * FROM bases WHERE part_id=?", (part_id,))
        if not row:
            return None
        return CADModel(
            part_id=row["part_id"],
            version=row["version"],
            oid=row["oid"],
            site_origin=row["site_origin"] or "",
            created_at=row["created_at"],
            modified_at=row["created_at"],
            branch="main",
            geometry=Geometry.from_dict(json.loads(row["geometry"])),
        )

    def _chain(self, part_id, branch):
        rows = _all(self.site_id, "SELECT * FROM deltas WHERE part_id=? AND branch=? ORDER BY from_version ASC, to_version ASC", (part_id, branch or "main"))
        return [
            Delta(
                part_id=row["part_id"],
                branch=row["branch"] or "main",
                from_version=row["from_version"],
                to_version=row["to_version"],
                changes=json.loads(row["changes"]),
                timestamp=row["timestamp"],
                author_site=row["author_site"] or "",
            )
            for row in rows
        ]

    def get(self, part_id, version, branch="main"):
        model = self._base(part_id)
        if not model or version <= model.version:
            return model
        for delta in self._chain(part_id, branch):
            if delta.from_version == model.version and delta.to_version <= version:
                model = delta.apply(model)
            if model.version == version:
                model.branch = branch or "main"
                return model
        return None

    def get_latest(self, part_id, branch="main"):
        row = _one(self.site_id, "SELECT MAX(to_version) AS version FROM deltas WHERE part_id=? AND branch=?", (part_id, branch or "main"))
        return self.get(part_id, row["version"] if row and row["version"] else 1, branch)

    def total_storage_bytes(self):
        bases = _all(self.site_id, "SELECT geometry FROM bases")
        deltas = _all(self.site_id, "SELECT changes FROM deltas")
        return sum(_json_size(json.loads(row["geometry"])) for row in bases) + sum(_json_size(json.loads(row["changes"])) for row in deltas)

    def rehydration_cost(self, part_id, version, branch="main"):
        base = self._base(part_id)
        return 0 if not base or version <= base.version else sum(1 for delta in self._chain(part_id, branch) if base.version < delta.to_version <= version)

    def rehydrate(self, part_id, target_version, branch="main"):
        return self.get(part_id, target_version, branch)


class CheckoutStore:
    def __init__(self, site_id):
        self.site_id = site_id

    def save(self, part_id, user, base_version, model, checkout_time):
        _write(self.site_id, "INSERT OR REPLACE INTO checkouts (part_id, user, base_version, checkout_time, model_json) VALUES (?, ?, ?, ?, ?)", (part_id, user, base_version, checkout_time, json.dumps(model.to_dict(), ensure_ascii=False)))

    def get(self, part_id, user):
        row = _one(self.site_id, "SELECT * FROM checkouts WHERE part_id=? AND user=?", (part_id, user))
        return None if not row else {"part_id": row["part_id"], "user": row["user"], "base_version": row["base_version"], "checkout_time": row["checkout_time"], "model": CADModel.from_dict(json.loads(row["model_json"]))}

    def delete(self, part_id, user):
        _write(self.site_id, "DELETE FROM checkouts WHERE part_id=? AND user=?", (part_id, user))

    def get_all(self):
        rows = _all(self.site_id, "SELECT * FROM checkouts")
        return [
            {
                "part_id": row["part_id"],
                "user": row["user"],
                "base_version": row["base_version"],
                "checkout_time": row["checkout_time"],
                "model": CADModel.from_dict(json.loads(row["model_json"]))
            }
            for row in rows
        ]

class ReplicationOutboxStore:
    def __init__(self, site_id):
        self.site_id = site_id

    def _now(self):
        return datetime.now().isoformat()

    def make_op_id(self, target_site, model):
        raw = f"{self.site_id}|{target_site}|{model.oid}|{model.version}|{model.branch or 'main'}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def enqueue_model(self, target_site, model):
        op_id, now = self.make_op_id(target_site, model), self._now()
        _write(
            self.site_id,
            """INSERT OR REPLACE INTO replication_outbox
               (op_id, source_site, target_site, part_id, oid, version, branch, payload_json, status, attempt_count, last_error, next_retry_at, created_at, updated_at, acked_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0, NULL, NULL, COALESCE((SELECT created_at FROM replication_outbox WHERE op_id=?), ?), ?, NULL)""",
            (op_id, self.site_id, target_site, model.part_id, model.oid, model.version, model.branch or "main", json.dumps(model.to_dict(), ensure_ascii=False), op_id, now, now),
        )
        return self.get(op_id)

    def _row(self, row):
        if not row:
            return None
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json"))
        return data

    def get(self, op_id):
        return self._row(_one(self.site_id, "SELECT * FROM replication_outbox WHERE op_id=?", (op_id,)))

    def list(self, status=None, target_site=None):
        sql, params = "SELECT * FROM replication_outbox WHERE 1=1", []
        if status:
            sql, params = sql + " AND status=?", params + [status]
        if target_site:
            sql, params = sql + " AND target_site=?", params + [target_site]
        return [self._row(row) for row in _all(self.site_id, sql + " ORDER BY created_at DESC", params)]

    def pending(self, target_site=None):
        sql, params = "SELECT * FROM replication_outbox WHERE status IN ('PENDING', 'FAILED')", []
        if target_site:
            sql, params = sql + " AND target_site=?", [target_site]
        return [self._row(row) for row in _all(self.site_id, sql + " ORDER BY created_at ASC", params)]

    def mark_delivered(self, op_id):
        now = self._now()
        _write(self.site_id, "UPDATE replication_outbox SET status='ACKED', updated_at=?, acked_at=?, last_error=NULL, next_retry_at=NULL WHERE op_id=?", (now, now, op_id))
        return self.get(op_id)

    def mark_failed(self, op_id, error):
        row = _one(self.site_id, "SELECT attempt_count FROM replication_outbox WHERE op_id=?", (op_id,))
        attempt = (row["attempt_count"] if row else 0) + 1
        retry_at = (datetime.now() + timedelta(seconds=min(60, 2 ** min(attempt, 5)))).isoformat()
        _write(self.site_id, "UPDATE replication_outbox SET status='FAILED', attempt_count=?, last_error=?, next_retry_at=?, updated_at=? WHERE op_id=?", (attempt, str(error), retry_at, self._now(), op_id))
        return self.get(op_id)

    def summary(self):
        summary = {"PENDING": 0, "FAILED": 0, "ACKED": 0}
        for row in _all(self.site_id, "SELECT status, COUNT(*) AS count FROM replication_outbox GROUP BY status"):
            summary[row["status"]] = row["count"]
        return summary


class ReplicationInboxStore:
    def __init__(self, site_id):
        self.site_id = site_id

    def _hash(self, payload):
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _row(self, row):
        if not row:
            return None
        data = dict(row)
        if data.get("stored_response_json") is not None:
            data["stored_response_json"] = json.loads(data["stored_response_json"])
        return data

    def get(self, op_id):
        return self._row(_one(self.site_id, "SELECT * FROM replication_inbox WHERE op_id=?", (op_id,)))

    def claim_or_get(self, op_id, request_payload, source_site, model):
        existing = self.get(op_id)
        if existing:
            return existing, False, None
        _write(
            self.site_id,
            "INSERT INTO replication_inbox (op_id, request_hash, source_site, part_id, oid, version, branch, checksum, status, processed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PROCESSING', ?)",
            (op_id, self._hash(request_payload), source_site, model.part_id, model.oid, model.version, model.branch or "main", model.checksum(), datetime.now().isoformat()),
        )
        return self.get(op_id), True, None

    def store_response(self, op_id, response_payload, status="PROCESSED"):
        _write(
            self.site_id,
            "UPDATE replication_inbox SET status=?, stored_response_json=?, stored_response_hash=?, processed_at=? WHERE op_id=?",
            (status, json.dumps(response_payload, ensure_ascii=False), self._hash(response_payload), datetime.now().isoformat(), op_id),
        )
        return self.get(op_id)

    def list(self, status=None):
        sql, params = "SELECT * FROM replication_inbox", []
        if status:
            sql, params = sql + " WHERE status=?", [status]
        return [self._row(row) for row in _all(self.site_id, sql + " ORDER BY processed_at DESC", params)]

    def delete(self, op_id):
        _write(self.site_id, "DELETE FROM replication_inbox WHERE op_id=?", (op_id,))


class TransactionManager:
    @staticmethod
    def commit_checkin(site_id, model, delta, checkout_part_id, checkout_user):
        with _get_conn(site_id) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO snapshots (part_id, version, branch, oid, site_origin, created_at, modified_at, locked_by, geometry)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (model.part_id, model.version, model.branch or "main", model.oid, model.site_origin, model.created_at, model.modified_at, model.locked_by, json.dumps(model.geometry.to_dict(), ensure_ascii=False)),
            )
            if delta:
                conn.execute(
                    "INSERT OR REPLACE INTO deltas (part_id, branch, from_version, to_version, changes, timestamp, author_site) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (delta.part_id, delta.branch or "main", delta.from_version, delta.to_version, json.dumps(delta.changes, ensure_ascii=False), delta.timestamp, delta.author_site),
                )
            if checkout_part_id and checkout_user:
                conn.execute("DELETE FROM checkouts WHERE part_id=? AND user=?", (checkout_part_id, checkout_user))
            conn.commit()
