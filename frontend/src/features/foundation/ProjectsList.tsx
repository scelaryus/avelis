import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '../../components/ui/Badge';
import { formatDA } from '../../lib/format';
import api from '../../lib/api-client';

export function ProjectsList() {
  const [projects, setProjects] = useState<any[]>([]);
  const [entityFilter, setEntityFilter] = useState('');
  const [entities, setEntities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get(`/foundation/projects${entityFilter ? `?entity_id=${entityFilter}` : ''}`),
      api.get('/foundation/entities'),
    ]).then(([pR, eR]) => {
      setProjects(pR.data.data || []);
      setEntities(eR.data.data || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [entityFilter]);

  if (loading) return <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-14 bg-mist rounded-lg animate-pulse" />)}</div>;

  // Extract associate names from parts for columns
  const founderNames = ['Ahmed', 'Mohamed', 'Yazid', 'Yamina'];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[32px] font-bold">Projets</h1>
          <p className="text-sm text-storm">{projects.length} projets du Groupe GFI</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={entityFilter} onChange={e => setEntityFilter(e.target.value)}
            className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
            <option value="">Toutes les entites</option>
            {entities.map(e => <option key={e.code} value={e.code}>{e.code}</option>)}
          </select>
          <Link to="/foundation/projects/new" className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">Nouveau projet</Link>
        </div>
      </div>

      <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
            <th className="py-3 px-3 text-left font-medium text-storm">Code</th>
            <th className="py-3 px-3 text-left font-medium text-storm">Nom</th>
            <th className="py-3 px-3 text-left font-medium text-storm">Entite</th>
            <th className="py-3 px-3 text-left font-medium text-storm">Statut</th>
            {founderNames.map(n => <th key={n} className="py-3 px-2 text-right font-medium text-storm">{n}%</th>)}
            <th className="py-3 px-3 text-right font-medium text-storm">Lots</th>
            <th className="py-3 px-3 text-right font-medium text-storm">Terrain</th>
          </tr></thead>
          <tbody>
            {projects.map(p => {
              const hasParts = p.has_parts;
              return (
                <tr key={p.code} className="border-b border-mist hover:bg-[#FAFAFA] transition cursor-pointer"
                  onClick={() => window.location.href = `/foundation/projects/${p.code}`}>
                  <td className="py-3 px-3 font-mono text-xs text-iris font-bold">{p.code}</td>
                  <td className="py-3 px-3 font-medium">{p.name}</td>
                  <td className="py-3 px-3 text-storm text-xs">{p.entity_code}</td>
                  <td className="py-3 px-3">
                    <Badge variant={p.status === 'ACTIF' ? 'success' : p.status === 'DONATION' ? 'info' : p.status === 'TERRAIN' ? 'neutral' : 'warning'}>{p.status}</Badge>
                  </td>
                  {founderNames.map(n => {
                    const val = p.parts?.[n];
                    return (
                      <td key={n} className="py-3 px-2 text-right font-mono text-xs">
                        {!hasParts ? (
                          <span className="text-honey italic">-</span>
                        ) : val ? (
                          <span className={parseFloat(val) === 0 ? 'text-silver' : ''}>{val}%</span>
                        ) : (
                          <span className="text-silver">0%</span>
                        )}
                      </td>
                    );
                  })}
                  <td className="py-3 px-3 text-right">{p.lot_count || 0}</td>
                  <td className="py-3 px-3 text-right font-mono text-xs">{p.terrain_cost ? formatDA(p.terrain_cost) : '-'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
