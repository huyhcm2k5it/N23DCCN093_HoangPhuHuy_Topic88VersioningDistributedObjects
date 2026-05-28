export const COORDINATOR_URL = 'http://127.0.0.1:5000';

export const SITES = {
  a: { key: 'a', site_id: 'Site-A', name: 'Site-A', port: 5001, host: 'http://127.0.0.1:5001', category: 'engine', strategy: 'Branching' },
  b: { key: 'b', site_id: 'Site-B', name: 'Site-B', port: 5002, host: 'http://127.0.0.1:5002', category: 'chassis', strategy: 'Branching' },
  c: { key: 'c', site_id: 'Site-C', name: 'Site-C', port: 5003, host: 'http://127.0.0.1:5003', category: 'interior', strategy: 'Branching' },
};

export const PREFIX_BY_SITE_KEY = { a: 'ENG', b: 'CHS', c: 'INT' };

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({ success: false, message: `HTTP ${response.status}` }));
  if (!response.ok) throw new Error(body.message || body.error || `HTTP ${response.status}`);
  return body;
}

async function fetchJSONRaw(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({ success: false, message: `HTTP ${response.status}` }));
  return { ...body, _status: response.status };
}

const jsonOptions = (body) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export async function healthCheck(key) {
  try {
    return { ...(await fetchJSON(`${SITES[key].host}/health`)), reachable: true };
  } catch (error) {
    return { reachable: false, error: error.message };
  }
}

export async function listModels(key) {
  return fetchJSON(`${SITES[key].host}/models`);
}

export async function getModel(key, partId, version = null) {
  const query = version ? `?version=${version}` : '';
  return fetchJSON(`${SITES[key].host}/models/${partId}${query}`);
}

export async function createModel(key, partId, geometry) {
  return fetchJSON(`${SITES[key].host}/models`, jsonOptions({ part_id: partId, geometry }));
}

export async function checkout(key, partId, user) {
  return fetchJSON(`${SITES[key].host}/models/${partId}/checkout`, jsonOptions({ user }));
}

export async function checkin(key, partId, user, model) {
  return fetchJSONRaw(`${SITES[key].host}/models/${partId}/checkin`, jsonOptions({ user, model }));
}

export async function getVersions(key, partId) {
  return fetchJSON(`${SITES[key].host}/models/${partId}/versions`);
}

export async function replicate(key, partId, targetSite) {
  return fetchJSON(`${SITES[key].host}/replicate`, jsonOptions({ part_id: partId, target_site: targetSite }));
}

export async function getStorageComparison(key) {
  return fetchJSON(`${SITES[key].host}/storage/compare`);
}

export async function getFragmentation(key) {
  return fetchJSON(`${SITES[key].host}/fragmentation`);
}

export async function getBenchmark(key) {
  return fetchJSON(`${SITES[key].host}/benchmark`);
}

export async function runBenchmark(key = 'a') {
  return fetchJSON(`${SITES[key].host}/benchmark/run`, { method: 'POST' });
}

export async function coordinatorHealth() {
  try {
    return await fetchJSON(`${COORDINATOR_URL}/health`);
  } catch {
    return { online: false, reachable: false };
  }
}

export async function getVersionGraph(partId) {
  return fetchJSON(`${COORDINATOR_URL}/meta/version-graph/${partId}`);
}

export async function disconnectNetwork(key) {
  return fetchJSON(`${SITES[key].host}/network/disconnect`, { method: 'POST' });
}

export async function reconnectNetwork(key) {
  return fetchJSON(`${SITES[key].host}/network/reconnect`, { method: 'POST' });
}

export async function getNetworkStatus(key) {
  return fetchJSON(`${SITES[key].host}/network/status`);
}

export async function getReplicationOutbox(key) {
  return fetchJSON(`${SITES[key].host}/replication/outbox`);
}

export async function replayReplication(key, targetSite) {
  return fetchJSON(`${SITES[key].host}/replication/replay`, jsonOptions({ target_site: targetSite }));
}

export async function getDatasetInfo(key) {
  return fetchJSON(`${SITES[key].host}/dataset/info`);
}

