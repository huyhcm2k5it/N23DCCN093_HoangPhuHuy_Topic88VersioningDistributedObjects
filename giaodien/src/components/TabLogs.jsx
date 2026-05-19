import { useState, useEffect } from 'react';
import { getWalStatus, restartCoordinator, getLogs, SITES } from '../api';

const ACTION_COLOR = {
  CHECKOUT:     { bg: '#E6F1FB', color: '#185FA5' },
  CHECKIN:      { bg: '#EAF3DE', color: '#3B6D11' },
  CREATE:       { bg: '#F0E9FB', color: '#6D28D9' },
  REPLICATE:    { bg: '#FAEEDA', color: '#854F0B' },
  WAL_ROLLBACK: { bg: '#FCEBEB', color: '#A32D2D' },
};

export default function TabLogs() {
  const [allWalEntries, setAllWalEntries] = useState([]);
  const [uncommitted,   setUncommitted]   = useState([]);
  const [actLogs,       setActLogs]       = useState([]);
  const [walMeta,       setWalMeta]       = useState(null);
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState(null);
  const [recovering,    setRecovering]    = useState(false);
  const [recoverResult, setRecoverResult] = useState(null);
  const [view,          setView]          = useState('activity');
  const [expanded,      setExpanded]      = useState(null);

  async function load() {
    setLoading(true); setError(null);
    try {
      // WAL status + activity logs tu ca 3 sites
      const [walA, walB, walC, logsA, logsB, logsC] = await Promise.allSettled([
        getWalStatus('a'), getWalStatus('b'), getWalStatus('c'),
        getLogs('a'), getLogs('b'), getLogs('c'),
      ]);

      // Gop WAL entries tu tat ca sites
      const allEntries = [];
      const allUncommitted = [];
      [walA, walB, walC].forEach((r, i) => {
        const siteKey = ['a', 'b', 'c'][i];
        const siteName = SITES[siteKey].name;
        if (r.status === 'fulfilled') {
          const s = r.value;
          // Gan them site info vao moi entry
          (s.all_entries || []).forEach(e => {
            allEntries.push({ ...e, _site: siteName, _siteKey: siteKey });
          });
          (s.pending_transactions || []).forEach(e => {
            allUncommitted.push({ ...e, _site: siteName, _siteKey: siteKey });
          });
          // Giu walMeta tu site dau tien co data
          if (!walMeta && s) setWalMeta(s);
        }
      });

      setAllWalEntries(allEntries);
      setUncommitted(allUncommitted);

      // Gop activity logs tu 3 sites, sort moi nhat truoc
      const allLogs = [];
      [logsA, logsB, logsC].forEach(r => {
        if (r.status === 'fulfilled' && Array.isArray(r.value)) {
          allLogs.push(...r.value);
        }
      });
      allLogs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      setActLogs(allLogs);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function handleRecover() {
    if (!confirm('Trigger WAL recovery? Tất cả entry uncommitted sẽ bị rollback.')) return;
    setRecovering(true); setRecoverResult(null);
    try {
      // Recover tu tat ca sites
      const results = await Promise.allSettled([
        restartCoordinator('a'),
        restartCoordinator('b'),
        restartCoordinator('c'),
      ]);
      const totalRollback = results.reduce((sum, r) =>
        sum + (r.status === 'fulfilled' ? (r.value.rolled_back_count || 0) : 0), 0);
      setRecoverResult({ total: totalRollback, results });
      await load();
    } catch (e) { setError(e.message); }
    finally { setRecovering(false); }
  }

  const uncommittedCount = uncommitted.length;

  return (
    <div style={{ color: '#111' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 500, color: '#e2e8f0' }}>Nhật ký WAL &amp; Activity</h2>
          <p style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
            Activity log thực tế từ 3 sites · WAL entries từ WAL file thật
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={load}
            style={{ background: 'transparent', border: '0.5px solid #ccc', borderRadius: 7, padding: '7px 14px', fontSize: 13, cursor: 'pointer', color: '#666' }}>
            Refresh
          </button>
          <button onClick={handleRecover} disabled={recovering || uncommittedCount === 0}
            style={{
              background: uncommittedCount > 0 ? '#A32D2D' : '#555',
              color: '#fff', border: 'none', borderRadius: 7,
              padding: '7px 16px', fontSize: 13,
              cursor: uncommittedCount > 0 ? 'pointer' : 'not-allowed',
              opacity: recovering ? 0.7 : 1,
            }}>
            {recovering ? 'Đang recover...' : `Trigger Recovery (${uncommittedCount})`}
          </button>
        </div>
      </div>

      {/* WAL Summary Banner */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Total WAL Entries', value: allWalEntries.length, warn: false },
          { label: 'Uncommitted (PENDING)', value: uncommittedCount, warn: uncommittedCount > 0 },
          { label: 'Committed', value: allWalEntries.filter(e => e.committed).length, warn: false },
        ].map(({ label, value, warn }) => (
          <div key={label} style={{
            borderRadius: 8, padding: '10px 14px',
            background: warn ? '#FCEBEB' : 'rgba(255,255,255,.03)',
            border: `0.5px solid ${warn ? '#f09595' : 'rgba(255,255,255,.08)'}`,
          }}>
            <div style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace', marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 18, fontWeight: 600, color: warn ? '#A32D2D' : '#34d399' }}>{String(value)}</div>
          </div>
        ))}
      </div>

      {recoverResult && (
        <div style={{ background: '#EAF3DE', border: '0.5px solid #C0DD97', borderRadius: 8, padding: '10px 14px', marginBottom: 16, fontSize: 13, color: '#3B6D11' }}>
          ✓ Recovery hoàn tất — Rolled back: {recoverResult.total} transactions
        </div>
      )}
      {error && (
        <div style={{ background: '#FCEBEB', borderRadius: 8, padding: '10px 14px', color: '#A32D2D', fontSize: 13, marginBottom: 12 }}>
          Lỗi: {error}
        </div>
      )}

      {/* View tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {[
          { key: 'activity', label: `Activity Log (${actLogs.length})` },
          { key: 'wal', label: `WAL Entries (${allWalEntries.length})` },
          { key: 'uncommitted', label: uncommittedCount > 0 ? `⚠ Uncommitted (${uncommittedCount})` : `Uncommitted (0)` },
        ].map(({ key, label }) => (
          <button key={key} onClick={() => setView(key)}
            style={{
              padding: '6px 18px', borderRadius: 20, fontSize: 13, cursor: 'pointer',
              border: '0.5px solid', fontWeight: view === key ? 500 : 400,
              borderColor: key === 'uncommitted' && uncommittedCount > 0 ? '#A32D2D' : view === key ? '#185FA5' : '#ddd',
              background: view === key ? (key === 'uncommitted' && uncommittedCount > 0 ? '#FCEBEB' : '#E6F1FB') : 'transparent',
              color: key === 'uncommitted' && uncommittedCount > 0 ? '#A32D2D' : view === key ? '#185FA5' : '#666',
            }}>
            {label}
          </button>
        ))}
      </div>

      {/* Activity Log view */}
      {view === 'activity' && (
        <div style={{ background: '#fff', border: '0.5px solid #e0e0de', borderRadius: 12, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f9f9f7' }}>
                {['Site', 'Action', 'Part ID', 'Thông tin', 'Thời gian'].map(h => (
                  <th key={h} style={{ padding: '8px 14px', textAlign: 'left', fontWeight: 500, color: '#888', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={5} style={{ padding: '20px 14px', color: '#aaa' }}>Đang tải...</td></tr>}
              {!loading && actLogs.length === 0 && (
                <tr><td colSpan={5} style={{ padding: '30px 14px', textAlign: 'center', color: '#aaa' }}>
                  Chưa có activity nào. Hãy thử Checkout / Checkin ở tab &quot;Làm việc&quot;.
                </td></tr>
              )}
              {actLogs.map((log, i) => {
                const c = ACTION_COLOR[log.action] || { bg: '#f0f0ee', color: '#555' };
                const siteMeta = Object.values(SITES).find(s => s.site_id === log.site);
                return (
                  <tr key={i} style={{ borderBottom: '0.5px solid #f5f5f3' }}>
                    <td style={{ padding: '9px 14px' }}>
                      <span style={{ fontWeight: 600, color: siteMeta?.color || '#60a5fa', fontSize: 12 }}>
                        {log.site}
                      </span>
                    </td>
                    <td style={{ padding: '9px 14px' }}>
                      <span style={{ ...c, borderRadius: 4, padding: '2px 8px', fontSize: 11 }}>{log.action}</span>
                    </td>
                    <td style={{ padding: '9px 14px', fontWeight: 500 }}>{log.part_id}</td>
                    <td style={{ padding: '9px 14px', color: '#555', fontSize: 12 }}>{log.message}</td>
                    <td style={{ padding: '9px 14px', color: '#aaa', fontSize: 12 }}>
                      {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* WAL Entries view - all entries from all sites */}
      {view === 'wal' && (
        <div style={{ background: '#fff', border: '0.5px solid #e0e0de', borderRadius: 12, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f9f9f7' }}>
                {['Site', 'Entry ID', 'Operation', 'Part ID', 'Status', 'Timestamp', ''].map(h => (
                  <th key={h} style={{ padding: '8px 14px', textAlign: 'left', fontWeight: 500, color: '#888', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={7} style={{ padding: '20px 14px', color: '#aaa' }}>Đang tải...</td></tr>}
              {!loading && allWalEntries.length === 0 && (
                <tr><td colSpan={7} style={{ padding: '30px 14px', textAlign: 'center', color: '#3B6D11' }}>
                  ✅ WAL file trống — Tất cả giao dịch đã commit hoặc chưa có.
                </td></tr>
              )}
              {allWalEntries.map((e, i) => {
                const isCommitted = e.committed;
                const statusBg = isCommitted ? '#EAF3DE' : '#FCEBEB';
                const statusColor = isCommitted ? '#3B6D11' : '#A32D2D';
                const statusText = isCommitted ? 'COMMITTED' : 'PENDING';
                const siteMeta = Object.values(SITES).find(s => s.name === e._site);
                return (
                  <>
                    <tr key={i} style={{ borderBottom: expanded === e.entry_id ? 'none' : '0.5px solid #f5f5f3' }}>
                      <td style={{ padding: '9px 14px' }}>
                        <span style={{ fontWeight: 600, color: siteMeta?.color || '#60a5fa', fontSize: 12 }}>
                          {e._site}
                        </span>
                      </td>
                      <td style={{ padding: '9px 14px', fontFamily: 'monospace', color: '#888' }}>{e.entry_id}</td>
                      <td style={{ padding: '9px 14px', fontWeight: 500 }}>{e.operation}</td>
                      <td style={{ padding: '9px 14px' }}>{e.part_id}</td>
                      <td style={{ padding: '9px 14px' }}>
                        <span style={{ background: statusBg, color: statusColor, borderRadius: 4, padding: '2px 8px', fontSize: 11 }}>
                          {statusText}
                        </span>
                      </td>
                      <td style={{ padding: '9px 14px', color: '#aaa', fontSize: 12 }}>
                        {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '—'}
                      </td>
                      <td style={{ padding: '9px 14px' }}>
                        <button onClick={() => setExpanded(expanded === e.entry_id ? null : e.entry_id)}
                          style={{ background: 'transparent', border: '0.5px solid #ddd', borderRadius: 5, padding: '2px 8px', fontSize: 11, cursor: 'pointer', color: '#666' }}>
                          {expanded === e.entry_id ? 'Ẩn ▲' : 'Xem ▼'}
                        </button>
                      </td>
                    </tr>
                    {expanded === e.entry_id && (
                      <tr key={`${i}-exp`} style={{ borderBottom: '0.5px solid #f5f5f3' }}>
                        <td colSpan={7} style={{ padding: '0 14px 12px 14px' }}>
                          <pre style={{ fontFamily: 'monospace', fontSize: 11, color: '#555', background: '#f9f9f7', borderRadius: 6, padding: '10px', margin: 0, overflowX: 'auto' }}>
                            {JSON.stringify(e.data, null, 2)}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Uncommitted view */}
      {view === 'uncommitted' && (
        <div style={{ background: '#fff', border: '0.5px solid #e0e0de', borderRadius: 12, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f9f9f7' }}>
                {['Site', 'Entry ID', 'Operation', 'Part ID', 'User', 'Timestamp'].map(h => (
                  <th key={h} style={{ padding: '8px 14px', textAlign: 'left', fontWeight: 500, color: '#888', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={6} style={{ padding: '20px 14px', color: '#aaa' }}>Đang tải...</td></tr>}
              {!loading && uncommitted.length === 0 && (
                <tr><td colSpan={6} style={{ padding: '30px 14px', textAlign: 'center', color: '#3B6D11' }}>
                  ✅ Không có giao dịch uncommitted — Hệ thống ổn định
                  <div style={{ fontSize: 12, color: '#aaa', marginTop: 6 }}>
                    Để thấy WAL entries, hãy dùng tab &quot;Demo WAL Crash&quot; → chạy crash demo.
                  </div>
                </td></tr>
              )}
              {uncommitted.map((e, i) => {
                const siteMeta = Object.values(SITES).find(s => s.name === e._site);
                return (
                  <tr key={i} style={{ borderBottom: '0.5px solid #f5f5f3', background: '#fffdf8' }}>
                    <td style={{ padding: '9px 14px' }}>
                      <span style={{ fontWeight: 600, color: siteMeta?.color || '#60a5fa', fontSize: 12 }}>{e._site}</span>
                    </td>
                    <td style={{ padding: '9px 14px', fontFamily: 'monospace', color: '#888' }}>{e.entry_id}</td>
                    <td style={{ padding: '9px 14px', fontWeight: 500 }}>{e.operation}</td>
                    <td style={{ padding: '9px 14px' }}>{e.part_id}</td>
                    <td style={{ padding: '9px 14px', color: '#555' }}>{e.data?.user || '—'}</td>
                    <td style={{ padding: '9px 14px', color: '#aaa', fontSize: 12 }}>
                      {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Theory note */}
      <div style={{ background: 'rgba(59,130,246,.06)', border: '1px solid rgba(59,130,246,.15)', borderRadius: 10, padding: '14px 18px', marginTop: 16 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#60a5fa', marginBottom: 6 }}>📚 WAL hoạt động như thế nào?</div>
        <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.8 }}>
          <strong>Activity Log</strong>: Mọi hành động Checkout / Checkin / Create từ tất cả 3 sites.<br/>
          <strong>WAL Entries</strong>: Tất cả giao dịch được ghi vào WAL file trước khi thực thi (Write-Ahead).<br/>
          <strong>Uncommitted</strong>: Entry bị bỏ lửng (crash trước commit) — cần recovery.<br/>
          <strong>Atomicity</strong>: Recovery rollback tất cả pending → Hệ thống trở về trạng thái nhất quán.
        </div>
      </div>
    </div>
  );
}
