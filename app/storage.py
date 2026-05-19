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
    from_version INTEGER NOT NULL,
    to_version   INTEGER NOT NULL,
    changes      TEXT    NOT NULL,
    timestamp    TEXT,
    author_site  TEXT    DEFAULT '',
    PRIMARY KEY (part_id, from_version, to_version)
);

CREATE INDEX IF NOT EXISTS idx_deltas_part ON deltas(part_id);

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

            conn.executescript(_SCHEMA_SQL)
            conn.commit()
            _initialized_dbs.add(site_id)

    return conn


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
                   (part_id, from_version, to_version, changes, timestamp, author_site)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    delta.part_id,
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
        # row order: part_id, from_version, to_version, changes, timestamp, author_site
        return Delta(
            part_id=row[0],
            from_version=row[1],
            to_version=row[2],
            changes=json.loads(row[3]),
            timestamp=row[4],
            author_site=row[5] or "",
        )

    def get(self, part_id, version):
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

            # Lay chuoi delta lien tuc tu base.version tro di
            # [S4] ORDER BY from_version ASC de dam bao apply dung thu tu
            delta_rows = conn.execute(
                """SELECT part_id, from_version, to_version, changes, timestamp, author_site
                   FROM deltas
                   WHERE part_id=? AND from_version >= ?
                   ORDER BY from_version ASC""",
                (part_id, base.version)
            ).fetchall()

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

    def get_latest(self, part_id):
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

            delta_rows = conn.execute(
                """SELECT part_id, from_version, to_version, changes, timestamp, author_site
                   FROM deltas
                   WHERE part_id=? AND from_version >= ?
                   ORDER BY from_version ASC""",
                (part_id, base.version)
            ).fetchall()

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

    def rehydration_cost(self, part_id, version):
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
            row = conn.execute(
                """SELECT COUNT(*) FROM deltas
                   WHERE part_id=? AND from_version >= ? AND to_version <= ?""",
                (part_id, base_version, version)
            ).fetchone()
            return row[0] if row else 0


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
                       (part_id, from_version, to_version, changes, timestamp, author_site)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (delta.part_id, delta.from_version, delta.to_version, changes_json, delta.timestamp, delta.author_site)
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