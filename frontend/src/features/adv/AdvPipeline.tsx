import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Badge } from '../../components/ui/Badge';
import { formatDA } from '../../lib/format';
import { useStore } from '../../store/useStore';
import api from '../../lib/api-client';

const LOT_COLUMNS = [
  { key: 'DISPONIBLE', label: 'Disponible', bg: 'bg-[rgba(85,239,196,0.08)]' },
  { key: 'VERROUILLE', label: 'Verrouille', bg: 'bg-[rgba(253,203,110,0.08)]' },
  { key: 'RESERVE', label: 'Reserve', bg: 'bg-[rgba(116,185,255,0.08)]' },
  { key: 'ENGAGE', label: 'Engage', bg: 'bg-[rgba(162,155,254,0.08)]' },
  { key: 'VENDU', label: 'Vendu', bg: 'bg-[rgba(0,184,148,0.08)]' },
];

export function AdvPipeline() {
  const nav = useNavigate();
  const { canSeeRF2 } = useStore();
  const [lots, setLots] = useState<any[]>([]);
  const [dossiers, setDossiers] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [projectFilter, setProjectFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const reload = () => {
    setLoading(true);
    Promise.all([
      api.get(`/adv/edd/lots?status=ALL${projectFilter ? `&project_id=${projectFilter}` : ''}`),
      api.get('/adv/dossiers'),
      api.get('/foundation/projects?status=ACTIF'),
    ]).then(([lotR, dosR, projR]) => {
      setLots(lotR.data.data || []);
      setDossiers(dosR.data.data || []);
      setProjects(projR.data.data || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { reload(); }, [projectFilter]);

  const dossierByLot: Record<string, any> = {};
  dossiers.forEach(d => { dossierByLot[d.lot] = d; });
  const projectNameByCode: Record<string, string> = {};
  projects.forEach((p) => { projectNameByCode[p.code] = p.name; });
  const cleanLegacyNames = (value: string) => value
    .replace(/EDEN/gi, 'Projet')
    .replace(/AUREA/gi, 'Projet')
    .replace(/IRENE/gi, 'Projet')
    .replace(/JASMIN/gi, 'Projet')
    .replace(/OPERA/gi, 'Projet')
    .replace(/LYS/gi, 'Projet')
    .replace(/BAYTI/gi, 'Projet')
    .replace(/ALLO_MAISON/gi, 'Projet')
    .replace(/MAGNOLIA/gi, 'Projet');

  const lockAndReserve = async (lotRef: string) => {
    try {
      await api.post(`/adv/edd/lots/${lotRef}/lock`);
      nav(`/adv/dossiers/new?lot=${lotRef}`);
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur de verrouillage');
      reload();
    }
  };

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-40 bg-mist rounded-card animate-pulse" />)}</div>;

  const grouped: Record<string, any[]> = {};
  LOT_COLUMNS.forEach(c => { grouped[c.key] = []; });
  lots.forEach(l => {
    if (grouped[l.status]) grouped[l.status].push(l);
  });

  const totalLots = lots.length;
  const dispoLots = (grouped['DISPONIBLE'] || []).length;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-[32px] font-bold">Lots EDD</h1>
          <p className="text-sm text-storm">{totalLots} lots — {dispoLots} disponibles — {totalLots - dispoLots} reserves/engages</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={projectFilter} onChange={e => setProjectFilter(e.target.value)}
            className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
            <option value="">Tous les projets</option>
            {projects.map(p => <option key={p.code} value={p.code}>{p.code} - {p.name}</option>)}
          </select>
          <Link to="/adv/lots/new" className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">+ Nouveau lot</Link>
        </div>
      </div>

      {/* Lots Kanban */}
      <div className="flex gap-3 overflow-x-auto pb-4">
        {LOT_COLUMNS.map(col => (
          <div key={col.key} className={`min-w-[240px] flex-shrink-0 rounded-lg p-3 ${col.bg}`}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-storm">{col.label}</h3>
              <span className="bg-white text-charcoal text-xs font-bold px-2 py-0.5 rounded-full shadow-sm">{grouped[col.key]?.length || 0}</span>
            </div>
            <div className="space-y-2">
              {(grouped[col.key] || []).map(lot => {
                const dos = dossierByLot[lot.ref];
                return (
                  <div key={lot.ref} className="bg-white rounded-lg border border-mist p-3 shadow-card hover:shadow-card-hover transition">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs text-iris font-bold">{cleanLegacyNames(lot.ref)}</span>
                      <Badge variant="neutral">{lot.typology}</Badge>
                    </div>
                    <p className="text-xs text-storm">{projectNameByCode[lot.project_code] || cleanLegacyNames(lot.project_code)} — {lot.surface}m2 — Et.{lot.floor}</p>
                    <p className="text-sm font-mono font-bold mt-1">{formatDA(lot.rf1_price)}</p>
                    {canSeeRF2 && lot.rf2_price && parseFloat(lot.rf2_price) > 0 && (
                      <p className="text-xs font-mono text-storm">RF2: {formatDA(lot.rf2_price)}</p>
                    )}
                    {dos && (
                      <div className="mt-2 pt-2 border-t border-mist">
                        <Link to={`/adv/dossiers/${dos.numero}`} className="text-xs text-iris hover:underline font-medium">{cleanLegacyNames(dos.numero)}</Link>
                        <p className="text-xs text-storm">{dos.client}</p>
                        <Badge variant={dos.rf2_status === 'SECURISE' ? 'success' : 'warning'}>
                          RF2 {dos.rf2_status === 'SECURISE' ? '✓' : '...'}
                        </Badge>
                      </div>
                    )}
                    {lot.locked && (
                      <div className="flex items-center gap-1 mt-1 text-xs text-honey">🔒 {lot.locked_by} — {lot.locked_minutes_remaining}min</div>
                    )}
                    {lot.status === 'DISPONIBLE' && (
                      <button onClick={() => lockAndReserve(lot.ref)}
                        className="mt-2 w-full py-1.5 bg-iris text-white rounded text-xs font-medium hover:bg-rose-800">
                        Reserver ce lot
                      </button>
                    )}
                  </div>
                );
              })}
              {(grouped[col.key] || []).length === 0 && <p className="text-xs text-silver text-center py-4">Aucun lot</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
