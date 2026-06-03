import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

const STAGES = ['ouvert', 'mise_en_demeure', 'negociation', 'audience_programmee', 'en_delibere', 'jugement', 'cloture'];
const STAGE_BG: Record<string, string> = {
  ouvert: 'bg-[rgba(116,185,255,0.1)]', mise_en_demeure: 'bg-[rgba(253,203,110,0.1)]',
  negociation: 'bg-[rgba(162,155,254,0.1)]', audience_programmee: 'bg-[rgba(255,107,107,0.1)]',
  en_delibere: 'bg-[rgba(253,121,168,0.1)]', jugement: 'bg-[rgba(0,184,148,0.1)]', cloture: 'bg-[rgba(223,230,233,0.3)]',
};

export function CasesList() {
  const [cases, setCases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { api.get('/juridique/cases').then(r => { setCases(r.data.data || []); setLoading(false); }).catch(() => setLoading(false)); }, []);

  if (loading) return <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-20 bg-mist rounded-lg animate-pulse" />)}</div>;

  const grouped = cases.reduce((acc: any, c: any) => { (acc[c.stage] = acc[c.stage] || []).push(c); return acc; }, {});

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div><Link to="/juridique" className="text-sm text-iris hover:underline">← Juridique</Link>
          <h1 className="text-[32px] font-bold mt-1">Dossiers Litiges</h1>
          <p className="text-sm text-storm">Transitions contrôlées par workflow — glisser-déposer désactivé</p></div>
        <Link to="/juridique/cases/new" className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">Nouveau dossier</Link>
      </div>

      <div className="flex gap-4 overflow-x-auto pb-4">
        {STAGES.map(stage => (
          <div key={stage} className={`min-w-[260px] flex-shrink-0 rounded-lg p-3 ${STAGE_BG[stage] || 'bg-gray-50'}`}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-storm">{stage.replace(/_/g, ' ')}</h3>
              <span className="bg-white text-charcoal text-xs font-bold px-2 py-0.5 rounded-full shadow-sm">{(grouped[stage] || []).length}</span>
            </div>
            <div className="space-y-3">
              {(grouped[stage] || []).map((c: any) => (
                <div key={c.id} onClick={() => window.location.href = `/juridique/cases/${c.id}`}
                  className="bg-white rounded-card border border-mist p-4 shadow-card hover:shadow-card-hover transition cursor-pointer">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-[10px] text-storm">{c.name}</span>
                    <Badge variant={c.priority === 'critique' ? 'error' : c.priority === 'important' ? 'warning' : 'info'}>{c.priority}</Badge>
                  </div>
                  <p className="text-sm font-semibold">{c.title}</p>
                  <p className="text-xs text-storm mt-1">vs {c.partner}</p>
                  <div className="flex items-center justify-between mt-3">
                    <span className="text-sm font-mono font-bold">{formatDA(c.amount_claimed)}</span>
                    <span className="text-[10px] text-storm">{c.days_open}j ouverts</span>
                  </div>
                  {c.ai_risk_score !== undefined && (
                    <div className="mt-2">
                      <div className="bg-mist rounded-full h-1.5"><div className={`h-full rounded-full ${c.ai_risk_score > 50 ? 'bg-coral' : c.ai_risk_score > 30 ? 'bg-honey' : 'bg-mint'}`} style={{ width: `${c.ai_risk_score}%` }} /></div>
                      <p className="text-[10px] text-storm mt-0.5">Risque IA: {c.ai_risk_score}%</p>
                    </div>
                  )}
                </div>
              ))}
              {(grouped[stage] || []).length === 0 && <p className="text-xs text-silver text-center py-4">Aucun dossier</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
