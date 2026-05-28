import { useState, useEffect } from 'react';
import { Database, Layers, TrendingDown, Cpu, Server, GitBranch, Network, HardDrive, Activity, BookOpen, Zap, Clock } from 'lucide-react';
import { SITES, getBenchmark, getDatasetInfo, runBenchmark } from '../api';

// ─── Architecture Diagram (SVG) ───
function ArchitectureDiagram() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '20px 0' }}>
      <svg width="520" height="320" viewBox="0 0 520 320" style={{ maxWidth: '100%' }}>
        {/* Client */}
        <rect x="190" y="8" width="140" height="40" rx="10" fill="rgba(59,130,246,.12)" stroke="rgba(59,130,246,.3)" strokeWidth="1.5" />
        <text x="260" y="32" textAnchor="middle" fill="#60a5fa" fontSize="13" fontWeight="600">🖥️ React Dashboard</text>

        {/* Coordinator */}
        <rect x="190" y="80" width="140" height="34" rx="10" fill="rgba(245,158,11,.1)" stroke="rgba(245,158,11,.3)" strokeWidth="1.5" />
        <text x="260" y="101" textAnchor="middle" fill="#fbbf24" fontSize="12" fontWeight="600">🔄 Coordinator Metadata</text>

        {/* Lines: Client → Coordinator */}
        <line x1="260" y1="48" x2="260" y2="80" stroke="rgba(148,163,184,.3)" strokeWidth="1.5" strokeDasharray="4,3" />

        {/* 3 Sites */}
        <rect x="20" y="160" width="140" height="130" rx="12" fill="rgba(59,130,246,.06)" stroke="rgba(59,130,246,.25)" strokeWidth="1.5" />
        <text x="90" y="186" textAnchor="middle" fill="#3b82f6" fontSize="13" fontWeight="700">Site-A (HN)</text>
        <text x="90" y="205" textAnchor="middle" fill="#64748b" fontSize="10">Port :5001</text>
        <text x="90" y="222" textAnchor="middle" fill="#60a5fa" fontSize="10">Engine Parts</text>
        <text x="90" y="240" textAnchor="middle" fill="#a78bfa" fontSize="10">Branching</text>
        <rect x="35" y="254" width="110" height="22" rx="5" fill="rgba(59,130,246,.1)" stroke="rgba(59,130,246,.2)" strokeWidth="1" />
        <text x="90" y="269" textAnchor="middle" fill="#94a3b8" fontSize="9">SQLite Site-A.db</text>

        <rect x="190" y="160" width="140" height="130" rx="12" fill="rgba(139,92,246,.06)" stroke="rgba(139,92,246,.25)" strokeWidth="1.5" />
        <text x="260" y="186" textAnchor="middle" fill="#8b5cf6" fontSize="13" fontWeight="700">Site-B (SG)</text>
        <text x="260" y="205" textAnchor="middle" fill="#64748b" fontSize="10">Port :5002</text>
        <text x="260" y="222" textAnchor="middle" fill="#a78bfa" fontSize="10">Chassis Parts</text>
        <text x="260" y="240" textAnchor="middle" fill="#a78bfa" fontSize="10">Branching</text>
        <rect x="205" y="254" width="110" height="22" rx="5" fill="rgba(139,92,246,.1)" stroke="rgba(139,92,246,.2)" strokeWidth="1" />
        <text x="260" y="269" textAnchor="middle" fill="#94a3b8" fontSize="9">SQLite Site-B.db</text>

        <rect x="360" y="160" width="140" height="130" rx="12" fill="rgba(16,185,129,.06)" stroke="rgba(16,185,129,.25)" strokeWidth="1.5" />
        <text x="430" y="186" textAnchor="middle" fill="#10b981" fontSize="13" fontWeight="700">Site-C (ĐN)</text>
        <text x="430" y="205" textAnchor="middle" fill="#64748b" fontSize="10">Port :5003</text>
        <text x="430" y="222" textAnchor="middle" fill="#34d399" fontSize="10">Interior Parts</text>
        <text x="430" y="240" textAnchor="middle" fill="#a78bfa" fontSize="10">Branching</text>
        <rect x="375" y="254" width="110" height="22" rx="5" fill="rgba(16,185,129,.1)" stroke="rgba(16,185,129,.2)" strokeWidth="1" />
        <text x="430" y="269" textAnchor="middle" fill="#94a3b8" fontSize="9">SQLite Site-C.db</text>

        {/* Lines: Coordinator → Sites */}
        <line x1="232" y1="114" x2="90" y2="160" stroke="rgba(148,163,184,.25)" strokeWidth="1.2" />
        <line x1="260" y1="114" x2="260" y2="160" stroke="rgba(148,163,184,.25)" strokeWidth="1.2" />
        <line x1="288" y1="114" x2="430" y2="160" stroke="rgba(148,163,184,.25)" strokeWidth="1.2" />

        {/* Labels on lines */}
        <text x="140" y="138" textAnchor="middle" fill="#475569" fontSize="9">HTTP REST</text>
        <text x="260" y="142" textAnchor="middle" fill="#475569" fontSize="9">HTTP REST</text>
        <text x="370" y="138" textAnchor="middle" fill="#475569" fontSize="9">HTTP REST</text>
      </svg>
    </div>
  );
}

