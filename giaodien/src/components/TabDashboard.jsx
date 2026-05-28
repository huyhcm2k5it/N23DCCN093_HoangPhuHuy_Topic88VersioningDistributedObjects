import { Database, Layers, GitBranch, Server, Cpu, HardDrive } from 'lucide-react';

// Mapping category → icon
const ICON_MAP = { engine: Cpu, chassis: HardDrive, interior: Database };
// Mapping category → label hiển thị
const CAT_LABEL = {
  engine:   'Engine Parts (ENG-*)',
  chassis:  'Chassis Parts (CHS-*)',
  interior: 'Interior Parts (INT-*)',
};

function SiteCard({ site }) {
  const color = site.color || '#60a5fa';
  const Icon  = ICON_MAP[site.category] || Database;
  const snap   = site.storage?.snapshot_total_bytes || 0;
  const delta  = site.storage?.delta_total_bytes    || 0;
  const saving = site.storage?.savings_percent ?? 0;
  const disconnected = site.reachable && site.network_online === false;
  const statusLabel = disconnected ? 'Disconnected' : (site.reachable ? 'Online' : 'Offline');
  const statusBadge = disconnected ? 'badge-amber' : (site.reachable ? 'badge-green' : 'badge-red');
  const statusDot = disconnected ? 'dot-amber' : (site.reachable ? 'dot-green' : 'dot-red');

  return (
    <div className="card" style={{ borderTop: `3px solid ${color}` }}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div style={{ background: `${color}22`, borderRadius: 8, padding: 7 }}>
            <Icon size={18} style={{ color }} />
          </div>
          <div>
            <div className="font-semibold text-sm">{site.name}</div>
            <div className="text-xs" style={{ color: '#64748b' }}>{site.label}</div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className={`badge ${statusBadge}`}>
            <span className={`dot ${statusDot}`} />
            {statusLabel}
          </span>
          <span className="badge badge-blue">
            {site.strategy}
          </span>
        </div>
      </div>

      {/* Fragment label */}
      <div className="text-xs mb-3" style={{ color: '#94a3b8' }}>
        Fragment: <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{CAT_LABEL[site.category] || 'N/A'}</span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 text-center mb-3">
        {[
          { label: 'Parts',    value: site.models?.length || 0 },
          { label: 'Snapshot', value: snap  > 0 ? `${(snap  / 1024).toFixed(1)}KB` : '—' },
          { label: 'Delta',    value: delta > 0 ? `${(delta / 1024).toFixed(1)}KB` : '—' },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: '8px 4px' }}>
            <div className="text-lg font-bold" style={{ color }}>{value}</div>
            <div className="text-xs" style={{ color: '#64748b' }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Savings bar */}
      {snap > 0 && (
        <div>
          <div className="flex justify-between text-xs mb-1" style={{ color: '#64748b' }}>
            <span>Delta tiết kiệm</span>
            <span style={{ color: '#34d399', fontWeight: 600 }}>{saving.toFixed(1)}%</span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${Math.min(saving, 100)}%`, background: `linear-gradient(90deg,${color},#10b981)` }} />
          </div>
        </div>
      )}
    </div>
  );
}

export default function TabDashboard({ sites }) {
  const onlineCount = Object.values(sites).filter(s => s?.reachable).length;
  const totalParts  = Object.values(sites).reduce((s, x) => s + (x.models?.length || 0), 0);

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Sites Online',    value: `${onlineCount}/3`,   color: onlineCount === 3 ? '#34d399' : '#f87171', Icon: Server    },
          { label: 'Total Parts',     value: totalParts,            color: '#60a5fa',                                 Icon: Database  },
          { label: 'Fragmentation',   value: 'Horizontal',          color: '#a78bfa',                                 Icon: Layers    },
          { label: 'Conflict Mode',   value: 'Branching',           color: '#fbbf24',                                 Icon: GitBranch },
        ].map(({ label, value, color, Icon }) => (
          <div key={label} className="card flex items-center gap-3">
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

      {/* Site Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {Object.entries(sites).map(([key, site]) => (
          <SiteCard key={key} site={site} />
        ))}
      </div>

      {/* Fragmentation Table */}
      <div className="card">
        <h3 className="font-semibold mb-4 flex items-center gap-2 text-sm">
          <Layers size={16} style={{ color: '#60a5fa' }} />
          Phân mảnh Ngang (Horizontal Fragmentation) — Predicate-based
        </h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
              {['Site', 'Port', 'Category', 'Predicate', 'Parts', 'Strategy', 'Status'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '8px 12px', color: '#64748b', fontWeight: 500, fontSize: 11 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(sites).map(([key, site]) => {
              const port = site.host?.split(':')[2] || '—';
              const rowDisconnected = site.reachable && site.network_online === false;
              return (
                <tr key={key} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={{ padding: '10px 12px', fontWeight: 600, color: site.color }}>{site.name}</td>
                  <td style={{ padding: '10px 12px', color: '#64748b', fontFamily: 'monospace', fontSize: 12 }}>:{port}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span className="badge badge-blue">{site.category}</span>
                  </td>
                  <td style={{ padding: '10px 12px', color: '#64748b', fontFamily: 'monospace', fontSize: 12 }}>
                    category = &apos;{site.category}&apos;
                  </td>
                  <td style={{ padding: '10px 12px', fontWeight: 600, color: '#e2e8f0' }}>{site.models?.length || 0}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span className="badge badge-blue">
                      {site.strategy}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span className={`badge ${rowDisconnected ? 'badge-amber' : (site.reachable ? 'badge-green' : 'badge-red')}`}>
                      {rowDisconnected ? '● Disconnected' : (site.reachable ? '● Online' : '○ Offline')}
                    </span>
                  </td>
                </tr>
              );
            })}
            <tr style={{ borderTop: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.02)' }}>
              <td colSpan={4} style={{ padding: '8px 12px', fontWeight: 600, color: '#94a3b8', fontSize: 12 }}>
                UNION(A ∪ B ∪ C) = Full Dataset — không trùng lặp
              </td>
              <td style={{ padding: '8px 12px', fontWeight: 700, color: '#34d399' }}>{totalParts}</td>
              <td colSpan={2} />
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
