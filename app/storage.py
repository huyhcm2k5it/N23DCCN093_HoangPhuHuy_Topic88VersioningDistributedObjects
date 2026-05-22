"""
Module: storage.py
Mo ta: Tang luu tru cho he thong versioning CAD phan tan.

Gom 2 class chinh:
  - SnapshotStore : Luu tru theo kieu Full Snapshot (Özsu §15.4)
  - DeltaStore    : Luu tru theo kieu Delta (Özsu §15.6)

Schema DB:
  - snapshots: Tach cot rieng (part_id, version, branch, oid, ..., geometry JSON)
  - bases:     Base version cho delta chain
  - deltas:    Delta giua 2 version lien ke, co PRIMARY KEY chong trung

FIX so voi phien ban cu:
  [S1] Schema tach cot thay vi 1 cot data TEXT blob
  [S2] PRIMARY KEY dung: snapshots(part_id, version, branch), deltas(part_id, from_ver, to_ver)
  [S3] Connection manager: init schema 1 lan, khong tao lai moi request
  [S4] Delta chain query: follow from_version lien tuc, khong dung range sai
  [S5] Them index cho cac truong hay query (part_id, branch)
"""

import sqlite3
import json
import os
import threading
import hashlib
from datetime import datetime
from .models import CADModel, Delta, Geometry


# ══════════════════════════════════════════════════════════
#  CONNECTION MANAGER
# ══════════════════════════════════════════════════════════

_DB_DIR = os.path.join(os.path.dirname(__file__), "db")
_initialized_dbs = set()
_init_lock = threading.Lock()

_SCHEMA_SQL = """
-- Bang snapshots: luu full snapshot moi version
-- PK = (part_id, version, branch) de ho tro branching conflict resolution
CREATE TABLE IF NOT EXISTS snapshots (
    part_id      TEXT    NOT NULL,
    version      INTEGER NOT NULL,
    branch       TEXT    NOT NULL DEFAULT 'main',
    oid          TEXT,
    site_origin  TEXT    DEFAULT '',
    created_at   TEXT,
    modified_at  TEXT,
    locked_by    TEXT,
    geometry     TEXT    NOT NULL,
    PRIMARY KEY (part_id, version, branch)
);

-- Index de query nhanh theo part_id va branch
CREATE INDEX IF NOT EXISTS idx_snapshots_part ON snapshots(part_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_branch ON snapshots(part_id, branch);

-- Bang bases: base version cho delta chain (1 base / part)
CREATE TABLE IF NOT EXISTS bases (
    part_id      TEXT    PRIMARY KEY,
    version      INTEGER NOT NULL DEFAULT 1,
    oid          TEXT,
    site_origin  TEXT    DEFAULT '',
    created_at   TEXT,
    geometry     TEXT    NOT NULL
);

-- Bang deltas: delta giua 2 version lien ke
-- PK chong insert trung lap
CREATE TABLE IF NOT EXISTS deltas (
    part_id      TEXT    NOT NULL,
    branch       TEXT    NOT NULL DEFAULT 'main',
    from_version INTEGER NOT NULL,
    to_version   INTEGER NOT NULL,
    changes      TEXT    NOT NULL,
    timestamp    TEXT,
    author_site  TEXT    DEFAULT '',
    PRIMARY KEY (part_id, branch, from_version, to_version)
);

CREATE INDEX IF NOT EXISTS idx_deltas_part ON deltas(part_id);
CREATE INDEX IF NOT EXISTS idx_deltas_branch ON deltas(part_id, branch);

-- Bang checkouts: persist trang thai checkout (Özsu §15.5 Optimistic CC)
-- Khong bi mat khi server restart
CREATE TABLE IF NOT EXISTS checkouts (
    part_id       TEXT    NOT NULL,
    user          TEXT    NOT NULL,
    base_version  INTEGER NOT NULL,
    checkout_time TEXT,
    model_json    TEXT    NOT NULL,
    PRIMARY KEY (part_id, user)
);

-- Bang replication_outbox: durable queue cho asynchronous replication
-- Source ghi outbox truoc khi gui qua mang, nen disconnect/timeout khong lam mat request
CREATE TABLE IF NOT EXISTS replication_outbox (
    op_id         TEXT    PRIMARY KEY,
    source_site   TEXT    NOT NULL,
    target_site   TEXT    NOT NULL,
    part_id       TEXT    NOT NULL,
    oid           TEXT,
    version       INTEGER NOT NULL,
    branch        TEXT    NOT NULL DEFAULT 'main',
    payload_json  TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'PENDING',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error    TEXT,
    next_retry_at TEXT,
    created_at    TEXT,
    updated_at    TEXT,
    acked_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_outbox_status ON replication_outbox(status);
CREATE INDEX IF NOT EXISTS idx_outbox_target ON replication_outbox(target_site, status);

-- Bang replication_inbox: dedupe incoming op_id tai target site
-- Dam bao replay cung op_id khong tao side-effect moi
CREATE TABLE IF NOT EXISTS replication_inbox (
    op_id         TEXT    PRIMARY KEY,
    request_hash  TEXT    NOT NULL,
    source_site   TEXT    NOT NULL,
    part_id       TEXT    NOT NULL,
    oid           TEXT,
    version       INTEGER,
    branch        TEXT    NOT NULL DEFAULT 'main',
    checksum      TEXT,
    status        TEXT    NOT NULL DEFAULT 'PROCESSED',
    processed_at  TEXT,
    stored_response_json TEXT,
    stored_response_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_inbox_source ON replication_inbox(source_site, processed_at);
"""


