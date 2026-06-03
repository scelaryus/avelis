import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '../../components/ui/Badge';
import { formatDA } from '../../lib/format';
import { useStore } from '../../store/useStore';
import api from '../../lib/api-client';

const DOSSIER_COLUMNS = [
  { key: 'PRE_RESERVE', label: 'Pre-reserve', bg: 'bg-[rgba(253,203,110,0.08)]' },
  { key: 'RESERVE', label: 'Reserve', bg: 'bg-[rgba(116,185,255,0.08)]' },
  { key: 'ENGAGE', label: 'Engage', bg: 'bg-[rgba(162,155,254,0.08)]' },
  { key: 'EN_COURS_CREDIT', label: 'Credit en cours', bg: 'bg-[rgba(9,132,227,0.08)]' },
  { key: 'EN_COURS_FONDS_PROPRES', label: 'Fonds propres', bg: 'bg-[rgba(253,203,110,0.08)]' },
  { key: 'LIVRAISON_PRETE', label: 'Livraison prete', bg: 'bg-[rgba(0,184,148,0.08)]' },
  { key: 'LIVRE', label: 'Livre', bg: 'bg-[rgba(85,239,196,0.08)]' },
  { key: 'CLOTURE', label: 'Cloture', bg: 'bg-[rgba(223,230,233,0.3)]' },
];

export function DossierPipeline() {
  const { canSeeRF2 } = useStore();
  const [dossiers, setDossiers] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [projectFilter, setProjectFilter] = useState('');
  const [view, setView] = useState<'kanban' | 'table'>('kanban');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/adv/dossiers${projectFilter ? `?project_id=${projectFilter}` : ''}`),
      api.get('/foundation/projects?status=ACTIF'),
    ]).then(([dosR, projR]) => {
      setDossiers(dosR.data.data || []);
      setProjects(projR.data.data || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [projectFilter]);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-32 bg-mist rounded-card animate-pulse" />)}</div>;

  const grouped: Record<string, any[]> = {};
  DOSSIER_COLUMNS.forEach(c => { grouped[c.key] = []; });
  dossiers.forEach(d => {
    if (grouped[d.status]) grouped[d.status].push(d);
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-[32px] font-bold">Pipeline Dossiers ADV</h1>
          <p className="text-sm text-storm">{dossiers.length} dossiers actifs</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={projectFilter} onChange={e => setProjectFilter(e.target.value)}
            className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
            <option value="">Tous les projets</option>
            {projects.map(p => <option key={p.code} value={p.code}>{p.code}</option>)}
          </select>
          <Link to="/adv/dossiers/new" className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">+ Dossier</Link>
        </div>
      </div>

      <div className="flex gap-2 mb-4">
        <button onClick={() => setView('kanban')} className={`px-4 py-2 rounded-lg text-sm font-medium transition ${view === 'kanban' ? 'bg-iris text-white' : 'bg-white border border-mist text-storm'}`}>Kanban</button>
        <button onClick={() => setView('table')} className={`px-4 py-2 rounded-lg text-sm font-medium transition ${view === 'table' ? 'bg-iris text-white' : 'bg-white border border-mist text-storm'}`}>Tableau</button>
      </div>

      {view === 'kanban' && (
        <div className="flex gap-3 overflow-x-auto pb-4">
          {DOSSIER_COLUMNS.map(col => (
            <div key={col.key} className={`min-w-[220px] flex-shrink-0 rounded-lg p-3 ${col.bg}`}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[10px] font-semibold uppercase tracking-wider text-storm">{col.label}</h3>
                <span className="bg-white text-charcoal text-xs font-bold px-2 py-0.5 rounded-full shadow-sm">{grouped[col.key]?.length || 0}</span>
              </div>
              <div className="space-y-2">
                {(grouped[col.key] || []).map(d => (
                  <Link key={d.numero} to={`/adv/dossiers/${d.numero}`}
                    className="block bg-white rounded-lg border border-mist p-3 shadow-card hover:shadow-card-hover hover:border-iris transition">
                    <p className="font-mono text-[10px] text-iris font-bold">{d.numero}</p>
                    <p className="text-sm font-medium mt-0.5">{d.client}</p>
                    <p className="text-xs text-storm">{d.lot} — {d.project}</p>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs font-mono">{formatDA(d.rf1)}</span>
                      <Badge variant={d.rf2_status === 'SECURISE' ? 'success' : d.rf2_status === 'PARTIELLEMENT_SECURISE' ? 'warning' : 'error'}>
                        RF2 {d.rf2_status === 'SECURISE' ? '✓' : '...'}
                      </Badge>
                    </div>
                    <div className="mt-1">
                      <Badge variant={d.type === 'CREDIT_BANCAIRE' ? 'info' : 'neutral'}>{d.type?.replace(/_/g, ' ')}</Badge>
                    </div>
                  </Link>
                ))}
                {(grouped[col.key] || []).length === 0 && <p className="text-xs text-silver text-center py-4">Aucun</p>}
              </div>
            </div>
          ))}
        </div>
      )}

      {view === 'table' && (
        <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
              <th className="py-3 px-3 text-left text-storm font-medium">N Dossier</th>
              <th className="py-3 px-3 text-left text-storm font-medium">Client</th>
              <th className="py-3 px-3 text-left text-storm font-medium">Lot</th>
              <th className="py-3 px-3 text-left text-storm font-medium">Projet</th>
              <th className="py-3 px-3 text-left text-storm font-medium">Type</th>
              <th className="py-3 px-3 text-left text-storm font-medium">Statut</th>
              <th className="py-3 px-3 text-left text-storm font-medium">Reel Non Decl.</th>
              <th className="py-3 px-3 text-right text-storm font-medium">Reel Decl. verse</th>
              <th className="py-3 px-3 text-left text-storm font-medium">Actions</th>
            </tr></thead>
            <tbody>
              {dossiers.length === 0 ? (
                <tr><td colSpan={9} className="py-8 text-center text-storm">Aucun dossier</td></tr>
              ) : dossiers.map(d => (
                <tr key={d.numero} className="border-b border-mist hover:bg-[#FAFAFA] transition">
                  <td className="py-2 px-3"><Link to={`/adv/dossiers/${d.numero}`} className="font-mono text-xs text-iris font-bold hover:underline">{d.numero}</Link></td>
                  <td className="py-2 px-3 font-medium text-sm">{d.client}</td>
                  <td className="py-2 px-3 font-mono text-xs">{d.lot}</td>
                  <td className="py-2 px-3 text-xs">{d.project}</td>
                  <td className="py-2 px-3"><Badge variant={d.type === 'CREDIT_BANCAIRE' ? 'info' : 'neutral'}>{d.type?.replace(/_/g, ' ')}</Badge></td>
                  <td className="py-2 px-3"><Badge variant={d.status === 'ENGAGE' ? 'info' : d.status === 'CLOTURE' ? 'success' : 'warning'}>{d.status?.replace(/_/g, ' ')}</Badge></td>
                  <td className="py-2 px-3"><Badge variant={d.rf2_status === 'SECURISE' ? 'success' : 'warning'}>{d.rf2_status || '-'}</Badge></td>
                  <td className="py-2 px-3 text-right font-mono text-xs">{formatDA(d.total_rf1_paid)} / {formatDA(d.rf1)}</td>
                  <td className="py-2 px-3">
                    <div className="flex gap-2">
                      <Link to={`/adv/dossiers/${d.numero}`} className="text-xs text-iris hover:underline">Detail</Link>
                      <Link to={`/adv/dossiers/${d.numero}/payment`} className="text-xs text-mint hover:underline">Paiement</Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
