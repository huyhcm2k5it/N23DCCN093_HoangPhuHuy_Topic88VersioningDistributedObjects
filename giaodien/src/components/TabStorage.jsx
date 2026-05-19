import { useState, useEffect } from 'react';
import { HardDrive, TrendingDown, Zap, SlidersHorizontal, ArrowRight, Layers, GitBranch } from 'lucide-react';
import { getBenchmark } from '../api';

// ─── Dữ liệu giả lập khi chưa có API ───
const FALLBACK_BENCHMARK = {
  num_versions: 10,
  snapshot_sizes: [
    3298, 3300, 3300, 3301, 3302, 3301, 3300, 3299, 3296, 3301
  ],
  delta_sizes: [
    3298, 1069, 1503, 1054, 831, 1618, 1510, 615, 496, 1277
  ],
  cumulative_snapshot: [
    3298, 6598, 9898, 13199, 16501, 19802, 23102, 26401, 29697, 32998
  ],
  cumulative_delta: [
    3298, 4367, 5870, 6924, 7755, 9373, 10883, 11498, 11994, 13271
  ],
  rehydration_costs: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  total_snapshot: 32998,
  total_delta: 13271,
  savings_bytes: 19727,
  savings_percent: 59.78,
  integrity_ok: true,
};

// ─── SVGBar Chart component ───
function BarChart({ data, versionCount }) {
  if (!data) return null;
  const { cumulative_snapshot: snap, cumulative_delta: delta } = data;
  const n = versionCount;
  const maxVal = Math.max(snap[n-1] || 1, delta[n-1] || 1);
  const chartH = 130;
  const barW = 14;
  const gap = 6;
  const padLeft = 40;
  const totalW = n * (barW * 2 + gap) + padLeft + 30;

  const bars = [];
  for (let i = 0; i < n; i++) {
    const x = padLeft + i * (barW * 2 + gap);
    const snapH = (snap[i] / maxVal) * chartH;
    const deltaH = (delta[i] / maxVal) * chartH;
    bars.push(
      <g key={i}>
        <rect x={x} y={chartH + 15 - snapH} width={barW} height={snapH} rx="2" fill="#475569" opacity="0.5"/>
        <rect x={x + barW} y={chartH + 15 - deltaH} width={barW} height={deltaH} rx="2" fill="#3b82f6"/>
        {n <= 10 && (
          <text x={x + barW} y={chartH + 32} textAnchor="middle" fill="#475569" fontSize="9">v{i+1}</text>
        )}
      </g>
    );
  }

  return (
    <div style={{ overflowX:'auto' }}>
      <svg width={totalW} height={chartH + 55} viewBox={`0 0 ${totalW} ${chartH + 55}`} style={{ minWidth:'100%' }}>
        <rect x={padLeft} y="4" width="10" height="10" rx="2" fill="#475569" opacity="0.5"/>
        <text x={padLeft + 15} y="13" fill="#64748b" fontSize="10">Full Snapshot</text>
        <rect x={padLeft + 100} y="4" width="10" height="10" rx="2" fill="#3b82f6"/>
        <text x={padLeft + 115} y="13" fill="#64748b" fontSize="10">Delta</text>
        {bars}
      </svg>
    </div>
  );
}