def _get_db_path(site_id):
    """Tra ve duong dan file .db cho site."""
    os.makedirs(_DB_DIR, exist_ok=True)
    return os.path.join(_DB_DIR, f"{site_id}.db")


def _get_conn(site_id):
    """
    Ket noi SQLite cho site. Init schema 1 lan duy nhat (thread-safe).
    [S3] Tranh tao lai bang moi request.
    Tu dong migrate DB cu (schema khong co branch) → schema moi.
    """
    db_path = _get_db_path(site_id)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    with _init_lock:
        if site_id not in _initialized_dbs:
            # Kiem tra schema cu: neu bang snapshots ton tai nhung khong co cot branch
            try:
                cursor = conn.execute("PRAGMA table_info(snapshots)")
                columns = [row[1] for row in cursor.fetchall()]
                if columns and "branch" not in columns:
                    # Schema cu → xoa va tao lai
                    conn.executescript("""
                        DROP TABLE IF EXISTS snapshots;
                        DROP TABLE IF EXISTS bases;
                        DROP TABLE IF EXISTS deltas;
                    """)
                    conn.commit()
            except Exception:
                pass

            try:
                cursor = conn.execute("PRAGMA table_info(deltas)")
                delta_columns = [row[1] for row in cursor.fetchall()]
                if delta_columns and "branch" not in delta_columns:
                    conn.execute("DROP TABLE IF EXISTS deltas")
                    conn.commit()
            except Exception:
                pass

            conn.executescript(_SCHEMA_SQL)
            _migrate_replication_tables(conn)
            conn.commit()
            _initialized_dbs.add(site_id)

    return conn


def _column_exists(conn, table_name, column_name):
    row = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()
    return any(col[1] == column_name for col in row)


