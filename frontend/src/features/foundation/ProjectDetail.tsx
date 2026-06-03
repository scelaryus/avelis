import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Badge } from '../../components/ui/Badge';
import { formatDA, formatPct } from '../../lib/format';
import api from '../../lib/api-client';

export function ProjectDetail() {
  const { projectCode } = useParams();
  const [project, setProject] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/foundation/projects/${projectCode}`).then(r => { setProject(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  }, [projectCode]);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-mist rounded-card animate-pulse" />)}</div>;
  if (!project) return <p className="text-storm">Projet introuvable</p>;

  // Check if company % differs from project %
  const entMap: Record<string, number> = {};
  (project.entreprise_associe || []).forEach((e: any) => { entMap[e.associate] = parseFloat(e.pct); });
  const projMap: Record<string, number> = {};
  (project.part_projet || []).forEach((p: any) => { projMap[p.associate] = parseFloat(p.pct); });
  const hasDifference = Object.keys(entMap).some(name => entMap[name] !== (projMap[name] || 0));

  return (
    <div>
      <Link to="/foundation/projects" className="text-sm text-iris hover:underline">Projets</Link>
      <div className="flex items-center gap-4 mt-2 mb-6">
        <h1 className="text-[32px] font-bold">{project.name}</h1>
        <span className="font-mono text-iris font-bold">{project.code}</span>
        <Badge variant={project.status === 'ACTIF' ? 'success' : project.status === 'DONATION' ? 'info' : 'warning'}>{project.status}</Badge>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Entite porteuse</p>
          <Link to={`/foundation/entities/${project.entity_code}`} className="text-sm font-semibold text-iris hover:underline">{project.entity_name}</Link>
          <p className="text-xs font-mono text-storm">{project.entity_code}</p>
        </div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Lots</p>
          <p className="text-xl font-bold">{project.lot_count || 0}</p>
          {project.lots_by_status && Object.entries(project.lots_by_status).map(([s, c]) => (
            <span key={s} className="text-xs text-storm mr-2">{s}: {c as number}</span>
          ))}
        </div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Cout terrain</p>
          <p className="text-lg font-bold font-mono">{project.terrain_cost ? formatDA(project.terrain_cost) : '-'}</p>
        </div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Aliases</p>
          <div className="flex flex-wrap gap-1 mt-1">
            {(project.aliases || []).map((a: string) => (
              <span key={a} className="text-xs bg-lavender/20 text-iris px-2 py-0.5 rounded">{a}</span>
            ))}
            {(!project.aliases || project.aliases.length === 0) && <span className="text-xs text-silver">Aucun alias</span>}
          </div>
        </div>
      </div>

      {/* Ownership comparison — the critical part */}
      {!project.has_parts ? (
        <div className="bg-[rgba(253,203,110,0.15)] border-2 border-honey rounded-card p-6 mb-8">
          <p className="text-lg font-bold text-[#E17055]">Parts non definies</p>
          <p className="text-sm text-storm mt-1">Ce projet est en statut "{project.status}". Aucune structure de parts n'a ete definie.</p>
          <p className="text-sm text-storm">Formulaire FC-013 requis pour activer ce projet. Aucune operation financiere autorisee.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-6 mb-8">
          {/* Table 1: Company ownership (entreprise_associe) */}
          <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
            <h2 className="text-lg font-semibold mb-1">% Entreprise ({project.entity_code})</h2>
            <p className="text-xs text-storm mb-4">Utilise pour: CFF, charges de siege</p>
            <div className="space-y-2">
              {(project.entreprise_associe || []).map((o: any) => {
                const pct = parseFloat(o.pct);
                const projPct = projMap[o.associate];
                const differs = projPct !== undefined && projPct !== pct;
                return (
                  <div key={o.associate} className={`flex items-center justify-between p-3 rounded-lg border ${differs ? 'border-honey bg-[rgba(253,203,110,0.08)]' : 'border-mist'}`}>
                    <span className="text-sm font-medium">{o.associate}</span>
                    <span className={`font-mono font-bold ${pct === 0 ? 'text-silver' : 'text-iris'}`}>{formatPct(pct)}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Table 2: Project ownership (part_projet) */}
          <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
            <h2 className="text-lg font-semibold mb-1">% Projet ({project.code})</h2>
            <p className="text-xs text-storm mb-4">Utilise pour: distribution benefices, charges directes</p>
            <div className="space-y-2">
              {(project.part_projet || []).map((p: any) => {
                const pct = parseFloat(p.pct);
                const entPct = entMap[p.associate];
                const differs = entPct !== undefined && entPct !== pct;
                return (
                  <div key={p.associate} className={`flex items-center justify-between p-3 rounded-lg border ${differs ? 'border-honey bg-[rgba(253,203,110,0.08)]' : 'border-mist'}`}>
                    <span className="text-sm font-medium">{p.associate}</span>
                    <div className="flex items-center gap-2">
                      <span className={`font-mono font-bold ${pct === 0 ? 'text-silver' : 'text-iris'}`}>{formatPct(pct)}</span>
                      {differs && <span className="text-xs text-honey font-bold">=/= {formatPct(entPct!)}</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {hasDifference && project.has_parts && (
        <div className="bg-[rgba(253,203,110,0.1)] border border-honey rounded-lg p-4 mb-8">
          <p className="text-sm font-semibold text-[#E17055]">Les pourcentages entreprise et projet different</p>
          <p className="text-xs text-storm mt-1">
            C'est NORMAL et VOULU. Exemple: le projet principal est porte par SARL-DP (25/25/25/25) mais les parts projet sont 60/20/20/0.
            Le CFF utilise % entreprise, la distribution de benefices utilise % projet.
          </p>
        </div>
      )}
    </div>
  );
}
