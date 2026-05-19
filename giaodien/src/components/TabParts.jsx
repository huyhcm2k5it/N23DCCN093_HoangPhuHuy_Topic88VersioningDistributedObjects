import { useState } from 'react';
import { Search, Download, Upload, Clock, Tag, ChevronRight, X, CheckCircle, AlertCircle } from 'lucide-react';
import { checkout, checkin, getVersions } from '../api';

function PartDetail({ siteKey, site, part, onClose, onRefresh }) {
  const [versions, setVersions] = useState(null);
  const [user, setUser] = useState('engineer_demo');
  const [working, setWorking] = useState(false);
  const [msg, setMsg] = useState(null);

  const loadVersions = async () => {
    try {
      const v = await getVersions(siteKey, part.part_id);
      setVersions(v);
    } catch (e) { setMsg({ type:'error', text: e.message }); }
  };

  const doCheckout = async () => {
    setWorking(true); setMsg(null);
    try {
      const m = await checkout(siteKey, part.part_id, user);
      setMsg({ type:'success', text: `✅ Checkout v${m.version} thành công! Model đang được ${user} giữ.` });
      onRefresh();
    } catch (e) { setMsg({ type:'error', text: `❌ ${e.message}` }); }
    setWorking(false);
  };

  const doCheckin = async () => {
    setWorking(true); setMsg(null);
    try {
      const m = await checkout(siteKey, part.part_id, user);
      // Simulate small change
      if (m.geometry?.vertices?.length > 0) {
        m.geometry.vertices[0].x = +(m.geometry.vertices[0].x + (Math.random()*2-1)).toFixed(4);
      }
      if (m.geometry?.properties) {
        m.geometry.properties.weight_kg = +(Math.random() * 50).toFixed(2);
      }
      const r = await checkin(siteKey, part.part_id, user, m);
      const isConflict = r.message?.toLowerCase().includes('xung') || r.message?.toLowerCase().includes('nhanh') || r.message?.toLowerCase().includes('branch');
      setMsg({
        type: isConflict ? 'conflict' : 'success',
        text: r.message,
      });
      onRefresh();
    } catch (e) { setMsg({ type:'error', text: `❌ ${e.message}` }); }
    setWorking(false);
  };

  const props = part.geometry?.properties || {};
  const vCount = part.version;

  return (
    <div style={{ background:'#0d1b30', border:'1px solid rgba(59,130,246,.25)', borderRadius:12, padding:20 }} className="slide-in">
      <div className="flex justify-between items-start mb-4">
        <div>
          <div className="font-bold text-lg mono" style={{ color: site.color }}>{part.part_id}</div>
          <div className="text-sm" style={{ color:'#94a3b8' }}>{props.part_name || '—'}</div>
        </div>
        <button onClick={onClose} className="btn btn-ghost btn-xs"><X size={14}/></button>
      </div>

      {/* Properties */}
      <div className="grid grid-cols-2 gap-2 mb-4">
        {[
          ['Version', `v${vCount}`],
          ['Branch', part.branch || 'main'],
          ['Material', props.material || '—'],
          ['Weight', props.weight_kg ? `${props.weight_kg} kg` : '—'],
          ['Vertices', part.geometry?.vertices?.length || 0],
          ['Edges', part.geometry?.edges?.length || 0],
        ].map(([k,v]) => (
          <div key={k} style={{ background:'rgba(255,255,255,0.03)', borderRadius:7, padding:'6px 10px' }}>
            <div className="text-xs" style={{ color:'#475569' }}>{k}</div>
            <div className="text-sm font-medium mono">{v}</div>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="mb-3">
        <div className="text-xs mb-1" style={{ color:'#64748b' }}>User / Kỹ sư</div>
        <input className="input" value={user} onChange={e => setUser(e.target.value)} placeholder="engineer_name" />
      </div>

      <div className="flex gap-2 mb-3">
        <button onClick={doCheckout} disabled={working} className="btn btn-primary btn-sm flex-1">
          <Download size={13}/> Checkout
        </button>
        <button onClick={doCheckin} disabled={working} className="btn btn-success btn-sm flex-1">
          <Upload size={13}/> Checkout → Sửa → Checkin
        </button>
      </div>
      <button onClick={loadVersions} className="btn btn-ghost btn-xs w-full">
        <Clock size={12}/> Xem lịch sử phiên bản
      </button>

      {/* Message */}
      {msg && (
        <div style={{ marginTop:10, padding:'8px 12px', borderRadius:8, fontSize:12,
          background: msg.type==='success' ? 'rgba(16,185,129,.1)' : msg.type==='conflict' ? 'rgba(245,158,11,.1)' : 'rgba(239,68,68,.1)',
          color: msg.type==='success' ? '#34d399' : msg.type==='conflict' ? '#fbbf24' : '#f87171',
          border: `1px solid ${msg.type==='success' ? 'rgba(16,185,129,.2)' : msg.type==='conflict' ? 'rgba(245,158,11,.2)' : 'rgba(239,68,68,.2)'}`,
        }}>
          {msg.type === 'success' && <CheckCircle size={12} style={{ display:'inline', marginRight:5 }} />}
          {msg.type === 'conflict' && <AlertCircle size={12} style={{ display:'inline', marginRight:5, color:'#fbbf24' }} />}
          {msg.text}
        </div>
      )}

      {/* Versions */}
      {versions && (
        <div style={{ marginTop:12 }}>
          <div className="text-xs font-semibold mb-2" style={{ color:'#64748b' }}>Lịch sử phiên bản</div>
          <div className="scroll-panel space-y-1" style={{ maxHeight:160 }}>
            {versions.map(v => (
              <div key={v.version} style={{ display:'flex', justifyContent:'space-between', padding:'5px 8px',
                background:'rgba(255,255,255,.02)', borderRadius:6, fontSize:11 }}>
                <span className="mono" style={{ color:'#60a5fa' }}>v{v.version}</span>
                <span style={{ color:'#64748b' }}>{v.branch}</span>
                <span style={{ color:'#475569' }}>{v.modified_at?.split('T')[0] || '—'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function TabParts({ sites, onRefresh }) {
  const [selectedSite, setSelectedSite] = useState('a');
  const [selectedPart, setSelectedPart] = useState(null);
  const [search, setSearch] = useState('');

  const site = sites[selectedSite] || { name:'...', models:[], color:'#3b82f6' };
  const parts = (site.models || []).filter(p =>
    p.part_id?.toLowerCase().includes(search.toLowerCase()) ||
    (p.geometry?.properties?.part_name || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-4">
      {/* Site Selector */}
      <div className="flex gap-2">
        {Object.entries(sites).map(([key, s]) => (
          <button key={key} onClick={() => { setSelectedSite(key); setSelectedPart(null); }}
            className="btn btn-sm" style={{
              background: selectedSite===key ? `${s.color}22` : 'rgba(255,255,255,.04)',
              border: `1px solid ${selectedSite===key ? s.color : 'rgba(255,255,255,.1)'}`,
              color: selectedSite===key ? s.color : '#64748b',
            }}>
            <span className={`dot ${s.online ? 'dot-green' : 'dot-red'}`} style={{ width:6, height:6 }} />
            {s.name} — {s.category}
            <span style={{ background:'rgba(255,255,255,.08)', borderRadius:4, padding:'1px 6px', fontSize:11 }}>
              {s.models?.length || 0}
            </span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left: Part List */}
        <div className="card" style={{ padding:0, overflow:'hidden' }}>
          <div style={{ padding:'14px 16px', borderBottom:'1px solid rgba(255,255,255,.07)' }}>
            <div className="flex items-center gap-2 mb-2">
              <Tag size={14} style={{ color: site.color }} />
              <span className="font-semibold text-sm">{site.name} — Fragment</span>
              <span className="badge badge-blue" style={{ marginLeft:'auto' }}>
                {parts.length} parts
              </span>
            </div>
            <div className="flex items-center gap-2" style={{ background:'rgba(255,255,255,.04)', borderRadius:7, padding:'6px 10px' }}>
              <Search size={13} style={{ color:'#475569' }} />
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Tìm part ID hoặc tên..." style={{ background:'none', border:'none', outline:'none', fontSize:12, color:'#e2e8f0', width:'100%' }} />
            </div>
          </div>

          <div className="scroll-panel" style={{ padding:'8px', maxHeight:400 }}>
            {!site.online && (
              <div style={{ textAlign:'center', padding:40, color:'#475569', fontSize:13 }}>
                Site offline — Khởi động server trước
              </div>
            )}
            {site.online && parts.length === 0 && (
              <div style={{ textAlign:'center', padding:40, color:'#475569', fontSize:13 }}>
                Chưa có parts. Chạy <code style={{ color:'#60a5fa' }}>python main.py --servers</code>
              </div>
            )}
            {parts.map(p => {
              const props = p.geometry?.properties || {};
              const isSelected = selectedPart?.part_id === p.part_id;
              return (
                <div key={p.part_id} onClick={() => setSelectedPart(isSelected ? null : p)}
                  className={`part-row ${isSelected ? 'selected' : ''}`}>
                  <div style={{ width:6, height:6, borderRadius:'50%', flexShrink:0,
                    background: p.branch === 'main' ? '#34d399' : '#fbbf24' }} />
                  <div style={{ flex:1, minWidth:0 }}>
                    <div className="font-medium mono text-sm" style={{ color: isSelected ? '#93c5fd' : '#e2e8f0' }}>
                      {p.part_id}
                    </div>
                    <div className="text-xs truncate" style={{ color:'#64748b' }}>
                      {props.part_name || 'Unknown'} · {props.material || ''}
                    </div>
                  </div>
                  <div style={{ textAlign:'right', flexShrink:0 }}>
                    <div className="text-xs font-semibold mono" style={{ color: site.color }}>v{p.version}</div>
                    <div className="text-xs" style={{ color: p.branch !== 'main' ? '#fbbf24' : '#334155' }}>
                      {p.branch !== 'main' ? '⎇ branched' : 'main'}
                    </div>
                  </div>
                  <ChevronRight size={12} style={{ color:'#334155', flexShrink:0 }} />
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Detail / Actions */}
        <div>
          {selectedPart ? (
            <PartDetail
              siteKey={selectedSite} site={site} part={selectedPart}
              onClose={() => setSelectedPart(null)} onRefresh={onRefresh}
            />
          ) : (
            <div className="card h-full flex flex-col items-center justify-center" style={{ minHeight:300, color:'#334155' }}>
              <Tag size={36} style={{ marginBottom:12, opacity:.3 }} />
              <p className="text-sm">Chọn một part để xem chi tiết</p>
              <p className="text-xs mt-1" style={{ color:'#1e293b' }}>Có thể Checkout, Checkin, xem lịch sử</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
