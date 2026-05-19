import { useState, useEffect, useCallback } from 'react';
import { Database, Server, GitBranch, HardDrive, RefreshCw, Wifi, WifiOff, ScrollText } from 'lucide-react';
import { SITES, healthCheck, getStorageComparison, listModels, getFragmentation } from './api';
import TabDashboard from './components/TabDashboard';
import TabWorkspace from './components/TabWorkspace';
import TabStorage from './components/TabStorage';
import TabOverview from './components/TabOverview';
import TabConflict from './components/TabConflict';
import TabCoordinatorCrash from './components/TabCoordinatorCrash';
import TabLogs from './components/TabLogs';

const TABS = [
  { id: 'overview',   label: 'Tổng quan',      Icon: Database   },
  { id: 'dashboard',  label: 'Hệ thống',        Icon: Server     },
  { id: 'workspace',  label: 'Làm việc',        Icon: GitBranch  },
  { id: 'conflict',   label: 'Demo Xung đột',   Icon: RefreshCw  },
  { id: 'crash',      label: 'Demo WAL Crash',  Icon: WifiOff    },
  { id: 'logs',       label: 'Nhật ký WAL',     Icon: ScrollText },
  { id: 'storage',    label: 'Lưu trữ',         Icon: HardDrive  },
];

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [sites, setSites] = useState({});
  const [refreshing, setRefreshing] = useState(false);

  const refreshAll = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true);
    const results = await Promise.all(
      Object.keys(SITES).map(async (key) => {
        const health = await healthCheck(key);
        let storage = null, models = [], fragmentation = null;
        if (health.online) {
          try { storage = await getStorageComparison(key); } catch {}
          try { const r = await listModels(key); models = r.models || []; } catch {}
          try { fragmentation = await getFragmentation(key); } catch {}
        }
        // Gộp metadata tĩnh (SITES[key]) với dữ liệu thực tế từ backend
        return [key, {
          ...SITES[key],       // name, host, site_id, category, label, color, strategy
          ...health,           // online, status
          storage,
          models,
          fragmentation,
        }];
      })
    );
    setSites(Object.fromEntries(results));
    if (!silent) setRefreshing(false);
  }, []);

  useEffect(() => {
    refreshAll();
    const t = setInterval(() => refreshAll(true), 15000);
    return () => clearInterval(t);
  }, [refreshAll]);

  const onlineCount = Object.values(sites).filter(s => s?.online).length;
  const allOnline   = onlineCount === Object.keys(SITES).length;

  return (
    <div className="min-h-screen grid-bg">
      {/* ── HEADER ── */}
      <header
        style={{ background: 'rgba(6,12,26,0.92)', borderBottom: '1px solid rgba(255,255,255,0.07)', backdropFilter: 'blur(16px)' }}
        className="sticky top-0 z-50"
      >
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div style={{ background: 'linear-gradient(135deg,#1d4ed8,#7c3aed)', borderRadius: 10 }} className="w-9 h-9 flex items-center justify-center">
              <Database size={18} className="text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold" style={{ color: '#e2e8f0' }}>
                Distributed CAD Versioning
              </h1>
              <p className="text-xs" style={{ color: '#475569' }}>Topic 88 · Özsu &amp; Valduriez · CSDL Phân tán</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs" style={{ color: allOnline ? '#34d399' : '#f87171' }}>
              {allOnline ? <Wifi size={14}/> : <WifiOff size={14}/>}
              <span>{onlineCount}/{Object.keys(SITES).length} Sites Online</span>
            </div>
            <button onClick={() => refreshAll()} disabled={refreshing} className="btn btn-ghost btn-sm">
              <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
              {refreshing ? 'Refreshing...' : 'Làm mới'}
            </button>
          </div>
        </div>

        {/* ── TAB BAR ── */}
        <div className="max-w-7xl mx-auto px-6 flex gap-1" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          {TABS.map(({ id, label, Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              className={`tab-item ${tab === id ? 'active' : ''}`}>
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>
      </header>

      {/* ── CONTENT ── */}
      <main className="max-w-7xl mx-auto px-6 py-6 fade-in">
        {tab === 'overview'  && <TabOverview        sites={sites} />}
        {tab === 'dashboard' && <TabDashboard        sites={sites} onRefresh={refreshAll} />}
        {tab === 'workspace' && <TabWorkspace        sites={sites} onRefresh={() => refreshAll(true)} allOnline={allOnline} />}
        {tab === 'conflict'  && <TabConflict         sites={sites} onRefresh={() => refreshAll(true)} />}
        {tab === 'crash'     && <TabCoordinatorCrash sites={sites} onRefresh={() => refreshAll(true)} />}
        {tab === 'logs'      && <TabLogs             sites={sites} onRefresh={() => refreshAll(true)} />}
        {tab === 'storage'   && <TabStorage          sites={sites} />}
      </main>
    </div>
  );
}
