"""
Module: site_node.py
Mo ta: Mo phong 1 node (site) trong he thong phan tan.
Xu ly: Checkout/Checkin, Conflict Resolution, Replication, WAL Logging.

FIX:
  [N1] WAL crash simulation dung WALLog object that
  [N2] wal_state la derived property tu WALLog
  [N3] Checkout state persist vao DB (CheckoutStore) — khong mat khi restart
"""

import copy
from datetime import datetime
from .models import CADModel, Delta, Geometry, WALLog
from .storage import SnapshotStore, DeltaStore, CheckoutStore
import os


class SiteNode:
    """Dai dien 1 site/node trong he thong phan tan."""

    def __init__(self, site_id, strategy="branching"):
        self.site_id = site_id
        self.strategy = strategy
        self.snapshot_store = SnapshotStore(site_id)
        self.delta_store = DeltaStore(site_id)
        self.checkout_store = CheckoutStore(site_id)

        self.log = []

        # WAL thuc thu — persist xuong file JSON
        db_dir = os.path.join(os.path.dirname(__file__), "db")
        os.makedirs(db_dir, exist_ok=True)
        self.wal_log = WALLog(os.path.join(db_dir, f"{site_id}_wal.json"))

        # Crash flag
        self.crash_on_next_checkin = False

    @property
    def wal_state(self):
        """Derived property tu WALLog thuc."""
        all_entries = self.wal_log.all_entries()
        uncommitted = self.wal_log.get_uncommitted()
        return {
            "crash_on_next_checkin": self.crash_on_next_checkin,
            "coordinator_crashed": len(uncommitted) > 0,
            "total_entries": len(all_entries),
            "uncommitted_count": len(uncommitted),
            "pending_transactions": [e.to_dict() for e in uncommitted],
            "all_entries": [e.to_dict() for e in all_entries],
        }

    def create_model(self, part_id, geometry):
        """Tao 1 doi tuong CAD moi tai site nay."""
        model = CADModel(
            part_id=part_id, geometry=geometry,
            version=1, site_origin=self.site_id
        )
        self.snapshot_store.save(model)
        self.delta_store.save_base(model)
        self._log("CREATE", part_id, "Tao model v1")
        return model

    def checkout(self, part_id, user):
        """
        [N3] Checkout voi persist vao DB.
        Cho phep nhieu user cung checkout (Optimistic CC).
        """
        model = self.snapshot_store.get_latest(part_id)
        if not model:
            return None

        checkout_copy = copy.deepcopy(model)
        checkout_time = datetime.now().isoformat()

        # Persist vao DB — khong mat khi restart
        self.checkout_store.save(
            part_id, user, model.version, checkout_copy, checkout_time
        )

        self._log("CHECKOUT", part_id, f"User '{user}' checkout v{model.version}")
        return checkout_copy

    def checkin(self, part_id, user, modified_model):
        """
        Checkin voi WAL bao ve giao dich + persistent checkout.
        """
        # Kiem tra checkout ton tai (tu DB)
        checkout_info = self.checkout_store.get(part_id, user)
        if not checkout_info:
            return False, f"User '{user}' chua checkout part nay.", None

        # 1. BEGIN WAL
        txn_data = {
            "user": user,
            "model_data": modified_model.to_dict()
        }
        entry_id = self.wal_log.begin("CHECKIN", part_id, txn_data)

        # 2. CRASH SIMULATION
        if self.crash_on_next_checkin:
            self.crash_on_next_checkin = False
            raise RuntimeError(
                f"CRASH_SIMULATED: WAL entry #{entry_id} PENDING. DB khong duoc cap nhat."
            )

        try:
            base_version = checkout_info['base_version']
            current = self.snapshot_store.get_latest(part_id)

            # === KIEM TRA XUNG DOT ===
            delta_obj = None
            if current and current.version > base_version:
                if self.strategy == "timestamp":
                    modified_model.version = current.version + 1
                    modified_model.branch = "main"
                    modified_model.modified_at = datetime.now().isoformat()
                    delta_obj = Delta.compute(current, modified_model, self.site_id)
                elif self.strategy == "branching":
                    branch_name = f"{self.site_id}/{user}/v{base_version + 1}"
                    modified_model.branch = branch_name
                    modified_model.version = base_version + 1
                    modified_model.modified_at = datetime.now().isoformat()
                    # Luu delta tu current (main) sang nhanh moi — de DeltaStore nhat quan
                    delta_obj = Delta.compute(current, modified_model, self.site_id)

                from .storage import TransactionManager
                TransactionManager.commit_checkin(self.site_id, modified_model, delta_obj, part_id, user)

                self.wal_log.commit(entry_id)
                self._log("CHECKIN", part_id,
                          f"XUNG DOT: User '{user}' resolved ({self.strategy})")
                return True, f"XUNG DOT phat hien va da giai quyet ({self.strategy}).", modified_model

            # === KHONG CO XUNG DOT ===
            modified_model.version = (current.version if current else 0) + 1
            modified_model.branch = "main"
            modified_model.modified_at = datetime.now().isoformat()
            
            if current:
                delta_obj = Delta.compute(current, modified_model, self.site_id)

            from .storage import TransactionManager
            TransactionManager.commit_checkin(self.site_id, modified_model, delta_obj, part_id, user)

            # 3. COMMIT WAL
            self.wal_log.commit(entry_id)
            self._log("CHECKIN", part_id,
                      f"User '{user}' check-in v{modified_model.version} thanh cong.")
            return True, f"Check-in v{modified_model.version} thanh cong.", modified_model

        except Exception as e:
            print(f"[SiteNode] Error during checkin: {e}")
            return False, str(e), None

    def replicate_to(self, other_site, part_id):
        """Sao chep phien ban moi nhat sang site khac."""
        model = self.snapshot_store.get_latest(part_id)
        if not model:
            return False
        other_site.snapshot_store.save(model)
        other_site.delta_store.save_base(model)
        self._log("REPLICATE", part_id,
                  f"Sao chep v{model.version} sang '{other_site.site_id}'")
        return True

    def get_storage_comparison(self):
        """So sanh dung luong Snapshot vs Delta."""
        snap = self.snapshot_store.total_storage_bytes()
        delta = self.delta_store.total_storage_bytes()
        return {
            "site_id": self.site_id,
            "snapshot_total_bytes": snap,
            "delta_total_bytes": delta,
            "savings_bytes": snap - delta,
            "savings_percent": round((1 - delta / max(snap, 1)) * 100, 2)
        }

    def wal_recover(self):
        """Recovery that: rollback cac WAL entry chua commit."""
        def _rollback_fn(entry):
            if entry.operation == "CHECKIN":
                from .storage import TransactionManager
                TransactionManager.rollback_cleanup(self.site_id, entry.part_id)
                
            self._log("WAL_ROLLBACK", entry.part_id,
                      f"Rolled back WAL entry #{entry.entry_id}: {entry.operation}")

        recovered = self.wal_log.recover(_rollback_fn)
        return recovered

    def _log(self, action, part_id, msg):
        self.log.append({
            "site": self.site_id, "action": action, "part_id": part_id,
            "message": msg, "timestamp": datetime.now().isoformat()
        })