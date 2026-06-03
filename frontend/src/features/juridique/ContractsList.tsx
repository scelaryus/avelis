import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { formatDA, formatDate } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

const STATUS_V: Record<string, 'success'|'warning'|'error'|'info'|'neutral'> = {
  actif: 'success', signe: 'success', en_revue: 'warning', brouillon: 'info', expire: 'error', resilie: 'error', archive: 'neutral',
};
const COMP_V: Record<string, 'success'|'warning'|'error'|'neutral'> = {
  conforme: 'success', non_conforme: 'error', en_cours_audit: 'warning', non_evalue: 'neutral',
};

export function ContractsList() {
  const [contracts, setContracts] = useState<any[]>([]);
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const reload = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (typeFilter) params.set('contract_type', typeFilter);
    if (statusFilter) params.set('status', statusFilter);
    api.get(`/juridique/contracts?${params}`).then(r => { setContracts(r.data.data || []); setLoading(false); }).catch(() => setLoading(false));
  };

  useEffect(() => { reload(); }, [typeFilter, statusFilter]);

  if (loading) return <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-16 bg-mist rounded-lg animate-pulse" />)}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/juridique" className="text-sm text-iris hover:underline">&larr; Juridique</Link>
          <h1 className="text-[32px] font-bold mt-1">Contrats ({contracts.length})</h1>
          <p className="text-sm text-storm">Tous les contrats sauf employes (geres par RH)</p>
        </div>
        <Link to="/juridique/contracts/new" className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">
          + Nouveau contrat
        </Link>
      </div>

      {/* Type filter */}
      <div className="flex gap-4 mb-4">
        <div>
          <p className="text-[10px] text-storm uppercase mb-1">Type</p>
          <div className="flex gap-1 flex-wrap">
            {['', 'fournisseur', 'prestation', 'client', 'partenariat', 'confidentialite', 'cadre'].map(t => (
              <button key={t} onClick={() => setTypeFilter(t)}
                className={`px-3 py-1 rounded text-xs font-medium transition ${typeFilter === t ? 'bg-iris text-white' : 'bg-white border border-mist text-storm hover:border-iris'}`}>
                {t || 'Tous'}
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="text-[10px] text-storm uppercase mb-1">Statut</p>
          <div className="flex gap-1 flex-wrap">
            {['', 'actif', 'signe', 'en_revue', 'brouillon', 'expire'].map(s => (
              <button key={s} onClick={() => setStatusFilter(s)}
                className={`px-3 py-1 rounded text-xs font-medium transition ${statusFilter === s ? 'bg-iris text-white' : 'bg-white border border-mist text-storm hover:border-iris'}`}>
                {s || 'Tous'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      {contracts.length === 0 ? (
        <div className="bg-white rounded-card border border-mist p-12 shadow-card text-center text-storm">Aucun contrat pour ces filtres</div>
      ) : (
        <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
              <th className="py-3 px-4 text-left text-storm font-medium">Reference</th>
              <th className="py-3 px-4 text-left text-storm font-medium">Titre</th>
              <th className="py-3 px-4 text-left text-storm font-medium">Type</th>
              <th className="py-3 px-4 text-left text-storm font-medium">Partenaire</th>
              <th className="py-3 px-4 text-left text-storm font-medium">Projet</th>
              <th className="py-3 px-4 text-center text-storm font-medium">Debut</th>
              <th className="py-3 px-4 text-center text-storm font-medium">Fin</th>
              <th className="py-3 px-4 text-right text-storm font-medium">Montant HT</th>
              <th className="py-3 px-4 text-center text-storm font-medium">Statut</th>
              <th className="py-3 px-4 text-center text-storm font-medium">Conformite</th>
            </tr></thead>
            <tbody>
              {contracts.map(c => (
                <tr key={c.id} className={`border-b border-mist hover:bg-[#FAFAFA] transition cursor-pointer ${c.alert ? 'bg-[rgba(255,107,107,0.03)]' : ''}`}>
                  <td className="py-3 px-4 font-mono text-xs text-iris font-semibold">{c.name}</td>
                  <td className="py-3 px-4 text-sm font-medium truncate max-w-[200px]">{c.title}</td>
                  <td className="py-3 px-4"><Badge variant="info">{c.type}</Badge></td>
                  <td className="py-3 px-4 text-sm">{c.partner}</td>
                  <td className="py-3 px-4 text-xs text-storm">{c.project || '-'}</td>
                  <td className="py-3 px-4 text-center font-mono text-xs">{c.date_start ? formatDate(c.date_start) : '-'}</td>
                  <td className="py-3 px-4 text-center font-mono text-xs">
                    {c.date_end ? formatDate(c.date_end) : '-'}
                    {c.days_to_expiry !== null && c.days_to_expiry <= 30 && c.days_to_expiry > 0 && (
                      <span className="text-coral text-[9px] block">{c.days_to_expiry}j restants</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-right font-mono">{formatDA(c.amount)}</td>
                  <td className="py-3 px-4 text-center"><Badge variant={STATUS_V[c.status] || 'neutral'}>{c.status}</Badge></td>
                  <td className="py-3 px-4 text-center"><Badge variant={COMP_V[c.compliance_status] || 'neutral'}>{(c.compliance_status || '').replace(/_/g, ' ')}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {contracts.some(c => c.alert) && (
        <div className="mt-4 bg-[rgba(255,107,107,0.06)] rounded-lg p-3">
          <p className="text-xs text-coral font-medium">Alertes:</p>
          {contracts.filter(c => c.alert).map(c => (
            <p key={c.id} className="text-xs text-storm mt-1">{c.name}: {c.alert}</p>
          ))}
        </div>
      )}
    </div>
  );
}
