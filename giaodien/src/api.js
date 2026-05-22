// api.js — Frontend API layer khớp hoàn toàn với backend server.py
// Backend endpoints: http://127.0.0.1:5001 (Site-A), 5002 (Site-B), 5003 (Site-C)
// Coordinator:       http://127.0.0.1:5000

export const COORDINATOR_URL = 'http://127.0.0.1:5000';

export const SITES = {
  a: {
    name: 'Site-A',
    host: 'http://127.0.0.1:5001',
    site_id: 'Site-A',
    category: 'engine',
    label: 'Engine Fragment',
    color: '#3b82f6',
    strategy: 'Branching',   // site_node.py: strategy="branching"
  },
  b: {
    name: 'Site-B',
    host: 'http://127.0.0.1:5002',
    site_id: 'Site-B',
    category: 'chassis',
    label: 'Chassis Fragment',
    color: '#8b5cf6',
    strategy: 'Branching',   // site_node.py: strategy="branching"
  },
  c: {
    name: 'Site-C',
    host: 'http://127.0.0.1:5003',
    site_id: 'Site-C',
    category: 'interior',
    label: 'Interior Fragment',
    color: '#10b981',
    strategy: 'Branching',
  },
};

export const SITE_ID_TO_KEY = {
  'Site-A': 'a',
  'Site-B': 'b',
  'Site-C': 'c',
};

export const PREFIX_BY_SITE_KEY = {
  a: 'ENG',
  b: 'CHS',
  c: 'INT',
};

// ─────────────────────────────────────────────
// HTTP helpers
// ─────────────────────────────────────────────

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.message || body.error || `HTTP ${response.status}`);
  }
  return body;
}

// Trả về body kèm _status để caller tự xử lý lỗi nghiệp vụ (vd: conflict 200 vs crash 500)
async function fetchJSONRaw(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({ success: false, message: `HTTP ${response.status}` }));
  return { ...body, _status: response.status };
}

// ─────────────────────────────────────────────
// Health — GET /health
// ─────────────────────────────────────────────

export async function healthCheck(key) {
  try {
    const response = await fetchJSON(`${SITES[key].host}/health`);
    const networkOnline = response.network_online !== false;
    return {
      reachable: true,
      online: networkOnline,
      network_online: networkOnline,
      ...response,
    };
  } catch {
    return { online: false, reachable: false, network_online: false };
  }
}

// ─────────────────────────────────────────────
// Models — CRUD + Checkout/Checkin
// ─────────────────────────────────────────────

/** GET /models — Liệt kê tất cả models trên site */
export async function listModels(key) {
  return fetchJSON(`${SITES[key].host}/models`);
}

/** GET /models/<part_id>?version=N — Lấy model, hỗ trợ query version cụ thể */
export async function getModel(key, partId, version = null) {
  const query = version ? `?version=${version}` : '';
  return fetchJSON(`${SITES[key].host}/models/${partId}${query}`);
}

/** POST /models — Tạo model mới */
export async function createModel(key, partId, geometry) {
  return fetchJSON(`${SITES[key].host}/models`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ part_id: partId, geometry }),
  });
}

/** POST /models/<part_id>/checkout — Checkout object (Optimistic CC) */
export async function checkout(key, partId, user) {
  return fetchJSON(`${SITES[key].host}/models/${partId}/checkout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user }),
  });
}

/** POST /models/<part_id>/checkin — Checkin object, phát hiện conflict */
export async function checkin(key, partId, user, model) {
  return fetchJSONRaw(`${SITES[key].host}/models/${partId}/checkin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user, model }),
  });
}

/** GET /models/<part_id>/versions — Xem lịch sử phiên bản + branches */
export async function getVersions(key, partId) {
  return fetchJSON(`${SITES[key].host}/models/${partId}/versions`);
}

// ─────────────────────────────────────────────
// Replication — POST /replicate
// ─────────────────────────────────────────────

