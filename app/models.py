"""
Module: models.py
Mo ta: Cac lop du lieu chinh cua he thong versioning CAD phan tan.

Gom 5 class:
  - Geometry    : Hinh hoc 3D (dinh, canh, mat)
  - CADModel    : Doi tuong CAD voi PartID, Geometry, Version
  - Delta       : Phan chenh lech giua 2 phien ban (tiet kiem bo nho)
  - WALEntry    : Mot ban ghi trong Write-Ahead Log
  - WALLog      : Quan ly toan bo WAL, persist xuong file JSON

Serialization:
  Su dung marshmallow (theo goi y de bai) de xu ly
  chuyen doi object <-> dict/JSON mot cach chuan hoa.

FIX so voi phien ban cu:
  [F1] Delta.compute() → dung jsondiff.diff(syntax='explicit') + sanitize keys
       → diff thuc su nho hon: chi luu index vertex thay doi, khong luu ca list
  [F2] Delta.apply()   → dung _apply_explicit_diff() cho nhat quan voi compute()
  [F3] _apply_explicit_diff() chuyen len truoc Delta de Python thay duoc no
  [F4] Them WALEntry + WALLog + schema tuong ung
  [F5] Thread-safe WAL voi threading.Lock (Flask multi-thread)
  [F6] Doi MD5 → SHA-256 de dong nhat voi Design Doc & chuan bao mat
"""

import uuid
import json
import copy
import hashlib
import threading
from datetime import datetime
from pathlib import Path

import jsondiff as jd
from marshmallow import Schema, fields, post_load, EXCLUDE


# ══════════════════════════════════════════════════════════
#  GEOMETRY
# ══════════════════════════════════════════════════════════

class Geometry:
    """Bieu dien hinh hoc 3D cua 1 linh kien CAD."""

    def __init__(self, vertices, edges, faces, properties=None, type="Polygon", **kwargs):
        self.type       = type
        self.vertices   = vertices
        self.edges      = edges
        self.faces      = faces
        self.properties = properties or {}

    def to_dict(self):
        return {
            "type":       self.type,
            "vertices":   self.vertices,
            "edges":      self.edges,
            "faces":      self.faces,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            type=data.get("type", "Polygon"),
            vertices=data["vertices"],
            edges=data["edges"],
            faces=data["faces"],
            properties=data.get("properties", {}),
        )

    def size_bytes(self):
        """Tinh dung luong (bytes) cua geometry khi luu JSON."""
        return len(json.dumps(self.to_dict()).encode("utf-8"))


# ══════════════════════════════════════════════════════════
#  GEOMETRY SCHEMA
# ══════════════════════════════════════════════════════════

class GeometrySchema(Schema):
    type       = fields.Str(load_default="Polygon", dump_default="Polygon")
    vertices   = fields.List(fields.Dict(),            required=True)
    edges      = fields.List(fields.Raw(), required=True)
    faces      = fields.List(fields.Raw(), required=True)
    properties = fields.Dict(load_default={}, dump_default={})

    class Meta:
        unknown = EXCLUDE

    @post_load
    def make_geometry(self, data, **kwargs):
        return Geometry(**data)


# ══════════════════════════════════════════════════════════
#  CAD MODEL
# ══════════════════════════════════════════════════════════

class CADModel:
    """
    Doi tuong CAD_Model chinh.
    # Özsu §15.2: OID immutable & globally unique across sites
    """

    def __init__(self, part_id, geometry, version=1, oid=None,
                 created_at=None, modified_at=None, site_origin="",
                 locked_by=None, branch="main"):
        self.part_id     = part_id
        self.geometry    = geometry
        self.version     = version
        self.oid         = oid or str(uuid.uuid4())
        self.created_at  = created_at  or datetime.now().isoformat()
        self.modified_at = modified_at or datetime.now().isoformat()
        self.site_origin = site_origin
        self.locked_by   = locked_by
        self.branch      = branch

    def to_dict(self):
        return {
            "part_id":     self.part_id,
            "geometry":    self.geometry.to_dict(),
            "version":     self.version,
            "oid":         self.oid,
            "created_at":  self.created_at,
            "modified_at": self.modified_at,
            "site_origin": self.site_origin,
            "locked_by":   self.locked_by,
            "branch":      self.branch,
        }

    @classmethod
    def from_dict(cls, data):
        data = data.copy()
        if isinstance(data["geometry"], dict):
            data["geometry"] = Geometry.from_dict(data["geometry"])
        return cls(**data)

    def snapshot_size(self):
        return len(json.dumps(self.to_dict()).encode("utf-8"))

    def checksum(self):
        """# Özsu §15.5: SHA-256 integrity verification for distributed sync"""
        geo_json = json.dumps(self.geometry.to_dict(), sort_keys=True)
        return hashlib.sha256(geo_json.encode()).hexdigest()

    def clone(self):
        return CADModel.from_dict(copy.deepcopy(self.to_dict()))


