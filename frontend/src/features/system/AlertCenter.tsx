import { useEffect, useState } from 'react';
import { Badge } from '../../components/ui/Badge';
import { formatDistanceToNow } from 'date-fns';
import { fr } from 'date-fns/locale';
import api from '../../lib/api-client';

const SEV_ORDER = ['BLOQUANT', 'CRITIQUE', 'ALERTE', 'ATTENTION', 'INFO'];
const SEV_VARIANT: Record<string, 'error' | 'warning' | 'info' | 'neutral'> = {
  BLOQUANT: 'error', CRITIQUE: 'error', ALERTE: 'warning', ATTENTION: 'warning', INFO: 'info',
};

export function AlertCenter() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [filter, setFilter] = useState<string>('ALL');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/system/alerts').then(r => { setAlerts(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="space-y-3">{[1,2,3,4].map(i => <div key={i} className="h-16 bg-mist rounded-lg animate-pulse" />)}</div>;

  const filtered = filter === 'ALL' ? alerts : alerts.filter(a => a.level === filter);
  const sorted = [...filtered].sort((a, b) => SEV_ORDER.indexOf(a.level) - SEV_ORDER.indexOf(b.level));

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-2">Centre d'Alertes</h1>
      <p className="text-sm text-storm mb-6">{alerts.length} alertes actives tous modules confondus</p>

      <div className="flex gap-2 mb-6">
        {['ALL', ...SEV_ORDER].map(s => (
          <button key={s} onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
              filter === s ? 'bg-iris text-white' : 'bg-white border border-mist text-storm hover:border-iris'}`}>
            {s === 'ALL' ? 'Toutes' : s} {s !== 'ALL' && `(${alerts.filter(a => a.level === s).length})`}
          </button>
        ))}
      </div>

      {sorted.length === 0 ? (
        <div className="bg-white rounded-card border border-mist p-12 text-center">
          <p className="text-4xl mb-2">✅</p>
          <p className="text-storm">Aucune alerte pour ce filtre</p>
        </div>
      ) : (
        <div className="space-y-2">
          {sorted.map((a, i) => (
            <div key={i} className={`bg-white rounded-lg border border-mist p-4 flex items-center gap-4 hover:shadow-card-hover transition ${
              a.level === 'CRITIQUE' || a.level === 'BLOQUANT' ? 'border-l-4 border-l-coral bg-[rgba(253,121,168,0.04)]' : ''}`}>
              <Badge variant={SEV_VARIANT[a.level] || 'neutral'}>{a.level}</Badge>
              <span className="text-xs bg-mist text-storm px-2 py-0.5 rounded font-medium">{a.module}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold truncate">{a.title}</p>
                <p className="text-xs text-storm truncate">{a.message}</p>
              </div>
              <span className="text-xs text-silver whitespace-nowrap">
                {a.created ? formatDistanceToNow(new Date(a.created), { addSuffix: true, locale: fr }) : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
