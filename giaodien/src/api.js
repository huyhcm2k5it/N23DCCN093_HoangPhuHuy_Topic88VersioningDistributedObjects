/**
 * api.js — Frontend API bridge.
 * 
 * Backend Sites (from main.py cmd_servers):
 *   Site-A: http://127.0.0.1:5001  (Engine parts,   strategy=branching)
 *   Site-B: http://127.0.0.1:5002  (Chassis parts,  strategy=branching)
 *   Site-C: http://127.0.0.1:5003  (Interior parts, strategy=timestamp)
 */
export const SITES = {
  a: { name: 'Site-A', host: 'http://127.0.0.1:5001', site_id: 'Site-A', category: 'engine',   label: 'Hà Nội (HN)',  color: '#3b82f6', strategy: 'Branching' },
  b: { name: 'Site-B', host: 'http://127.0.0.1:5002', site_id: 'Site-B', category: 'chassis',  label: 'Sài Gòn (SG)', color: '#8b5cf6', strategy: 'Branching' },
  c: { name: 'Site-C', host: 'http://127.0.0.1:5003', site_id: 'Site-C', category: 'interior', label: 'Đà Nẵng (ĐN)', color: '#10b981', strategy: 'Timestamp' },
};

export const SITE_ID_TO_KEY = {
  'Site-A': 'a',
  'Site-B': 'b',
  'Site-C': 'c',
};

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.message || body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Fetch that returns body even on non-2xx (e.g. crash 500).
 * Used by checkin and crash endpoints.
 */
async function fetchJSONRaw(url, options = {}) {
  const res = await fetch(url, options);
  const body = await res.json().catch(() => ({ success: false, message: `HTTP ${res.status}` }));
  return { ...body, _status: res.status };
}

// ── HEALTH ──────────────────────────────────────────────────
export async function healthCheck(key) {
  try {
    const res = await fetchJSON(`${SITES[key].host}/health`);
    return { online: true, ...res };
  } catch {
    return { online: false };
  }
}

// ── MODELS ──────────────────────────────────────────────────
export async function listModels(key) {
  return fetchJSON(`${SITES[key].host}/models`);
}

export async function getModel(key, partId, version = null) {
  const url = version
    ? `${SITES[key].host}/models/${partId}?version=${version}`
    : `${SITES[key].host}/models/${partId}`;
  return fetchJSON(url);
}

export async function createModel(key, partId, geometry) {
  return fetchJSON(`${SITES[key].host}/models`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ part_id: partId, geometry }),
  });
}

export async function checkout(key, partId, user) {
  return fetchJSON(`${SITES[key].host}/models/${partId}/checkout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user }),
  });
}

/**
 * Checkin — dung fetchJSONRaw de handle crash 500.
 * Khi crash: server tra 500 + body {success:false, message, wal_status}
 * Thay vi throw, tra ve body cho frontend xu ly.
 */
export async function checkin(key, partId, user, model) {
  return fetchJSONRaw(`${SITES[key].host}/models/${partId}/checkin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user, model }),
  });
}

export async function getVersions(key, partId) {
  return fetchJSON(`${SITES[key].host}/models/${partId}/versions`);
}

// ── CHECKOUTS ───────────────────────────────────────────────
// GET /checkouts → { site_id, checkouts: [{part_id, user, base_version, checkout_time}] }
export async function getCheckouts(key) {
  return fetchJSON(`${SITES[key].host}/checkouts`);
}

// ── STORAGE ──────────────────────────────────────────────────
export async function getStorageComparison(key) {
  return fetchJSON(`${SITES[key].host}/storage/compare`);
}

// ── FRAGMENTATION ───────────────────────────────────────────
export async function getFragmentation(key) {
  return fetchJSON(`${SITES[key].host}/fragmentation`);
}

// ── DATASET INFO ────────────────────────────────────────────
export async function getDatasetInfo(key) {
  return fetchJSON(`${SITES[key].host}/dataset/info`);
}

// ── LOGS ────────────────────────────────────────────────────
export async function getLogs(key) {
  return fetchJSON(`${SITES[key].host}/logs`);
}

// ── BENCHMARK ───────────────────────────────────────────────
export async function getBenchmark(key) {
  return fetchJSON(`${SITES[key].host}/benchmark`);
}

export async function runBenchmark(key = 'a') {
  return fetchJSON(`${SITES[key].host}/benchmark/run`, { method: 'POST' });
}

export async function getRehydrationBenchmark(key = 'a') {
  return fetchJSON(`${SITES[key].host}/rehydration/benchmark`);
}

export async function getSerializationAnalysis(key = 'a') {
  return fetchJSON(`${SITES[key].host}/serialization/analysis`);
}

// ── WAL / CRASH ─────────────────────────────────────────────
// GET /wal/status → { crash_on_next_checkin, coordinator_crashed,
//   total_entries, uncommitted_count, pending_transactions, all_entries }
// Moi entry: { entry_id, operation, part_id, data:{user, model_data}, committed, timestamp }
export async function getWalStatus(key) {
  return fetchJSON(`${SITES[key].host}/wal/status`);
}

// POST /crash/simulate → { success, message, wal_status }
export async function simulateCrash(key) {
  return fetchJSON(`${SITES[key].host}/crash/simulate`, { method: 'POST' });
}

/**
 * POST /crash/demo → Full crash sequence in 1 call.
 * Backend: checkout → set crash → checkin (crash) → return WAL status.
 * Response: { success, crashed, message, detail, part_id,
 *             version_before_crash, version_after_crash, wal_status }
 */
export async function runCrashDemo(key, partId, user = 'crash_demo_user') {
  return fetchJSON(`${SITES[key].host}/crash/demo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ part_id: partId, user }),
  });
}

// POST /coordinator/restart → { success, message, rolled_back_count,
//   recovered_entries: [WALEntry], wal_status }
export async function restartCoordinator(key) {
  return fetchJSON(`${SITES[key].host}/coordinator/restart`, { method: 'POST' });
}
