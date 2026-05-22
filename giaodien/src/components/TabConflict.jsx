import { useState, useEffect } from 'react';
import {
  SITES,
  PREFIX_BY_SITE_KEY,
  checkout,
  checkin,
  createModel,
  getModel,
  getVersions,
  listModels,
  replicate,
} from '../api';
import { createPyramidDemoGeometry } from '../demoGeometry';
import { AlertTriangle, CheckCircle, GitPullRequest, Network, RefreshCw } from 'lucide-react';

const STEPS = [
  { id: 1, label: 'Setup' },
  { id: 2, label: 'Checkout 2 sites' },
  { id: 3, label: 'Source checkin' },
  { id: 4, label: 'Sync latest' },
  { id: 5, label: 'Resolve conflict' },
];

function mutateModel(model, material, deltaX) {
  const next = JSON.parse(JSON.stringify(model));
  next.geometry.properties = {
    ...next.geometry.properties,
    material,
    edited_by: material.includes('source') ? 'source_site' : 'target_site',
  };
  if (next.geometry.vertices?.length) {
    next.geometry.vertices[0].x = Number((next.geometry.vertices[0].x + deltaX).toFixed(2));
  }
  return next;
}

function otherSiteKey(key) {
  return key === 'a' ? 'b' : 'a';
}