def _add_column_if_missing(conn, table_name, column_def):
    column_name = column_def.split()[0]
    if not _column_exists(conn, table_name, column_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")


def _migrate_replication_tables(conn):
    """
    Backward-compatible migration cho outbox/inbox schema.
    """
    _add_column_if_missing(conn, "replication_outbox", "next_retry_at TEXT")

    _add_column_if_missing(conn, "replication_inbox", "request_hash TEXT DEFAULT ''")
    _add_column_if_missing(conn, "replication_inbox", "stored_response_json TEXT")
    _add_column_if_missing(conn, "replication_inbox", "stored_response_hash TEXT")


# ══════════════════════════════════════════════════════════
#  SNAPSHOT STORE  (Özsu §15.4 — Full Snapshot)
# ══════════════════════════════════════════════════════════

class SnapshotStore:
    """
    Luu tru theo kieu Full Snapshot.
    Moi version luu toan bo object → truy van O(1), ton dung luong.
    """

    def __init__(self, site_id):
        self.site_id = site_id

    def save(self, model):
        """
        Luu 1 snapshot vao DB.
        [S1] Tach cot: part_id, version, branch, oid, ... rieng biet.
        geometry la JSON duy nhat (vi cau truc phuc tap).
        """
        geo_json = json.dumps(model.geometry.to_dict(), ensure_ascii=False)
        with _get_conn(self.site_id) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO snapshots
                   (part_id, version, branch, oid, site_origin,
                    created_at, modified_at, locked_by, geometry)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    model.part_id,
                    model.version,
                    model.branch or "main",
                    model.oid,
                    model.site_origin,
                    model.created_at,
                    model.modified_at,
                    model.locked_by,
                    geo_json,
                )
            )
            conn.commit()
        return len(geo_json.encode("utf-8"))

    def _row_to_model(self, row):
        """Chuyen 1 row DB thanh CADModel object."""
        # row order: part_id, version, branch, oid, site_origin,
        #            created_at, modified_at, locked_by, geometry
        geo = Geometry.from_dict(json.loads(row[8]))
        return CADModel(
            part_id=row[0],
            geometry=geo,
            version=row[1],
            branch=row[2],
            oid=row[3],
            site_origin=row[4] or "",
            created_at=row[5],
            modified_at=row[6],
            locked_by=row[7],
        )

    def get(self, part_id, version, branch="main"):
        """Lay snapshot theo part_id + version (mac dinh branch=main)."""
        with _get_conn(self.site_id) as conn:
            row = conn.execute(
                """SELECT part_id, version, branch, oid, site_origin,
                          created_at, modified_at, locked_by, geometry
                   FROM snapshots
                   WHERE part_id=? AND version=? AND branch=?""",
                (part_id, version, branch)
            ).fetchone()
            if row:
                return self._row_to_model(row)

            # Fallback: neu khong tim thay branch cu the, thu tim bat ky branch nao
            row = conn.execute(
                """SELECT part_id, version, branch, oid, site_origin,
                          created_at, modified_at, locked_by, geometry
                   FROM snapshots
                   WHERE part_id=? AND version=?
                   ORDER BY CASE WHEN branch='main' THEN 0 ELSE 1 END
                   LIMIT 1""",
                (part_id, version)
            ).fetchone()
            if row:
                return self._row_to_model(row)
        return None

    def get_exact(self, part_id, version, branch="main"):
        """Lay dung snapshot theo (part_id, version, branch), khong fallback sang branch khac."""
        with _get_conn(self.site_id) as conn:
            row = conn.execute(
                """SELECT part_id, version, branch, oid, site_origin,
                          created_at, modified_at, locked_by, geometry
                   FROM snapshots
                   WHERE part_id=? AND version=? AND branch=?""",
                (part_id, version, branch or "main")
            ).fetchone()
            if row:
                return self._row_to_model(row)
        return None

    def get_latest(self, part_id, branch="main"):
        """Lay phien ban moi nhat tren branch cu the (mac dinh main)."""
        with _get_conn(self.site_id) as conn:
            row = conn.execute(
                """SELECT part_id, version, branch, oid, site_origin,
                          created_at, modified_at, locked_by, geometry
                   FROM snapshots
                   WHERE part_id=? AND branch=?
                   ORDER BY version DESC LIMIT 1""",
                (part_id, branch)
            ).fetchone()
            if row:
                return self._row_to_model(row)

            # Fallback: lay version cao nhat bat ky branch nao
            row = conn.execute(
                """SELECT part_id, version, branch, oid, site_origin,
                          created_at, modified_at, locked_by, geometry
                   FROM snapshots
                   WHERE part_id=?
                   ORDER BY version DESC LIMIT 1""",
                (part_id,)
            ).fetchone()
            if row:
                return self._row_to_model(row)
        return None

    def get_all_versions(self, part_id):
        """Lay toan bo phien ban cua 1 part (moi branch) theo thu tu tang dan."""
        with _get_conn(self.site_id) as conn:
            rows = conn.execute(
                """SELECT part_id, version, branch, oid, site_origin,
                          created_at, modified_at, locked_by, geometry
                   FROM snapshots
                   WHERE part_id=?
                   ORDER BY version ASC, branch ASC""",
                (part_id,)
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def get_all_part_ids(self):
        """Lay danh sach tat ca part_id trong DB."""
        with _get_conn(self.site_id) as conn:
            rows = conn.execute(
                "SELECT DISTINCT part_id FROM snapshots ORDER BY part_id"
            ).fetchall()
        return [r[0] for r in rows]

    def get_part_id_by_oid(self, oid):
        """Tra ve part_id tu OID bat bien."""
        with _get_conn(self.site_id) as conn:
            row = conn.execute(
                """SELECT part_id
                   FROM snapshots
                   WHERE oid=?
                   ORDER BY version DESC
                   LIMIT 1""",
                (oid,),
            ).fetchone()
            if row:
                return row[0]
            row = conn.execute(
                """SELECT part_id
                   FROM bases
                   WHERE oid=?
                   LIMIT 1""",
                (oid,),
            ).fetchone()
            return row[0] if row else None

    def total_storage_bytes(self):
        """Tinh tong dung luong luu tru (bytes) cua toan bo snapshots."""
        with _get_conn(self.site_id) as conn:
            row = conn.execute(
                "SELECT SUM(LENGTH(geometry)) FROM snapshots"
            ).fetchone()
            return row[0] if row[0] else 0


# ══════════════════════════════════════════════════════════
#  DELTA STORE  (Özsu §15.6 — Delta Storage)
# ══════════════════════════════════════════════════════════

class DeltaStore:
    """
    Luu tru theo kieu Delta.
    Chi luu phan khac biet (patch) giua 2 version lien ke.
    Tiet kiem dung luong nhung rehydrate ton O(k) voi k = so delta.
    """

    def __init__(self, site_id):
        self.site_id = site_id

    def save_base(self, model):
        """Luu base version (version dau tien) cho delta chain."""
        geo_json = json.dumps(model.geometry.to_dict(), ensure_ascii=False)
        with _get_conn(self.site_id) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO bases
                   (part_id, version, oid, site_origin, created_at, geometry)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    model.part_id,
                    model.version,
                    model.oid,
                    model.site_origin,
                    model.created_at,
                    geo_json,
                )
            )
            conn.commit()
        return len(geo_json.encode("utf-8"))

    def _base_to_model(self, row):
        """Chuyen row tu bang bases thanh CADModel."""
        # row order: part_id, version, oid, site_origin, created_at, geometry
        geo = Geometry.from_dict(json.loads(row[5]))
        return CADModel(
            part_id=row[0],
            geometry=geo,
            version=row[1],
            oid=row[2],
            site_origin=row[3] or "",
            created_at=row[4],
        )

    def save_delta(self, delta):
        """
        Luu 1 delta vao DB.
        [S2] PRIMARY KEY (part_id, from_version, to_version) chong trung.
        """
        changes_json = json.dumps(delta.changes, ensure_ascii=False)
        with _get_conn(self.site_id) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO deltas
                   (part_id, branch, from_version, to_version, changes, timestamp, author_site)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    delta.part_id,
                    delta.branch or "main",
                    delta.from_version,
                    delta.to_version,
                    changes_json,
                    delta.timestamp,
                    delta.author_site,
                )
            )
            conn.commit()
        return len(changes_json.encode("utf-8"))

    def _load_delta_from_row(self, row):
        """Chuyen 1 row tu bang deltas thanh Delta object."""
        # row order: part_id, branch, from_version, to_version, changes, timestamp, author_site
        return Delta(
            part_id=row[0],
            branch=row[1] or "main",
            from_version=row[2],
            to_version=row[3],
            changes=json.loads(row[4]),
            timestamp=row[5],
            author_site=row[6] or "",
        )

    def _delta_rows_for_branch(self, conn, part_id, base_version, branch):
        """Load delta chain cho main hoac cho branch phu kem prefix main."""
        target_branch = branch or "main"
        main_rows = conn.execute(
            """SELECT part_id, branch, from_version, to_version, changes, timestamp, author_site
               FROM deltas
               WHERE part_id=? AND branch='main' AND from_version >= ?
               ORDER BY from_version ASC""",
            (part_id, base_version)
        ).fetchall()

        if target_branch == "main":
            return main_rows

        branch_rows = conn.execute(
            """SELECT part_id, branch, from_version, to_version, changes, timestamp, author_site
               FROM deltas
               WHERE part_id=? AND branch=? AND from_version >= ?
               ORDER BY from_version ASC""",
            (part_id, target_branch, base_version)
        ).fetchall()
        if not branch_rows:
            return []

        branch_start = branch_rows[0][2]
        prefix_rows = [r for r in main_rows if r[2] < branch_start]
        return prefix_rows + branch_rows

    def get(self, part_id, version, branch="main"):
        """
        Lay phien ban bang cach rehydrate tu base + delta chain.
        [S4] Logic dung: lay base → apply delta(base→base+1) → delta(base+1→base+2) → ... → version
        """
        with _get_conn(self.site_id) as conn:
            # Lay base
            base_row = conn.execute(
                """SELECT part_id, version, oid, site_origin, created_at, geometry
                   FROM bases WHERE part_id=?""",
                (part_id,)
            ).fetchone()
            if not base_row:
                return None

            base = self._base_to_model(base_row)

            # Neu yeu cau chinh la base version → tra ve luon
            if version == base.version:
                return base

            delta_rows = self._delta_rows_for_branch(conn, part_id, base.version, branch)

        # Apply tuan tu: base → v2 → v3 → ... → target version
        model = base
        for row in delta_rows:
            delta = self._load_delta_from_row(row)

            # Kiem tra chain lien tuc: from_version phai = model.version hien tai
            if delta.from_version != model.version:
                print(f"[DeltaStore] Chain bi dut tai v{model.version} → v{delta.from_version}")
                break

            try:
                model = delta.apply(model)
            except Exception as e:
                print(f"[DeltaStore] Loi rehydration v{delta.to_version} part {part_id}: {e}")
                return None

            # Da dat den version can → dung
            if model.version >= version:
                break

        return model if model.version == version else None

    def get_latest(self, part_id, branch="main"):
        """Lay phien ban moi nhat bang cach rehydrate toan bo chuoi delta."""
        with _get_conn(self.site_id) as conn:
            base_row = conn.execute(
                """SELECT part_id, version, oid, site_origin, created_at, geometry
                   FROM bases WHERE part_id=?""",
                (part_id,)
            ).fetchone()
            if not base_row:
                return None

            base = self._base_to_model(base_row)

            delta_rows = self._delta_rows_for_branch(conn, part_id, base.version, branch)

        model = base
        for row in delta_rows:
            delta = self._load_delta_from_row(row)
            if delta.from_version != model.version:
                break
            try:
                model = delta.apply(model)
            except Exception as e:
                print(f"[DeltaStore] Loi rehydration latest part {part_id}: {e}")
                break
        return model

    def total_storage_bytes(self):
        """Tinh tong dung luong: base + toan bo deltas."""
        with _get_conn(self.site_id) as conn:
            base_size = conn.execute(
                "SELECT SUM(LENGTH(geometry)) FROM bases"
            ).fetchone()[0] or 0
            delta_size = conn.execute(
                "SELECT SUM(LENGTH(changes)) FROM deltas"
            ).fetchone()[0] or 0
            return base_size + delta_size

    def rehydration_cost(self, part_id, version, branch="main"):
        """Dem so luong delta can ap dung de dat den version nay (= k trong O(k))."""
        with _get_conn(self.site_id) as conn:
            base_row = conn.execute(
                "SELECT version FROM bases WHERE part_id=?",
                (part_id,)
            ).fetchone()
            if not base_row:
                return 0
            base_version = base_row[0]
            if version <= base_version:
                return 0
            target_branch = branch or "main"
            if target_branch == "main":
                row = conn.execute(
                    """SELECT COUNT(*) FROM deltas
                       WHERE part_id=? AND branch='main'
                         AND from_version >= ? AND to_version <= ?""",
                    (part_id, base_version, version)
                ).fetchone()
                return row[0] if row else 0

            row = conn.execute(
                """SELECT MIN(from_version) FROM deltas
                   WHERE part_id=? AND branch=?""",
                (part_id, target_branch)
            ).fetchone()
            branch_start = row[0] if row else None
            if branch_start is None:
                return 0

            main_count = conn.execute(
                """SELECT COUNT(*) FROM deltas
                   WHERE part_id=? AND branch='main'
                     AND from_version >= ? AND to_version <= ?""",
                (part_id, base_version, branch_start)
            ).fetchone()[0] or 0
            branch_count = conn.execute(
                """SELECT COUNT(*) FROM deltas
                   WHERE part_id=? AND branch=?
                     AND from_version >= ? AND to_version <= ?""",
                (part_id, target_branch, branch_start, version)
            ).fetchone()[0] or 0
            return main_count + branch_count

    def delta_patch_bytes(self, part_id, version, branch="main"):
        """Tong logical bytes cua delta patches can ap dung de den target version."""
        with _get_conn(self.site_id) as conn:
            base_row = conn.execute(
                "SELECT version FROM bases WHERE part_id=?",
                (part_id,),
            ).fetchone()
            if not base_row:
                return 0
            base_version = base_row[0]
            if version <= base_version:
                return 0

            target_branch = branch or "main"
            if target_branch == "main":
                row = conn.execute(
                    """SELECT SUM(LENGTH(changes)) FROM deltas
                       WHERE part_id=? AND branch='main'
                         AND from_version >= ? AND to_version <= ?""",
                    (part_id, base_version, version),
                ).fetchone()
                return row[0] or 0

            row = conn.execute(
                """SELECT SUM(LENGTH(changes)) FROM deltas
                   WHERE part_id=? AND (
                        (branch='main' AND to_version <= ?)
                        OR (branch=? AND to_version <= ?)
                   )""",
                (part_id, version, target_branch, version),
            ).fetchone()
            return row[0] or 0

    def rehydrate(self, oid, target_version, branch="main"):
        """
        Rehydrate object theo OID bat bien.
        Tra ve (model, meta) de benchmark va verify checksum.
        """
        snapshot_store = SnapshotStore(self.site_id)
        part_id = snapshot_store.get_part_id_by_oid(oid)
        if not part_id:
            return None, {"error": "OID_NOT_FOUND"}

        model = self.get(part_id, target_version, branch=branch)
        if not model:
            return None, {"error": "TARGET_VERSION_NOT_FOUND"}

        base = snapshot_store.get(part_id, 1, "main")
        base_bytes = len(json.dumps(base.to_dict(), ensure_ascii=False).encode("utf-8")) if base else 0
        patch_bytes = self.delta_patch_bytes(part_id, target_version, branch=branch)
        rehydrated_bytes = len(json.dumps(model.to_dict(), ensure_ascii=False).encode("utf-8"))
        steps = self.rehydration_cost(part_id, target_version, branch=branch)

        return model, {
            "part_id": part_id,
            "oid": oid,
            "target_version": target_version,
            "branch": branch,
            "base_snapshot_bytes": base_bytes,
            "delta_patch_bytes": patch_bytes,
            "rehydrated_object_bytes": rehydrated_bytes,
            "rehydration_steps": steps,
        }


