import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDA, rfLabel } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { useStore } from '../../store/useStore';
import api from '../../lib/api-client';

const RF_V: Record<string, 'info'|'warning'> = { RF1: 'info', RF2: 'warning' };
const STAT_V: Record<string, 'success'|'warning'|'error'|'neutral'> = { ENCAISSE: 'success', EN_ATTENTE: 'warning', REJETE: 'error', ANNULE: 'neutral' };

export function PaymentsList() {
  const { canSeeRF2 } = useStore();
  const [data, setData] = useState<any>(null);
  const [filterRf, setFilterRf] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [loading, setLoading] = useState(true);

  const reload = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterRf) params.set('type_rf', filterRf);
    if (filterStatus) params.set('status', filterStatus);
    api.get(`/adv/payments?${params}`).then(r => { setData(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  };

  useEffect(() => { reload(); }, [filterRf, filterStatus]);

  if (loading) return <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-16 bg-mist rounded-lg animate-pulse" />)}</div>;
  if (!data) return <p className="text-storm">Aucune donnee</p>;

  const { payments, kpis } = data;

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-2">Paiements ADV</h1>
      <p className="text-sm text-storm mb-6">Tous les paiements enregistres sur les dossiers de vente</p>

      {/* KPI cards */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="bg-white rounded-card border border-[#E0E0E0] p-4 shadow-card text-center">
          <p className="text-xs text-storm">Total</p>
          <p className="text-2xl font-bold">{kpis.total}</p>
        </div>
        <div className="bg-white rounded-card border border-mint p-4 shadow-card text-center">
          <p className="text-xs text-storm">Encaisses</p>
          <p className="text-2xl font-bold text-mint">{kpis.encaisse}</p>
        </div>
        <div className="bg-white rounded-card border border-honey p-4 shadow-card text-center">
          <p className="text-xs text-storm">En attente</p>
          <p className="text-2xl font-bold text-[#E17055]">{kpis.en_attente}</p>
        </div>
        <div className="bg-white rounded-card border border-ocean p-4 shadow-card text-center">
          <p className="text-xs text-storm">Total RF1</p>
          <p className="text-xl font-bold font-mono">{formatDA(kpis.total_rf1)}</p>
        </div>
        {canSeeRF2 && kpis.total_rf2 && (
          <div className="bg-white rounded-card border border-iris p-4 shadow-card text-center">
            <p className="text-xs text-storm">Total RF2</p>
            <p className="text-xl font-bold font-mono text-iris">{formatDA(kpis.total_rf2)}</p>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-4">
        <div>
          <p className="text-[10px] text-storm uppercase mb-1">Type RF</p>
          <div className="flex gap-1">
            {['', 'RF1', ...(canSeeRF2 ? ['RF2'] : [])].map(rf => (
              <button key={rf} onClick={() => setFilterRf(rf)}
                className={`px-3 py-1 rounded text-xs font-medium ${filterRf === rf ? 'bg-iris text-white' : 'bg-white border border-mist text-storm hover:border-iris'}`}>
                {rf || 'Tous'}
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="text-[10px] text-storm uppercase mb-1">Statut</p>
          <div className="flex gap-1">
            {['', 'ENCAISSE', 'EN_ATTENTE', 'REJETE'].map(s => (
              <button key={s} onClick={() => setFilterStatus(s)}
                className={`px-3 py-1 rounded text-xs font-medium ${filterStatus === s ? 'bg-iris text-white' : 'bg-white border border-mist text-storm hover:border-iris'}`}>
                {s || 'Tous'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      {payments.length === 0 ? (
        <div className="bg-white rounded-card border border-mist p-12 shadow-card text-center">
          <p className="text-3xl mb-2">💳</p>
          <p className="text-storm font-medium">Aucun paiement enregistre</p>
          <p className="text-xs text-storm mt-1">Les paiements sont crees depuis les dossiers ADV</p>
          <Link to="/adv/pipeline" className="text-sm text-iris hover:underline mt-2 block">Ouvrir le pipeline dossiers</Link>
        </div>
      ) : (
        <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
              <th className="py-3 px-4 text-left text-storm font-medium">Date</th>
              <th className="py-3 px-4 text-left text-storm font-medium">Dossier</th>
              <th className="py-3 px-4 text-left text-storm font-medium">Client</th>
              <th className="py-3 px-4 text-left text-storm font-medium">Lot</th>
              <th className="py-3 px-4 text-left text-storm font-medium">Projet</th>
              <th className="py-3 px-4 text-center text-storm font-medium">RF</th>
              <th className="py-3 px-4 text-center text-storm font-medium">Mode</th>
              <th className="py-3 px-4 text-right text-storm font-medium">Montant</th>
              <th className="py-3 px-4 text-center text-storm font-medium">Statut</th>
              <th className="py-3 px-4 text-left text-storm font-medium">Reference</th>
            </tr></thead>
            <tbody>
              {payments.map((p: any) => (
                <tr key={p.id} className="border-b border-mist hover:bg-[#FAFAFA] transition">
                  <td className="py-3 px-4 font-mono text-xs">{p.date}</td>
                  <td className="py-3 px-4">
                    {p.dossier_numero ? (
                      <Link to={`/adv/dossiers/${p.dossier_numero}`} className="text-iris hover:underline font-mono text-xs">{p.dossier_numero}</Link>
                    ) : '-'}
                  </td>
                  <td className="py-3 px-4 text-sm">{p.client || '-'}</td>
                  <td className="py-3 px-4 text-xs text-storm">{p.lot || '-'}</td>
                  <td className="py-3 px-4 text-xs text-storm">{p.project || '-'}</td>
                  <td className="py-3 px-4 text-center"><Badge variant={RF_V[p.type_rf] || 'neutral'}>{rfLabel(p.type_rf)}</Badge></td>
                  <td className="py-3 px-4 text-center text-xs">{p.mode}</td>
                  <td className="py-3 px-4 text-right font-mono font-bold">{formatDA(p.montant)}</td>
                  <td className="py-3 px-4 text-center"><Badge variant={STAT_V[p.status] || 'neutral'}>{p.status}</Badge></td>
                  <td className="py-3 px-4 text-xs text-storm">{p.reference || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