/** POST /replicate — Sao chép phiên bản mới nhất sang site khác */
export async function replicate(key, partId, targetSite) {
  return fetchJSON(`${SITES[key].host}/replicate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ part_id: partId, target_site: targetSite }),
  });
}

// ─────────────────────────────────────────────
// Storage & Fragmentation
// ─────────────────────────────────────────────

/** GET /storage/compare — So sánh Snapshot vs Delta */
export async function getStorageComparison(key) {
  return fetchJSON(`${SITES[key].host}/storage/compare`);
}

/** GET /fragmentation — Thông tin phân mảnh ngang */
export async function getFragmentation(key) {
  return fetchJSON(`${SITES[key].host}/fragmentation`);
}

// ─────────────────────────────────────────────
// Logs — GET /logs
// ─────────────────────────────────────────────

/** GET /logs — Nhật ký hoạt động của site */
export async function getLogs(key) {
  return fetchJSON(`${SITES[key].host}/logs`);
}

// ─────────────────────────────────────────────
// Benchmark & Analysis
// ─────────────────────────────────────────────

/** GET /benchmark — Đọc benchmark_results.json đã lưu */
export async function getBenchmark(key) {
  return fetchJSON(`${SITES[key].host}/benchmark`);
}

/** POST /benchmark/run — Chạy benchmark 10 versions ngay lập tức */
export async function runBenchmark(key = 'a') {
  return fetchJSON(`${SITES[key].host}/benchmark/run`, { method: 'POST' });
}

/** GET /rehydration/benchmark — Đo latency O(1) Snapshot vs O(k) Delta */
export async function getRehydrationBenchmark(key = 'a') {
  return fetchJSON(`${SITES[key].host}/rehydration/benchmark`);
}

/** GET /serialization/analysis — So sánh JSON vs marshmallow vs pickle */
export async function getSerializationAnalysis(key = 'a') {
  return fetchJSON(`${SITES[key].host}/serialization/analysis`);
}

/** GET /dataset/info — Thông tin dataset + schema */
export async function getDatasetInfo(key) {
  return fetchJSON(`${SITES[key].host}/dataset/info`);
}

// ─────────────────────────────────────────────
// WAL & Crash Demo — Özsu §15.7
// ─────────────────────────────────────────────

/** GET /wal/status — Trạng thái WAL (uncommitted entries, crash flag) */
export async function getWalStatus(key) {
  return fetchJSON(`${SITES[key].host}/wal/status`);
}

/** GET /checkouts — Danh sách checkout đang active (persist trong DB) */
export async function getCheckouts(key) {
  return fetchJSON(`${SITES[key].host}/checkouts`);
}

/**
 * POST /crash/demo — Full crash demo: checkout → sửa → set crash flag → checkin → CRASH
 * Kết quả: WAL có entry PENDING, DB không thay đổi
 */
export async function runCrashDemo(key, partId) {
  return fetchJSONRaw(`${SITES[key].host}/crash/demo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ part_id: partId, user: 'crash_demo_user' }),
  });
}

/**
 * POST /crash/simulate — Bật flag crash cho checkin tiếp theo của site
 * Dùng khi muốn tự kiểm soát từng bước thay vì gọi /crash/demo
 */
export async function simulateCrash(key) {
  return fetchJSON(`${SITES[key].host}/crash/simulate`, { method: 'POST' });
}

/**
 * POST /coordinator/restart — Recovery: rollback tất cả WAL PENDING entries
 * Đảm bảo Atomicity (all-or-nothing)
 */
export async function restartCoordinator(key) {
  return fetchJSON(`${SITES[key].host}/coordinator/restart`, { method: 'POST' });
}

// ─────────────────────────────────────────────
// Coordinator Metadata (port 5000)
// ─────────────────────────────────────────────

/** GET http://127.0.0.1:5000/health — Kiểm tra coordinator online */
export async function coordinatorHealth() {
  try {
    return await fetchJSON(`${COORDINATOR_URL}/health`);
  } catch {
    return { online: false, reachable: false };
  }
}

/** GET /meta/version-graph/<part_id> — Xem DAG phiên bản của object */
export async function getVersionGraph(partId) {
  return fetchJSON(`${COORDINATOR_URL}/meta/version-graph/${partId}`);
}

/** GET /meta/branch-heads/<part_id> — Xem branch head mỗi nhánh */
export async function getBranchHeads(partId) {
  return fetchJSON(`${COORDINATOR_URL}/meta/branch-heads/${partId}`);
}

/** GET /meta/conflicts/<part_id> — Danh sách conflict đã ghi nhận */
export async function getConflicts(partId) {
  return fetchJSON(`${COORDINATOR_URL}/meta/conflicts/${partId}`);
}

/** POST /meta/register-object — Đăng ký OID với coordinator */
export async function registerObject(partId, oid, siteId) {
  return fetchJSON(`${COORDINATOR_URL}/meta/register-object`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ part_id: partId, oid, site_id: siteId }),
  });
}

// ─────────────────────────────────────────────
// Compatibility helpers for TabNetworkDisconnect
// ─────────────────────────────────────────────

/** POST /network/disconnect — Ngắt kết nối mạng của site */
export async function disconnectNetwork(key) {
  return fetchJSON(`${SITES[key].host}/network/disconnect`, { method: 'POST' });
}

/** POST /network/reconnect — Kết nối lại mạng của site */
export async function reconnectNetwork(key) {
  return fetchJSON(`${SITES[key].host}/network/reconnect`, { method: 'POST' });
}

/** GET /network/status — Lấy trạng thái mạng của site */
export async function getNetworkStatus(key) {
  return fetchJSON(`${SITES[key].host}/network/status`);
}

/** GET /replication/outbox — Lấy replication outbox của site */
export async function getReplicationOutbox(key) {
  return fetchJSON(`${SITES[key].host}/replication/outbox`);
}

/** POST /replication/replay — Replay replication queue */
export async function replayReplication(key, targetSite) {
  return fetchJSON(`${SITES[key].host}/replication/replay`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_site: targetSite }),
  });
}
