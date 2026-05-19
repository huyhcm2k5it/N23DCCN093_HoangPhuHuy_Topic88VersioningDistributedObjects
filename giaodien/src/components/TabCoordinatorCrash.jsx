import { useState, useEffect } from 'react';
import { listModels, runCrashDemo, getWalStatus, restartCoordinator, getModel, SITES } from '../api';

const STEPS = [
  { id: 1, label: 'Chọn Part & Site',  desc: 'Chọn part muốn demo crash' },
  { id: 2, label: 'Crash Simulation',   desc: 'Checkout → Sửa → Checkin → 💥 CRASH trước commit' },
  { id: 3, label: 'Kiểm tra WAL',       desc: 'Xác nhận entry PENDING trong WAL file' },
  { id: 4, label: 'Recovery',           desc: 'Coordinator restart → rollback pending → Atomicity' },
  { id: 5, label: 'Xác minh',           desc: 'Part trở về version trước crash — không mất dữ liệu' },
];

export default function TabCoordinatorCrash({ onRefresh }) {
  const [parts,    setParts]   = useState([]);
  const [selPart,  setSelPart] = useState('');
  const [selKey,   setSelKey]  = useState('a');
  const [step,     setStep]    = useState(1);
  const [loading,  setLoading] = useState(false);
  const [error,    setError]   = useState(null);

  const [crashResult,   setCrashResult]   = useState(null);
  const [walState,      setWalState]      = useState(null);
  const [recoverResult, setRecoverResult] = useState(null);
  const [verifyModel,   setVerifyModel]   = useState(null);
  const [showRawWal,    setShowRawWal]    = useState(false);

  useEffect(() => {
    listModels(selKey).then(d => setParts(d.models || [])).catch(() => setParts([]));
  }, [selKey]);

  function resetDemo() {
    setStep(1); setCrashResult(null); setWalState(null);
    setRecoverResult(null); setVerifyModel(null); setError(null);
    setSelPart(''); setShowRawWal(false);
  }

  async function handleCrashDemo() {
    if (!selPart) { setError('Chọn Part trước'); return; }
    setLoading(true); setError(null);
    try {
      const res = await runCrashDemo(selKey, selPart);
      setCrashResult(res);
      setStep(2);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  async function handleCheckWAL() {
    setLoading(true); setError(null);
    try {
      const status = await getWalStatus(selKey);
      setWalState(status);
      setStep(3);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  async function handleRecover() {
    setLoading(true); setError(null);
    try {
      const res = await restartCoordinator(selKey);
      setRecoverResult(res);
      try {
        const model = await getModel(selKey, selPart);
        setVerifyModel(model);
      } catch { /* ignore */ }
      setStep(5);
      onRefresh?.();
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  const siteMeta = SITES[selKey];

  return (
    <div style={{ color: '#111' }}>
      <h2 style={{ fontSize: 20, fontWeight: 500, marginBottom: 4, color: '#e2e8f0' }}>Demo WAL Crash &amp; Recovery</h2>
      <p style={{ fontSize: 13, color: '#64748b', marginBottom: 24 }}>
        Minh họa tính Atomicity — hoặc commit toàn bộ hoặc rollback hoàn toàn (Özsu §15.7)
      </p>

      {/* Step progress */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 28, overflowX: 'auto' }}>
        {STEPS.map((s, i) => {
          const done   = step > s.id;
          const active = step === s.id;
          return (
            <div key={s.id} style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 120 }}>
              <div style={{ flex: 1, textAlign: 'center' }}>
                <div style={{
                  width: 32, height: 32, borderRadius: '50%', margin: '0 auto 6px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 600,
                  background: done ? '#10b981' : active ? '#3b82f6' : 'rgba(255,255,255,.05)',
                  color: done || active ? '#fff' : '#475569',
                  border: `2px solid ${done ? '#10b981' : active ? '#3b82f6' : 'rgba(255,255,255,.1)'}`,
                }}>
                  {done ? '✓' : s.id}
                </div>
                <div style={{ fontSize: 11, fontWeight: active ? 600 : 400, color: active ? '#e2e8f0' : '#475569' }}>
                  {s.label}
                </div>
                {active && <div style={{ fontSize: 10, color: '#64748b', marginTop: 2, padding: '0 4px' }}>{s.desc}</div>}
              </div>
              {i < STEPS.length - 1 && (
                <div style={{ width: 24, height: 2, background: done ? '#10b981' : 'rgba(255,255,255,.1)', flexShrink: 0 }} />
              )}
            </div>
          );
        })}
      </div>

      {error && (
        <div style={{ background: '#FCEBEB', border: '0.5px solid #f09595', borderRadius: 8, padding: '10px 14px', marginBottom: 16, fontSize: 13, color: '#A32D2D' }}>
          ❌ {error}
        </div>
      )}

      {/* Step 1: Chon Part & Site */}
      {step === 1 && (
        <div style={{ background: '#fff', border: '0.5px solid #e0e0de', borderRadius: 12, padding: '20px 24px' }}>
          <h3 style={{ fontSize: 15, fontWeight: 500, marginBottom: 16, color: '#111' }}>Bước 1 — Chọn Site &amp; Part</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
            <div>
              <div style={{ fontSize: 12, color: '#888', marginBottom: 6 }}>Site</div>
              <select value={selKey} onChange={e => { setSelKey(e.target.value); setSelPart(''); }}
                style={{ width: '100%', padding: '8px 10px', fontSize: 13, border: '0.5px solid #ccc', borderRadius: 7, background: '#fafafa', color: '#111' }}>
                {Object.entries(SITES).map(([k, s]) => (
                  <option key={k} value={k}>{s.name} — {s.label}</option>
                ))}
              </select>
            </div>
            <div>
              <div style={{ fontSize: 12, color: '#888', marginBottom: 6 }}>Part ({parts.length})</div>
              <select value={selPart} onChange={e => setSelPart(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', fontSize: 13, border: '0.5px solid #ccc', borderRadius: 7, background: '#fafafa', color: '#111' }}>
                <option value="">-- Chọn Part --</option>
                {parts.map(p => <option key={p.part_id} value={p.part_id}>{p.part_id} (v{p.version})</option>)}
              </select>
            </div>
          </div>

          {/* Transaction Sequence Diagram */}
          <div style={{ background: '#f9f9f7', border: '0.5px solid #e0e0de', borderRadius: 8, padding: '14px 16px', marginBottom: 20, fontSize: 12, color: '#555', lineHeight: 1.8 }}>
            <strong>Kịch bản (Transaction Sequence):</strong>
            <div style={{ fontFamily: 'monospace', fontSize: 11, marginTop: 8, background: '#fff', padding: '10px 14px', borderRadius: 6, border: '0.5px solid #e0e0de' }}>
              <div>1. <span style={{ color: '#185FA5' }}>BEGIN_TXN</span>  → Checkout part</div>
              <div>2. <span style={{ color: '#185FA5' }}>WRITE_WAL</span> → Ghi WAL entry (status=PENDING)</div>
              <div>3. <span style={{ color: '#A32D2D' }}>💥 CRASH</span>   → Coordinator crash TRƯỚC commit</div>
              <div>4. <span style={{ color: '#888' }}>MODIFY_DB</span>  → ❌ KHÔNG thực thi (crash)</div>
              <div>5. <span style={{ color: '#888' }}>COMMIT</span>     → ❌ KHÔNG thực thi (crash)</div>
              <div style={{ marginTop: 8, color: '#3B6D11' }}>
                → WAL file: entry PENDING | DB: KHÔNG thay đổi | Atomicity: ĐẢM BẢO
              </div>
            </div>
          </div>

          <button onClick={handleCrashDemo} disabled={!selPart || loading}
            style={{ background: selPart ? '#dc2626' : '#ccc', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 24px', fontSize: 14, cursor: selPart ? 'pointer' : 'not-allowed' }}>
            {loading ? 'Đang thực hiện...' : '💥 Bắt đầu Crash Demo →'}
          </button>
        </div>
      )}

      {/* Step 2: Crash result */}
      {step === 2 && crashResult && (
        <div style={{ background: '#fff', border: '0.5px solid #e0e0de', borderRadius: 12, padding: '20px 24px' }}>
          <div style={{ background: '#FCEBEB', border: '0.5px solid #f09595', borderRadius: 8, padding: '14px 16px', marginBottom: 16 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#A32D2D', marginBottom: 6 }}>💥 COORDINATOR CRASHED!</div>
            <div style={{ fontSize: 13, color: '#555', lineHeight: 1.6 }}>{crashResult.message}</div>
          </div>

          {/* Transaction state */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
            {[
              { label: 'Part', value: crashResult.part_id, bg: '#f9f9f7', color: '#111' },
              { label: 'DB Version', value: `v${crashResult.version_after_crash}`, bg: '#EAF3DE', color: '#3B6D11' },
              { label: 'WAL Pending', value: crashResult.wal_status?.uncommitted_count || 0, bg: '#FCEBEB', color: '#A32D2D' },
              { label: 'DB Changed?', value: crashResult.version_before_crash === crashResult.version_after_crash ? 'KHÔNG ✓' : 'CÓ ⚠', bg: crashResult.version_before_crash === crashResult.version_after_crash ? '#EAF3DE' : '#FCEBEB', color: crashResult.version_before_crash === crashResult.version_after_crash ? '#3B6D11' : '#A32D2D' },
            ].map(({ label, value, bg, color }) => (
              <div key={label} style={{ background: bg, borderRadius: 8, padding: '10px 14px', border: '0.5px solid #e0e0de' }}>
                <div style={{ fontSize: 10, color: '#888', marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 16, fontWeight: 600, color }}>{String(value)}</div>
              </div>
            ))}
          </div>

          {/* Explanation */}
          <div style={{ fontSize: 12, color: '#555', marginBottom: 16, lineHeight: 1.7, background: '#f9f9f7', padding: '12px 16px', borderRadius: 8 }}>
            <strong>Trạng thái hệ thống:</strong><br/>
            • WAL file đã ghi 1 entry <code style={{ color: '#A32D2D' }}>PENDING</code> (uncommitted)<br/>
            • DB vẫn giữ version <strong>v{crashResult.version_after_crash}</strong> (không thay đổi)<br/>
            • Hệ thống đang ở trạng thái <strong>inconsistent</strong> — cần Recovery để khôi phục
          </div>

          <button onClick={handleCheckWAL} disabled={loading}
            style={{ background: '#185FA5', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 24px', fontSize: 14, cursor: 'pointer' }}>
            {loading ? 'Đang tải...' : 'Kiểm tra WAL File →'}
          </button>
        </div>
      )}

      {/* Step 3: WAL status + raw content */}
      {step === 3 && walState && (
        <div style={{ background: '#fff', border: '0.5px solid #e0e0de', borderRadius: 12, padding: '20px 24px' }}>
          <h3 style={{ fontSize: 15, fontWeight: 500, marginBottom: 14, color: '#111' }}>WAL File — {siteMeta?.name}</h3>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
            {[
              { label: 'Total Entries', value: walState.total_entries, warn: false },
              { label: 'Uncommitted', value: walState.uncommitted_count, warn: walState.uncommitted_count > 0 },
              { label: 'crash_flag', value: String(walState.crash_on_next_checkin), warn: walState.crash_on_next_checkin },
              { label: 'crashed', value: String(walState.coordinator_crashed), warn: walState.coordinator_crashed },
            ].map(({ label, value, warn }) => (
              <div key={label} style={{ background: warn ? '#FCEBEB' : '#f9f9f7', borderRadius: 8, padding: '10px 14px', border: `0.5px solid ${warn ? '#f09595' : '#e0e0de'}` }}>
                <div style={{ fontSize: 10, color: '#888', marginBottom: 4, fontFamily: 'monospace' }}>{label}</div>
                <div style={{ fontSize: 18, fontWeight: 600, color: warn ? '#A32D2D' : '#3B6D11' }}>{String(value)}</div>
              </div>
            ))}
          </div>

          {/* Pending entries detail */}
          {walState.pending_transactions?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: '#888', marginBottom: 8 }}>Uncommitted Entries:</div>
              {walState.pending_transactions.map((e, i) => (
                <div key={i} style={{ background: '#fffdf8', border: '0.5px solid #e8e0cc', borderRadius: 8, padding: '10px 14px', marginBottom: 8, fontSize: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <div><strong>ID:</strong> {e.entry_id} · <strong>Op:</strong> {e.operation} · <strong>Part:</strong> {e.part_id}</div>
                    <span style={{ color: '#A32D2D', fontWeight: 600, fontSize: 11 }}>PENDING</span>
                  </div>
                  <div style={{ color: '#888', marginTop: 4 }}>
                    User: {e.data?.user || '—'} · Timestamp: {e.timestamp}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Raw WAL JSON */}
          <div style={{ marginBottom: 16 }}>
            <button onClick={() => setShowRawWal(!showRawWal)}
              style={{ background: 'transparent', border: '0.5px solid #ccc', borderRadius: 6, padding: '4px 12px', fontSize: 11, cursor: 'pointer', color: '#666' }}>
              {showRawWal ? '▲ Ẩn Raw WAL JSON' : '▼ Xem Raw WAL JSON'}
            </button>
            {showRawWal && (
              <pre style={{ background: '#0a0a0a', border: '0.5px solid #333', borderRadius: 6, padding: '12px', fontSize: 10, color: '#94a3b8', marginTop: 8, maxHeight: 250, overflow: 'auto', fontFamily: 'monospace' }}>
{JSON.stringify(walState, null, 2)}
              </pre>
            )}
          </div>

          <div style={{ fontSize: 13, color: '#555', marginBottom: 16, lineHeight: 1.6 }}>
            WAL xác nhận có <strong>{walState.uncommitted_count}</strong> entry PENDING.<br/>
            → <strong>Recovery</strong> sẽ rollback tất cả PENDING → khôi phục trạng thái nhất quán.
          </div>

          <button onClick={handleRecover} disabled={loading}
            style={{ background: '#10b981', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 24px', fontSize: 14, cursor: 'pointer' }}>
            {loading ? 'Đang recover...' : '🔄 Trigger Recovery →'}
          </button>
        </div>
      )}

      {/* Step 5: Recovery + Verification */}
      {step === 5 && recoverResult && (
        <div style={{ background: '#fff', border: '0.5px solid #e0e0de', borderRadius: 12, padding: '20px 24px' }}>
          <div style={{ background: '#EAF3DE', border: '0.5px solid #C0DD97', borderRadius: 8, padding: '14px 16px', marginBottom: 16 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#3B6D11', marginBottom: 4 }}>✅ Recovery thành công!</div>
            <div style={{ fontSize: 13, color: '#555' }}>{recoverResult.message}</div>
          </div>

          {/* Recovery stats */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
            {[
              { label: 'Rolled back', value: recoverResult.rolled_back_count ?? 0, color: '#3B6D11' },
              { label: 'crashed (after)', value: String(recoverResult.wal_status?.coordinator_crashed ?? false), color: '#3B6D11' },
              { label: 'pending (after)', value: recoverResult.wal_status?.uncommitted_count ?? 0, color: '#3B6D11' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ background: '#EAF3DE', borderRadius: 8, padding: '10px 14px', border: '0.5px solid #C0DD97' }}>
                <div style={{ fontSize: 10, color: '#888', marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 20, fontWeight: 600, color }}>{String(value)}</div>
              </div>
            ))}
          </div>

          {/* Atomicity Verification */}
          <div style={{ background: '#f0f7ff', border: '0.5px solid #b3d4fc', borderRadius: 8, padding: '16px', marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 500, color: '#185FA5', marginBottom: 10 }}>🔍 Xác minh Atomicity (DB Query)</div>
            
            <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
              <tbody>
                <tr style={{ borderBottom: '0.5px solid #d4e5f7' }}>
                  <td style={{ padding: '6px 0', color: '#888', width: 180 }}>Part ID</td>
                  <td style={{ padding: '6px 0', fontWeight: 500 }}>{selPart}</td>
                </tr>
                <tr style={{ borderBottom: '0.5px solid #d4e5f7' }}>
                  <td style={{ padding: '6px 0', color: '#888' }}>Version trước crash</td>
                  <td style={{ padding: '6px 0', fontWeight: 500 }}>v{crashResult?.version_before_crash}</td>
                </tr>
                <tr style={{ borderBottom: '0.5px solid #d4e5f7' }}>
                  <td style={{ padding: '6px 0', color: '#888' }}>Version hiện tại (sau recovery)</td>
                  <td style={{ padding: '6px 0', fontWeight: 500 }}>v{verifyModel?.version}</td>
                </tr>
                <tr style={{ borderBottom: '0.5px solid #d4e5f7' }}>
                  <td style={{ padding: '6px 0', color: '#888' }}>Branch</td>
                  <td style={{ padding: '6px 0' }}>{verifyModel?.branch}</td>
                </tr>
                <tr style={{ borderBottom: '0.5px solid #d4e5f7' }}>
                  <td style={{ padding: '6px 0', color: '#888' }}>OID</td>
                  <td style={{ padding: '6px 0', fontFamily: 'monospace', fontSize: 11 }}>{verifyModel?.oid}</td>
                </tr>
                <tr>
                  <td style={{ padding: '6px 0', color: '#888' }}>Kết luận</td>
                  <td style={{ padding: '6px 0' }}>
                    {verifyModel?.version === crashResult?.version_before_crash ? (
                      <span style={{ color: '#3B6D11', fontWeight: 600 }}>✅ Version KHÔNG ĐỔI → Atomicity đảm bảo (all-or-nothing)</span>
                    ) : (
                      <span style={{ color: '#A32D2D' }}>⚠ Version thay đổi — cần kiểm tra lại</span>
                    )}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Recovered entries */}
          {recoverResult.recovered_entries?.length > 0 && (
            <details style={{ marginBottom: 16 }}>
              <summary style={{ fontSize: 12, color: '#888', cursor: 'pointer' }}>
                📄 Rolled-back WAL Entries ({recoverResult.recovered_entries.length})
              </summary>
              <pre style={{ background: '#f9f9f7', border: '0.5px solid #e0e0de', borderRadius: 6, padding: 10, fontSize: 10, color: '#555', marginTop: 8, overflow: 'auto' }}>
{JSON.stringify(recoverResult.recovered_entries, null, 2)}
              </pre>
            </details>
          )}

          {/* Theory */}
          <div style={{ background: 'rgba(59,130,246,.06)', border: '1px solid rgba(59,130,246,.15)', borderRadius: 8, padding: '12px 16px', marginBottom: 16, fontSize: 12, color: '#64748b', lineHeight: 1.7 }}>
            <strong>Özsu §15.7 — Write-Ahead Logging:</strong><br/>
            • <strong>WAL Rule:</strong> Ghi log TRƯỚC khi sửa DB → Nếu crash, log vẫn còn.<br/>
            • <strong>Atomicity:</strong> Transaction phải commit toàn bộ hoặc rollback toàn bộ.<br/>
            • <strong>Recovery:</strong> Đọc WAL → Tìm entry PENDING → Rollback → DB nhất quán.
          </div>

          <button onClick={resetDemo}
            style={{ background: '#185FA5', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 22px', fontSize: 14, cursor: 'pointer' }}>
            ← Demo lại
          </button>
        </div>
      )}
    </div>
  );
}
