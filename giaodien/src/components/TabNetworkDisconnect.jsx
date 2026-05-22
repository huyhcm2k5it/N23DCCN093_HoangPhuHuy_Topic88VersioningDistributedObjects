import { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  ClipboardList,
  Database,
  Play,
  RefreshCw,
  RotateCcw,
  Server,
  Wifi,
  WifiOff,
} from 'lucide-react';
import {
  createModel,
  disconnectNetwork,
  getModel,
  getNetworkStatus,
  getReplicationOutbox,
  reconnectNetwork,
  replicate,
  replayReplication,
  SITES,
} from '../api';
import { createTriangleDemoGeometry } from '../demoGeometry';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const STEPS = [
  'Create object',
  'Disconnect Site-B',
  'Queue outbox',
  'Reconnect Site-B',
  'Replay and verify',
];

function InfoBox({ type = 'info', children }) {
  const color = {
    info: ['rgba(59,130,246,.08)', 'rgba(59,130,246,.22)', '#60a5fa'],
    ok: ['rgba(16,185,129,.08)', 'rgba(16,185,129,.22)', '#34d399'],
    warn: ['rgba(245,158,11,.08)', 'rgba(245,158,11,.22)', '#fbbf24'],
    error: ['rgba(239,68,68,.08)', 'rgba(239,68,68,.22)', '#f87171'],
  }[type];

  return (
    <div
      style={{
        background: color[0],
        border: `1px solid ${color[1]}`,
        color: color[2],
        borderRadius: 8,
        padding: '12px 14px',
        fontSize: 13,
        lineHeight: 1.7,
      }}
    >
      {children}
    </div>
  );
}