// ─── Benchmark Chart (SVG Bar Chart) ───
function BenchmarkChart({ data }) {
  if (!data || !data.snapshot_sizes) {
    return <div style={{ textAlign: 'center', padding: 30, color: '#475569', fontSize: 13 }}>Chưa có dữ liệu benchmark. Chạy: python main.py --benchmark</div>;
  }

  const { snapshot_sizes, delta_sizes, cumulative_snapshot, cumulative_delta, savings_percent, num_versions } = data;
  const maxVal = Math.max(...cumulative_snapshot);
  const barW = 18;
  const gap = 6;
  const totalW = num_versions * (barW * 2 + gap) + 100;
  const h = 200;
  const chartH = 150;
  const padL = 55;

  const bars = [];
  for (let i = 0; i < num_versions; i++) {
    const x = padL + i * (barW * 2 + gap);
    const snapH = maxVal > 0 ? (cumulative_snapshot[i] / maxVal) * chartH : 0;
    const deltaH = maxVal > 0 ? (cumulative_delta[i] / maxVal) * chartH : 0;
    bars.push(
      <g key={i}>
        <rect x={x} y={chartH - snapH + 20} width={barW} height={snapH} rx="2" fill="#64748b" opacity="0.7" />
        <rect x={x + barW} y={chartH - deltaH + 20} width={barW} height={deltaH} rx="2" fill="#3b82f6" />
        {i % 2 === 0 && <text x={x + barW} y={chartH + 36} textAnchor="middle" fill="#475569" fontSize="10">v{i + 1}</text>}
      </g>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg width={totalW} height={h} viewBox={`0 0 ${totalW} ${h}`} style={{ minWidth: '100%' }}>
        {/* Legend */}
        <rect x={padL} y="4" width="10" height="10" rx="2" fill="#64748b" opacity="0.7" />
        <text x={padL + 15} y="13" fill="#94a3b8" fontSize="10">Full Snapshot</text>
        <rect x={padL + 100} y="4" width="10" height="10" rx="2" fill="#3b82f6" />
        <text x={padL + 115} y="13" fill="#94a3b8" fontSize="10">Delta Storage</text>
        {bars}
      </svg>
    </div>
  );
}

// ─── Per-Version Table ───
function VersionTable({ data }) {
  if (!data || !data.snapshot_sizes) return null;
  const { snapshot_sizes, delta_sizes, rehydration_costs } = data;
  return (
    <div className="scroll-panel" style={{ maxHeight: 260 }}>
      <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(255,255,255,.07)' }}>
            {['Version', 'Snapshot (B)', 'Delta (B)', 'Tiết kiệm', 'Rehydration'].map(h => (
              <th key={h} style={{ textAlign: 'left', padding: '7px 12px', color: '#64748b', fontWeight: 500, fontSize: 11 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {snapshot_sizes.map((snap, i) => {
            const delta = delta_sizes[i];
            const saving = snap > 0 ? ((snap - delta) / snap * 100).toFixed(1) : '0.0';
            return (
              <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,.04)' }}>
                <td style={{ padding: '7px 12px', fontWeight: 600, color: '#60a5fa' }}>v{i + 1}</td>
                <td style={{ padding: '7px 12px', color: '#94a3b8', fontFamily: 'monospace' }}>{snap}</td>
                <td style={{ padding: '7px 12px', color: '#3b82f6', fontFamily: 'monospace', fontWeight: 500 }}>{delta}</td>
                <td style={{ padding: '7px 12px', color: parseFloat(saving) > 50 ? '#34d399' : '#fbbf24', fontWeight: 600 }}>
                  {saving}%
                </td>
                <td style={{ padding: '7px 12px', color: '#64748b' }}>{rehydration_costs[i]} deltas</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Dataset Schema Display ───
function DatasetSchema({ schema }) {
  if (!schema) return null;
  const isGeoObj = typeof schema.geometry === 'object' && schema.geometry !== null;

  return (
    <div style={{ fontSize: 12, lineHeight: 1.8 }}>
      <div style={{ marginBottom: 6 }}>
        <span style={{ color: '#60a5fa', fontWeight: 600 }}>part_id</span>
        <span style={{ color: '#64748b' }}> — {schema.part_id}</span>
      </div>
      <div style={{ marginBottom: 6 }}>
        <span style={{ color: '#60a5fa', fontWeight: 600 }}>geometry</span>
        <span style={{ color: '#64748b' }}> — {isGeoObj ? 'object:' : String(schema.geometry)}</span>
        {isGeoObj && (
          <div style={{ paddingLeft: 20, marginTop: 4 }}>
            <div><span style={{ color: '#a78bfa' }}>↳ vertices</span><span style={{ color: '#64748b' }}> — {schema.geometry.vertices}</span></div>
            <div><span style={{ color: '#a78bfa' }}>↳ edges</span><span style={{ color: '#64748b' }}> — {schema.geometry.edges}</span></div>
            <div><span style={{ color: '#a78bfa' }}>↳ faces</span><span style={{ color: '#64748b' }}> — {schema.geometry.faces}</span></div>
            <div><span style={{ color: '#a78bfa' }}>↳ properties</span><span style={{ color: '#64748b' }}> — object:</span>
              <div style={{ paddingLeft: 16 }}>
                {schema.geometry.properties && Object.entries(schema.geometry.properties).map(([k, v]) => (
                  <div key={k}><span style={{ color: '#fbbf24' }}>· {k}</span><span style={{ color: '#64748b' }}> — {v}</span></div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
      <div style={{ marginBottom: 6 }}>
        <span style={{ color: '#60a5fa', fontWeight: 600 }}>version</span>
        <span style={{ color: '#64748b' }}> — {schema.version}</span>
      </div>
      <div style={{ marginBottom: 6 }}>
        <span style={{ color: '#60a5fa', fontWeight: 600 }}>branch</span>
        <span style={{ color: '#64748b' }}> — {schema.branch || "string"}</span>
      </div>
      <div style={{ marginBottom: 6 }}>
        <span style={{ color: '#60a5fa', fontWeight: 600 }}>oid</span>
        <span style={{ color: '#64748b' }}> — {schema.oid}</span>
      </div>
    </div>
  );
}

// ─── MAIN COMPONENT ───
export default function TabOverview({ sites }) {
  const [benchmark, setBenchmark] = useState(null);
  const [datasetInfo, setDatasetInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [runningBench, setRunningBench] = useState(false);

  async function loadAll() {
    setLoading(true);
    try {
      const bm = await getBenchmark('a').catch(() => null);
      if (!bm?.error) setBenchmark(bm);
    } catch { }

    try {
      const ds = await getDatasetInfo('a').catch(() => null);
      if (!ds?.error) setDatasetInfo(ds);
    } catch { }

    setLoading(false);
  }

  useEffect(() => { loadAll(); }, []);

  async function handleRunBenchmark() {
    setRunningBench(true);
    try {
      const res = await runBenchmark('a');
      if (res && !res.error) setBenchmark(res);
    } catch { }
    finally { setRunningBench(false); }
  }

  const totalParts = Object.values(sites).reduce((s, x) => s + (x.models?.length || 0), 0);
  const totalSnap = Object.values(sites).reduce((s, x) => s + (x.storage?.snapshot_total_bytes || 0), 0);
  const totalDelta = Object.values(sites).reduce((s, x) => s + (x.storage?.delta_total_bytes || 0), 0);
  const totalSaving = totalSnap > 0 ? ((totalSnap - totalDelta) / totalSnap * 100).toFixed(1) : '0.0';

  return (
    <div className="space-y-6 fade-in">
      {/* ── HEADER ── */}
      <div className="card" style={{ background: 'linear-gradient(135deg, rgba(59,130,246,.08), rgba(139,92,246,.06))', border: '1px solid rgba(59,130,246,.15)' }}>
        <div className="flex items-start gap-4">
          <div style={{ background: 'linear-gradient(135deg,#1d4ed8,#7c3aed)', borderRadius: 12, padding: 14, flexShrink: 0 }}>
            <Database size={28} className="text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold" style={{ color: '#e2e8f0' }}>Distributed CAD Versioning System</h2>
            <p className="text-sm mt-1" style={{ color: '#94a3b8' }}>
              Topic 88: Versioning Distributed Objects — "Collaborative Design"
            </p>
            <p className="text-xs mt-2" style={{ color: '#475569' }}>
              Dựa trên lý thuyết <strong style={{ color: '#60a5fa' }}>Özsu & Valduriez</strong> — Principles of Distributed Database Systems, 4th Edition, Chapter 15
            </p>
          </div>
        </div>
      </div>

      {/* ── ROW 1: Dataset + Architecture ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Dataset Specification */}
        <div className="card" style={{ borderTop: '3px solid #3b82f6' }}>
          <h3 className="font-semibold text-sm mb-4 flex items-center gap-2">
            <Database size={15} style={{ color: '#60a5fa' }} />
            Dataset Specification
          </h3>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 30, color: '#475569' }}>Đang tải dữ liệu...</div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {[
                  { label: 'Tổng Parts', value: totalParts || (datasetInfo?.total_parts || 0), color: '#60a5fa' },
                  { label: 'DB Size', value: datasetInfo?.storage_size_bytes ? `${(datasetInfo.storage_size_bytes / 1024).toFixed(1)} KB` : '—', color: '#a78bfa' },
                  { label: 'Nguồn', value: 'generate_dataset.py', color: '#34d399' },
                  { label: 'Loại', value: 'CAD_Model Objects', color: '#fbbf24' },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{ background: 'rgba(255,255,255,.02)', borderRadius: 8, padding: '8px 10px' }}>
                    <div className="text-xs" style={{ color: '#64748b' }}>{label}</div>
                    <div className="text-sm font-bold" style={{ color }}>{value}</div>
                  </div>
                ))}
              </div>
              <div style={{ marginBottom: 12 }}>
                <div className="text-xs font-semibold mb-2" style={{ color: '#94a3b8' }}>Schema — CAD_Model</div>
                <DatasetSchema schema={datasetInfo?.schema} />
              </div>
              {datasetInfo?.fragmentation && (
                <div>
                  <div className="text-xs font-semibold mb-2" style={{ color: '#94a3b8' }}>Phân mảnh Ngang (Horizontal)</div>
                  <div className="flex gap-2 flex-wrap">
                    {Array.isArray(datasetInfo.fragmentation.fragments)
                      ? datasetInfo.fragmentation.fragments.map(f => (
                        <span key={f.site} className="badge badge-blue">{f.site}: {f.predicate}</span>
                      ))
                      : (
                        <span className="badge badge-blue">
                          {datasetInfo.fragmentation.type || 'horizontal'}: {datasetInfo.fragmentation.predicate || 'category'}
                        </span>
                      )
                    }
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* System Architecture */}
        <div className="card" style={{ borderTop: '3px solid #8b5cf6' }}>
          <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
            <Network size={15} style={{ color: '#a78bfa' }} />
            System Architecture
          </h3>
          <ArchitectureDiagram />
          <div className="grid grid-cols-2 gap-2 mt-2">
            {[
              { label: 'Sites', value: '3 (HN, SG, ĐN)', Icon: Server, color: '#60a5fa' },
              { label: 'Protocol', value: 'HTTP REST API', Icon: Activity, color: '#34d399' },
              { label: 'Storage', value: 'SQLite per site', Icon: HardDrive, color: '#fbbf24' },
              { label: 'Coordinator', value: 'Metadata + Version Graph', Icon: GitBranch, color: '#a78bfa' },
            ].map(({ label, value, Icon, color }) => (
              <div key={label} style={{ background: 'rgba(255,255,255,.02)', borderRadius: 8, padding: '8px 10px', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Icon size={14} style={{ color, flexShrink: 0 }} />
                <div>
                  <div className="text-xs" style={{ color: '#64748b' }}>{label}</div>
                  <div className="text-xs font-semibold" style={{ color }}>{value}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── ROW 2: Benchmark Charts ── */}
      <div className="card" style={{ borderTop: '3px solid #10b981' }}>
        <h3 className="font-semibold text-sm mb-4 flex items-center gap-2">
          <TrendingDown size={15} style={{ color: '#34d399' }} />
          Success Metrics — Full Snapshot vs Delta Storage (10 Versions)
        </h3>

        {benchmark ? (
          <>
            {/* Summary KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
              {[
                { label: 'Tổng Snapshot', value: `${((benchmark.total_snapshot || 0) / 1024).toFixed(1)} KB`, color: '#64748b', Icon: HardDrive },
                { label: 'Tổng Delta', value: `${((benchmark.total_delta || 0) / 1024).toFixed(1)} KB`, color: '#3b82f6', Icon: TrendingDown },
                { label: 'Tiết kiệm', value: `${(benchmark.savings_percent || 0).toFixed(1)}%`, color: '#34d399', Icon: Activity },
                { label: 'Toàn vẹn', value: benchmark.integrity_ok ? '✅ PASS' : '❌ FAIL', color: benchmark.integrity_ok ? '#34d399' : '#f87171', Icon: Layers },
              ].map(({ label, value, color, Icon }) => (
                <div key={label} className="card flex items-center gap-3" style={{ padding: 14 }}>
                  <div style={{ background: `${color}1a`, borderRadius: 9, padding: 9 }}>
                    <Icon size={18} style={{ color }} />
                  </div>
                  <div>
                    <div className="text-lg font-bold" style={{ color }}>{value}</div>
                    <div className="text-xs" style={{ color: '#64748b' }}>{label}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Cumulative Chart */}
            <div className="mb-5">
              <div className="text-xs font-semibold mb-2" style={{ color: '#94a3b8' }}>Dung lượng tích lũy qua 10 phiên bản</div>
              <BenchmarkChart data={benchmark} />
            </div>

            {/* Per-version Table */}
            <div>
              <div className="text-xs font-semibold mb-2" style={{ color: '#94a3b8' }}>Chi tiết từng phiên bản</div>
              <VersionTable data={benchmark} />
            </div>

            {/* Theory Box */}
            <div className="card mt-4" style={{ background: 'rgba(59,130,246,.06)', border: '1px solid rgba(59,130,246,.15)' }}>
              <h4 className="font-semibold text-sm mb-3 flex items-center gap-2" style={{ color: '#60a5fa' }}>
                <BookOpen size={14} />
                Özsu & Valduriez — Ch.15 §15.6: Object Management
              </h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="font-medium mb-1" style={{ color: '#94a3b8' }}>Full Snapshot Storage</div>
                  <ul style={{ color: '#64748b', fontSize: 12, lineHeight: 1.8, listStyle: 'disc', paddingLeft: 16 }}>
                    <li>Lưu toàn bộ object mỗi version</li>
                    <li>Read: O(1) — truy xuất trực tiếp bất kỳ version</li>
                    <li>Write: O(1) — insert thẳng object mới vào DB (rất nhanh)</li>
                    <li>Dung lượng: O(n × size) — tăng tuyến tính</li>
                  </ul>
                </div>
                <div>
                  <div className="font-medium mb-1" style={{ color: '#94a3b8' }}>Delta Storage (Incremental)</div>
                  <ul style={{ color: '#64748b', fontSize: 12, lineHeight: 1.8, listStyle: 'disc', paddingLeft: 16 }}>
                    <li>Lưu base v1 + các diff giữa versions</li>
                    <li>Object Rehydration: apply k deltas tuần tự</li>
                    <li>Tiết kiệm ~60-85% dung lượng thực tế</li>
                    <li>Trade-off: read chậm (O(k)), write chậm (phải tính diff), bù lại tiết kiệm I/O</li>
                  </ul>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: 30, color: '#475569', fontSize: 13 }}>
            {loading ? 'Đang tải dữ liệu benchmark...' : (
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center' }}>
                <span>Chưa có dữ liệu benchmark.</span>
                <button onClick={handleRunBenchmark} disabled={runningBench}
                  style={{ background: '#185FA5', color: '#fff', border: 'none', borderRadius: 7, padding: '6px 16px', fontSize: 13, cursor: 'pointer' }}>
                  {runningBench ? '⏳ Đang chạy...' : '▶ Chạy Benchmark ngay'}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
