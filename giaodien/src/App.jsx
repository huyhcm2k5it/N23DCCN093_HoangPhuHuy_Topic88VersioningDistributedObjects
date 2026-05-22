import { useState, useEffect, useCallback } from 'react';
import { Database, Server, RefreshCw, Wifi, WifiOff, AlertTriangle } from 'lucide-react';
import { SITES, healthCheck, getStorageComparison, listModels, getFragmentation } from './api';
import TabDashboard from './components/TabDashboard';
import TabOverview from './components/TabOverview';
import TabConflict from './components/TabConflict';
import TabNetworkDisconnect from './components/TabNetworkDisconnect';

const TABS = [
  { id: 'overview', label: 'Overview & Metrics', Icon: Database },
  { id: 'dashboard', label: 'Distributed Sites', Icon: Server },
  { id: 'conflict', label: 'Conflict Demo', Icon: RefreshCw },
  { id: 'network', label: 'Failure Demo: Outbox Retry', Icon: AlertTriangle },
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
        let storage = null;
        let models = [];
        let fragmentation = null;

        if (health.reachable) {
          try { storage = await getStorageComparison(key); } catch {}
          try { const r = await listModels(key); models = r.models || []; } catch {}
          try { fragmentation = await getFragmentation(key); } catch {}
        }

        return [key, {
          ...SITES[key],
          ...health,
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

  const connectedCount = Object.values(sites).filter(
    (site) => site?.reachable && site?.network_online !== false
  ).length;
  const allConnected = connectedCount === Object.keys(SITES).length;

  return (
    <div className="min-h-screen grid-bg">
      <header
        style={{
          background: 'rgba(6,12,26,0.92)',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          backdropFilter: 'blur(16px)',
        }}
        className="sticky top-0 z-50"
      >
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              style={{ background: 'linear-gradient(135deg,#1d4ed8,#7c3aed)', borderRadius: 10 }}
              className="w-9 h-9 flex items-center justify-center"
            >
              <Database size={18} className="text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold" style={{ color: '#e2e8f0' }}>
                Distributed CAD Versioning
              </h1>
              <p className="text-xs" style={{ color: '#475569' }}>
                Topic 88 · Ozsu &amp; Valduriez · Distributed Database
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs" style={{ color: allConnected ? '#34d399' : '#f87171' }}>
              {allConnected ? <Wifi size={14} /> : <WifiOff size={14} />}
              <span>{connectedCount}/{Object.keys(SITES).length} Sites Connected</span>
            </div>
            <button onClick={() => refreshAll()} disabled={refreshing} className="btn btn-ghost btn-sm">
              <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
              {refreshing ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-6 flex gap-1" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          {TABS.map(({ id, label, Icon }) => (
            <button key={id} onClick={() => setTab(id)} className={`tab-item ${tab === id ? 'active' : ''}`}>
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 fade-in">
        {tab === 'overview' && <TabOverview sites={sites} />}
        {tab === 'dashboard' && <TabDashboard sites={sites} onRefresh={refreshAll} />}
        {tab === 'conflict' && <TabConflict sites={sites} onRefresh={() => refreshAll(true)} />}
        {tab === 'network' && <TabNetworkDisconnect onRefresh={() => refreshAll(true)} />}
      </main>
    </div>
  );
}
