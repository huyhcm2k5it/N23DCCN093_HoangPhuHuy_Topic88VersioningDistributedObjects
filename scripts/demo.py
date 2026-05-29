import time
from datetime import datetime

import requests

from scripts.benchmark import run_benchmark
from scripts.visualize import generate_all_charts


SITES = {
    "Site-A": "http://127.0.0.1:5001",
    "Site-B": "http://127.0.0.1:5002",
    "Site-C": "http://127.0.0.1:5003",
}


def print_banner(message):
    print(f"\n{'=' * 74}")
    print(f"  {message}")
    print(f"{'=' * 74}")


def post_json(site_name, path, payload=None, expected=None):
    response = requests.post(f"{SITES[site_name]}{path}", json=payload or {}, timeout=10)
    if expected and response.status_code != expected:
        raise RuntimeError(f"{site_name}{path} HTTP {response.status_code}: {response.text}")
    return response


def get_json(site_name, path):
    response = requests.get(f"{SITES[site_name]}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


def demo_geometry():
    return {
        "type": "Solid",
        "vertices": [
            {"id": "V1", "x": 0, "y": 0, "z": 0},
            {"id": "V2", "x": 120, "y": 0, "z": 0},
            {"id": "V3", "x": 0, "y": 80, "z": 0},
            {"id": "V4", "x": 30, "y": 30, "z": 60},
        ],
        "edges": [
            {"id": "E1", "from": "V1", "to": "V2"},
            {"id": "E2", "from": "V2", "to": "V3"},
            {"id": "E3", "from": "V3", "to": "V1"},
            {"id": "E4", "from": "V1", "to": "V4"},
            {"id": "E5", "from": "V2", "to": "V4"},
            {"id": "E6", "from": "V3", "to": "V4"},
        ],
        "faces": [
            {"id": "F1", "edges": ["E1", "E2", "E3"]},
            {"id": "F2", "edges": ["E1", "E4", "E5"]},
            {"id": "F3", "edges": ["E2", "E5", "E6"]},
            {"id": "F4", "edges": ["E3", "E4", "E6"]},
        ],
        "properties": {
            "category": "engine",
            "material": "baseline_steel",
            "tolerance_mm": 0.01,
            "weight_kg": 18.5,
        },
    }


def mutate_model(model, material, delta_x):
    updated = dict(model)
    geometry = {
        **model["geometry"],
        "vertices": [dict(vertex) for vertex in model["geometry"]["vertices"]],
        "properties": dict(model["geometry"].get("properties", {})),
    }
    geometry["properties"]["material"] = material
    geometry["properties"]["edited_by"] = material
    geometry["vertices"][0]["x"] = round(geometry["vertices"][0]["x"] + delta_x, 2)
    updated["geometry"] = geometry
    return updated


def get_outbox_entry(source_site, op_id):
    outbox = get_json(source_site, "/replication/outbox")
    for entry in outbox.get("entries", []):
        if entry.get("op_id") == op_id:
            return entry
    return None


def wait_for_retry_window(source_site, op_id):
    entry = get_outbox_entry(source_site, op_id)
    next_retry_at = (entry or {}).get("next_retry_at")
    if not next_retry_at:
        return

    try:
        retry_time = datetime.fromisoformat(next_retry_at)
        now = datetime.now(retry_time.tzinfo) if retry_time.tzinfo else datetime.now()
        delay_seconds = (retry_time - now).total_seconds()
    except Exception:
        return

    if delay_seconds > 0:
        print(f"   Cho den retry window cua outbox ({delay_seconds:.1f}s)...")
        time.sleep(delay_seconds + 0.2)


def replay_until_acked(source_site, target_site, op_id, attempts=4):
    replay_result = None
    outbox_entry = get_outbox_entry(source_site, op_id)
    for attempt in range(1, attempts + 1):
        if outbox_entry and outbox_entry.get("status") == "ACKED":
            return {"message": "Operation da ACK truoc do."}, outbox_entry

        wait_for_retry_window(source_site, op_id)
        replay_result = post_json(
            source_site,
            "/replication/replay",
            {"target_site": target_site},
        ).json()
        outbox_entry = get_outbox_entry(source_site, op_id)
        if outbox_entry and outbox_entry.get("status") == "ACKED":
            return replay_result, outbox_entry

        if attempt < attempts:
            print(f"   Replay attempt {attempt} chua ACK, thu lai...")
            time.sleep(1)

    status = (outbox_entry or {}).get("status", "MISSING")
    raise RuntimeError(f"Outbox {op_id} chua ACK sau {attempts} lan replay. status={status}")


def check_sites_online():
    print("\n[BUOC 1] KIEM TRA 3 SITE PHAN TAN")
    for site_name, site_url in SITES.items():
        try:
            health = requests.get(f"{site_url}/health", timeout=2).json()
            fragmentation = get_json(site_name, "/fragmentation")
            print(
                f"  OK {site_name}: {health['status']} | "
                f"strategy={health.get('strategy')} | parts={fragmentation.get('local_parts_count')} | "
                f"fragment={fragmentation.get('predicate')}"
            )
        except Exception:
            print(f"  FAIL {site_name}: OFFLINE. Hay chay 'python main.py --servers' truoc.")
            return False
    return True


def run_collaborative_conflict_demo():
    print_banner("KICH BAN CHINH: 2 SITE CHECKOUT CUNG CAD OBJECT VA TAO CONFLICT")

    source_site = "Site-A"
    target_site = "Site-B"
    part_id = f"ENG-DEMO-{int(time.time() * 1000)}"

    created = post_json(
        source_site,
        "/models",
        {"part_id": part_id, "geometry": demo_geometry()},
        expected=201,
    ).json()
    post_json(source_site, "/replicate", {"part_id": part_id, "target_site": target_site})
    replicated = get_json(target_site, f"/models/{part_id}")

    print(f"1. Tao CAD_Model {part_id} tai {source_site} va replicate sang {target_site}.")
    print(f"   Schema: part_id, nested geometry, version, oid, branch, checksum")
    print(
        f"   Geometry: {len(created['geometry']['vertices'])} vertices, "
        f"{len(created['geometry']['edges'])} edges, {len(created['geometry']['faces'])} faces"
    )
    print(f"   OID {source_site}: {created['oid']}")
    print(f"   OID {target_site}: {replicated['oid']}")
    print(f"   OID invariant across sites: {created['oid'] == replicated['oid']}")

    source_checkout = post_json(
        source_site,
        f"/models/{part_id}/checkout",
        {"user": "Engineer_A"},
    ).json()
    target_checkout = post_json(
        target_site,
        f"/models/{part_id}/checkout",
        {"user": "Engineer_B"},
    ).json()
    print(f"2. Hai site checkout cung object:")
    print(f"   {source_site}: base v{source_checkout['version']} | oid={source_checkout['oid']}")
    print(f"   {target_site}: base v{target_checkout['version']} | oid={target_checkout['oid']}")

    source_result = post_json(
        source_site,
        f"/models/{part_id}/checkin",
        {"user": "Engineer_A", "model": mutate_model(source_checkout, "carbon_fiber", 40)},
    ).json()
    print(f"3. {source_site} checkin truoc:")
    print(f"   branch={source_result['branch']} | version={source_result['version_after']} | conflict={source_result['is_conflict']}")

    post_json(source_site, "/replicate", {"part_id": part_id, "target_site": target_site})
    target_latest = get_json(target_site, f"/models/{part_id}")
    print(f"4. Replicate v2 sang {target_site}; current head tai {target_site}=v{target_latest['version']}.")
    print(f"   Engineer_B van dang giu ban cu base v{target_checkout['version']}.")

    target_result = post_json(
        target_site,
        f"/models/{part_id}/checkin",
        {"user": "Engineer_B", "model": mutate_model(target_checkout, "titanium_alloy", -35)},
    ).json()
    versions = get_json(target_site, f"/models/{part_id}/versions")
    branches = sorted({version["branch"] for version in versions})

    print(f"5. {target_site} checkin stale base -> he thong phat hien conflict.")
    print(f"   strategy={target_result['conflict_strategy']} | branch={target_result['branch']} | version={target_result['version_after']}")
    print(f"   Branches tai {target_site}: {', '.join(branches)}")
    print("   Ket luan: dung yeu cau de bai - khong overwrite, bao ton 2 nhanh thiet ke.")


def run_delta_storage_demo():
    print_banner("PHAN TICH: FULL SNAPSHOT VS DELTA STORAGE CHO 10 PHIEN BAN")
    results = run_benchmark(num_versions=10, complexity=5)
    generate_all_charts()
    print("Tom tat metric bat buoc:")
    print(f"   full_snapshot_bytes={results['full_snapshot_bytes']}")
    print(f"   delta_storage_bytes={results['delta_storage_bytes']}")
    print(f"   saving_percent={results['saving_percent']}%")
    print(f"   avg_rehydration_ms={results['avg_rehydration_ms']} | integrity_ok={results['integrity_ok']}")


def run_node_disconnect_failure_demo():
    print_banner("KICH BAN LOI DUY NHAT: NODE DISCONNECT + OUTBOX RETRY")

    part_id = f"ENG-NET-{int(time.time() * 1000)}"
    created = post_json(
        "Site-A",
        "/models",
        {"part_id": part_id, "geometry": demo_geometry()},
        expected=201,
    ).json()
    queued = None

    print(f"1. Tao object {part_id} tai Site-A. OID={created['oid']}")
    try:
        disconnected = post_json("Site-B", "/network/disconnect").json()
        print(f"2. Gia lap Site-B disconnect: mode={disconnected['network_status']['mode']}")

        queued_response = post_json(
            "Site-A",
            "/replicate",
            {"part_id": part_id, "target_site": "Site-B"},
        )
        queued = queued_response.json()
        print("3. Site-A replicate khi Site-B disconnected:")
        print(f"   HTTP {queued_response.status_code} | queued={queued['queued']} | outbox_status={queued['outbox_entry']['status']}")
        print(f"   op_id={queued['op_id']}")
    finally:
        reconnected = post_json("Site-B", "/network/reconnect").json()
        print(f"4. Site-B reconnect: mode={reconnected['network_status']['mode']}")

    replay, outbox_entry = replay_until_acked("Site-A", "Site-B", queued["op_id"])
    replicated = get_json("Site-B", f"/models/{part_id}")
    print("5. Replay outbox sau reconnect:")
    print(f"   {replay['message']} | final_outbox_status={outbox_entry['status']}")
    print(f"   Site-B nhan object: oid={replicated['oid']} | oid_match={replicated['oid'] == created['oid']}")
    print("   Ket luan: request replication khong mat khi node disconnect.")


def run_full_backend_demo():
    print_banner("TOPIC 88 DEMO - VERSIONING DISTRIBUTED CAD OBJECTS")
    print("Demo bam dung de bai: checkout cung object, conflict branching, delta metric, 1 loi node disconnect.")

    if not check_sites_online():
        return

    run_collaborative_conflict_demo()
    run_delta_storage_demo()
    run_node_disconnect_failure_demo()

    print_banner("DEMO HOAN TAT")
    print("Da bao phu: CAD_Model nested object, OID invariant, 2-site checkout/checkin conflict, delta storage 10 versions, va 1 failure scenario Node Disconnect.")