// ─── MAIN COMPONENT ───
export default function TabStorage({ sites }) {
  const [benchmark, setBenchmark] = useState(null);
  const [versionCount, setVersionCount] = useState(10); // slider

  useEffect(() => {
    let cancelled = false;
    getBenchmark('a').then(bm => {
      if (!cancelled && !bm?.error) setBenchmark(bm);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const data = benchmark || FALLBACK_BENCHMARK;
  const n = versionCount;
  const totalSnap = data.cumulative_snapshot[n-1] || 0;
  const totalDelta = data.cumulative_delta[n-1] || 0;
  const savings = totalSnap > 0 ? ((totalSnap - totalDelta) / totalSnap * 100).toFixed(1) : '0.0';
  const savingsBytes = totalSnap - totalDelta;

  return (
    <div className="space-y-5 fade-in">
      {/* ── HEADER BANNER ── */}
      <div className="card" style={{ background:'rgba(59,130,246,.04)', border:'1px solid rgba(59,130,246,.12)' }}>
        <div style={{ display:'flex', alignItems:'start', gap:8, fontSize:13, color:'#94a3b8' }}>
          <Layers size={16} style={{ color:'#3b82f6', flexShrink:0, marginTop:2 }} />
          <div>
            <strong style={{ color:'#e2e8f0' }}>Công thức:</strong><br />
            <code style={{ color:'#60a5fa' }}>
              Full Snapshot = {n} versions × ~3.3 KB = {(totalSnap/1024).toFixed(1)} KB
            </code><br />
            <code style={{ color:'#34d399' }}>
              Delta = 3.3 KB (base) + {n-1} × ~1.1 KB (diff) ≈ {(totalDelta/1024).toFixed(1)} KB
            </code><br />
            <span style={{ color:'#fbbf24', fontWeight:600 }}>
              → Tiết kiệm: {savings}% ({(savingsBytes/1024).toFixed(1)} KB)
            </span>
          </div>
        </div>
      </div>

      {/* ─── SLIDER ─── */}
      <div className="card">
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:12 }}>
          <h3 className="font-semibold text-sm flex items-center gap-2" style={{ color:'#e2e8f0' }}>
            <SlidersHorizontal size={15} style={{ color:'#3b82f6' }} />
            Kéo slider để thấy tác động qua từng phiên bản
          </h3>
          <span className="badge" style={{ background:'rgba(59,130,246,.1)', color:'#60a5fa', border:'1px solid rgba(59,130,246,.2)', fontSize:12 }}>
            Version: {versionCount}/10
          </span>
        </div>

        <input
          type="range"
          min="1" max="10" value={versionCount}
          onChange={e => setVersionCount(Number(e.target.value))}
          style={{
            width: '100%', height: 6, appearance: 'none',
            background: `linear-gradient(to right, #3b82f6 ${(versionCount-1)/9*100}%, rgba(255,255,255,.08) ${(versionCount-1)/9*100}%)`,
            borderRadius: 3, outline: 'none', cursor: 'pointer',
          }}
        />

        <div style={{ display:'flex', justifyContent:'space-between', marginTop:6, fontSize:10, color:'#475569' }}>
          <span>v1</span><span>v2</span><span>v3</span><span>v4</span><span>v5</span>
          <span>v6</span><span>v7</span><span>v8</span><span>v9</span><span>v10</span>
        </div>
      </div>

      {/* ─── KPI ROW ─── */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label:'Full Snapshot', value:`${(totalSnap/1024).toFixed(1)} KB`, color:'#475569', Icon: HardDrive },
          { label:'Delta Storage', value:`${(totalDelta/1024).toFixed(1)} KB`, color:'#3b82f6', Icon: Zap },
          { label:'Tiết kiệm', value:`${savings}%`, color: parseFloat(savings) > 30 ? '#34d399' : '#fbbf24', Icon: TrendingDown },
        ].map(({ label, value, color, Icon }) => (
          <div key={label} className="card flex items-center gap-3" style={{ padding:14 }}>
            <div style={{ background:`${color}1a`, borderRadius:9, padding:9 }}>
              <Icon size={18} style={{ color }} />
            </div>
            <div>
              <div className="text-xl font-bold" style={{ color }}>{value}</div>
              <div className="text-xs" style={{ color:'#475569' }}>{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ─── BAR CHART ─── */}
      <div className="card">
        <h4 className="text-xs font-semibold mb-3" style={{ color:'#94a3b8' }}>
          Dung lượng tích lũy — kéo slider để xem sự thay đổi
        </h4>
        <BarChart data={data} versionCount={versionCount} />
      </div>

      {/* ─── PER-VERSION TABLE ─── */}
      <div className="card">
        <h4 className="text-xs font-semibold mb-3 flex items-center gap-2" style={{ color:'#94a3b8' }}>
          <GitBranch size={13} style={{ color:'#a78bfa' }} />
          Chi tiết từng phiên bản (hiển thị {versionCount}/10)
        </h4>
        <div className="scroll-panel" style={{ maxHeight:280 }}>
          <table style={{ width:'100%', fontSize:12, borderCollapse:'collapse' }}>
            <thead>
              <tr style={{ borderBottom:'1px solid rgba(255,255,255,.06)' }}>
                {['Version','Snapshot','Delta','Tiết kiệm','Rehydration cost'].map(h => (
                  <th key={h} style={{ textAlign:'left', padding:'7px 12px', color:'#475569', fontWeight:500, fontSize:11 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.snapshot_sizes.slice(0, versionCount).map((snap, i) => {
                const delta = data.delta_sizes[i];
                const saving = snap > 0 ? ((snap - delta) / snap * 100).toFixed(1) : '0.0';
                return (
                  <tr key={i} style={{ borderBottom:'1px solid rgba(255,255,255,.03)' }}>
                    <td style={{ padding:'7px 12px', fontWeight:600, color:'#60a5fa' }}>v{i+1}</td>
                    <td style={{ padding:'7px 12px', color:'#64748b', fontFamily:'monospace' }}>{snap} B</td>
                    <td style={{ padding:'7px 12px', color:'#3b82f6', fontFamily:'monospace', fontWeight:500 }}>{delta} B</td>
                    <td style={{ padding:'7px 12px', color: parseFloat(saving) > 50 ? '#34d399' : '#fbbf24', fontWeight:600 }}>{saving}%</td>
                    <td style={{ padding:'7px 12px', color:'#475569' }}>{data.rehydration_costs[i]} delta(s)</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Công thức rehydration */}
        <div className="text-xs mt-4" style={{ color:'#475569', lineHeight:1.8, background:'rgba(255,255,255,.02)', borderRadius:8, padding:12 }}>
          <strong style={{ color:'#94a3b8' }}>Cách lưu Object Delta giữa các site:</strong><br />
          Server chỉ truyền <strong style={{ color:'#60a5fa' }}>diff</strong> — ví dụ một lần thêm lỗ khoan chỉ tốn vài byte thay vì gửi lại toàn bộ file.<br />
          Khi site cần phiên bản cụ thể, server <strong style={{ color:'#a78bfa' }}>tái tạo</strong> bằng chuỗi:
          <code style={{ color:'#34d399', marginLeft:8 }}>v1 + Δ² + Δ³ + ... = v{n}</code>
        </div>
      </div>

      {/* ─── 3 SITE PER-BAR ─── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {Object.entries(sites).map(([key, site]) => {
          const snap = site.storage?.snapshot_total_bytes || 0;
          const delta = site.storage?.delta_total_bytes || 0;
          const saving = site.storage?.savings_percent?.toFixed(1) || '0.0';
          const max = Math.max(snap, 1);
          return (
            <div key={key} className="card" style={{ borderTop:`3px solid ${site.color}` }}>
              <div className="font-semibold text-sm mb-3" style={{ color: site.color }}>{site.name}</div>
              {!site.online ? (
                <div style={{ textAlign:'center', padding:20, color:'#334155', fontSize:12 }}>Offline</div>
              ) : snap === 0 ? (
                <div style={{ textAlign:'center', padding:20, color:'#334155', fontSize:12 }}>Chưa có dữ liệu</div>
              ) : (
                <>
                  <div style={{ marginBottom:8 }}>
                    <div style={{ display:'flex', justifyContent:'space-between', fontSize:11, marginBottom:2 }}>
                      <span style={{ color:'#475569' }}>Snapshot</span>
                      <span style={{ color:'#64748b', fontFamily:'monospace' }}>{(snap/1024).toFixed(1)} KB</span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width:`${(snap/max)*100}%`, background:'#475569', opacity:0.6 }} />
                    </div>
                  </div>
                  <div style={{ marginBottom:10 }}>
                    <div style={{ display:'flex', justifyContent:'space-between', fontSize:11, marginBottom:2 }}>
                      <span style={{ color:'#475569' }}>Delta</span>
                      <span style={{ color: site.color, fontFamily:'monospace' }}>{(delta/1024).toFixed(1)} KB</span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width:`${(delta/max)*100}%`, background: site.color }} />
                    </div>
                  </div>
                  <div style={{ padding:'8px 12px', borderRadius:7, background:`${site.color}11`, fontSize:12, color:'#34d399', fontWeight:600, display:'flex', alignItems:'center', gap:6 }}>
                    <TrendingDown size={14} />
                    Tiết kiệm {saving}%
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* ─── THEORY BOX ─── */}
      <div className="card" style={{ background:'rgba(59,130,246,.06)', border:'1px solid rgba(59,130,246,.15)' }}>
        <h4 className="font-semibold text-sm mb-3" style={{ color:'#60a5fa' }}>
          📚 Özsu & Valduriez — Ch.15 §15.6: Object Management
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
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
    </div>
  );
}
