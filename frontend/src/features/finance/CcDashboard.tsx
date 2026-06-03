import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { DoubleViewToggle } from '../../components/shared/DoubleViewToggle';
import { useStore } from '../../store/useStore';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import api from '../../lib/api-client';

export function CcDashboard() {
  const { viewMode } = useStore();
  const [tree, setTree] = useState<any[]>([]);
  const [entities, setEntities] = useState<any[]>([]);
  const [entityId, setEntityId] = useState('');
  const [year, setYear] = useState<string>('');
  const [viewTab, setViewTab] = useState<'tree' | 'table' | 'chart'>('tree');
  const [associates, setAssociates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    params.set('view', viewMode);
    if (entityId) params.set('entity_id', entityId);
    if (year) params.set('year', year);
    Promise.all([
      api.get(`/cc/tree?${params}`),
      api.get('/foundation/entities'),
      api.get(`/cc/dashboard/${viewMode}`),
    ]).then(([treeR, entR, dashR]) => {
      const raw = treeR.data.data;
      setTree(raw?.children || (Array.isArray(raw) ? raw : []));
      setEntities(entR.data.data || []);
      setAssociates(dashR.data.data?.associates || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [viewMode, entityId, year]);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-24 bg-mist rounded-card animate-pulse" />)}</div>;

  const yaminaAlert = associates.find((a: any) => a.yamina_alert);

  const renderNode = (node: any, depth = 0): any => (
    <div key={node.code}>
      <Link to={`/finance/cc/${node.code}`}
        className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-[rgba(108,92,231,0.04)] transition group"
        style={{ paddingLeft: `${12 + depth * 24}px` }}>
        <div className="flex items-center gap-2">
          {node.children?.length > 0 && <span className="text-storm text-xs">&#9656;</span>}
          <span className="font-mono text-xs text-iris font-semibold">{node.code}</span>
          <span className="text-sm">{node.label}</span>
          {node.categorie && <Badge variant="neutral">{node.categorie}</Badge>}
        </div>
        <div className="flex items-center gap-4">
          {viewMode === 'interne' && node.montant_rf2 && parseFloat(node.montant_rf2) !== 0 && (
            <span className="text-xs font-mono text-storm">RF2: {formatDA(node.montant_rf2)}</span>
          )}
          {viewMode === 'interne' && node.montant_rf3 && parseFloat(node.montant_rf3) !== 0 && (
            <span className="text-xs font-mono text-honey">RF3: {formatDA(node.montant_rf3)}</span>
          )}
          <span className={`font-mono text-sm font-bold ${node.montant_total && parseFloat(node.montant_total) < 0 ? 'text-coral' : ''}`}>
            {node.montant_total ? formatDA(node.montant_total) : ''}
          </span>
        </div>
      </Link>
      {node.children?.map((c: any) => renderNode(c, depth + 1))}
    </div>
  );

  // Flatten tree for table/chart view
  const flatNodes: any[] = [];
  const flatten = (nodes: any[], depth = 0) => {
    for (const n of nodes) {
      flatNodes.push({ ...n, depth });
      if (n.children) flatten(n.children, depth + 1);
    }
  };
  flatten(tree);

  return (
    <div>
      {yaminaAlert && (
        <div className="bg-coral text-white rounded-lg p-4 mb-6 animate-[flash_2s_infinite]">
          <p className="font-bold">VIOLATION Y2/Y3/Y4 : Yamina a un CFF impute sur une entite ou elle est a 0%.</p>
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[32px] font-bold">Centre de Couts</h1>
        <div className="flex items-center gap-3">
          <select value={year} onChange={e => setYear(e.target.value)}
            className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
            <option value="">Toutes les annees</option>
            {Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i).map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <select value={entityId} onChange={e => setEntityId(e.target.value)}
            className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
            <option value="">Toutes les entites</option>
            {entities.map(e => <option key={e.code} value={e.code}>{e.code} - {e.name}</option>)}
          </select>
          <DoubleViewToggle />
        </div>
      </div>

      <div className="flex gap-2 mb-4">
        {(['tree', 'table', 'chart'] as const).map(v => (
          <button key={v} onClick={() => setViewTab(v)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${viewTab === v ? 'bg-iris text-white' : 'bg-white border border-mist text-storm hover:border-iris'}`}>
            {v === 'tree' ? 'Arbre' : v === 'table' ? 'Tableau' : 'Graphique'}
          </button>
        ))}
      </div>

      {viewTab === 'tree' && (
        <div className="bg-white rounded-card border border-[#E0E0E0] p-4 shadow-card">
          {tree.length === 0 ? <p className="text-sm text-storm py-4 text-center">Aucun noeud CC</p> : tree.map(n => renderNode(n))}
        </div>
      )}

      {viewTab === 'table' && (
        <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
              <th className="py-2 px-4 text-left text-storm">Code</th>
              <th className="py-2 px-4 text-left text-storm">Libelle</th>
              <th className="py-2 px-4 text-right text-storm">Reel Declare</th>
              {viewMode === 'interne' && <th className="py-2 px-4 text-right text-storm">Reel Non Decl.</th>}
              {viewMode === 'interne' && <th className="py-2 px-4 text-right text-storm">Fictif Declare</th>}
              <th className="py-2 px-4 text-right text-storm">Total</th>
            </tr></thead>
            <tbody>
              {flatNodes.filter(n => n.montant_total && parseFloat(n.montant_total) !== 0).map(n => (
                <tr key={n.code} className="border-b border-mist hover:bg-[#FAFAFA] cursor-pointer"
                  onClick={() => window.location.href = `/finance/cc/${n.code}`}>
                  <td className="py-2 px-4 font-mono text-xs text-iris" style={{ paddingLeft: `${16 + n.depth * 16}px` }}>{n.code}</td>
                  <td className="py-2 px-4">{n.label}</td>
                  <td className="py-2 px-4 text-right font-mono">{n.montant_rf1 && parseFloat(n.montant_rf1) !== 0 ? formatDA(n.montant_rf1) : '-'}</td>
                  {viewMode === 'interne' && <td className="py-2 px-4 text-right font-mono">{n.montant_rf2 && parseFloat(n.montant_rf2) !== 0 ? formatDA(n.montant_rf2) : '-'}</td>}
                  {viewMode === 'interne' && <td className="py-2 px-4 text-right font-mono">{n.montant_rf3 && parseFloat(n.montant_rf3) !== 0 ? formatDA(n.montant_rf3) : '-'}</td>}
                  <td className={`py-2 px-4 text-right font-mono font-bold ${parseFloat(n.montant_total) < 0 ? 'text-coral' : ''}`}>{formatDA(n.montant_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {viewTab === 'chart' && (
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <ResponsiveContainer width="100%" height={Math.max(300, flatNodes.filter(n => n.level === 3).length * 30)}>
            <BarChart data={flatNodes.filter(n => n.level === 3 && n.montant_total)} layout="vertical">
              <XAxis type="number" tickFormatter={v => `${(v / 1000000).toFixed(0)}M`} tick={{ fontSize: 11, fill: '#636E72' }} />
              <YAxis type="category" dataKey="label" tick={{ fontSize: 10, fill: '#2D3436' }} width={160} />
              <Tooltip formatter={(v: number) => formatDA(v)} />
              <Bar dataKey="montant_total" fill="#6C5CE7" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Associate cards */}
      <div className="mt-8">
        <h2 className="text-lg font-semibold mb-4">Quote-Parts Associes</h2>
        <div className="grid grid-cols-4 gap-4">
          {associates.map((a: any) => (
            <div key={a.name} className={`bg-white rounded-card border p-5 shadow-card ${a.yamina_alert ? 'border-coral' : 'border-mist'}`}>
              <p className="font-semibold mb-3">{a.name}</p>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between"><span className="text-storm">QP Brute</span><span className="font-mono">{formatDA(a.qp_brute)}</span></div>
                <div className="flex justify-between"><span className="text-storm">CFF</span><span className="font-mono text-coral">{parseFloat(a.cff_deducted) === 0 ? '0 DA' : '-' + formatDA(a.cff_deducted)}</span></div>
                <div className="flex justify-between border-t border-mist pt-1"><span className="font-medium">CCA Solde</span>
                  <span className={`font-mono font-bold ${parseFloat(a.cca_balance) < 0 ? 'text-coral' : 'text-mint'}`}>{formatDA(a.cca_balance)}</span></div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <style>{`@keyframes flash { 0%,100% { opacity:1 } 50% { opacity:0.5 } }`}</style>
    </div>
  );
}
