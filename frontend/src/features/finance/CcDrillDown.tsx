import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { formatDA, formatDate, rfName, rfLabel } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { DoubleViewToggle } from '../../components/shared/DoubleViewToggle';
import { useStore } from '../../store/useStore';
import api from '../../lib/api-client';

export function CcDrillDown() {
  const { nodeCode } = useParams();
  const { viewMode } = useStore();
  const [node, setNode] = useState<any>(null);
  const [txns, setTxns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [year, setYear] = useState<string>('');

  useEffect(() => {
    const params = new URLSearchParams();
    params.set('view', viewMode);
    if (year) params.set('year', year);
    api.get(`/cc/tree/${nodeCode}/drill-down?${params}`).then(r => {
      setNode(r.data.data?.node);
      setTxns(r.data.data?.transactions || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [nodeCode, viewMode, year]);

  if (loading) return <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-12 bg-mist rounded-lg animate-pulse" />)}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/finance/cc" className="text-sm text-iris hover:underline">← Centre de Coûts</Link>
          <h1 className="text-[32px] font-bold mt-1">{node?.label || nodeCode}</h1>
          <p className="text-sm font-mono text-storm">{nodeCode}</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={year} onChange={e => setYear(e.target.value)}
            className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none">
            <option value="">Toutes annees</option>
            {Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i).map(y => (
              <option key={y} value={String(y)}>{y}</option>
            ))}
          </select>
          <DoubleViewToggle />
        </div>
      </div>
      <div className="grid grid-cols-4 gap-4 mb-6">
        {['RF1', 'RF2', 'RF3', 'RF4'].map(rf => (
          (viewMode === 'interne' || rf === 'RF1') && (
            <div key={rf} className="bg-white rounded-card border border-mist p-4 shadow-card">
              <p className="text-xs text-storm font-medium">{rfLabel(rf)}</p>
              <p className="text-xl font-bold font-mono mt-1">{formatDA(node?.[`montant_${rf.toLowerCase()}`] || 0)}</p>
            </div>
          )
        ))}
        <div className="bg-white rounded-card border border-iris p-4 shadow-card">
          <p className="text-xs text-iris font-medium">Total</p>
          <p className="text-xl font-bold font-mono mt-1 text-iris">{formatDA(node?.montant_total || 0)}</p>
        </div>
      </div>
      <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-mist">
          <h2 className="font-semibold">Transactions ({txns.length})</h2>
          <button className="text-sm text-iris font-medium hover:underline">Exporter Excel</button>
        </div>
        <table className="w-full text-sm">
          <thead><tr className="bg-[#FAFAFA] border-b border-mist">
            <th className="py-2 px-4 text-left font-medium text-storm">Date</th>
            <th className="py-2 px-4 text-left font-medium text-storm">Source</th>
            <th className="py-2 px-4 text-left font-medium text-storm">Libellé</th>
            <th className="py-2 px-4 text-left font-medium text-storm">RF</th>
            <th className="py-2 px-4 text-right font-medium text-storm">Montant</th>
            <th className="py-2 px-4 text-left font-medium text-storm">Pièce</th>
          </tr></thead>
          <tbody>
            {txns.length === 0 ? (
              <tr><td colSpan={6} className="py-8 text-center text-storm">Aucune transaction pour ce noeud</td></tr>
            ) : txns.map((t: any, i: number) => (
              <tr key={i} className="border-b border-mist hover:bg-[#FAFAFA] transition">
                <td className="py-2.5 px-4 font-mono text-xs">{formatDate(t.date)}</td>
                <td className="py-2.5 px-4"><Badge variant="neutral">{t.source_type}</Badge></td>
                <td className="py-2.5 px-4">{t.label}</td>
                <td className="py-2.5 px-4"><Badge variant={t.rf === 'RF2' ? 'warning' : t.rf === 'RF3' ? 'error' : 'info'}>{rfLabel(t.rf)}</Badge></td>
                <td className={`py-2.5 px-4 text-right font-mono font-bold ${t.amount < 0 ? 'text-coral' : 'text-mint'}`}>{formatDA(t.amount)}</td>
                <td className="py-2.5 px-4">{t.doc_id ? <Link to={`/documents/${t.doc_id}`} className="text-iris text-xs hover:underline">Voir</Link> : <span className="text-silver text-xs">—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
