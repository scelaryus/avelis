import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

const PRIO_VARIANT: Record<string, 'error' | 'warning' | 'info'> = {
  CRITIQUE: 'error', ELEVEE: 'warning', STANDARD: 'info',
};

export function FormulairesList() {
  const [formulaires, setFormulaires] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL');

  useEffect(() => {
    api.get('/foundation/formulaires').then(r => { setFormulaires(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-16 bg-mist rounded-lg animate-pulse" />)}</div>;

  const filtered = filter === 'ALL' ? formulaires : formulaires.filter(f => f.priority === filter);
  const critCount = formulaires.filter(f => f.priority === 'CRITIQUE').length;
  const elevCount = formulaires.filter(f => f.priority === 'ELEVEE').length;

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-2">Formulaires en Attente</h1>
      <p className="text-sm text-storm mb-6">
        {formulaires.length} formulaires bloquent des operations. Repondez pour debloquer.
        {critCount > 0 && <span className="text-coral font-bold ml-2">{critCount} CRITIQUES</span>}
      </p>

      <div className="flex gap-2 mb-6">
        {['ALL', 'CRITIQUE', 'ELEVEE', 'STANDARD'].map(p => (
          <button key={p} onClick={() => setFilter(p)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
              filter === p ? 'bg-iris text-white' : 'bg-white border border-mist text-storm hover:border-iris'}`}>
            {p === 'ALL' ? 'Tous' : p} {p !== 'ALL' && `(${formulaires.filter(f => f.priority === p).length})`}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="bg-white rounded-card border border-mist p-12 text-center">
          <p className="text-4xl mb-2">&#10003;</p>
          <p className="text-mint font-semibold">Aucun formulaire en attente</p>
          <p className="text-sm text-storm mt-1">Tous les workflows sont debloques</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(f => (
            <Link key={f.code} to={`/system/formulaires/${f.code}`}
              className={`block bg-white rounded-card border p-5 shadow-card hover:shadow-card-hover transition ${
                f.priority === 'CRITIQUE' ? 'border-l-4 border-l-coral' : f.priority === 'ELEVEE' ? 'border-l-4 border-l-honey' : 'border-mist'}`}>
              <div className="flex items-start gap-4">
                <Badge variant={PRIO_VARIANT[f.priority] || 'info'}>{f.priority}</Badge>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono text-iris font-bold">{f.code}</span>
                    <h3 className="text-sm font-semibold">{f.title}</h3>
                  </div>
                  <p className="text-xs text-storm">{f.context}</p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-storm">
                    <span>Module bloque: <strong>{f.blocked_module}</strong></span>
                    <span>Age: <strong className={f.age_days > 14 ? 'text-coral' : f.age_days > 7 ? 'text-honey' : ''}>{f.age_days} jours</strong></span>
                    <span>Champs: {f.fields?.length || 0}</span>
                  </div>
                </div>
                <div className="text-right">
                  <Badge variant={f.status === 'EN_ATTENTE' ? 'warning' : f.status === 'REMPLI' ? 'success' : 'neutral'}>{f.status}</Badge>
                  <p className="text-xs text-iris mt-2 font-medium">Repondre &rarr;</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
