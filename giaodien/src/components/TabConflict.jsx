import { useState, useEffect } from 'react';
import { listModels, checkout, checkin, getVersions, SITES } from '../api';
import { GitPullRequest, AlertTriangle, CheckCircle } from 'lucide-react';

const STEPS = [
  { id: 1, label: 'Chọn Part',        desc: 'Chọn linh kiện và Site để demo' },
  { id: 2, label: 'Đồng Checkout',    desc: 'Kỹ sư A và B cùng checkout cùng version' },
  { id: 3, label: 'User A Checkin',   desc: 'Kỹ sư A sửa và checkin (Thành công)' },
  { id: 4, label: 'User B Checkin',   desc: 'Kỹ sư B checkin → XUNG ĐỘT!' },
  { id: 5, label: 'Kết quả Xử lý',   desc: 'Phân tích kết quả conflict resolution' },
];

export default function TabConflict({ onRefresh }) {
  const [parts, setParts] = useState([]);
  const [selKey, setSelKey] = useState('a');
  const [selPart, setSelPart] = useState('');
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [userAModel, setUserAModel] = useState(null);
  const [userBModel, setUserBModel] = useState(null);
  const [userAChange, setUserAChange] = useState('');
  const [userBChange, setUserBChange] = useState('');
  const [checkinResultA, setCheckinResultA] = useState(null);
  const [checkinResultB, setCheckinResultB] = useState(null);
  const [versionTree, setVersionTree] = useState([]);

  useEffect(() => {
    listModels(selKey).then(d => setParts(d.models || [])).catch(() => setParts([]));
    setSelPart('');
    resetDemo();
  }, [selKey]);

  function resetDemo() {
    setStep(1); setUserAModel(null); setUserBModel(null);
    setCheckinResultA(null); setCheckinResultB(null);
    setVersionTree([]); setError(null);
    setUserAChange('carbon_fiber_reinforced');
    setUserBChange('titanium_alloy_v2');
  }

  // Buoc 2: Hai user cung checkout
  async function handleCheckout() {
    if (!selPart) { setError('Chọn Part trước!'); return; }
    setLoading(true); setError(null);
    try {
      const modelA = await checkout(selKey, selPart, 'Ky_su_A');
      const modelB = await checkout(selKey, selPart, 'Ky_su_B');
      setUserAModel(modelA);
      setUserBModel(modelB);
      setStep(2);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  // Buoc 3: User A checkin truoc
  async function handleUserACheckin() {
    setLoading(true); setError(null);
    try {
      const modifiedA = { ...userAModel };
      modifiedA.geometry = { ...modifiedA.geometry, properties: { ...modifiedA.geometry.properties, material: userAChange } };
      
      const res = await checkin(selKey, selPart, 'Ky_su_A', modifiedA);
      if (res._status >= 400 || !res.success) throw new Error(res.message || 'Checkin thất bại');
      setCheckinResultA(res);
      setStep(3);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  // Buoc 4: User B checkin sau (XUNG DOT!)
  async function handleUserBCheckin() {
    setLoading(true); setError(null);
    try {
      const modifiedB = { ...userBModel };
      modifiedB.geometry = { ...modifiedB.geometry, properties: { ...modifiedB.geometry.properties, material: userBChange } };
      
      const res = await checkin(selKey, selPart, 'Ky_su_B', modifiedB);
      if (res._status >= 500) throw new Error(res.message || 'Server error');
      setCheckinResultB(res);

      // Fetch version tree
      try {
        const versions = await getVersions(selKey, selPart);
        setVersionTree(versions || []);
      } catch { setVersionTree([]); }

      setStep(5);
      onRefresh?.();
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  const siteMeta = SITES[selKey];

  return (
    <div style={{ color: '#111' }}>
      <h2 style={{ fontSize: 20, fontWeight: 500, marginBottom: 4, color: '#e2e8f0' }}>Conflict Resolution Demo</h2>
      <p style={{ fontSize: 13, color: '#64748b', marginBottom: 24 }}>
        Hai kỹ sư checkout cùng 1 part → sửa khác nhau → checkin → Hệ thống tự giải quyết xung đột (Özsu §15.5)
      </p>

      {/* Progress Bar */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 28, overflowX: 'auto' }}>
        {STEPS.map((s, i) => {
          const done   = step > s.id || (step === 5 && s.id === 4);
          const active = step === s.id;
          return (
            <div key={s.id} style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 110 }}>
              <div style={{ flex: 1, textAlign: 'center' }}>
                <div style={{
                  width: 30, height: 30, borderRadius: '50%', margin: '0 auto 6px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 600,
                  background: done ? '#10b981' : active ? '#3b82f6' : 'rgba(255,255,255,.05)',
                  color: done || active ? '#fff' : '#475569',
                  border: `2px solid ${done ? '#10b981' : active ? '#3b82f6' : 'rgba(255,255,255,.1)'}`,
                }}>
                  {done ? '✓' : s.id}
                </div>
                <div style={{ fontSize: 11, fontWeight: active ? 600 : 400, color: active ? '#e2e8f0' : '#475569' }}>
                  {s.label}
                </div>
              </div>
              {i < STEPS.length - 1 && <div style={{ width: 20, height: 2, background: done ? '#10b981' : 'rgba(255,255,255,.1)' }} />}
            </div>
          );
        })}
      </div>

      {error && (
        <div style={{ background: '#7f1d1d', color: '#fca5a5', padding: '12px 16px', borderRadius: 8, marginBottom: 20, fontSize: 13, border: '1px solid #991b1b' }}>
          <strong>Lỗi:</strong> {error}
        </div>
      )}

      {/* Main Panel */}
      <div style={{ background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 12, padding: 20 }}>
        
        {/* Step 1 */}
        {step === 1 && (
          <div className="fade-in">
            <h3 style={{ fontSize: 16, color: '#e2e8f0', marginBottom: 16, textAlign: 'center' }}>Bước 1: Chọn môi trường &amp; Part</h3>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginBottom: 16 }}>
              {Object.entries(SITES).map(([k, s]) => (
                <button key={k} onClick={() => setSelKey(k)} style={{
                  padding: '8px 16px', borderRadius: 8, background: selKey === k ? s.color : 'transparent',
                  color: selKey === k ? '#fff' : '#94a3b8', border: `1px solid ${s.color}`, cursor: 'pointer'
                }}>
                  {s.name} ({s.strategy})
                </button>
              ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 20, maxWidth: 600, margin: '0 auto 20px' }}>
              <div>
                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Part</div>
                <select value={selPart} onChange={e => setSelPart(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 6, background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155', fontSize: 12 }}>
                  <option value="">-- Chọn --</option>
                  {parts.map(p => <option key={p.part_id} value={p.part_id}>{p.part_id} (v{p.version})</option>)}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Kỹ sư A sửa thành</div>
                <input value={userAChange} onChange={e => setUserAChange(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 6, background: '#0f172a', color: '#60a5fa', border: '1px solid #334155', fontSize: 12, fontFamily: 'monospace' }} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Kỹ sư B sửa thành</div>
                <input value={userBChange} onChange={e => setUserBChange(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 6, background: '#0f172a', color: '#a78bfa', border: '1px solid #334155', fontSize: 12, fontFamily: 'monospace' }} />
              </div>
            </div>

            <div style={{ textAlign: 'center' }}>
              <button onClick={handleCheckout} disabled={!selPart || loading}
                style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '10px 24px', borderRadius: 8, fontWeight: 500, cursor: 'pointer', opacity: (!selPart || loading) ? 0.5 : 1 }}>
                {loading ? 'Đang Checkout...' : '2 Kỹ sư cùng Checkout →'}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Both checked out */}
        {step === 2 && (
          <div className="fade-in">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
              <div style={{ background: 'rgba(59,130,246,.1)', border: '1px solid rgba(59,130,246,.3)', padding: 16, borderRadius: 8 }}>
                <h4 style={{ color: '#60a5fa', marginBottom: 8 }}>👨‍💻 Kỹ sư A</h4>
                <p style={{ fontSize: 13, color: '#94a3b8' }}>Đã tải về: <strong>{selPart} v{userAModel?.version}</strong></p>
                <p style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
                  Sẽ sửa material → <span style={{ color: '#60a5fa', fontFamily: 'monospace' }}>"{userAChange}"</span>
                </p>
                <button onClick={handleUserACheckin} disabled={loading} style={{ marginTop: 12, background: '#3b82f6', color: '#fff', padding: '8px 16px', borderRadius: 6, border: 'none', cursor: 'pointer' }}>
                  Sửa &amp; Checkin ngay
                </button>
              </div>
              <div style={{ background: 'rgba(139,92,246,.1)', border: '1px solid rgba(139,92,246,.3)', padding: 16, borderRadius: 8, opacity: 0.6 }}>
                <h4 style={{ color: '#a78bfa', marginBottom: 8 }}>👨‍💻 Kỹ sư B</h4>
                <p style={{ fontSize: 13, color: '#94a3b8' }}>Cũng đang giữ: <strong>{selPart} v{userBModel?.version}</strong></p>
                <p style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
                  Sẽ sửa material → <span style={{ color: '#a78bfa', fontFamily: 'monospace' }}>"{userBChange}"</span>
                </p>
                <p style={{ fontSize: 11, color: '#475569', marginTop: 8 }}>(Chờ Kỹ sư A checkin trước)</p>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: A succeeded, B's turn */}
        {step === 3 && (
          <div className="fade-in">
            <div style={{ background: 'rgba(16,185,129,.1)', border: '1px solid rgba(16,185,129,.3)', padding: 16, borderRadius: 8, marginBottom: 20 }}>
              <div style={{ color: '#34d399', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8 }}>
                <CheckCircle size={18} /> Kỹ sư A checkin thành công!
              </div>
              {checkinResultA && (
                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 8, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                  {[
                    { label: 'Version', value: `v${checkinResultA.version_before} → v${checkinResultA.version_after}` },
                    { label: 'Branch', value: checkinResultA.branch },
                    { label: 'SHA-256', value: checkinResultA.checksum_after?.substring(0, 12) + '...' },
                    { label: 'WAL Entries', value: checkinResultA.wal_entry_count },
                  ].map(({ label, value }) => (
                    <div key={label} style={{ background: 'rgba(255,255,255,.05)', borderRadius: 4, padding: '4px 8px' }}>
                      <div style={{ fontSize: 10, color: '#475569' }}>{label}</div>
                      <div style={{ fontSize: 12, fontWeight: 500, color: '#e2e8f0' }}>{value}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div style={{ background: 'rgba(139,92,246,.1)', border: '1px solid rgba(139,92,246,.3)', padding: 16, borderRadius: 8 }}>
              <h4 style={{ color: '#a78bfa', marginBottom: 8 }}>👨‍💻 Kỹ sư B — Bây giờ checkin</h4>
              <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 4 }}>
                Vẫn đang giữ bản cũ (v{userBModel?.version}). Server đã lên v{checkinResultA?.version_after}.
              </p>
              <p style={{ fontSize: 12, color: '#f59e0b', marginBottom: 12 }}>
                ⚠ base_version ({userBModel?.version}) &lt; current_version ({checkinResultA?.version_after}) → XUNG ĐỘT!
              </p>
              <button onClick={handleUserBCheckin} disabled={loading} style={{ background: '#8b5cf6', color: '#fff', padding: '8px 16px', borderRadius: 6, border: 'none', cursor: 'pointer' }}>
                Cố tình Checkin (Tạo Xung đột) 💥
              </button>
            </div>
          </div>
        )}

        {/* Step 5: Conflict Result */}
        {step === 5 && (
          <div className="fade-in">
            <div style={{ textAlign: 'center', marginBottom: 20 }}>
              <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 56, height: 56, borderRadius: '50%', background: 'rgba(245,158,11,.1)', color: '#fbbf24', marginBottom: 12 }}>
                <AlertTriangle size={28} />
              </div>
              <h3 style={{ fontSize: 18, color: '#fbbf24', marginBottom: 4 }}>XUNG ĐỘT PHÁT HIỆN &amp; GIẢI QUYẾT!</h3>
              <p style={{ fontSize: 13, color: '#94a3b8' }}>Chiến lược: <strong style={{ color: '#e2e8f0' }}>{siteMeta.strategy}</strong></p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
              {/* User A Result */}
              <div style={{ background: 'rgba(59,130,246,.05)', border: '1px solid rgba(59,130,246,.2)', borderRadius: 8, padding: 16 }}>
                <h4 style={{ fontSize: 13, color: '#60a5fa', marginBottom: 10 }}>Kỹ sư A — {checkinResultA?.message?.includes('XUNG DOT') ? 'Bị ghi đè' : 'Thành công'}</h4>
                {checkinResultA && (
                  <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.8 }}>
                    Version: v{checkinResultA.version_before} → <strong>v{checkinResultA.version_after}</strong><br/>
                    Branch: <span style={{ color: '#60a5fa' }}>{checkinResultA.branch}</span><br/>
                    Material: <code style={{ color: '#60a5fa' }}>{userAChange}</code><br/>
                    Checksum: <code style={{ fontSize: 10 }}>{checkinResultA.checksum_after?.substring(0, 16)}...</code>
                  </div>
                )}
              </div>

              {/* User B Result */}
              <div style={{ background: 'rgba(139,92,246,.05)', border: '1px solid rgba(139,92,246,.2)', borderRadius: 8, padding: 16 }}>
                <h4 style={{ fontSize: 13, color: '#a78bfa', marginBottom: 10 }}>Kỹ sư B — {checkinResultB?.is_conflict ? '⚡ Conflict Resolved' : 'Thành công'}</h4>
                {checkinResultB && (
                  <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.8 }}>
                    Version: v{checkinResultB.version_before} → <strong>v{checkinResultB.version_after}</strong><br/>
                    Branch: <span style={{ color: '#a78bfa' }}>{checkinResultB.branch}</span><br/>
                    Material: <code style={{ color: '#a78bfa' }}>{userBChange}</code><br/>
                    Checksum: <code style={{ fontSize: 10 }}>{checkinResultB.checksum_after?.substring(0, 16)}...</code>
                  </div>
                )}
              </div>
            </div>

            {/* Resolution Analysis */}
            <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, padding: 16, marginBottom: 20 }}>
              <h4 style={{ fontSize: 13, color: '#e2e8f0', marginBottom: 12 }}>📊 Phân tích kết quả</h4>
              <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.8 }}>
                {siteMeta.strategy.toLowerCase() === 'branching' ? (
                  <>
                    <strong style={{ color: '#10b981' }}>Branching Strategy:</strong> Server tách bản của Kỹ sư B thành nhánh riêng.<br/>
                    • Kỹ sư A → branch: <code style={{ color: '#60a5fa' }}>{checkinResultA?.branch}</code> (v{checkinResultA?.version_after})<br/>
                    • Kỹ sư B → branch: <code style={{ color: '#a78bfa' }}>{checkinResultB?.branch}</code> (v{checkinResultB?.version_after})<br/>
                    • <strong style={{ color: '#10b981' }}>Không mất dữ liệu</strong> — cả hai bản đều được lưu. Có thể merge sau.
                  </>
                ) : (
                  <>
                    <strong style={{ color: '#f59e0b' }}>Timestamp (Last-Write-Wins) Strategy:</strong> Server cho phép checkin sau ghi đè.<br/>
                    • Kỹ sư A → v{checkinResultA?.version_after} (main) — <span style={{ color: '#f59e0b' }}>có thể bị ghi đè</span><br/>
                    • Kỹ sư B → v{checkinResultB?.version_after} (main) — <span style={{ color: '#10b981' }}>bản mới nhất</span><br/>
                    • <strong style={{ color: '#f59e0b' }}>Cảnh báo:</strong> Thay đổi của Kỹ sư A có thể bị mất.
                  </>
                )}
              </div>
            </div>

            {/* Version Tree */}
            {versionTree.length > 0 && (
              <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, padding: 16, marginBottom: 20 }}>
                <h4 style={{ fontSize: 13, color: '#e2e8f0', marginBottom: 12 }}>🌳 Version Tree — {selPart}</h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {versionTree.map((v, i) => (
                    <div key={i} style={{
                      padding: '6px 12px', borderRadius: 6, fontSize: 11,
                      background: v.branch === 'main' ? 'rgba(16,185,129,.1)' : 'rgba(245,158,11,.1)',
                      border: `1px solid ${v.branch === 'main' ? 'rgba(16,185,129,.3)' : 'rgba(245,158,11,.3)'}`,
                      color: v.branch === 'main' ? '#34d399' : '#fbbf24',
                    }}>
                      v{v.version} · {v.branch}
                    </div>
                  ))}
                </div>
                <div style={{ fontSize: 11, color: '#475569', marginTop: 8 }}>
                  Branches: {[...new Set(versionTree.map(v => v.branch))].join(', ')}
                </div>
              </div>
            )}

            {/* Server Response */}
            <details style={{ marginBottom: 16 }}>
              <summary style={{ fontSize: 12, color: '#64748b', cursor: 'pointer' }}>
                📄 Raw Server Response (B)
              </summary>
              <pre style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 6, padding: 12, fontSize: 11, color: '#94a3b8', marginTop: 8, overflow: 'auto' }}>
                {JSON.stringify(checkinResultB, null, 2)}
              </pre>
            </details>

            <button onClick={resetDemo} style={{ background: 'transparent', color: '#94a3b8', border: '1px solid #475569', padding: '8px 20px', borderRadius: 8, cursor: 'pointer' }}>
              Thử lại từ đầu ↻
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