# ══════════════════════════════════════════════════════════
#  CHECKOUT STORE  (Özsu §15.5 — Optimistic CC)
# ══════════════════════════════════════════════════════════

class CheckoutStore:
    """
    Persist trang thai checkout vao DB.
    Khong bi mat khi server restart (khac voi dict in-memory).
    """

    def __init__(self, site_id):
        self.site_id = site_id

    def save(self, part_id, user, base_version, model, checkout_time):
        """Luu checkout state vao DB."""
        model_json = json.dumps(model.to_dict(), ensure_ascii=False)
        with _get_conn(self.site_id) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO checkouts
                   (part_id, user, base_version, checkout_time, model_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (part_id, user, base_version, checkout_time, model_json)
            )
            conn.commit()

    def get(self, part_id, user):
        """Lay checkout info. Tra ve dict {model, base_version, checkout_time} hoac None."""
        with _get_conn(self.site_id) as conn:
            row = conn.execute(
                """SELECT base_version, checkout_time, model_json
                   FROM checkouts WHERE part_id=? AND user=?""",
                (part_id, user)
            ).fetchone()
            if row:
                return {
                    'base_version': row[0],
                    'checkout_time': row[1],
                    'model': CADModel.from_dict(json.loads(row[2])),
                }
        return None

    def delete(self, part_id, user):
        """Xoa checkout sau khi checkin thanh cong."""
        with _get_conn(self.site_id) as conn:
            conn.execute(
                "DELETE FROM checkouts WHERE part_id=? AND user=?",
                (part_id, user)
            )
            conn.commit()

    def has_checkout(self, part_id, user):
        """Kiem tra user da checkout part nay chua."""
        with _get_conn(self.site_id) as conn:
            row = conn.execute(
                "SELECT 1 FROM checkouts WHERE part_id=? AND user=?",
                (part_id, user)
            ).fetchone()
            return row is not None

    def get_all(self):
        """Lay toan bo checkouts dang active."""
        with _get_conn(self.site_id) as conn:
            rows = conn.execute(
                "SELECT part_id, user, base_version, checkout_time FROM checkouts"
            ).fetchall()
        return [
            {"part_id": r[0], "user": r[1], "base_version": r[2], "checkout_time": r[3]}
            for r in rows
        ]

