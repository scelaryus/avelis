import { useEffect, useState } from 'react';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

const MODULE_COLORS: Record<string, string> = {
  DRH: '#6C5CE7', JURIDIQUE: '#0984E3', FINANCE: '#00B894', GED: '#E17055',
  SPI: '#FDCB6E', FONDATION: '#636E72', SYSTEME: '#A29BFE', ADV: '#74B9FF',
};

export function AgentStatus() {
  const [agents, setAgents] = useState<any[]>([]);
  const [meta, setMeta] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [moduleFilter, setModuleFilter] = useState('ALL');

  const reload = () => {
    setLoading(true);
    api.get('/system/agents/status').then(r => {
      setAgents(r.data.data?.agents || []);
      setMeta(r.data.data || {});
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { reload(); const i = setInterval(reload, 30000); return () => clearInterval(i); }, []);

  if (loading) return <div className="grid grid-cols-4 gap-4">{[...Array(12)].map((_, i) => <div key={i} className="h-28 bg-mist rounded-card animate-pulse" />)}</div>;

  const modules = [...new Set(agents.map(a => a.module))];
  const filtered = moduleFilter === 'ALL' ? agents : agents.filter(a => a.module === moduleFilter);
  const sorted = [...filtered].sort((a, b) => {
    const order: Record<string, number> = { ERROR: 0, RUNNING: 1, IDLE: 2 };
    return (order[a.status] ?? 3) - (order[b.status] ?? 3);
  });

  const running = agents.filter(a => a.status === 'RUNNING').length;
  const totalQueue = agents.reduce((s, a) => s + (a.queue_depth || 0), 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[32px] font-bold">Agents IA</h1>
          <p className="text-sm text-storm">{meta.total || 0} agents — {running} en cours — {totalQueue} taches en queue</p>
        </div>
        <button onClick={reload} className="px-3 py-2 border border-mist rounded-button text-sm text-storm hover:border-iris">
          Rafraichir
        </button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-card border border-[#E0E0E0] p-4 shadow-card">
          <p className="text-xs text-storm">Total Agents</p>
          <p className="text-2xl font-bold">{meta.total || 0}</p>
        </div>
        <div className="bg-white rounded-card border border-mint p-4 shadow-card">
          <p className="text-xs text-storm">En Cours</p>
          <p className="text-2xl font-bold text-mint">{running}</p>
        </div>
        <div className="bg-white rounded-card border border-[#E0E0E0] p-4 shadow-card">
          <p className="text-xs text-storm">En Attente</p>
          <p className="text-2xl font-bold">{agents.filter(a => a.status === 'IDLE').length}</p>
        </div>
        <div className="bg-white rounded-card border border-[#E0E0E0] p-4 shadow-card">
          <p className="text-xs text-storm">Queue Totale</p>
          <p className={`text-2xl font-bold ${totalQueue > 10 ? 'text-honey' : ''}`}>{totalQueue}</p>
        </div>
      </div>

      {/* Module filter */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <button onClick={() => setModuleFilter('ALL')}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${moduleFilter === 'ALL' ? 'bg-iris text-white' : 'bg-white border border-mist text-storm hover:border-iris'}`}>
          Tous ({agents.length})
        </button>
        {modules.map(m => (
          <button key={m} onClick={() => setModuleFilter(m)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${moduleFilter === m ? 'bg-iris text-white' : 'bg-white border border-mist text-storm hover:border-iris'}`}>
            <span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ background: MODULE_COLORS[m] || '#636E72' }} />
            {m} ({agents.filter(a => a.module === m).length})
          </button>
        ))}
      </div>

      {/* Agent grid */}
      <div className="grid grid-cols-4 gap-3">
        {sorted.map((a, i) => (
          <div key={i} className={`bg-white rounded-card border p-4 shadow-card transition hover:shadow-card-hover ${
            a.status === 'ERROR' ? 'border-coral bg-[rgba(255,107,107,0.04)]' :
            a.status === 'RUNNING' ? 'border-mint' : 'border-mist'}`}>
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${a.status === 'RUNNING' ? 'bg-mint animate-pulse' : a.status === 'ERROR' ? 'bg-coral' : 'bg-silver'}`} />
                <p className="text-sm font-semibold">{a.name}</p>
              </div>
              <Badge variant={a.status === 'ERROR' ? 'error' : a.status === 'RUNNING' ? 'success' : 'neutral'}>
                {a.status}
              </Badge>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-bold text-white px-1.5 py-0.5 rounded"
                style={{ background: MODULE_COLORS[a.module] || '#636E72' }}>{a.module}</span>
            </div>
            <p className="text-xs text-storm">{a.description}</p>
            {a.current_task && (
              <div className="mt-2 bg-[rgba(0,184,148,0.06)] rounded p-2">
                <p className="text-xs text-mint font-medium">{a.current_task}</p>
              </div>
            )}
            {a.queue_depth > 0 && (
              <div className="mt-2 flex items-center gap-2">
                <div className="flex-1 bg-mist rounded-full h-1.5">
                  <div className="bg-iris h-full rounded-full" style={{ width: `${Math.min(a.queue_depth * 10, 100)}%` }} />
                </div>
                <span className="text-[10px] font-mono text-storm">{a.queue_depth}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
