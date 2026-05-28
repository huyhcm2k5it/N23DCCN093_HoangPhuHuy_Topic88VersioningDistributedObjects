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
from .models import CADModel, Delta
from .storage import (
    SnapshotStore,
    DeltaStore,
    CheckoutStore,
    ReplicationOutboxStore,
    ReplicationInboxStore,
    )
import os
import requests

class SiteNode:
    """Dai dien 1 site/node trong he thong phan tan."""

    FRAGMENT_PREFIX_BY_SITE = {
        "Site-A": "ENG",
        "Site-B": "CHS",
        "Site-C": "INT",
    }

    FRAGMENT_CATEGORY_BY_SITE = {
        "Site-A": "engine",
        "Site-B": "chassis",
        "Site-C": "interior",
    }

    def __init__(self, site_id, strategy="branching", coordinator_url="http://127.0.0.1:5000"):
        self.site_id = site_id
        self.strategy = "branching"
        self.snapshot_store = SnapshotStore(site_id)
        self.delta_store = DeltaStore(site_id)
        self.checkout_store = CheckoutStore(site_id)
        self.replication_outbox = ReplicationOutboxStore(site_id)
        self.replication_inbox = ReplicationInboxStore(site_id)
        self.coordinator_url = coordinator_url.rstrip("/") if coordinator_url else None
        self.network_online = True
        self.log = []


    @property
    def network_state(self):
        """Trang thai ket noi mang cua node cho demo node disconnect."""
        return {
            "site_id": self.site_id,
            "network_online": self.network_online,
            "status": "online" if self.network_online else "disconnected",
            "mode": "distributed" if self.network_online else "local-only",
            "outbox": self.replication_outbox.summary(),
        }

    def disconnect_network(self):
        """Gia lap node bi mat ket noi voi cac site khac."""
        self.network_online = False
        self._log("NETWORK", "-", "Node disconnected from distributed network")
        self.push_site_health()
        return self.network_state

    def reconnect_network(self):
        """Khoi phuc ket noi mang cua node."""
        self.network_online = True
        self._log("NETWORK", "-", "Node reconnected to distributed network")
        self.push_site_health()
        return self.network_state

    def expected_fragment_prefix(self):
        """Prefix part_id ma site nay quan ly theo phan manh ngang."""
        return self.FRAGMENT_PREFIX_BY_SITE.get(self.site_id)

    def expected_fragment_category(self):
        """Category ma site nay quan ly theo phan manh ngang."""
        return self.FRAGMENT_CATEGORY_BY_SITE.get(self.site_id)

    def accepts_local_part(self, part_id):
        """Kiem tra part_id co thoa predicate phan manh cua site hay khong."""
        prefix = self.expected_fragment_prefix()
        return not prefix or str(part_id).startswith(f"{prefix}-")

    def _coordinator_post(self, path, payload):
        if not self.coordinator_url:
            return None
        try:
            response = requests.post(
                f"{self.coordinator_url}{path}",
                json=payload,
                timeout=1.0,
            )
            if response.status_code in (200, 201):
                return response.json()
        except Exception:
            return None
        return None

    def _coordinator_get(self, path):
        if not self.coordinator_url:
            return None
        try:
            response = requests.get(f"{self.coordinator_url}{path}", timeout=1.0)
            if response.status_code == 200:
                return response.json()
        except Exception:
            return None
        return None

    def push_site_health(self):
        return self._coordinator_post(
            "/meta/site-health",
            {
                "site_id": self.site_id,
                "network_online": self.network_online,
                "status": "online" if self.network_online else "disconnected",
                "outbox": self.replication_outbox.summary(),
                "timestamp": datetime.now().isoformat(),
            },
        )

    def notify_register_object(self, model):
        return self._coordinator_post(
            "/meta/register-object",
            {
                "site_id": self.site_id,
                "part_id": model.part_id,
                "oid": model.oid,
                "version": model.version,
                "branch": model.branch or "main",
                "checksum": model.checksum(),
            },
        )

    def notify_update_head(self, model, parent_version=None, parent_branch=None):
        return self._coordinator_post(
            "/meta/update-head",
            {
                "site_id": self.site_id,
                "part_id": model.part_id,
                "oid": model.oid,
                "version": model.version,
                "branch": model.branch or "main",
                "checksum": model.checksum(),
                "parent_version": parent_version,
                "parent_branch": parent_branch or "main",
            },
        )

    def notify_conflict(self, model, base_version, detail):
        return self._coordinator_post(
            "/meta/record-conflict",
            {
                "site_id": self.site_id,
                "part_id": model.part_id,
                "oid": model.oid,
                "base_version": base_version,
                "conflict_branch": model.branch or "main",
                "detail": detail,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def get_version_graph(self, part_id):
        data = self._coordinator_get(f"/meta/version-graph/{part_id}")
        if data:
            return data

        versions = self.snapshot_store.get_all_versions(part_id)
        nodes = []
        for model in versions:
            if model.version == 1:
                parent_version = None
                parent_branch = None
            elif model.branch == "main":
                parent_version = model.version - 1
                parent_branch = "main"
            else:
                parent_version = 1
                parent_branch = "main"
            nodes.append(
                {
                    "part_id": model.part_id,
                    "oid": model.oid,
                    "version": model.version,
                    "branch": model.branch,
                    "checksum": model.checksum(),
                    "parent_version": parent_version,
                    "parent_branch": parent_branch,
                    "site_id": self.site_id,
                }
            )
        return {
            "part_id": part_id,
            "nodes": nodes,
            "source": "site-local-fallback",
        }

    def create_model(self, part_id, geometry):
        """Tao 1 doi tuong CAD moi tai site nay."""
        model = CADModel(
            part_id=part_id, geometry=geometry,
            version=1, site_origin=self.site_id
        )
        self.snapshot_store.save(model)
        self.delta_store.save_base(model)
        self.notify_register_object(model)
        self.notify_update_head(model, parent_version=None, parent_branch=None)
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
        Checkin voi persistent checkout.
        """
        # Kiem tra checkout ton tai (tu DB)
        checkout_info = self.checkout_store.get(part_id, user)
        if not checkout_info:
            return False, f"User '{user}' chua checkout part nay.", None
        if modified_model.part_id != part_id:
            return False, "PartID trong payload khong khop voi URL checkin.", None

        checkout_base = checkout_info["model"]
        modified_model.oid = checkout_base.oid
        if not modified_model.site_origin:
            modified_model.site_origin = checkout_base.site_origin

        try:
            base_version = checkout_info['base_version']
            current = self.snapshot_store.get_latest(part_id)

            # === KIEM TRA XUNG DOT ===
            delta_obj = None
            if current and current.version > base_version:
                conflict_branch = f"v{base_version + 1}_conflict_{self.site_id.replace('-', '_').upper()}"
                existing_conflict = self.snapshot_store.get_exact(
                    part_id, base_version + 1, conflict_branch
                )
                if existing_conflict and existing_conflict.checksum() != modified_model.checksum():
                    conflict_branch = f"{conflict_branch}_{user}"

                modified_model.branch = conflict_branch
                modified_model.version = base_version + 1
                modified_model.oid = checkout_base.oid
                modified_model.modified_at = datetime.now().isoformat()
                # Branch delta bat dau tu ban user da checkout, khong phai main moi nhat.
                delta_obj = Delta.compute(checkout_base, modified_model, self.site_id)

                from .storage import TransactionManager
                TransactionManager.commit_checkin(self.site_id, modified_model, delta_obj, part_id, user)

                self.notify_update_head(
                    modified_model,
                    parent_version=base_version,
                    parent_branch="main",
                )
                self.notify_conflict(
                    modified_model,
                    base_version=base_version,
                    detail=f"stale-checkin from {user}: base v{base_version}, current v{current.version}",
                )
                self._log("CHECKIN", part_id,
                          f"XUNG DOT: User '{user}' -> branch {modified_model.branch}")
                return True, "XUNG DOT phat hien va da giai quyet (branching).", modified_model

            # === KHONG CO XUNG DOT ===
            modified_model.version = (current.version if current else 0) + 1
            modified_model.branch = "main"
            modified_model.modified_at = datetime.now().isoformat()
            
            if current:
                delta_obj = Delta.compute(current, modified_model, self.site_id)

            from .storage import TransactionManager
            TransactionManager.commit_checkin(self.site_id, modified_model, delta_obj, part_id, user)

            self.notify_update_head(
                modified_model,
                parent_version=(current.version if current else None),
                parent_branch="main",
            )
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
        other_site.import_model(model)
        self._log("REPLICATE", part_id,
                  f"Sao chep v{model.version} sang '{other_site.site_id}'")
        return True

    def import_model(self, model, source_site=None):
        """
        Nhap model tu site khac nhung giu OID/version neu khong xung dot.
        Neu target da co cung (part_id, version, branch) nhung checksum khac,
        import se tach sang branch replica de khong overwrite local write.
        """
        incoming = model.clone()
        source_label = source_site or incoming.site_origin or "remote"
        branch = incoming.branch or "main"
        incoming.branch = branch
        import_conflict = False

        exact = self.snapshot_store.get_exact(incoming.part_id, incoming.version, branch)
        if exact:
            same_object = exact.oid == incoming.oid and exact.checksum() == incoming.checksum()
            if same_object:
                self._log("IMPORT_IDEMPOTENT", incoming.part_id,
                          f"Bo qua duplicate {incoming.part_id} v{incoming.version} branch {branch}")
                return exact

            conflict_branch = f"{source_label}/replica/v{incoming.version}"
            existing_conflict = self.snapshot_store.get_exact(
                incoming.part_id, incoming.version, conflict_branch
            )
            if existing_conflict:
                same_conflict_object = (
                    existing_conflict.oid == incoming.oid
                    and existing_conflict.checksum() == incoming.checksum()
                )
                if same_conflict_object:
                    self._log(
                        "IMPORT_IDEMPOTENT",
                        incoming.part_id,
                        f"Replay duplicate da ton tai o branch {conflict_branch}",
                    )
                    return existing_conflict
                conflict_branch = f"{conflict_branch}/{datetime.now().strftime('%H%M%S%f')}"
            incoming.branch = conflict_branch
            branch = conflict_branch
            import_conflict = True
            self._log("IMPORT_CONFLICT", incoming.part_id,
                      f"Same version collision tai {self.site_id}; luu incoming vao branch {branch}")

        existing_versions = self.snapshot_store.get_all_versions(incoming.part_id)
        previous = self.snapshot_store.get_latest(incoming.part_id, branch)
        if not previous and branch != "main":
            previous = self.snapshot_store.get(incoming.part_id, incoming.version - 1, "main")
        if not previous:
            previous = self.snapshot_store.get_latest(incoming.part_id, "main")

        self.snapshot_store.save(incoming)

        if not existing_versions:
            self.delta_store.save_base(incoming)
            self.notify_register_object(incoming)
        elif previous and incoming.version > previous.version:
            delta = Delta.compute(previous, incoming, self.site_id)
            self.delta_store.save_delta(delta)

        self.notify_update_head(
            incoming,
            parent_version=(previous.version if previous else None),
            parent_branch=(previous.branch if previous else None),
        )
        if import_conflict:
            self.notify_conflict(
                incoming,
                base_version=incoming.version,
                detail=f"incoming collision from {source_label} on same version/branch",
            )

        self._log("IMPORT", incoming.part_id,
                  f"Nhan {incoming.part_id} v{incoming.version} branch {branch}")
        return incoming

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



    def _log(self, action, part_id, msg):
        self.log.append({
            "site": self.site_id, "action": action, "part_id": part_id,
            "message": msg, "timestamp": datetime.now().isoformat()
        })
