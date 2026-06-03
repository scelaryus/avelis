import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

export function EntitiesList() {
  const [entities, setEntities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/foundation/entities').then(r => { setEntities(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-14 bg-mist rounded-lg animate-pulse" />)}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[32px] font-bold">Entites Juridiques</h1>
          <p className="text-sm text-storm">{entities.length} entites du Groupe GFI</p>
        </div>
        <Link to="/foundation/entities/new" className="px-4 py-2 bg-rose-800 text-white rounded-button text-sm font-semibold hover:bg-rose-900">Nouvelle entite</Link>
      </div>

      <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
            <th className="py-3 px-4 text-left font-medium text-storm">Code</th>
            <th className="py-3 px-4 text-left font-medium text-storm">Nom</th>
            <th className="py-3 px-4 text-left font-medium text-storm">Forme</th>
            <th className="py-3 px-4 text-left font-medium text-storm">Statut</th>
            <th className="py-3 px-4 text-left font-medium text-storm">CNAS</th>
            <th className="py-3 px-4 text-right font-medium text-storm">IBS</th>
            <th className="py-3 px-4 text-right font-medium text-storm">TAP</th>
            <th className="py-3 px-4 text-right font-medium text-storm">Projets</th>
          </tr></thead>
          <tbody>
            {entities.map(e => (
              <tr key={e.code} className="border-b border-mist hover:bg-[#FAFAFA] transition cursor-pointer"
                onClick={() => window.location.href = `/foundation/entities/${e.code}`}>
                <td className="py-3 px-4 font-mono text-xs text-iris font-bold">{e.code}</td>
                <td className="py-3 px-4 font-medium">{e.name}</td>
                <td className="py-3 px-4"><Badge variant="neutral">{e.form}</Badge></td>
                <td className="py-3 px-4">
                  <Badge variant={e.status === 'ACTIF' ? 'success' : e.status === 'DISSOUTE' ? 'error' : e.status === 'SATELLITE' ? 'info' : 'warning'}>{e.status}</Badge>
                </td>
                <td className="py-3 px-4">
                  {e.cnas_regime ? <Badge variant={e.cnas_regime === 'BTPH' ? 'info' : 'neutral'}>{e.cnas_regime}</Badge> : <span className="text-silver">-</span>}
                </td>
                <td className="py-3 px-4 text-right font-mono">
                  {e.ibs_rate ? `${e.ibs_rate}%` : <span className="text-coral font-bold">NULL</span>}
                </td>
                <td className="py-3 px-4 text-right font-mono">
                  {e.tap_rate ? `${e.tap_rate}%` : <span className="text-coral font-bold">NULL</span>}
                </td>
                <td className="py-3 px-4 text-right font-bold">{e.project_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
