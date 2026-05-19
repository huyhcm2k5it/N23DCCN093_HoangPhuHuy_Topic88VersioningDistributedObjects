import { useState, useEffect } from 'react';
import { listModels, checkout, checkin, getVersions, getCheckouts, SITES } from '../api';

const SITE_OPTIONS = Object.entries(SITES).map(([key, s]) => ({
  key,
  label: `${s.name} — ${s.label} (${s.strategy})`,
  color: s.color,
}));

export default function TabWorkspace({ onRefresh }) {
  const [parts,      setParts]      = useState([]);
  const [selPart,    setSelPart]    = useState('');
  const [selSiteKey, setSelSiteKey] = useState('a');
  const [status,     setStatus]     = useState('idle');
  const [checkedOut, setCheckedOut] = useState(null);
  const [editJson,   setEditJson]   = useState('');
  const [jsonError,  setJsonError]  = useState(null);
  const [message,    setMessage]    = useState(null);
  const [loadingParts, setLoadingParts] = useState(true);

  // Data sau checkin
  const [checkinResult, setCheckinResult] = useState(null);
  const [versionHistory, setVersionHistory] = useState([]);
  const [activeCheckouts, setActiveCheckouts] = useState([]);

  useEffect(() => {
    setLoadingParts(true);
    Promise.all([
      listModels(selSiteKey).then(d => setParts(d.models || [])).catch(() => setParts([])),
      getCheckouts(selSiteKey).then(d => setActiveCheckouts(d.checkouts || [])).catch(() => setActiveCheckouts([])),
    ]).finally(() => setLoadingParts(false));
  }, [selSiteKey]);

  async function handleCheckout() {
    if (!selPart) return;
    setStatus('submitting'); setMessage(null); setCheckinResult(null);
    try {
      const data = await checkout(selSiteKey, selPart, 'ky_su_demo');
      setCheckedOut(data);
      setEditJson(JSON.stringify(data.geometry, null, 2));
      // Refresh active checkouts
      getCheckouts(selSiteKey).then(d => setActiveCheckouts(d.checkouts || [])).catch(() => {});
      setStatus('checked_out');
    } catch (e) {
      setMessage({ type: 'error', text: `Checkout thất bại: ${e.message}` });
      setStatus('idle');
    }
  }

  async function handleCheckin() {
    setJsonError(null);
    let geo;
    try { geo = JSON.parse(editJson); }
    catch { setJsonError('JSON không hợp lệ — kiểm tra lại cú pháp'); return; }

    setStatus('submitting'); setMessage(null);
    try {
      const model = { ...checkedOut, geometry: geo };
      const res = await checkin(selSiteKey, selPart, 'ky_su_demo', model);

      if (res._status === 500) {
        setStatus('error');
        setMessage({ type: 'error', text: res.message || '💥 Coordinator crashed!' });
        return;
      }

      setCheckinResult(res);

      if (res.success) {
        // Fetch version history
        try {
          const versions = await getVersions(selSiteKey, selPart);
          setVersionHistory(versions || []);
        } catch { setVersionHistory([]); }

        const isConflict = res.is_conflict;
        setStatus(isConflict ? 'conflict' : 'success');
        setMessage({ type: 'success', text: res.message || 'Checkin thành công' });
        setCheckedOut(null);
        // Refresh checkouts list
        getCheckouts(selSiteKey).then(d => setActiveCheckouts(d.checkouts || [])).catch(() => {});
        onRefresh?.();
      } else {
        setStatus('error');
        setMessage({ type: 'error', text: res.message || 'Checkin thất bại' });
      }
    } catch (e) {
      setStatus('error');
      setMessage({ type: 'error', text: e.message });
    }
  }

  function handleReset() {
    setStatus('idle'); setCheckedOut(null);
    setEditJson(''); setMessage(null); setJsonError(null);
    setSelPart(''); setCheckinResult(null); setVersionHistory([]);
  }

  return (
    <div style={{ color: '#111' }}>
      <h2 style={{ fontSize: 20, fontWeight: 500, marginBottom: 20, color: '#e2e8f0' }}>Workspace — Checkout / Checkin</h2>

      {/* Alert */}
      {message && (
        <div style={{
          background: message.type === 'success' ? '#EAF3DE' : '#FCEBEB',
          border: `0.5px solid ${message.type === 'success' ? '#C0DD97' : '#f09595'}`,
          borderRadius: 8, padding: '10px 14px', marginBottom: 16, fontSize: 13,
          color: message.type === 'success' ? '#3B6D11' : '#A32D2D',
        }}>
          {message.text}
        </div>
      )}

      {/* Step 1: Chon Part & Site */}
      {status === 'idle' && (
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20 }}>
          <div style={{ background: '#fff', border: '0.5px solid #e0e0de', borderRadius: 12, padding: '20px 24px' }}>
            <h3 style={{ fontSize: 15, fontWeight: 500, marginBottom: 16, color: '#111' }}>
              Bước 1 — Chọn Part &amp; Site
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
              <div>
                <div style={{ fontSize: 12, color: '#888', marginBottom: 6 }}>Site thực hiện</div>
                <select value={selSiteKey} onChange={e => { setSelSiteKey(e.target.value); setSelPart(''); }}
                  style={{ width: '100%', padding: '8px 10px', fontSize: 13, border: '0.5px solid #ccc', borderRadius: 7, background: '#fafafa', color: '#111' }}>
                  {SITE_OPTIONS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#888', marginBottom: 6 }}>
                  Part {loadingParts ? '(đang tải...)' : `(${parts.length} parts)`}
                </div>
                <select value={selPart} onChange={e => setSelPart(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', fontSize: 13, border: '0.5px solid #ccc', borderRadius: 7, background: '#fafafa', color: '#111' }}>
                  <option value="">-- Chọn Part --</option>
                  {parts.map(p => (
                    <option key={p.part_id} value={p.part_id}>
                      {p.part_id} (v{p.version}){p.locked_by ? ` 🔒 ${p.locked_by}` : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <button onClick={handleCheckout} disabled={!selPart}
              style={{ background: selPart ? '#185FA5' : '#ccc', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 24px', fontSize: 14, cursor: selPart ? 'pointer' : 'not-allowed' }}>
              Checkout →
            </button>
          </div>

          {/* Active Checkouts panel */}
          <div style={{ background: '#fff', border: '0.5px solid #e0e0de', borderRadius: 12, padding: '16px 20px' }}>
            <h4 style={{ fontSize: 13, fontWeight: 500, color: '#111', marginBottom: 12 }}>
              🔒 Active Checkouts — {SITES[selSiteKey]?.name}
            </h4>
            {activeCheckouts.length === 0 ? (
              <div style={{ fontSize: 12, color: '#aaa', textAlign: 'center', padding: '20px 0' }}>
                Chưa có checkout nào
              </div>
            ) : (
              activeCheckouts.map((c, i) => (
                <div key={i} style={{ background: '#fffdf8', border: '0.5px solid #e8e0cc', borderRadius: 6, padding: '8px 12px', marginBottom: 8, fontSize: 12 }}>
                  <div style={{ fontWeight: 500 }}>{c.part_id} · v{c.base_version}</div>
                  <div style={{ color: '#888' }}>User: {c.user} · {c.checkout_time ? new Date(c.checkout_time).toLocaleTimeString() : ''}</div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Step 2: Edit geometry */}
      {status === 'checked_out' && checkedOut && (
        <div style={{ background: '#fff', border: '0.5px solid #e0e0de', borderRadius: 12, padding: '20px 24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <div>
              <h3 style={{ fontSize: 15, fontWeight: 500, color: '#111' }}>Bước 2 — Chỉnh sửa Geometry</h3>
              <div style={{ fontSize: 12, color: '#888', marginTop: 3 }}>
                {checkedOut.part_id} · v{checkedOut.version} · {SITES[selSiteKey]?.name} · branch: {checkedOut.branch}
              </div>
            </div>
            <span style={{ background: '#FAEEDA', color: '#854F0B', borderRadius: 6, padding: '4px 12px', fontSize: 12, fontWeight: 500 }}>
              🔒 Đang giữ lock
            </span>
          </div>

          {/* Part metadata */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 16 }}>
            {[
              { label: 'OID', value: checkedOut.oid?.substring(0, 12) + '...' },
              { label: 'Version', value: `v${checkedOut.version}` },
              { label: 'Branch', value: checkedOut.branch },
              { label: 'Site Origin', value: checkedOut.site_origin },
            ].map(({ label, value }) => (
              <div key={label} style={{ background: '#f9f9f7', borderRadius: 6, padding: '6px 10px', border: '0.5px solid #e0e0de' }}>
                <div style={{ fontSize: 10, color: '#888', fontFamily: 'monospace' }}>{label}</div>
                <div style={{ fontSize: 12, fontWeight: 500, color: '#333' }}>{value}</div>
              </div>
            ))}
          </div>

          <div style={{ fontSize: 12, color: '#888', marginBottom: 6 }}>
            Geometry JSON — sửa trực tiếp (vertices, edges, faces, properties)
          </div>
          <textarea value={editJson} onChange={e => { setEditJson(e.target.value); setJsonError(null); }}
            rows={14} style={{
              width: '100%', fontFamily: 'monospace', fontSize: 12,
              border: `0.5px solid ${jsonError ? '#f09595' : '#ccc'}`,
              borderRadius: 8, padding: '10px 12px', background: '#fafaf8',
              color: '#111', resize: 'vertical', lineHeight: 1.6,
            }} />
          {jsonError && <div style={{ color: '#A32D2D', fontSize: 12, marginTop: 6 }}>⚠ {jsonError}</div>}

          <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
            <button onClick={handleCheckin}
              style={{ background: '#185FA5', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 24px', fontSize: 14, cursor: 'pointer' }}>
              Checkin →
            </button>
            <button onClick={handleReset}
              style={{ background: 'transparent', border: '0.5px solid #ccc', borderRadius: 8, padding: '10px 20px', fontSize: 14, cursor: 'pointer', color: '#666' }}>
              Huỷ
            </button>
          </div>
        </div>
      )}

      {status === 'submitting' && (
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#888', fontSize: 14 }}>
          ⏳ Đang xử lý...
        </div>
      )}

      {/* Checkin Result Panel */}
      {['success', 'conflict', 'error'].includes(status) && checkinResult && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {/* Left: Audit Trail */}
          <div style={{ background: '#fff', border: '0.5px solid #e0e0de', borderRadius: 12, padding: '20px 24px' }}>
            <h4 style={{ fontSize: 14, fontWeight: 500, color: '#111', marginBottom: 16 }}>📋 Transaction Audit Trail</h4>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
              {[
                { label: 'Version trước', value: `v${checkinResult.version_before}`, color: '#888' },
                { label: 'Version sau', value: `v${checkinResult.version_after}`, color: '#3B6D11' },
                { label: 'Branch', value: checkinResult.branch, color: '#185FA5' },
                { label: 'Conflict?', value: checkinResult.is_conflict ? `✓ ${checkinResult.conflict_strategy}` : '✗ Không', color: checkinResult.is_conflict ? '#A32D2D' : '#3B6D11' },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ background: '#f9f9f7', borderRadius: 6, padding: '8px 12px', border: '0.5px solid #e0e0de' }}>
                  <div style={{ fontSize: 10, color: '#888' }}>{label}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color }}>{value}</div>
                </div>
              ))}
            </div>

            {/* Checksum verification */}
            <div style={{ background: '#f0f7ff', border: '0.5px solid #b3d4fc', borderRadius: 6, padding: '10px 12px', marginBottom: 16, fontSize: 11, fontFamily: 'monospace' }}>
              <div style={{ color: '#185FA5', fontWeight: 500, marginBottom: 4 }}>SHA-256 Integrity</div>
              <div style={{ color: '#888' }}>Before: {checkinResult.checksum_before?.substring(0, 24)}...</div>
              <div style={{ color: '#333' }}>After:  {checkinResult.checksum_after?.substring(0, 24)}...</div>
              <div style={{ color: '#3B6D11', marginTop: 4 }}>
                {checkinResult.checksum_before !== checkinResult.checksum_after
                  ? '✓ Checksum thay đổi — dữ liệu đã cập nhật'
                  : '⚠ Checksum giống nhau'}
              </div>
            </div>

            <div style={{ fontSize: 12, color: '#888' }}>
              Branches: {checkinResult.all_branches?.join(', ')} · 
              Total versions: {checkinResult.total_versions} · 
              WAL entries: {checkinResult.wal_entry_count}
            </div>
          </div>

          {/* Right: Version History */}
          <div style={{ background: '#fff', border: '0.5px solid #e0e0de', borderRadius: 12, padding: '20px 24px' }}>
            <h4 style={{ fontSize: 14, fontWeight: 500, color: '#111', marginBottom: 16 }}>📊 Version History — {selPart}</h4>
            {versionHistory.length === 0 ? (
              <div style={{ color: '#aaa', fontSize: 12 }}>Không có dữ liệu</div>
            ) : (
              <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                {versionHistory.map((v, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '8px 12px', borderRadius: 6, marginBottom: 4,
                    background: v.version === checkinResult.version_after && v.branch === checkinResult.branch
                      ? '#EAF3DE' : '#f9f9f7',
                    border: `0.5px solid ${v.version === checkinResult.version_after && v.branch === checkinResult.branch ? '#C0DD97' : '#e0e0de'}`,
                  }}>
                    {/* Version dot */}
                    <div style={{
                      width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                      background: v.branch === 'main' ? '#3B6D11' : '#854F0B',
                    }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, fontWeight: 500, color: '#111' }}>
                        v{v.version}
                        <span style={{ fontSize: 10, color: '#888', marginLeft: 8 }}>
                          branch: {v.branch}
                        </span>
                      </div>
                      <div style={{ fontSize: 10, color: '#aaa' }}>
                        {v.modified_at ? new Date(v.modified_at).toLocaleString() : ''}
                        {v.oid && ` · OID: ${v.oid.substring(0, 8)}...`}
                      </div>
                    </div>
                    {v.version === checkinResult.version_after && v.branch === checkinResult.branch && (
                      <span style={{ fontSize: 10, color: '#3B6D11', fontWeight: 600 }}>← MỚI</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Reset button */}
      {['success', 'conflict', 'error'].includes(status) && (
        <button onClick={handleReset}
          style={{ background: '#185FA5', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 22px', fontSize: 14, cursor: 'pointer', marginTop: 16 }}>
          ← Bắt đầu lại
        </button>
      )}
    </div>
  );
}