# ══════════════════════════════════════════════════════════
#  TRANSACTION MANAGER  (Atomic Checkin & Rollback)
# ══════════════════════════════════════════════════════════

class ReplicationOutboxStore:
    """
    Durable outbox cho replication.
    Source ghi operation vao DB truoc khi gui qua mang:
      PENDING -> ACKED neu target import thanh cong
      PENDING/FAILED -> retry duoc khi node reconnect
    """

    def __init__(self, site_id):
        self.site_id = site_id

    def _now(self):
        return datetime.now().isoformat()

    def _retry_seconds(self, attempt_count):
        # Exponential backoff cap 60s
        return min(60, 2 ** max(0, min(attempt_count, 6)))

    def make_op_id(self, target_site, model):
        branch = model.branch or "main"
        return f"{self.site_id}->{target_site}:{model.oid}:{model.part_id}:{branch}:v{model.version}"

    def enqueue_model(self, target_site, model):
        op_id = self.make_op_id(target_site, model)
        payload_json = json.dumps(model.to_dict(), ensure_ascii=False)
        now = self._now()
        with _get_conn(self.site_id) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO replication_outbox
                   (op_id, source_site, target_site, part_id, oid, version, branch,
                    payload_json, status, attempt_count, last_error, next_retry_at, created_at, updated_at, acked_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0, NULL, NULL, ?, ?, NULL)""",
                (
                    op_id,
                    self.site_id,
                    target_site,
                    model.part_id,
                    model.oid,
                    model.version,
                    model.branch or "main",
                    payload_json,
                    now,
                    now,
                )
            )
            conn.execute(
                """UPDATE replication_outbox
                   SET payload_json=?, version=?, branch=?, status='PENDING',
                       last_error=NULL, next_retry_at=NULL, updated_at=?
                   WHERE op_id=? AND status <> 'ACKED'""",
                (payload_json, model.version, model.branch or "main", now, op_id)
            )
            conn.commit()
        return self.get(op_id)

    def _row_to_dict(self, row):
        if not row:
            return None
        return {
            "op_id": row[0],
            "source_site": row[1],
            "target_site": row[2],
            "part_id": row[3],
            "oid": row[4],
            "version": row[5],
            "branch": row[6],
            "payload": json.loads(row[7]),
            "status": row[8],
            "attempt_count": row[9],
            "last_error": row[10],
            "next_retry_at": row[11],
            "created_at": row[12],
            "updated_at": row[13],
            "acked_at": row[14],
        }

    def get(self, op_id):
        with _get_conn(self.site_id) as conn:
            row = conn.execute(
                """SELECT op_id, source_site, target_site, part_id, oid, version, branch,
                          payload_json, status, attempt_count, last_error, next_retry_at, created_at, updated_at, acked_at
                   FROM replication_outbox WHERE op_id=?""",
                (op_id,)
            ).fetchone()
        return self._row_to_dict(row)

    def list(self, status=None, target_site=None):
        query = """SELECT op_id, source_site, target_site, part_id, oid, version, branch,
                          payload_json, status, attempt_count, last_error, next_retry_at, created_at, updated_at, acked_at
                   FROM replication_outbox"""
        clauses = []
        params = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if target_site:
            clauses.append("target_site=?")
            params.append(target_site)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at ASC"
        with _get_conn(self.site_id) as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def pending(self, target_site=None):
        query = """SELECT op_id, source_site, target_site, part_id, oid, version, branch,
                          payload_json, status, attempt_count, last_error, next_retry_at, created_at, updated_at, acked_at
                   FROM replication_outbox
                   WHERE status IN ('PENDING', 'FAILED')
                     AND (next_retry_at IS NULL OR next_retry_at <= ?)"""
        now = self._now()
        params = [now]
        if target_site:
            query += " AND target_site=?"
            params.append(target_site)
        query += " ORDER BY created_at ASC"
        with _get_conn(self.site_id) as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def mark_delivered(self, op_id):
        now = self._now()
        with _get_conn(self.site_id) as conn:
            conn.execute(
                """UPDATE replication_outbox
                   SET status='ACKED', attempt_count=attempt_count+1,
                       last_error=NULL, next_retry_at=NULL, updated_at=?, acked_at=?
                   WHERE op_id=?""",
                (now, now, op_id)
            )
            conn.commit()
        return self.get(op_id)

    def mark_failed(self, op_id, error):
        now = self._now()
        current = self.get(op_id) or {}
        attempt_count = int(current.get("attempt_count", 0)) + 1
        retry_after = self._retry_seconds(attempt_count)
        next_retry_at = datetime.fromtimestamp(
            datetime.now().timestamp() + retry_after
        ).isoformat()
        with _get_conn(self.site_id) as conn:
            conn.execute(
                """UPDATE replication_outbox
                   SET status='FAILED', attempt_count=?,
                       last_error=?, next_retry_at=?, updated_at=?
                   WHERE op_id=?""",
                (attempt_count, str(error)[:1000], next_retry_at, now, op_id)
            )
            conn.commit()
        return self.get(op_id)

    def summary(self):
        with _get_conn(self.site_id) as conn:
            rows = conn.execute(
                """SELECT status, COUNT(*) FROM replication_outbox
                   GROUP BY status ORDER BY status"""
            ).fetchall()
        counts = {row[0]: row[1] for row in rows}
        return {
            "site_id": self.site_id,
            "pending": counts.get("PENDING", 0),
            "failed": counts.get("FAILED", 0),
            "acked": counts.get("ACKED", 0),
            "total": sum(counts.values()),
        }


class ReplicationInboxStore:
    """
    Durable inbox cho idempotent consumer semantics.
    Cung op_id + cung request_hash => tra lai ACK cu, khong apply lan nua.
    Cung op_id + request_hash khac => reject.
    """

    def __init__(self, site_id):
        self.site_id = site_id

    def _now(self):
        return datetime.now().isoformat()

    def _hash_payload(self, payload):
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _row_to_dict(self, row):
        if not row:
            return None
        response_json = row[9]
        return {
            "op_id": row[0],
            "request_hash": row[1],
            "source_site": row[2],
            "part_id": row[3],
            "oid": row[4],
            "version": row[5],
            "branch": row[6],
            "checksum": row[7],
            "status": row[8],
            "stored_response_json": json.loads(response_json) if response_json else None,
            "stored_response_hash": row[10],
            "processed_at": row[11],
        }

    def get(self, op_id):
        with _get_conn(self.site_id) as conn:
            row = conn.execute(
                """SELECT op_id, request_hash, source_site, part_id, oid, version, branch,
                          checksum, status, stored_response_json, stored_response_hash, processed_at
                   FROM replication_inbox WHERE op_id=?""",
                (op_id,),
            ).fetchone()
        return self._row_to_dict(row)

    def claim_or_get(self, op_id, request_payload, source_site, model):
        request_hash = self._hash_payload(request_payload)
        with _get_conn(self.site_id) as conn:
            existing = conn.execute(
                """SELECT op_id, request_hash, source_site, part_id, oid, version, branch,
                          checksum, status, stored_response_json, stored_response_hash, processed_at
                   FROM replication_inbox WHERE op_id=?""",
                (op_id,),
            ).fetchone()
            if existing:
                return self._row_to_dict(existing), False, request_hash

            conn.execute(
                """INSERT INTO replication_inbox
                   (op_id, request_hash, source_site, part_id, oid, version, branch, checksum,
                    status, processed_at, stored_response_json, stored_response_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PROCESSING', ?, NULL, NULL)""",
                (
                    op_id,
                    request_hash,
                    source_site,
                    model.part_id,
                    model.oid,
                    model.version,
                    model.branch or "main",
                    model.checksum(),
                    self._now(),
                ),
            )
            conn.commit()
        return self.get(op_id), True, request_hash

    def store_response(self, op_id, response_payload, status="PROCESSED"):
        response_json = json.dumps(response_payload, ensure_ascii=False, sort_keys=True)
        response_hash = hashlib.sha256(response_json.encode("utf-8")).hexdigest()
        now = self._now()
        with _get_conn(self.site_id) as conn:
            conn.execute(
                """UPDATE replication_inbox
                   SET status=?, stored_response_json=?, stored_response_hash=?, processed_at=?
                   WHERE op_id=?""",
                (status, response_json, response_hash, now, op_id),
            )
            conn.commit()
        return self.get(op_id)

    def list(self, status=None):
        query = """SELECT op_id, request_hash, source_site, part_id, oid, version, branch,
                          checksum, status, stored_response_json, stored_response_hash, processed_at
                   FROM replication_inbox"""
        params = []
        if status:
            query += " WHERE status=?"
            params.append(status)
        query += " ORDER BY processed_at DESC"
        with _get_conn(self.site_id) as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def delete(self, op_id):
        with _get_conn(self.site_id) as conn:
            conn.execute("DELETE FROM replication_inbox WHERE op_id=?", (op_id,))
            conn.commit()