# ══════════════════════════════════════════════════════════
#  CAD MODEL SCHEMA
# ══════════════════════════════════════════════════════════

class CADModelSchema(Schema):
    part_id     = fields.Str(required=True)
    geometry    = fields.Nested(GeometrySchema, required=True)
    version     = fields.Int(load_default=1,      dump_default=1)
    oid         = fields.Str(load_default=None,   dump_default=None,  allow_none=True)
    created_at  = fields.Str(load_default=None,   dump_default=None,  allow_none=True)
    modified_at = fields.Str(load_default=None,   dump_default=None,  allow_none=True)
    site_origin = fields.Str(load_default="",     dump_default="")
    locked_by   = fields.Str(load_default=None,   dump_default=None,  allow_none=True)
    branch      = fields.Str(load_default="main", dump_default="main")

    class Meta:
        unknown = EXCLUDE

    @post_load
    def make_model(self, data, **kwargs):
        return CADModel(**data)


# ══════════════════════════════════════════════════════════
#  HELPER: Sanitize jsondiff keys
# ══════════════════════════════════════════════════════════

def _sanitize_jsondiff_keys(obj):
    """
    Chuyen jsondiff Symbol keys sang string de json.dumps() khong bao loi.
    Compact diff cung co the tra ve dict key la Symbol (add, delete, v.v.)
    """
    import jsondiff as jd
    symbol_map = {
        jd.add: "$add",
        jd.delete: "$delete",
        jd.update: "$update",
        jd.insert: "$insert",
        jd.replace: "$replace"
    }
    if isinstance(obj, dict):
        return {str(symbol_map.get(k, k)): _sanitize_jsondiff_keys(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_jsondiff_keys(i) for i in obj]
    return obj


def _desanitize_jsondiff_keys(obj):
    """Chuyen cac String tro lai thanh Symbol cua jsondiff de patch."""
    import jsondiff as jd
    inv_map = {
        "$add": jd.add,
        "$delete": jd.delete,
        "$update": jd.update,
        "$insert": jd.insert,
        "$replace": jd.replace
    }
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            new_key = inv_map.get(k, k)
            # Quan trong: Chuyen string index sang int cho list patching (compact syntax)
            if isinstance(k, str) and k.isdigit():
                new_key = int(k)
            new_dict[new_key] = _desanitize_jsondiff_keys(v)
        return new_dict
    elif isinstance(obj, list):
        return [_desanitize_jsondiff_keys(i) for i in obj]
    return obj


# ══════════════════════════════════════════════════════════
#  HELPER: _apply_explicit_diff
# ══════════════════════════════════════════════════════════

def _apply_explicit_diff(base, patch_dict) -> any:
    """
    Ap dung compact diff cua jsondiff.
    Giai ma string keys (tu JSON) thanh int index truoc khi patch.
    """
    if not patch_dict or not isinstance(patch_dict, dict):
        return base

    # Giai ma cac key tu string sang Symbol/Int
    real_patch = _desanitize_jsondiff_keys(patch_dict)

    try:
        return jd.patch(base, real_patch)
    except Exception as e:
        print(f"[ERROR] jsondiff.patch failed: {e}")
        return base


# ══════════════════════════════════════════════════════════
#  DELTA
# ══════════════════════════════════════════════════════════

class Delta:
    """
    Phan chenh lech (patch) giua 2 phien ban.
    # Özsu §15.6: Delta storage reduces disk/network payload at rehydration cost
    """

    def __init__(self, from_version, to_version, part_id, changes,
                 timestamp=None, author_site="", branch="main"):
        self.from_version = from_version
        self.to_version   = to_version
        self.part_id      = part_id
        self.changes      = changes
        self.timestamp    = timestamp or datetime.now().isoformat()
        self.author_site  = author_site
        self.branch       = branch or "main"

    def to_dict(self):
        return {
            "from_version": self.from_version,
            "to_version":   self.to_version,
            "part_id":      self.part_id,
            "changes":      self.changes,
            "timestamp":    self.timestamp,
            "author_site":  self.author_site,
            "branch":       self.branch,
        }

    def size_bytes(self):
        return len(json.dumps(self.to_dict()).encode("utf-8"))

    @staticmethod
    def compute(old_model, new_model, author_site=""):
        """
        Tinh delta bang jsondiff compact syntax.
        Compact diff chi luu index vertex/face thay doi → giam bo nho.
        NOTE: jsondiff.patch() chi hoat dong voi compact syntax (khong phai explicit).
        """
        old_geo = old_model.geometry.to_dict()
        new_geo = new_model.geometry.to_dict()

        # Dung compact syntax (default) de dam bao patch() hoat dong dung
        changes = jd.diff(old_geo, new_geo)
        changes = _sanitize_jsondiff_keys(changes)  # Serialize Symbol keys sang string

        if not changes:
            changes = {}

        return Delta(
            from_version=old_model.version,
            to_version=new_model.version,
            part_id=old_model.part_id,
            changes=changes,
            author_site=author_site,
            branch=new_model.branch or "main",
        )

    def apply(self, model):
        """
        [F2] Ap dung delta de rehydrate phien ban moi.
        Chi phi CPU ty le thuan voi so luong delta (O(k)).
        """
        new_model = model.clone()
        geo_dict  = new_model.geometry.to_dict()

        if self.changes:
            geo_dict = _apply_explicit_diff(geo_dict, self.changes)

        new_model.geometry    = Geometry.from_dict(geo_dict)
        new_model.version     = self.to_version
        new_model.modified_at = datetime.now().isoformat()
        return new_model


# ══════════════════════════════════════════════════════════
#  DELTA SCHEMA
# ══════════════════════════════════════════════════════════

class DeltaSchema(Schema):
    from_version = fields.Int(required=True)
    to_version   = fields.Int(required=True)
    part_id      = fields.Str(required=True)
    changes      = fields.Dict(required=True)
    timestamp    = fields.Str(load_default=None, dump_default=None, allow_none=True)
    author_site  = fields.Str(load_default="",   dump_default="")
    branch       = fields.Str(load_default="main", dump_default="main")

    @post_load
    def make_delta(self, data, **kwargs):
        return Delta(**data)


# ══════════════════════════════════════════════════════════
#  WAL ENTRY
# ══════════════════════════════════════════════════════════

class WALEntry:
    """
    Write-Ahead Log entry.
    # Özsu §15.7: Crash recovery without distributed 2PC
    """

    def __init__(self, entry_id, operation, part_id, data,
                 committed=False, timestamp=None):
        self.entry_id  = entry_id
        self.operation = operation
        self.part_id   = part_id
        self.data      = data
        self.committed = committed
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self):
        return {
            "entry_id":  self.entry_id,
            "operation": self.operation,
            "part_id":   self.part_id,
            "data":      self.data,
            "committed": self.committed,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class WALEntrySchema(Schema):
    entry_id  = fields.Int(required=True)
    operation = fields.Str(required=True)
    part_id   = fields.Str(required=True)
    data      = fields.Dict(required=True)
    committed = fields.Bool(load_default=False, dump_default=False)
    timestamp = fields.Str(load_default=None,  dump_default=None, allow_none=True)

    @post_load
    def make_entry(self, data, **kwargs):
        return WALEntry(**data)


# ══════════════════════════════════════════════════════════
#  WAL LOG
# ══════════════════════════════════════════════════════════

class WALLog:
    """
    Quan ly Write-Ahead Log cua 1 site.
    [F5] Thread-safe voi threading.Lock de tranh race condition trong Flask.
    """

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self._schema  = WALEntrySchema()
        self.entries: dict[int, WALEntry] = {}
        self.next_id  = 1
        self._lock    = threading.Lock()  # ← FIX thread-safety
        self._load()

    def _load(self):
        if not self.filepath.exists():
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
                entry = self._schema.load(v)
                self.entries[entry.entry_id] = entry
            if self.entries:
                self.next_id = max(self.entries.keys()) + 1
        except (json.JSONDecodeError, KeyError):
            self.entries = {}
            self.next_id = 1

    def _persist(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            data = {str(k): self._schema.dump(v) for k, v in self.entries.items()}
            json.dump(data, f, indent=2, ensure_ascii=False)

    def begin(self, operation: str, part_id: str, data: dict) -> int:
        with self._lock:
            entry = WALEntry(
                entry_id=self.next_id, operation=operation,
                part_id=part_id, data=data, committed=False,
            )
            self.entries[self.next_id] = entry
            self._persist()
            entry_id = self.next_id
            self.next_id += 1
            return entry_id

    def commit(self, entry_id: int):
        with self._lock:
            if entry_id in self.entries:
                self.entries[entry_id].committed = True
                self._persist()

    def get_uncommitted(self) -> list[WALEntry]:
        return [e for e in self.entries.values() if not e.committed]

    def remove(self, entry_id: int):
        with self._lock:
            if entry_id in self.entries:
                del self.entries[entry_id]
                self._persist()

    def recover(self, rollback_fn) -> list[WALEntry]:
        with self._lock:
            pending   = self.get_uncommitted()
            recovered = []
            for entry in pending:
                try:
                    rollback_fn(entry)
                    del self.entries[entry.entry_id]
                    recovered.append(entry)
                except Exception as e:
                    print(f"[WAL] Rollback failed for entry {entry.entry_id}: {e}")
            self._persist()
            return recovered

    def all_entries(self) -> list[WALEntry]:
        return list(self.entries.values())
