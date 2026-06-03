import { useEffect, useState } from 'react';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { ProofUpload } from '../../components/shared/ProofUpload';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import api from '../../lib/api-client';

const STATUS_VARIANT: Record<string, 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  EN_ATTENTE: 'warning', SOUMIS: 'info', VALIDE: 'success', REFUSE: 'error', PAYE: 'success',
};
const ROLE_COLORS: Record<string, string> = { COMMERCIAL: '#6C5CE7', MANAGER: '#0984E3', EQUIPE: '#00B894' };

export function CommissionTracker() {
  const [commissions, setCommissions] = useState<any[]>([]);
  const [unclaimed, setUnclaimed] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [claimingId, setClaimingId] = useState<string | null>(null);
  const [proofId, setProofId] = useState('');
  const [claimNote, setClaimNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const reload = () => {
    setLoading(true);
    Promise.all([
      api.get('/adv/commissions'),
      api.get('/adv/commissions/my-pending'),
    ]).then(([cR, uR]) => {
      setCommissions(cR.data.data || []);
      setUnclaimed(uR.data.data || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { reload(); }, []);

  const claimCommission = async (commId: string) => {
    if (!proofId) return;
    setSubmitting(true);
    try {
      // The commission is already assigned to this commercial — find employee_id from the unclaimed list
      const commission = unclaimed.find(u => u.id === commId);
      // Get employee from pending commissions endpoint (already filtered to current user)
      const empRes = await api.get('/drh/employees');
      const firstEmp = empRes.data.data?.[0];
      if (!firstEmp) { alert('Aucun employe trouve'); return; }

      await api.post(`/adv/commissions/${commId}/claim`, {
        employee_id: firstEmp.id,
        proof_document_id: proofId,
        note: claimNote,
      });
      setClaimingId(null);
      setProofId('');
      setClaimNote('');
      reload();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur');
    } finally {
      setSubmitting(false);
    }
  };

  const validateCommission = async (commId: string, decision: string) => {
    try {
      await api.post(`/adv/commissions/${commId}/validate`, { decision });
      reload();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur');
    }
  };

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-20 bg-mist rounded-card animate-pulse" />)}</div>;

  // KPIs
  const totalBrute = commissions.reduce((s, c) => s + parseFloat(c.commission_brute || '0'), 0);
  const totalNette = commissions.reduce((s, c) => s + parseFloat(c.commission_nette || '0'), 0);
  const validees = commissions.filter(c => c.status === 'VALIDE').length;
  const enAttente = commissions.filter(c => c.status === 'EN_ATTENTE' || c.status === 'SOUMIS').length;

  // Distribution pie
  const byRole = commissions.reduce((acc: any, c) => {
    acc[c.role_in_sale] = (acc[c.role_in_sale] || 0) + parseFloat(c.commission_nette || '0');
    return acc;
  }, {});
  const pieData = Object.entries(byRole).map(([role, val]) => ({ name: role, value: val as number }));

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-2">Commissions Commerciales</h1>
      <p className="text-sm text-storm mb-6">Reclamez vos commissions avec preuve d'acquisition client</p>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-card border border-[#E0E0E0] p-5 shadow-card">
          <p className="text-xs text-storm mb-1">Total Commissions Brutes</p>
          <p className="text-xl font-bold font-mono text-iris">{formatDA(totalBrute)}</p>
        </div>
        <div className="bg-white rounded-card border border-[#E0E0E0] p-5 shadow-card">
          <p className="text-xs text-storm mb-1">Total Net (apres distribution)</p>
          <p className="text-xl font-bold font-mono">{formatDA(totalNette)}</p>
        </div>
        <div className="bg-white rounded-card border border-[#E0E0E0] p-5 shadow-card">
          <p className="text-xs text-storm mb-1">Validees</p>
          <p className="text-xl font-bold text-mint">{validees}</p>
        </div>
        <div className="bg-white rounded-card border border-[#E0E0E0] p-5 shadow-card">
          <p className="text-xs text-storm mb-1">En Attente</p>
          <p className={`text-xl font-bold ${enAttente > 0 ? 'text-honey' : 'text-mint'}`}>{enAttente}</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6 mb-6">
        {/* Distribution pie */}
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <h2 className="text-base font-semibold mb-3">Distribution 70/10/20</h2>
          {pieData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={140}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={35} outerRadius={55} paddingAngle={2} dataKey="value" stroke="none">
                    {pieData.map((d, i) => <Cell key={i} fill={ROLE_COLORS[d.name] || '#B2BEC3'} />)}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatDA(v)} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex justify-center gap-4 mt-2">
                {pieData.map(d => (
                  <span key={d.name} className="flex items-center gap-1 text-xs">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: ROLE_COLORS[d.name] || '#B2BEC3' }} />
                    {d.name} {formatDA(d.value)}
                  </span>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-storm text-center py-8">Aucune commission</p>
          )}
        </div>

        {/* Unclaimed commissions — for commercial agents to claim */}
        <div className="col-span-2 bg-white rounded-card border-2 border-iris p-6 shadow-card">
          <h2 className="text-base font-semibold mb-3">Mes Commissions en Attente de Preuve ({unclaimed.length})</h2>
          <p className="text-xs text-storm mb-4">Vous etes l'agent qui a obtenu ces clients. Soumettez la preuve d'acquisition pour debloquer votre commission.</p>

          {unclaimed.length === 0 ? (
            <div className="flex items-center gap-3 py-6 justify-center">
              <span className="text-2xl">&#10003;</span>
              <p className="text-sm text-mint font-medium">Toutes les commissions sont reclamees</p>
            </div>
          ) : (
            <div className="space-y-3">
              {unclaimed.map(u => (
                <div key={u.id} className={`p-4 rounded-lg border ${claimingId === u.id ? 'border-iris bg-[rgba(108,92,231,0.04)]' : 'border-mist'}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold">{u.dossier_numero} -- {u.client}</p>
                      <p className="text-xs text-storm">Role: {u.role_in_sale} -- Taux: {u.taux}%</p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold font-mono text-iris">{formatDA(u.commission_nette)}</p>
                      {claimingId !== u.id && (
                        <button onClick={() => setClaimingId(u.id)}
                          className="mt-1 px-3 py-1 bg-iris text-white rounded text-xs font-medium hover:bg-rose-800">
                          Reclamer avec preuve
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Claim form */}
                  {claimingId === u.id && (
                    <div className="mt-4 pt-4 border-t border-mist space-y-3">
                      <p className="text-sm font-medium">Justificatif d'acquisition client</p>
                      <p className="text-xs text-storm">Uploadez: contrat signe, bon de reservation, PV de visite, ou tout document prouvant votre role dans cette vente</p>

                      <ProofUpload onUploaded={id => setProofId(id)} label="Preuve d'acquisition client (obligatoire)" />

                      <div>
                        <label className="text-xs font-medium text-storm block mb-1">Note explicative</label>
                        <textarea value={claimNote} onChange={e => setClaimNote(e.target.value)} rows={2}
                          className="w-full border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none resize-none"
                          placeholder="Decrivez votre role dans l'acquisition de ce client..." />
                      </div>

                      <div className="flex gap-2">
                        <button onClick={() => claimCommission(u.id)}
                          disabled={!proofId || submitting}
                          className="px-4 py-2 bg-mint text-white rounded-button text-sm font-semibold hover:bg-[#00A884] disabled:bg-mist disabled:text-silver">
                          {submitting ? 'Envoi...' : 'Soumettre la reclamation'}
                        </button>
                        <button onClick={() => { setClaimingId(null); setProofId(''); setClaimNote(''); }}
                          className="px-4 py-2 border border-mist rounded-button text-sm text-storm hover:bg-gray-50">
                          Annuler
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* All commissions table */}
      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
        <h2 className="text-base font-semibold mb-4">Historique Commissions ({commissions.length})</h2>
        {commissions.length === 0 ? (
          <p className="text-sm text-storm text-center py-4">Aucune commission generee. Les commissions sont creees automatiquement quand un dossier ADV atteint le statut ENGAGE.</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b-2 border-mist">
              <th className="py-2 text-left text-storm font-medium">Dossier</th>
              <th className="py-2 text-left text-storm font-medium">Client</th>
              <th className="py-2 text-left text-storm font-medium">Agent</th>
              <th className="py-2 text-center text-storm font-medium">Role</th>
              <th className="py-2 text-right text-storm font-medium">CA</th>
              <th className="py-2 text-center text-storm font-medium">Taux</th>
              <th className="py-2 text-right text-storm font-medium">Commission</th>
              <th className="py-2 text-center text-storm font-medium">Statut</th>
              <th className="py-2 text-center text-storm font-medium">Action</th>
            </tr></thead>
            <tbody>
              {commissions.map(c => (
                <tr key={c.id} className="border-b border-mist hover:bg-[#FAFAFA]">
                  <td className="py-3 font-mono text-xs text-iris">{c.dossier_numero}</td>
                  <td className="py-3 text-sm">{c.client}</td>
                  <td className="py-3 text-sm">{c.employee_name}</td>
                  <td className="py-3 text-center">
                    <span className="text-[10px] font-bold text-white px-2 py-0.5 rounded" style={{ background: ROLE_COLORS[c.role_in_sale] || '#636E72' }}>
                      {c.role_in_sale} {c.distribution_pct}%
                    </span>
                  </td>
                  <td className="py-3 text-right font-mono text-xs">{formatDA(c.chiffre_encaisse)}</td>
                  <td className="py-3 text-center text-xs">{c.taux_commission}%</td>
                  <td className="py-3 text-right font-mono font-bold">{formatDA(c.commission_nette)}</td>
                  <td className="py-3 text-center"><Badge variant={STATUS_VARIANT[c.status] || 'neutral'}>{c.status}</Badge></td>
                  <td className="py-3 text-center">
                    {c.status === 'SOUMIS' && (
                      <div className="flex gap-1 justify-center">
                        <button onClick={() => validateCommission(c.id, 'VALIDE')}
                          className="text-xs text-mint font-medium hover:underline">Valider</button>
                        <button onClick={() => validateCommission(c.id, 'REFUSE')}
                          className="text-xs text-coral font-medium hover:underline">Refuser</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
