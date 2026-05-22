import { useState, useEffect } from 'react';
import { Database, Layers, TrendingDown, Cpu, Server, GitBranch, Network, HardDrive, Activity, BookOpen, Zap, Clock } from 'lucide-react';
import { SITES, getBenchmark, getDatasetInfo, getRehydrationBenchmark, runBenchmark, getSerializationAnalysis } from '../api';

// ─── Architecture Diagram (SVG) ───
function ArchitectureDiagram() {
  return (
    <div style={{ display:'flex', justifyContent:'center', padding:'20px 0' }}>
      <svg width="520" height="320" viewBox="0 0 520 320" style={{ maxWidth:'100%' }}>
        {/* Client */}
        <rect x="190" y="8" width="140" height="40" rx="10" fill="rgba(59,130,246,.12)" stroke="rgba(59,130,246,.3)" strokeWidth="1.5"/>
        <text x="260" y="32" textAnchor="middle" fill="#60a5fa" fontSize="13" fontWeight="600">🖥️ React Dashboard</text>

        {/* Coordinator */}
        <rect x="190" y="80" width="140" height="34" rx="10" fill="rgba(245,158,11,.1)" stroke="rgba(245,158,11,.3)" strokeWidth="1.5"/>
        <text x="260" y="101" textAnchor="middle" fill="#fbbf24" fontSize="12" fontWeight="600">🔄 Coordinator Metadata</text>

        {/* Lines: Client → Coordinator */}
        <line x1="260" y1="48" x2="260" y2="80" stroke="rgba(148,163,184,.3)" strokeWidth="1.5" strokeDasharray="4,3"/>

        {/* 3 Sites */}
        <rect x="20" y="160" width="140" height="130" rx="12" fill="rgba(59,130,246,.06)" stroke="rgba(59,130,246,.25)" strokeWidth="1.5"/>
        <text x="90" y="186" textAnchor="middle" fill="#3b82f6" fontSize="13" fontWeight="700">Site-A (HN)</text>
        <text x="90" y="205" textAnchor="middle" fill="#64748b" fontSize="10">Port :5001</text>
        <text x="90" y="222" textAnchor="middle" fill="#60a5fa" fontSize="10">Engine Parts</text>
        <text x="90" y="240" textAnchor="middle" fill="#a78bfa" fontSize="10">Branching</text>
        <rect x="35" y="254" width="110" height="22" rx="5" fill="rgba(59,130,246,.1)" stroke="rgba(59,130,246,.2)" strokeWidth="1"/>
        <text x="90" y="269" textAnchor="middle" fill="#94a3b8" fontSize="9">SQLite Site-A.db</text>

        <rect x="190" y="160" width="140" height="130" rx="12" fill="rgba(139,92,246,.06)" stroke="rgba(139,92,246,.25)" strokeWidth="1.5"/>
        <text x="260" y="186" textAnchor="middle" fill="#8b5cf6" fontSize="13" fontWeight="700">Site-B (SG)</text>
        <text x="260" y="205" textAnchor="middle" fill="#64748b" fontSize="10">Port :5002</text>
        <text x="260" y="222" textAnchor="middle" fill="#a78bfa" fontSize="10">Chassis Parts</text>
        <text x="260" y="240" textAnchor="middle" fill="#a78bfa" fontSize="10">Branching</text>
        <rect x="205" y="254" width="110" height="22" rx="5" fill="rgba(139,92,246,.1)" stroke="rgba(139,92,246,.2)" strokeWidth="1"/>
        <text x="260" y="269" textAnchor="middle" fill="#94a3b8" fontSize="9">SQLite Site-B.db</text>

        <rect x="360" y="160" width="140" height="130" rx="12" fill="rgba(16,185,129,.06)" stroke="rgba(16,185,129,.25)" strokeWidth="1.5"/>
        <text x="430" y="186" textAnchor="middle" fill="#10b981" fontSize="13" fontWeight="700">Site-C (ĐN)</text>
        <text x="430" y="205" textAnchor="middle" fill="#64748b" fontSize="10">Port :5003</text>
        <text x="430" y="222" textAnchor="middle" fill="#34d399" fontSize="10">Interior Parts</text>
        <text x="430" y="240" textAnchor="middle" fill="#a78bfa" fontSize="10">Branching</text>
        <rect x="375" y="254" width="110" height="22" rx="5" fill="rgba(16,185,129,.1)" stroke="rgba(16,185,129,.2)" strokeWidth="1"/>
        <text x="430" y="269" textAnchor="middle" fill="#94a3b8" fontSize="9">SQLite Site-C.db</text>

        {/* Lines: Coordinator → Sites */}
        <line x1="232" y1="114" x2="90" y2="160" stroke="rgba(148,163,184,.25)" strokeWidth="1.2"/>
        <line x1="260" y1="114" x2="260" y2="160" stroke="rgba(148,163,184,.25)" strokeWidth="1.2"/>
        <line x1="288" y1="114" x2="430" y2="160" stroke="rgba(148,163,184,.25)" strokeWidth="1.2"/>

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
    return <div style={{ textAlign:'center', padding:30, color:'#475569', fontSize:13 }}>Chưa có dữ liệu benchmark. Chạy: python main.py --benchmark</div>;
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
        <rect x={x} y={chartH - snapH + 20} width={barW} height={snapH} rx="2" fill="#64748b" opacity="0.7"/>
        <rect x={x + barW} y={chartH - deltaH + 20} width={barW} height={deltaH} rx="2" fill="#3b82f6"/>
        {i % 2 === 0 && <text x={x + barW} y={chartH + 36} textAnchor="middle" fill="#475569" fontSize="10">v{i+1}</text>}
      </g>
    );
  }

  return (
    <div style={{ overflowX:'auto' }}>
      <svg width={totalW} height={h} viewBox={`0 0 ${totalW} ${h}`} style={{ minWidth:'100%' }}>
        {/* Legend */}
        <rect x={padL} y="4" width="10" height="10" rx="2" fill="#64748b" opacity="0.7"/>
        <text x={padL + 15} y="13" fill="#94a3b8" fontSize="10">Full Snapshot</text>
        <rect x={padL + 100} y="4" width="10" height="10" rx="2" fill="#3b82f6"/>
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
    <div className="scroll-panel" style={{ maxHeight:260 }}>
      <table style={{ width:'100%', fontSize:12, borderCollapse:'collapse' }}>
        <thead>
          <tr style={{ borderBottom:'1px solid rgba(255,255,255,.07)' }}>
            {['Version','Snapshot (B)','Delta (B)','Tiết kiệm','Rehydration'].map(h => (
              <th key={h} style={{ textAlign:'left', padding:'7px 12px', color:'#64748b', fontWeight:500, fontSize:11 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {snapshot_sizes.map((snap, i) => {
            const delta = delta_sizes[i];
            const saving = snap > 0 ? ((snap - delta) / snap * 100).toFixed(1) : '0.0';
            return (
              <tr key={i} style={{ borderBottom:'1px solid rgba(255,255,255,.04)' }}>
                <td style={{ padding:'7px 12px', fontWeight:600, color:'#60a5fa' }}>v{i+1}</td>
                <td style={{ padding:'7px 12px', color:'#94a3b8', fontFamily:'monospace' }}>{snap}</td>
                <td style={{ padding:'7px 12px', color:'#3b82f6', fontFamily:'monospace', fontWeight:500 }}>{delta}</td>
                <td style={{ padding:'7px 12px', color: parseFloat(saving) > 50 ? '#34d399' : '#fbbf24', fontWeight:600 }}>
                  {saving}%
                </td>
                <td style={{ padding:'7px 12px', color:'#64748b' }}>{rehydration_costs[i]} deltas</td>
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
    <div style={{ fontSize:12, lineHeight:1.8 }}>
      <div style={{ marginBottom:6 }}>
        <span style={{ color:'#60a5fa', fontWeight:600 }}>part_id</span>
        <span style={{ color:'#64748b' }}> — {schema.part_id}</span>
      </div>
      <div style={{ marginBottom:6 }}>
        <span style={{ color:'#60a5fa', fontWeight:600 }}>geometry</span>
        <span style={{ color:'#64748b' }}> — {isGeoObj ? 'object:' : String(schema.geometry)}</span>
        {isGeoObj && (
          <div style={{ paddingLeft:20, marginTop:4 }}>
            <div><span style={{ color:'#a78bfa' }}>↳ vertices</span><span style={{ color:'#64748b' }}> — {schema.geometry.vertices}</span></div>
            <div><span style={{ color:'#a78bfa' }}>↳ edges</span><span style={{ color:'#64748b' }}> — {schema.geometry.edges}</span></div>
            <div><span style={{ color:'#a78bfa' }}>↳ faces</span><span style={{ color:'#64748b' }}> — {schema.geometry.faces}</span></div>
            <div><span style={{ color:'#a78bfa' }}>↳ properties</span><span style={{ color:'#64748b' }}> — object:</span>
              <div style={{ paddingLeft:16 }}>
                {schema.geometry.properties && Object.entries(schema.geometry.properties).map(([k,v]) => (
                  <div key={k}><span style={{ color:'#fbbf24' }}>· {k}</span><span style={{ color:'#64748b' }}> — {v}</span></div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
      <div style={{ marginBottom:6 }}>
        <span style={{ color:'#60a5fa', fontWeight:600 }}>version</span>
        <span style={{ color:'#64748b' }}> — {schema.version}</span>
      </div>
      <div style={{ marginBottom:6 }}>
        <span style={{ color:'#60a5fa', fontWeight:600 }}>branch</span>
        <span style={{ color:'#64748b' }}> — {schema.branch || "string"}</span>
      </div>
      <div style={{ marginBottom:6 }}>
        <span style={{ color:'#60a5fa', fontWeight:600 }}>oid</span>
        <span style={{ color:'#64748b' }}> — {schema.oid}</span>
      </div>
    </div>
  );
}

// ─── MAIN COMPONENT ───
export default function TabOverview({ sites }) {
  const [benchmark,         setBenchmark]         = useState(null);
  const [datasetInfo,       setDatasetInfo]       = useState(null);
  const [rehydration,       setRehydration]       = useState(null);
  const [serializationData, setSerializationData] = useState(null);
  const [loading,      setLoading]      = useState(true);
  const [runningBench, setRunningBench] = useState(false);

  async function loadAll() {
    setLoading(true);
    try {
      const bm = await getBenchmark('a').catch(() => null);
      if (!bm?.error) setBenchmark(bm);
    } catch {}

    try {
      const ds = await getDatasetInfo('a').catch(() => null);
      if (!ds?.error) setDatasetInfo(ds);
    } catch {}

    try {
      const rh = await getRehydrationBenchmark('a').catch(() => null);
      if (rh && !rh.error) setRehydration(rh);
    } catch {}

    try {
      const sr = await getSerializationAnalysis('a').catch(() => null);
      if (sr && !sr.error) setSerializationData(sr);
    } catch {}

    setLoading(false);
  }

  useEffect(() => { loadAll(); }, []);

  async function handleRunBenchmark() {
    setRunningBench(true);
    try {
      const res = await runBenchmark('a');
      if (res && !res.error) setBenchmark(res);
    } catch {}
    finally { setRunningBench(false); }
  }

  const totalParts = Object.values(sites).reduce((s, x) => s + (x.models?.length || 0), 0);
  const totalSnap = Object.values(sites).reduce((s, x) => s + (x.storage?.snapshot_total_bytes || 0), 0);
  const totalDelta = Object.values(sites).reduce((s, x) => s + (x.storage?.delta_total_bytes || 0), 0);
  const totalSaving = totalSnap > 0 ? ((totalSnap - totalDelta) / totalSnap * 100).toFixed(1) : '0.0';

  return (
    <div className="space-y-6 fade-in">
      {/* ── HEADER ── */}
      <div className="card" style={{ background:'linear-gradient(135deg, rgba(59,130,246,.08), rgba(139,92,246,.06))', border:'1px solid rgba(59,130,246,.15)' }}>
        <div className="flex items-start gap-4">
          <div style={{ background:'linear-gradient(135deg,#1d4ed8,#7c3aed)', borderRadius:12, padding:14, flexShrink:0 }}>
            <Database size={28} className="text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold" style={{ color:'#e2e8f0' }}>Distributed CAD Versioning System</h2>
            <p className="text-sm mt-1" style={{ color:'#94a3b8' }}>
              Topic 88: Versioning Distributed Objects — "Collaborative Design"
            </p>
            <p className="text-xs mt-2" style={{ color:'#475569' }}>
              Dựa trên lý thuyết <strong style={{ color:'#60a5fa' }}>Özsu & Valduriez</strong> — Principles of Distributed Database Systems, 4th Edition, Chapter 15
            </p>
          </div>
        </div>
      </div>

      {/* ── ROW 1: Dataset + Architecture ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Dataset Specification */}
        <div className="card" style={{ borderTop:'3px solid #3b82f6' }}>
          <h3 className="font-semibold text-sm mb-4 flex items-center gap-2">
            <Database size={15} style={{ color:'#60a5fa' }} />
            Dataset Specification
          </h3>
          {loading ? (
            <div style={{ textAlign:'center', padding:30, color:'#475569' }}>Đang tải dữ liệu...</div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {[
                  { label:'Tổng Parts', value: totalParts || (datasetInfo?.total_parts || 0), color:'#60a5fa' },
                  { label:'DB Size', value: datasetInfo?.storage_size_bytes ? `${(datasetInfo.storage_size_bytes/1024).toFixed(1)} KB` : '—', color:'#a78bfa' },
                  { label:'Nguồn', value:'generate_dataset.py', color:'#34d399' },
                  { label:'Loại', value:'CAD_Model Objects', color:'#fbbf24' },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{ background:'rgba(255,255,255,.02)', borderRadius:8, padding:'8px 10px' }}>
                    <div className="text-xs" style={{ color:'#64748b' }}>{label}</div>
                    <div className="text-sm font-bold" style={{ color }}>{value}</div>
                  </div>
                ))}
              </div>
              <div style={{ marginBottom:12 }}>
                <div className="text-xs font-semibold mb-2" style={{ color:'#94a3b8' }}>Schema — CAD_Model</div>
                <DatasetSchema schema={datasetInfo?.schema} />
              </div>
              {datasetInfo?.fragmentation && (
                <div>
                  <div className="text-xs font-semibold mb-2" style={{ color:'#94a3b8' }}>Phân mảnh Ngang (Horizontal)</div>
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
        <div className="card" style={{ borderTop:'3px solid #8b5cf6' }}>
          <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
            <Network size={15} style={{ color:'#a78bfa' }} />
            System Architecture
          </h3>
          <ArchitectureDiagram />
          <div className="grid grid-cols-2 gap-2 mt-2">
            {[
              { label:'Sites', value:'3 (HN, SG, ĐN)', Icon: Server, color:'#60a5fa' },
              { label:'Protocol', value:'HTTP REST API', Icon: Activity, color:'#34d399' },
              { label:'Storage', value:'SQLite per site', Icon: HardDrive, color:'#fbbf24' },
              { label:'Coordinator', value:'Metadata + Version Graph', Icon: GitBranch, color:'#a78bfa' },
            ].map(({ label, value, Icon, color }) => (
              <div key={label} style={{ background:'rgba(255,255,255,.02)', borderRadius:8, padding:'8px 10px', display:'flex', alignItems:'center', gap:8 }}>
                <Icon size={14} style={{ color, flexShrink:0 }} />
                <div>
                  <div className="text-xs" style={{ color:'#64748b' }}>{label}</div>
                  <div className="text-xs font-semibold" style={{ color }}>{value}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── ROW 2: Benchmark Charts ── */}
      <div className="card" style={{ borderTop:'3px solid #10b981' }}>
        <h3 className="font-semibold text-sm mb-4 flex items-center gap-2">
          <TrendingDown size={15} style={{ color:'#34d399' }} />
          Success Metrics — Full Snapshot vs Delta Storage (10 Versions)
        </h3>

        {benchmark ? (
          <>
            {/* Summary KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
              {[
                { label:'Tổng Snapshot', value:`${((benchmark.total_snapshot||0)/1024).toFixed(1)} KB`, color:'#64748b', Icon: HardDrive },
                { label:'Tổng Delta', value:`${((benchmark.total_delta||0)/1024).toFixed(1)} KB`, color:'#3b82f6', Icon: TrendingDown },
                { label:'Tiết kiệm', value:`${(benchmark.savings_percent||0).toFixed(1)}%`, color:'#34d399', Icon: Activity },
                { label:'Toàn vẹn', value: benchmark.integrity_ok ? '✅ PASS' : '❌ FAIL', color: benchmark.integrity_ok ? '#34d399' : '#f87171', Icon: Layers },
              ].map(({ label, value, color, Icon }) => (
                <div key={label} className="card flex items-center gap-3" style={{ padding:14 }}>
                  <div style={{ background:`${color}1a`, borderRadius:9, padding:9 }}>
                    <Icon size={18} style={{ color }} />
                  </div>
                  <div>
                    <div className="text-lg font-bold" style={{ color }}>{value}</div>
                    <div className="text-xs" style={{ color:'#64748b' }}>{label}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Cumulative Chart */}
            <div className="mb-5">
              <div className="text-xs font-semibold mb-2" style={{ color:'#94a3b8' }}>Dung lượng tích lũy qua 10 phiên bản</div>
              <BenchmarkChart data={benchmark} />
            </div>

            {/* Per-version Table */}
            <div>
              <div className="text-xs font-semibold mb-2" style={{ color:'#94a3b8' }}>Chi tiết từng phiên bản</div>
              <VersionTable data={benchmark} />
            </div>

            {/* Theory Box */}
            <div className="card mt-4" style={{ background:'rgba(59,130,246,.06)', border:'1px solid rgba(59,130,246,.15)' }}>
              <h4 className="font-semibold text-sm mb-3 flex items-center gap-2" style={{ color:'#60a5fa' }}>
                <BookOpen size={14} />
                Özsu & Valduriez — Ch.15 §15.6: Object Management
              </h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="font-medium mb-1" style={{ color:'#94a3b8' }}>Full Snapshot Storage</div>
                  <ul style={{ color:'#64748b', fontSize:12, lineHeight:1.8, listStyle:'disc', paddingLeft:16 }}>
                    <li>Lưu toàn bộ object mỗi version</li>
                    <li>Read: O(1) — truy xuất trực tiếp bất kỳ version</li>
                    <li>Write: O(1) — insert thẳng object mới vào DB (rất nhanh)</li>
                    <li>Dung lượng: O(n × size) — tăng tuyến tính</li>
                  </ul>
                </div>
                <div>
                  <div className="font-medium mb-1" style={{ color:'#94a3b8' }}>Delta Storage (Incremental)</div>
                  <ul style={{ color:'#64748b', fontSize:12, lineHeight:1.8, listStyle:'disc', paddingLeft:16 }}>
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
          <div style={{ textAlign:'center', padding:30, color:'#475569', fontSize:13 }}>
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

      {/* ══ SECTION: NETWORK AWARENESS — Rehydration Cost ══ */}
      <div className="card" style={{ border: '1px solid rgba(59,130,246,.2)', background: 'rgba(59,130,246,.03)' }}>
        <h3 className="font-semibold mb-1 flex items-center gap-2 text-sm" style={{ color: '#60a5fa' }}>
          <Network size={16} />
          Network Awareness — Object Rehydration Cost (Özsu §15.6)
        </h3>
        <p style={{ fontSize: 12, color: '#475569', marginBottom: 16 }}>
          Đo toàn vòng đời: <strong>DB read → serialize → (network) → deserialize</strong>.
          Chứng minh trade-off O(1) Snapshot vs O(k) Delta chain.
        </p>

        {rehydration ? (
          <>
            {/* KPI summary */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 16 }}>
              {[
                { label: 'Snapshot avg latency', value: `${rehydration.avg_snapshot_ms} ms`, sub: 'O(1)', color: '#34d399' },
                { label: 'Delta avg latency',    value: `${rehydration.avg_delta_ms} ms`,    sub: `O(${rehydration.avg_rehydration_steps} deltas)`, color: '#f87171' },
                { label: 'Overhead per request', value: `+${rehydration.avg_overhead_ms} ms`, sub: 'Delta vs Snapshot', color: '#fbbf24' },
                { label: 'Payload tiết kiệm',   value: `${rehydration.avg_payload_savings}%`, sub: 'Delta vs Snapshot bytes', color: '#a78bfa' },
              ].map(({ label, value, sub, color }) => (
                <div key={label} style={{ background: 'rgba(255,255,255,.03)', borderRadius: 8, padding: '10px 14px', border: '0.5px solid rgba(255,255,255,.08)', textAlign: 'center' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color }}>{value}</div>
                  <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{label}</div>
                  <div style={{ fontSize: 10, color: '#475569' }}>{sub}</div>
                </div>
              ))}
            </div>

            {/* Detail table */}
            <div style={{ overflowX: 'auto', marginBottom: 12 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,.08)' }}>
                    {['Part ID','Ver','k','Snap DB(ms)','Snap Ser(ms)','Snap Total(ms)','Δ Compute(ms)','Δ Ser(ms)','Δ Total(ms)','Overhead','Payload saving'].map(h => (
                      <th key={h} style={{ padding:'6px 8px', textAlign:'right', color:'#475569', fontWeight:500, whiteSpace:'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(rehydration.measurements || []).slice(0, 15).map((m, i) => (
                    <tr key={i} style={{ borderBottom: '0.5px solid rgba(255,255,255,.04)' }}>
                      <td style={{ padding:'5px 8px', fontWeight:500, color:'#60a5fa', textAlign:'left', fontFamily:'monospace', fontSize:10 }}>{m.part_id}</td>
                      <td style={{ padding:'5px 8px', textAlign:'right', color:'#94a3b8' }}>v{m.version}</td>
                      <td style={{ padding:'5px 8px', textAlign:'right', color:'#fbbf24', fontWeight:600 }}>{m.rehydration_steps}</td>
                      <td style={{ padding:'5px 8px', textAlign:'right', color:'#34d399' }}>{m.snap_db_read_ms}</td>
                      <td style={{ padding:'5px 8px', textAlign:'right', color:'#34d399' }}>{m.snap_serialize_ms}</td>
                      <td style={{ padding:'5px 8px', textAlign:'right', color:'#34d399', fontWeight:600 }}>{m.snap_total_ms}</td>
                      <td style={{ padding:'5px 8px', textAlign:'right', color:'#f87171' }}>{m.delta_compute_ms}</td>
                      <td style={{ padding:'5px 8px', textAlign:'right', color:'#f87171' }}>{m.delta_serialize_ms}</td>
                      <td style={{ padding:'5px 8px', textAlign:'right', color:'#f87171', fontWeight:600 }}>{m.delta_total_ms}</td>
                      <td style={{ padding:'5px 8px', textAlign:'right', color: m.overhead_ms > 0 ? '#fbbf24' : '#34d399' }}>{m.overhead_ms > 0 ? '+' : ''}{m.overhead_ms}ms</td>
                      <td style={{ padding:'5px 8px', textAlign:'right', color:'#a78bfa', fontWeight:600 }}>{m.saving_percent}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Theory box */}
            <div style={{ background: 'rgba(59,130,246,.06)', borderRadius: 8, padding: '10px 14px', fontSize: 12 }}>
              <div style={{ fontWeight: 600, color: '#60a5fa', marginBottom: 6 }}>📐 Kết luận lý thuyết</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, color: '#64748b', lineHeight: 1.7 }}>
                <div>
                  <strong style={{ color: '#34d399' }}>Full Snapshot — O(1)</strong><br/>
                  • Direct DB lookup, không cần compute<br/>
                  • Payload lớn hơn ~5–10×<br/>
                  • Phù hợp read-heavy workloads
                </div>
                <div>
                  <strong style={{ color: '#f87171' }}>Delta Rehydration — O(k)</strong><br/>
                  • Apply k deltas tuần tự: v1 → v2 → … → vk<br/>
                  • Payload nhỏ hơn ~{rehydration.avg_payload_savings}%<br/>
                  • Trade-off: compute cost tăng tuyến tính theo k
                </div>
              </div>
              <div style={{ marginTop: 8, color: '#475569', fontSize: 11 }}>
                <strong>Ref:</strong> {rehydration.theory?.reference}
              </div>
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: 20, color: '#475569', fontSize: 13 }}>
            {loading ? '⏳ Đang đo rehydration cost...' : 'Chưa có dữ liệu — hãy thực hiện Checkout/Checkin ít nhất 1 lần để tạo delta chain.'}
          </div>
        )}
      </div>

      {/* ══ SECTION: SERIALIZATION ANALYSIS ══ */}
      <div className="card" style={{ border: '1px solid rgba(139,92,246,.2)', background: 'rgba(139,92,246,.03)' }}>
        <h3 className="font-semibold mb-1 flex items-center gap-2 text-sm" style={{ color: '#a78bfa' }}>
          <Zap size={16} />
          Serialization Analysis — JSON vs marshmallow vs pickle
        </h3>
        <p style={{ fontSize: 12, color: '#475569', marginBottom: 16 }}>
          Đề gợi ý dùng <strong>pickle</strong> hoặc <strong>marshmallow</strong>.
          Benchmark thực tế 50 vòng lặp trên object CAD thực — đo serialize/deserialize speed và payload size.
        </p>

        {serializationData ? (
          <>
            {/* Methods comparison table */}
            <div style={{ overflowX: 'auto', marginBottom: 16 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,.08)', background: 'rgba(255,255,255,.02)' }}>
                    {['Phương pháp','Serialize (ms)','Deserialize (ms)','Size (bytes)','vs JSON','Cross-lang','Readable','Schema validate','Safe (network)'].map(h => (
                      <th key={h} style={{ padding:'8px 10px', textAlign: h === 'Phương pháp' ? 'left' : 'right', color:'#64748b', fontWeight:500, fontSize:11 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(serializationData.methods || {}).map(([key, m]) => {
                    const rowColor = key === 'json' ? '#34d399' : key === 'marshmallow' ? '#60a5fa' : '#f87171';
                    const sizeSign = m.size_vs_json_pct > 0 ? '+' : '';
                    return (
                      <tr key={key} style={{ borderBottom: '0.5px solid rgba(255,255,255,.04)' }}>
                        <td style={{ padding:'8px 10px', fontWeight:600, color: rowColor }}>{m.method}</td>
                        <td style={{ padding:'8px 10px', textAlign:'right', fontFamily:'monospace' }}>{m.avg_serialize_ms}</td>
                        <td style={{ padding:'8px 10px', textAlign:'right', fontFamily:'monospace' }}>{m.avg_deserialize_ms}</td>
                        <td style={{ padding:'8px 10px', textAlign:'right', fontFamily:'monospace' }}>{m.avg_size_bytes?.toLocaleString()}</td>
                        <td style={{ padding:'8px 10px', textAlign:'right', color: m.size_vs_json_pct <= 0 ? '#34d399' : '#f87171' }}>
                          {sizeSign}{m.size_vs_json_pct}%
                        </td>
                        {['cross_language','human_readable','schema_validation','safe'].map(attr => (
                          <td key={attr} style={{ padding:'8px 10px', textAlign:'right' }}>
                            <span style={{ color: m[attr] ? '#34d399' : '#f87171', fontWeight:600 }}>{m[attr] ? '✓' : '✗'}</span>
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Decision panel */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div style={{ background: 'rgba(34,197,94,.06)', border: '1px solid rgba(34,197,94,.2)', borderRadius: 8, padding: '12px 16px' }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#34d399', marginBottom: 6 }}>
                  ✅ Quyết định: {serializationData.decision?.chosen}
                </div>
                <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.7 }}>
                  {serializationData.decision?.reason}
                </div>
                <div style={{ fontSize: 11, color: '#475569', marginTop: 8 }}>
                  <strong>Ref:</strong> {serializationData.decision?.reference}
                </div>
              </div>

              <div style={{ background: 'rgba(255,255,255,.02)', border: '0.5px solid rgba(255,255,255,.08)', borderRadius: 8, padding: '12px 16px' }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#a78bfa', marginBottom: 8 }}>📚 Trade-off Analysis</div>
                <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.8 }}>
                  <strong style={{ color: '#34d399' }}>JSON</strong> — Baseline, cross-language, HTTP-safe<br/>
                  <strong style={{ color: '#60a5fa' }}>marshmallow</strong> — Schema validation + type coercion, overhead nhỏ<br/>
                  <strong style={{ color: '#f87171' }}>pickle</strong> — Nhanh nhất nhưng <strong>Python-only</strong> + <strong>RCE risk</strong><br/>
                  <strong style={{ color: '#fbbf24' }}>jsondiff</strong> — Delta format: chỉ lưu diff → tiết kiệm 60–85%
                </div>
              </div>
            </div>

            <div style={{ marginTop: 10, fontSize: 11, color: '#475569' }}>
              Benchmark trên: <code style={{ fontFamily: 'monospace' }}>{serializationData.part_id}</code> — {serializationData.iterations} iterations mỗi method
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: 20, color: '#475569', fontSize: 13 }}>
            {loading ? '⏳ Đang chạy serialization benchmark...' : 'Chưa có dữ liệu — cần có ít nhất 1 part trong DB.'}
          </div>
        )}
      </div>

    </div>
  );
}
