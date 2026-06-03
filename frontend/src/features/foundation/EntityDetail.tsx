import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Badge } from '../../components/ui/Badge';
import { formatPct } from '../../lib/format';
import api from '../../lib/api-client';

export function EntityDetail() {
  const { entityId } = useParams();
  const [entity, setEntity] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/foundation/entities/${entityId}`).then(r => { setEntity(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  }, [entityId]);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-20 bg-mist rounded-card animate-pulse" />)}</div>;
  if (!entity) return <p className="text-storm">Entite introuvable</p>;

  return (
    <div>
      <Link to="/foundation/entities" className="text-sm text-iris hover:underline">Entites</Link>
      <div className="flex items-center gap-4 mt-2 mb-6">
        <h1 className="text-[32px] font-bold">{entity.name}</h1>
        <Badge variant="neutral">{entity.form}</Badge>
        <Badge variant={entity.status === 'ACTIF' ? 'success' : entity.status === 'DISSOUTE' ? 'error' : 'warning'}>{entity.status}</Badge>
      </div>

      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-card border border-mist p-5 shadow-card">
          <p className="text-xs text-storm font-medium mb-1">Code</p>
          <p className="font-mono font-bold text-iris">{entity.code}</p>
        </div>
        <div className="bg-white rounded-card border border-mist p-5 shadow-card">
          <p className="text-xs text-storm font-medium mb-1">Regime CNAS</p>
          <p className="font-semibold">{entity.cnas_regime || <span className="text-coral">Non defini</span>}</p>
          {entity.cnas_regime === 'BTPH' && <p className="text-xs text-storm mt-1">Salarie 9.375% + Patronal 25.375% (incl. CACOBATPH)</p>}
          {entity.cnas_regime === 'GENERAL' && <p className="text-xs text-storm mt-1">Salarie 9% + Patronal 25%</p>}
        </div>
        <div className="bg-white rounded-card border border-mist p-5 shadow-card">
          <p className="text-xs text-storm font-medium mb-1">Taux fiscaux</p>
          <div className="flex gap-4">
            <div>
              <span className="text-xs text-storm">IBS:</span>
              <span className={`font-mono font-bold ml-1 ${entity.ibs_rate ? '' : 'text-coral'}`}>{entity.ibs_rate ? `${entity.ibs_rate}%` : 'NULL'}</span>
            </div>
            <div>
              <span className="text-xs text-storm">TAP:</span>
              <span className={`font-mono font-bold ml-1 ${entity.tap_rate ? '' : 'text-coral'}`}>{entity.tap_rate ? `${entity.tap_rate}%` : 'NULL'}</span>
            </div>
          </div>
          {(!entity.ibs_rate || !entity.tap_rate) && <p className="text-xs text-coral mt-1 font-medium">FC-005 requis - CFF bloque</p>}
        </div>
      </div>

      {/* Ownership */}
      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card mb-8">
        <h2 className="text-lg font-semibold mb-4">Actionnariat (entreprise_associe)</h2>
        {entity.ownership?.length > 0 ? (
          <div className="grid grid-cols-4 gap-4">
            {entity.ownership.map((o: any) => {
              const pct = parseFloat(o.pct);
              return (
                <div key={o.associate} className={`p-4 rounded-lg border ${pct === 0 ? 'border-mist bg-gray-50' : 'border-iris bg-[rgba(108,92,231,0.03)]'}`}>
                  <p className="font-semibold text-sm">{o.associate}</p>
                  <p className={`text-2xl font-bold font-mono mt-1 ${pct === 0 ? 'text-silver' : 'text-iris'}`}>{formatPct(pct)}</p>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-storm">Aucun actionnaire renseigne</p>
        )}
      </div>

      {/* Projects */}
      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
        <h2 className="text-lg font-semibold mb-4">Projets portes ({entity.projects?.length || 0})</h2>
        {entity.projects?.length > 0 ? (
          <div className="space-y-2">
            {entity.projects.map((p: any) => (
              <Link key={p.code} to={`/foundation/projects/${p.code}`}
                className="flex items-center justify-between p-3 rounded-lg border border-mist hover:border-iris transition">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-iris font-bold text-sm">{p.code}</span>
                  <span className="text-sm font-medium">{p.name}</span>
                </div>
                <Badge variant={p.status === 'ACTIF' ? 'success' : p.status === 'DONATION' ? 'info' : 'warning'}>{p.status}</Badge>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm text-storm">Aucun projet</p>
        )}
      </div>
    </div>
  );
}