function Stepper({ step }) {
  return (
    <div className="card">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 10 }}>
        {STEPS.map((label, index) => {
          const stepNumber = index + 1;
          const done = step > stepNumber;
          const active = step === stepNumber;
          return (
            <div key={label} style={{ textAlign: 'center', minWidth: 0 }}>
              <div
                style={{
                  margin: '0 auto 8px',
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  display: 'grid',
                  placeItems: 'center',
                  background: done ? '#10b981' : active ? '#2563eb' : 'rgba(255,255,255,.05)',
                  color: done || active ? '#fff' : '#64748b',
                  fontWeight: 700,
                  border: `1px solid ${done ? '#10b981' : active ? '#3b82f6' : 'rgba(255,255,255,.12)'}`,
                }}
              >
                {done ? 'OK' : stepNumber}
              </div>
              <div style={{ fontSize: 11, color: active ? '#e2e8f0' : done ? '#34d399' : '#64748b' }}>
                {label}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StatusRow({ label, value, tone = 'info' }) {
  const colors = {
    info: '#94a3b8',
    ok: '#34d399',
    warn: '#fbbf24',
    error: '#f87171',
  };
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,.05)' }}>
      <span style={{ color: '#64748b', fontSize: 12 }}>{label}</span>
      <span className="mono" style={{ color: colors[tone], fontSize: 12, textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {value || '-'}
      </span>
    </div>
  );
}

export default function TabNetworkDisconnect({ onRefresh }) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [partId, setPartId] = useState('');
  const [created, setCreated] = useState(null);
  const [disconnectResult, setDisconnectResult] = useState(null);
  const [queuedReplication, setQueuedReplication] = useState(null);
  const [outboxEntry, setOutboxEntry] = useState(null);
  const [reconnectResult, setReconnectResult] = useState(null);
  const [replayResult, setReplayResult] = useState(null);
  const [replicatedModel, setReplicatedModel] = useState(null);

  function resetDemo() {
    setStep(1);
    setLoading(false);
    setError(null);
    setPartId('');
    setCreated(null);
    setDisconnectResult(null);
    setQueuedReplication(null);
    setOutboxEntry(null);
    setReconnectResult(null);
    setReplayResult(null);
    setReplicatedModel(null);
  }

  async function getSourceOutboxEntry(opId) {
    const outbox = await getReplicationOutbox('a');
    return outbox.entries?.find((entry) => entry.op_id === opId) || null;
  }

  async function waitForRetryWindow(opId) {
    const entry = await getSourceOutboxEntry(opId);
    setOutboxEntry(entry);
    if (!entry?.next_retry_at) return;

    const retryAt = new Date(entry.next_retry_at).getTime();
    const delay = retryAt - Date.now();
    if (delay > 0) await sleep(delay + 250);
  }

  async function replayUntilAcked(opId, attempts = 4) {
    let lastReplay = null;
    let entry = await getSourceOutboxEntry(opId);
    setOutboxEntry(entry);

    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      if (entry?.status === 'ACKED') {
        return { replay: lastReplay || { message: 'Operation was already ACKED.' }, entry };
      }

      await waitForRetryWindow(opId);
      lastReplay = await replayReplication('a', SITES.b.site_id);
      entry = await getSourceOutboxEntry(opId);
      setOutboxEntry(entry);

      if (entry?.status === 'ACKED') {
        return { replay: lastReplay, entry };
      }

      if (attempt < attempts) await sleep(1000);
    }

    throw new Error(`Outbox entry ${opId} was not ACKED after ${attempts} replay attempts.`);
  }

  async function runDemo() {
    setLoading(true);
    setError(null);

    try {
      const newPartId = `ENG-NET-${Date.now()}`;
      setPartId(newPartId);

      const newModel = await createModel('a', newPartId, createTriangleDemoGeometry());
      setCreated(newModel);
      setStep(2);
      await sleep(400);

      const disconnected = await disconnectNetwork('b');
      setDisconnectResult(disconnected);
      onRefresh?.();
      setStep(3);
      await sleep(400);

      const queued = await replicate('a', newPartId, SITES.b.site_id);
      setQueuedReplication(queued);
      setOutboxEntry(queued.outbox_entry || null);
      setStep(4);
      await sleep(400);

      const reconnected = await reconnectNetwork('b');
      setReconnectResult(reconnected);
      onRefresh?.();
      setStep(5);
      await sleep(400);

      const { replay, entry } = await replayUntilAcked(queued.op_id);
      const targetModel = await getModel('b', newPartId);
      setReplayResult(replay);
      setOutboxEntry(entry);
      setReplicatedModel(targetModel);
      setStep(6);
      onRefresh?.();
    } catch (err) {
      setError(err.message || String(err));
      try {
        const status = await getNetworkStatus('b');
        if (status?.network_online === false) await reconnectNetwork('b');
      } catch {}
      onRefresh?.();
    } finally {
      setLoading(false);
    }
  }

  const oidMatches = Boolean(created?.oid && replicatedModel?.oid && created.oid === replicatedModel.oid);
  const finalOk = step >= 6 && oidMatches && outboxEntry?.status === 'ACKED';

  return (
    <div className="space-y-5 fade-in">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <AlertTriangle size={20} color="#fbbf24" />
            <h2 style={{ fontSize: 20, fontWeight: 600, color: '#e2e8f0', margin: 0 }}>
              Failure Demo: Node Disconnect + Outbox Retry
            </h2>
          </div>
          <p style={{ color: '#64748b', fontSize: 13, maxWidth: 820 }}>
            Main failure scenario for Topic 88. Site-B loses inter-site connectivity while Site-A is replicating a CAD object.
            The request is kept in Site-A durable outbox, then replayed after Site-B reconnects.
          </p>
        </div>

        <div className="flex gap-2">
          <button onClick={runDemo} disabled={loading} className="btn btn-primary">
            {loading ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
            {loading ? 'Running...' : 'Run Failure Demo'}
          </button>
          <button onClick={resetDemo} disabled={loading} className="btn btn-ghost">
            <RotateCcw size={14} />
            Reset
          </button>
        </div>
      </div>

      <Stepper step={step} />

      {error && (
        <InfoBox type="error">
          <strong>Error:</strong> {error}
        </InfoBox>
      )}

      {finalOk && (
        <InfoBox type="ok">
          <strong>Success:</strong> Outbox entry is ACKED and Site-B received the object with the same immutable OID.
        </InfoBox>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="card" style={{ borderTop: '3px solid #3b82f6' }}>
          <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
            <Database size={15} style={{ color: '#60a5fa' }} />
            Object Identity
          </h3>
          <StatusRow label="Source site" value="Site-A :5001" />
          <StatusRow label="Target site" value="Site-B :5002" />
          <StatusRow label="Part ID" value={partId} />
          <StatusRow label="Site-A OID" value={created?.oid} tone={created ? 'ok' : 'info'} />
          <StatusRow label="Site-B OID" value={replicatedModel?.oid} tone={replicatedModel ? 'ok' : 'info'} />
          <StatusRow label="OID invariant" value={replicatedModel ? String(oidMatches) : '-'} tone={oidMatches ? 'ok' : replicatedModel ? 'error' : 'info'} />
        </div>

        <div className="card" style={{ borderTop: '3px solid #f59e0b' }}>
          <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
            <WifiOff size={15} style={{ color: '#fbbf24' }} />
            Failure Path
          </h3>
          <StatusRow label="Create object" value={created ? 'DONE' : 'WAITING'} tone={created ? 'ok' : 'info'} />
          <StatusRow
            label="Site-B network"
            value={disconnectResult ? disconnectResult.network_status?.mode : 'distributed'}
            tone={disconnectResult ? 'warn' : 'info'}
          />
          <StatusRow
            label="Replicate response"
            value={queuedReplication ? `HTTP queued=${String(queuedReplication.queued)}` : 'WAITING'}
            tone={queuedReplication ? 'warn' : 'info'}
          />
          <StatusRow label="Op ID" value={queuedReplication?.op_id} tone={queuedReplication ? 'warn' : 'info'} />
          <StatusRow label="Target ACK before reconnect" value={queuedReplication ? 'NO' : '-'} tone={queuedReplication ? 'warn' : 'info'} />
        </div>

        <div className="card" style={{ borderTop: '3px solid #10b981' }}>
          <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
            <Wifi size={15} style={{ color: '#34d399' }} />
            Recovery Path
          </h3>
          <StatusRow
            label="Reconnect Site-B"
            value={reconnectResult ? reconnectResult.network_status?.mode : 'WAITING'}
            tone={reconnectResult ? 'ok' : 'info'}
          />
          <StatusRow
            label="Replay result"
            value={replayResult ? replayResult.message : 'WAITING'}
            tone={replayResult ? 'ok' : 'info'}
          />
          <StatusRow
            label="Outbox status"
            value={outboxEntry?.status}
            tone={outboxEntry?.status === 'ACKED' ? 'ok' : outboxEntry ? 'warn' : 'info'}
          />
          <StatusRow
            label="Attempts"
            value={outboxEntry?.attempt_count != null ? String(outboxEntry.attempt_count) : '-'}
            tone={outboxEntry ? 'ok' : 'info'}
          />
          <StatusRow label="Target model loaded" value={replicatedModel ? 'YES' : 'NO'} tone={replicatedModel ? 'ok' : 'info'} />
        </div>
      </div>

      <div className="card">
        <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
          <ClipboardList size={15} style={{ color: '#a78bfa' }} />
          Source Outbox Entry
        </h3>
        {outboxEntry ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
            <StatusRow label="Status" value={outboxEntry.status} tone={outboxEntry.status === 'ACKED' ? 'ok' : 'warn'} />
            <StatusRow label="Target" value={outboxEntry.target_site} />
            <StatusRow label="Branch" value={outboxEntry.branch} />
            <StatusRow label="Version" value={`v${outboxEntry.version}`} />
            <StatusRow label="Last error" value={outboxEntry.last_error || '-'} tone={outboxEntry.last_error ? 'warn' : 'info'} />
            <StatusRow label="ACK time" value={outboxEntry.acked_at || '-'} tone={outboxEntry.acked_at ? 'ok' : 'info'} />
          </div>
        ) : (
          <div style={{ color: '#64748b', fontSize: 13 }}>
            Run the demo to create a durable replication operation in Site-A outbox.
          </div>
        )}
      </div>

      <div className="card" style={{ background: 'rgba(59,130,246,.04)', border: '1px solid rgba(59,130,246,.14)' }}>
        <h3 className="font-semibold text-sm mb-2 flex items-center gap-2" style={{ color: '#60a5fa' }}>
          <Server size={15} />
          Why this is the only failure demo
        </h3>
        <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.8 }}>
          This scenario directly matches a distributed system failure: one site is temporarily disconnected while another site still
          accepts local work. The source site stores replication intent durably before network delivery. Retry is idempotent through
          op_id, so replay after reconnect preserves object identity without duplicate side effects.
        </p>
        <div className="flex flex-wrap gap-2 mt-3">
          <span className="badge badge-blue">network awareness</span>
          <span className="badge badge-amber">durable outbox</span>
          <span className="badge badge-green">idempotent retry</span>
          <span className="badge badge-purple">OID invariant</span>
        </div>
      </div>
    </div>
  );
}