class TransactionManager:
    @staticmethod
    def commit_checkin(site_id, model, delta, checkout_part_id, checkout_user):
        """Thuc thi Atomic Transaction cho Checkin (Snapshot + Delta + xoa Checkout)"""
        geo_json = json.dumps(model.geometry.to_dict(), ensure_ascii=False)
        with _get_conn(site_id) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO snapshots
                   (part_id, version, branch, oid, site_origin, created_at, modified_at, locked_by, geometry)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (model.part_id, model.version, model.branch or "main", model.oid, model.site_origin, model.created_at, model.modified_at, model.locked_by, geo_json)
            )
            if delta:
                changes_json = json.dumps(delta.changes, ensure_ascii=False)
                conn.execute(
                    """INSERT OR REPLACE INTO deltas
                       (part_id, branch, from_version, to_version, changes, timestamp, author_site)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (delta.part_id, delta.branch or "main", delta.from_version, delta.to_version, changes_json, delta.timestamp, delta.author_site)
                )
            if checkout_part_id and checkout_user:
                conn.execute("DELETE FROM checkouts WHERE part_id=? AND user=?", (checkout_part_id, checkout_user))
            conn.commit()

    @staticmethod
    def rollback_cleanup(site_id, part_id):
        """
        Don dep du lieu mo coi (orphan) do crash giua chung.

        [Ly thuyet Ozsu §15.7 — WAL Atomicity]
        Neu crash xay ra SAU khi ghi Snapshot nhung TRUOC khi ghi Delta:
          → Snapshot v_max ton tai trong DB nhung khong co Delta tuong ung
          → Day la trang thai inconsistent: can xoa Snapshot orphan nay

        Neu crash xay ra TRUOC khi ghi Snapshot (truong hop thong thuong qua flag):
          → DB khong bi thay doi → khong can xoa gi
        """
        with _get_conn(site_id) as conn:
            cursor = conn.execute("SELECT MAX(version) FROM snapshots WHERE part_id=?", (part_id,))
            row = cursor.fetchone()
            if row and row[0] and row[0] > 1:
                v_max = row[0]
                # Kiem tra co delta den version nay khong
                delta_check = conn.execute(
                    "SELECT 1 FROM deltas WHERE part_id=? AND to_version=?",
                    (part_id, v_max)
                ).fetchone()
                if not delta_check:
                    # Orphan snapshot: da co snapshot nhung khong co delta → xoa de rollback
                    conn.execute(
                        "DELETE FROM snapshots WHERE part_id=? AND version=?",
                        (part_id, v_max)
                    )
                    conn.commit()
                    print(f"[Rollback] Site {site_id}: Removed orphan snapshot {part_id} v{v_max} (no delta found)")
                else:
                    print(f"[Rollback] Site {site_id}: Integrity OK for {part_id} v{v_max}")