export default function TabConflict({ onRefresh }) {
  const [sourceKey, setSourceKey] = useState('a');
  const [targetKey, setTargetKey] = useState('b');
  const [sourceParts, setSourceParts] = useState([]);
  const [useFreshPart, setUseFreshPart] = useState(true);
  const [selectedPart, setSelectedPart] = useState('');
  const [activePart, setActivePart] = useState('');
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [sourceMaterial, setSourceMaterial] = useState('source_carbon_fiber');
  const [targetMaterial, setTargetMaterial] = useState('target_titanium_alloy');
  const [sourceCheckout, setSourceCheckout] = useState(null);
  const [targetCheckout, setTargetCheckout] = useState(null);
  const [targetSeed, setTargetSeed] = useState(null);
  const [sourceResult, setSourceResult] = useState(null);
  const [syncResult, setSyncResult] = useState(null);
  const [targetResult, setTargetResult] = useState(null);
  const [versionTree, setVersionTree] = useState([]);

  useEffect(() => {
    listModels(sourceKey).then(d => setSourceParts(d.models || [])).catch(() => setSourceParts([]));
    setSelectedPart('');
    resetRun();
  }, [sourceKey]);

  function resetRun() {
    setStep(1);
    setError(null);
    setActivePart('');
    setSourceCheckout(null);
    setTargetCheckout(null);
    setTargetSeed(null);
    setSourceResult(null);
    setSyncResult(null);
    setTargetResult(null);
    setVersionTree([]);
  }

  function changeSource(key) {
    setSourceKey(key);
    if (key === targetKey) setTargetKey(otherSiteKey(key));
  }

  function changeTarget(key) {
    setTargetKey(key === sourceKey ? otherSiteKey(sourceKey) : key);
    resetRun();
  }

  async function prepareCrossSiteCheckout() {
    if (!useFreshPart && !selectedPart) {
      setError('Chon part co san hoac dung che do tao demo object moi.');
      return;
    }
    if (sourceKey === targetKey) {
      setError('Source site va target site phai khac nhau.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      let partId = selectedPart;
      if (useFreshPart) {
        const prefix = PREFIX_BY_SITE_KEY[sourceKey] || 'ENG';
        partId = `${prefix}-XDEMO-${Date.now()}`;
        const geometry = createPyramidDemoGeometry();
        geometry.properties.category = SITES[sourceKey].category;
        await createModel(sourceKey, partId, geometry);
      }

      await replicate(sourceKey, partId, SITES[targetKey].site_id);
      const targetLatest = await getModel(targetKey, partId);
      const sourceModel = await checkout(sourceKey, partId, 'Engineer_Source');
      const targetModel = await checkout(targetKey, partId, 'Engineer_Target');

      setActivePart(partId);
      setSourceCheckout(sourceModel);
      setTargetCheckout(targetModel);
      setTargetSeed(targetLatest);
      setStep(2);

      if (useFreshPart) {
        listModels(sourceKey).then(d => setSourceParts(d.models || [])).catch(() => {});
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function sourceCheckin() {
    setLoading(true);
    setError(null);
    try {
      const modified = mutateModel(sourceCheckout, sourceMaterial, 40);
      const res = await checkin(sourceKey, activePart, 'Engineer_Source', modified);
      if (res._status >= 400 || !res.success) throw new Error(res.message || 'Source checkin failed');
      setSourceResult(res);
      setStep(3);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function syncLatestToTarget() {
    setLoading(true);
    setError(null);
    try {
      const rep = await replicate(sourceKey, activePart, SITES[targetKey].site_id);
      const targetLatest = await getModel(targetKey, activePart);
      setSyncResult({ ...rep, target_version: targetLatest.version, target_oid: targetLatest.oid });
      setStep(4);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function targetCheckinOldCopy() {
    setLoading(true);
    setError(null);
    try {
      const modified = mutateModel(targetCheckout, targetMaterial, -35);
      const res = await checkin(targetKey, activePart, 'Engineer_Target', modified);
      if (res._status >= 500) throw new Error(res.message || 'Target checkin failed');
      setTargetResult(res);
      try {
        const versions = await getVersions(targetKey, activePart);
        setVersionTree(versions || []);
      } catch {
        setVersionTree([]);
      }
      setStep(5);
      onRefresh?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const sourceSite = SITES[sourceKey];
  const targetSite = SITES[targetKey];
  const oidMatches = sourceCheckout?.oid && targetCheckout?.oid && sourceCheckout.oid === targetCheckout.oid;
  return (
    <div style={{ color: '#e2e8f0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <Network size={20} color="#60a5fa" />
        <h2 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>Cross-site Conflict Demo</h2>
      </div>
      <p style={{ fontSize: 13, color: '#64748b', marginBottom: 24 }}>
        Hai site checkout cung mot object co cung OID. Source site checkin truoc, dong bo version moi sang target site,
        sau do target site checkin ban cu de kich hoat OCC conflict resolution dung yeu cau Topic 88.
      </p>

      <div style={{ display: 'flex', gap: 0, marginBottom: 24, overflowX: 'auto' }}>
        {STEPS.map((s, index) => {
          const done = step > s.id;
          const active = step === s.id;
          return (
            <div key={s.id} style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 120 }}>
              <div style={{ flex: 1, textAlign: 'center' }}>
                <div style={{
                  width: 30,
                  height: 30,
                  borderRadius: '50%',
                  margin: '0 auto 6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 12,
                  fontWeight: 700,
                  background: done ? '#10b981' : active ? '#3b82f6' : 'rgba(255,255,255,.05)',
                  border: `1px solid ${done ? '#10b981' : active ? '#3b82f6' : 'rgba(255,255,255,.12)'}`,
                  color: done || active ? '#fff' : '#64748b',
                }}>
                  {done ? 'OK' : s.id}
                </div>
                <div style={{ fontSize: 11, color: active ? '#e2e8f0' : '#64748b' }}>{s.label}</div>
              </div>
              {index < STEPS.length - 1 && (
                <div style={{ width: 22, height: 2, background: done ? '#10b981' : 'rgba(255,255,255,.1)' }} />
              )}
            </div>
          );
        })}
      </div>

      {error && (
        <div style={{ background: '#7f1d1d', color: '#fecaca', padding: '12px 16px', borderRadius: 8, marginBottom: 18, fontSize: 13, border: '1px solid #991b1b' }}>
          <strong>Loi:</strong> {error}
        </div>
      )}

      <div style={{ background: 'rgba(255,255,255,.025)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 10, padding: 20 }}>
        {step === 1 && (
          <div className="fade-in">
            <h3 style={{ fontSize: 16, marginBottom: 16 }}>1. Chon 2 site va object demo</h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 18 }}>
              <SitePicker title="Source site" value={sourceKey} onChange={changeSource} />
              <SitePicker title="Target site conflict resolver" value={targetKey} onChange={changeTarget} exclude={sourceKey} />
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#cbd5e1', marginBottom: 14 }}>
              <input type="checkbox" checked={useFreshPart} onChange={e => { setUseFreshPart(e.target.checked); resetRun(); }} />
              Tao object demo moi moi lan chay de tranh du lieu cu anh huong ket qua
            </label>

            {!useFreshPart && (
              <div style={{ maxWidth: 420, marginBottom: 18 }}>
                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Source part</div>
                <select value={selectedPart} onChange={e => setSelectedPart(e.target.value)}
                  style={{ width: '100%', padding: '9px 10px', borderRadius: 6, background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155', fontSize: 12 }}>
                  <option value="">-- Chon part tu {sourceSite.name} --</option>
                  {sourceParts.map(p => <option key={p.part_id} value={p.part_id}>{p.part_id} (v{p.version})</option>)}
                </select>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 18 }}>
              <TextInput label="Source material change" value={sourceMaterial} onChange={setSourceMaterial} color="#60a5fa" />
              <TextInput label="Target material change" value={targetMaterial} onChange={setTargetMaterial} color="#a78bfa" />
            </div>

            <button onClick={prepareCrossSiteCheckout} disabled={loading}
              style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '10px 18px', borderRadius: 8, fontWeight: 600, cursor: 'pointer', opacity: loading ? 0.6 : 1 }}>
              {loading ? 'Dang chuan bi...' : 'Tao/replicate va checkout tren 2 site'}
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="fade-in">
            <h3 style={{ fontSize: 16, marginBottom: 16 }}>2. Hai site da checkout cung object</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 18 }}>
              <ModelCard title={`${sourceSite.name} checkout`} model={sourceCheckout} color="#60a5fa" />
              <ModelCard title={`${targetSite.name} checkout`} model={targetCheckout} color="#a78bfa" />
            </div>
            <div style={{ fontSize: 13, color: oidMatches ? '#34d399' : '#f87171', marginBottom: 18 }}>
              OID check: {oidMatches ? 'MATCH - cung mot distributed object' : 'MISMATCH - can kiem tra replication'}
            </div>
            <button onClick={sourceCheckin} disabled={loading}
              style={{ background: '#2563eb', color: '#fff', border: 'none', padding: '9px 16px', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
              {loading ? 'Dang checkin...' : `${sourceSite.name} checkin version moi`}
            </button>
          </div>
        )}

        {step === 3 && (
          <div className="fade-in">
            <ResultBanner ok text={`${sourceSite.name} da checkin thanh cong tren branch ${sourceResult?.branch}.`} />
            <MetricGrid items={[
              ['Part', activePart],
              ['Version', `v${sourceResult?.version_before} -> v${sourceResult?.version_after}`],
              ['Source branch', sourceResult?.branch],
              ['Checksum', `${sourceResult?.checksum_after?.slice(0, 14)}...`],
            ]} />
            <button onClick={syncLatestToTarget} disabled={loading}
              style={{ marginTop: 18, background: '#0f766e', color: '#fff', border: 'none', padding: '9px 16px', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
              {loading ? 'Dang replicate...' : `Replicate v${sourceResult?.version_after} sang ${targetSite.name}`}
            </button>
          </div>
        )}

        {step === 4 && (
          <div className="fade-in">
            <ResultBanner ok text={`${targetSite.name} da nhan version moi nhung Engineer_Target van giu ban checkout cu.`} />
            <MetricGrid items={[
              ['Target current', `v${syncResult?.target_version}`],
              ['Target old checkout', `v${targetCheckout?.version}`],
              ['OCC condition', `${targetCheckout?.version} < ${syncResult?.target_version}`],
              ['Target strategy', targetSite.strategy],
            ]} />
            <button onClick={targetCheckinOldCopy} disabled={loading}
              style={{ marginTop: 18, background: '#7c3aed', color: '#fff', border: 'none', padding: '9px 16px', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
              {loading ? 'Dang tao conflict...' : `${targetSite.name} checkin ban cu de tao conflict`}
            </button>
          </div>
        )}

        {step === 5 && (
          <div className="fade-in">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, color: targetResult?.is_conflict ? '#fbbf24' : '#f87171' }}>
              <AlertTriangle size={22} />
              <h3 style={{ fontSize: 17, margin: 0 }}>
                {targetResult?.is_conflict ? 'Conflict detected and resolved' : 'No conflict detected'}
              </h3>
            </div>
            <MetricGrid items={[
              ['Resolver site', targetSite.name],
              ['Strategy', targetResult?.conflict_strategy || targetSite.strategy],
              ['Version', `v${targetResult?.version_before} -> v${targetResult?.version_after}`],
              ['Branch', targetResult?.branch],
            ]} />

            <div style={{ marginTop: 16, background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, padding: 14, fontSize: 13, color: '#94a3b8', lineHeight: 1.7 }}>
              <strong style={{ color: '#34d399' }}>Branching:</strong> target site tao branch rieng cho ban checkin muon.
              Du lieu cua source va target deu duoc giu lai, dung yeu cau Topic 88 va khong overwrite im lang.
            </div>

            {versionTree.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <h4 style={{ fontSize: 13, marginBottom: 10 }}>Version tree tai {targetSite.name}</h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {versionTree.map((v, index) => (
                    <div key={`${v.version}-${v.branch}-${index}`} style={{
                      padding: '6px 10px',
                      borderRadius: 6,
                      fontSize: 11,
                      background: v.branch === 'main' ? 'rgba(16,185,129,.1)' : 'rgba(245,158,11,.1)',
                      border: `1px solid ${v.branch === 'main' ? 'rgba(16,185,129,.3)' : 'rgba(245,158,11,.3)'}`,
                      color: v.branch === 'main' ? '#34d399' : '#fbbf24',
                    }}>
                      v{v.version} | {v.branch}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <details style={{ marginTop: 16 }}>
              <summary style={{ fontSize: 12, color: '#64748b', cursor: 'pointer' }}>Raw target checkin response</summary>
              <pre style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: 6, padding: 12, color: '#94a3b8', fontSize: 11, overflow: 'auto' }}>
                {JSON.stringify(targetResult, null, 2)}
              </pre>
            </details>

            <button onClick={resetRun}
              style={{ marginTop: 16, background: 'transparent', color: '#94a3b8', border: '1px solid #475569', padding: '8px 16px', borderRadius: 8, cursor: 'pointer' }}>
              Chay lai demo
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function SitePicker({ title, value, onChange, exclude }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>{title}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {Object.entries(SITES).map(([key, site]) => {
          const disabled = exclude === key;
          return (
            <button key={key} disabled={disabled} onClick={() => onChange(key)}
              style={{
                padding: '8px 12px',
                borderRadius: 8,
                background: value === key ? site.color : 'transparent',
                color: value === key ? '#fff' : disabled ? '#475569' : '#94a3b8',
                border: `1px solid ${disabled ? '#334155' : site.color}`,
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.45 : 1,
              }}>
              {site.name} | {site.strategy}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function TextInput({ label, value, onChange, color }) {
  return (
    <label style={{ display: 'block' }}>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>{label}</div>
      <input value={value} onChange={e => onChange(e.target.value)}
        style={{ width: '100%', padding: '9px 10px', borderRadius: 6, background: '#0f172a', color, border: '1px solid #334155', fontSize: 12, fontFamily: 'monospace' }} />
    </label>
  );
}

function ModelCard({ title, model, color }) {
  return (
    <div style={{ background: 'rgba(15,23,42,.72)', border: `1px solid ${color}55`, borderRadius: 8, padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color, fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
        <GitPullRequest size={16} /> {title}
      </div>
      <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.8 }}>
        Part: <strong style={{ color: '#e2e8f0' }}>{model?.part_id}</strong><br />
        Version: <strong style={{ color: '#e2e8f0' }}>v{model?.version}</strong><br />
        Branch: <code>{model?.branch}</code><br />
        OID: <code style={{ fontSize: 10 }}>{model?.oid}</code>
      </div>
    </div>
  );
}

function ResultBanner({ ok, text }) {
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'center', background: ok ? 'rgba(16,185,129,.1)' : 'rgba(239,68,68,.1)', border: `1px solid ${ok ? 'rgba(16,185,129,.3)' : 'rgba(239,68,68,.3)'}`, borderRadius: 8, padding: 14, marginBottom: 14 }}>
      {ok ? <CheckCircle size={18} color="#34d399" /> : <AlertTriangle size={18} color="#f87171" />}
      <span style={{ fontSize: 13, color: ok ? '#bbf7d0' : '#fecaca' }}>{text}</span>
    </div>
  );
}

function MetricGrid({ items }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
      {items.map(([label, value]) => (
        <div key={label} style={{ background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.08)', borderRadius: 6, padding: '8px 10px', minWidth: 0 }}>
          <div style={{ color: '#64748b', fontSize: 10, marginBottom: 4 }}>{label}</div>
          <div style={{ color: '#e2e8f0', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{value}</div>
        </div>
      ))}
    </div>
  );
}
