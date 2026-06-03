import { useEffect, useState } from 'react';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

export function TaskNeeds() {
  const [needs, setNeeds] = useState<any[]>([]);
  const [assignments, setAssignments] = useState<any[]>([]);
  const [needText, setNeedText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [decomposing, setDecomposing] = useState<string | null>(null);
  const [decomResult, setDecomResult] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = () => {
    setLoading(true);
    Promise.all([
      api.get('/drh/spi360/needs'),
      api.get('/drh/spi360/assignments'),
    ]).then(([nR, aR]) => {
      setNeeds(nR.data.data || []);
      setAssignments(aR.data.data || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { reload(); }, []);

  const submitNeed = async () => {
    if (!needText.trim()) return;
    setSubmitting(true);
    try {
      const res = await api.post('/drh/spi360/needs', { need_text: needText });
      const needId = res.data.data.need_id;
      setNeedText('');

      // Auto-decompose
      setDecomposing(needId);
      const decRes = await api.post(`/drh/spi360/needs/${needId}/decompose`);
      setDecomResult(decRes.data.data.subtasks || []);
      setDecomposing(null);
      reload();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur');
    } finally {
      setSubmitting(false);
    }
  };

  const respondToAssignment = async (id: string, response: string, counter?: number) => {
    try {
      await api.post(`/drh/spi360/assignments/${id}/daf-respond`, {
        response, counter_bonus_da: counter,
      });
      reload();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur');
    }
  };

  const finalizeAssignment = async (id: string, score: number) => {
    try {
      await api.post(`/drh/spi360/assignments/${id}/finalize`, { final_score: score });
      reload();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Erreur');
    }
  };

  const COMPLEXITY_COLORS: Record<string, string> = {
    SIMPLE: '#00B894', MOYEN: '#0984E3', COMPLEXE: '#E17055',
  };
  const STATUS_VARIANT: Record<string, 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
    PROPOSE: 'info', PROPOSITION_SOUMISE: 'warning', EN_NEGOCIATION: 'warning',
    EN_COURS: 'info', PREUVE_SOUMISE: 'warning', VALIDE_IA: 'success',
    FINALISE: 'success', ANNULE: 'error',
  };

  return (
    <div>
      <h1 className="text-[32px] font-bold mb-2">Gestion des Taches SPI</h1>
      <p className="text-sm text-storm mb-6">Decrivez vos besoins du jour. L&apos;agent IA analyse, decompose et dispatch chaque tache vers un collaborateur.</p>

      {/* Need input */}
      <div className="bg-white rounded-card border-2 border-iris p-6 shadow-card mb-8">
        <h2 className="font-semibold mb-3">Besoins du jour</h2>
        <textarea value={needText} onChange={e => setNeedText(e.target.value)} rows={4}
          className="w-full border border-mist rounded-input px-4 py-3 text-sm focus:border-iris outline-none resize-none"
          placeholder="Ex: Aujourd'hui je veux que l'equipe finalise les relances des 5 dossiers ADV en retard, prepare le rapprochement bancaire de Mars, et mette a jour le centre de couts du projet principal..." />
        <div className="flex items-center justify-between mt-3">
          <p className="text-xs text-storm">{needText.length} caracteres — l&apos;agent va decomposer et dispatcher</p>
          <button onClick={submitNeed} disabled={!needText.trim() || submitting}
            className="px-6 py-2.5 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800 disabled:bg-mist disabled:text-silver">
            {submitting ? 'Envoi + decomposition IA...' : 'Envoyer et decomposer'}
          </button>
        </div>
      </div>

      {/* Decomposition result */}
      {decomposing && (
        <div className="bg-[rgba(108,92,231,0.06)] rounded-card p-6 mb-6 text-center">
          <div className="animate-spin w-8 h-8 border-2 border-iris border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-sm text-iris font-medium">L&apos;agent analyse, decompose et dispatch vos besoins...</p>
        </div>
      )}

      {decomResult.length > 0 && (
        <div className="bg-white rounded-card border border-mint p-6 shadow-card mb-8">
          <h2 className="font-semibold mb-3 text-mint">Decomposition IA: {decomResult.length} taches identifiees</h2>
          <div className="space-y-3">
            {decomResult.map((st: any, i: number) => (
              <div key={i} className="flex items-center gap-4 p-3 rounded-lg border border-mist">
                <span className="text-xs font-bold text-white px-2 py-1 rounded" style={{ background: COMPLEXITY_COLORS[st.complexity] || '#636E72' }}>
                  {st.complexity}
                </span>
                <div className="flex-1">
                  <p className="text-sm font-medium">{st.title}</p>
                  <p className="text-xs text-storm">
                    {st.department ? `${st.department} · ` : ''}Assigne a: {st.employee} (SPI: {st.spi})
                  </p>
                  {st.assignment_reason && (
                    <p className="text-[10px] text-silver mt-0.5">{st.assignment_reason}</p>
                  )}
                </div>
                <div className="text-right">
                  <p className="text-xs text-storm">{st.est_hours}h</p>
                  <p className="text-sm font-mono font-bold text-iris">{formatDA(st.est_bonus)}</p>
                </div>
              </div>
            ))}
          </div>
          <button onClick={() => setDecomResult([])} className="mt-3 text-sm text-iris hover:underline">Fermer</button>
        </div>
      )}

      {/* Past needs */}
      {needs.length > 0 && (
        <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card mb-8">
          <h2 className="text-base font-semibold mb-4">Besoins soumis ({needs.length})</h2>
          <div className="space-y-2">
            {needs.map((n: any) => (
              <div key={n.id} className="flex items-center gap-4 p-3 rounded-lg border border-mist hover:bg-[#FAFAFA]">
                <Badge variant={n.status === 'APPROUVE' ? 'success' : n.status === 'DECOMPOSE' ? 'info' : 'warning'}>{n.status}</Badge>
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate">{n.text}</p>
                  <p className="text-xs text-storm">{n.submitted_at} -- {n.submitted_by}</p>
                </div>
                <span className="text-xs text-iris font-medium">{n.task_count} taches</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Active assignments */}
      <div className="bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
        <h2 className="text-base font-semibold mb-4">Taches en cours ({assignments.length})</h2>
        {assignments.length === 0 ? (
          <p className="text-sm text-storm text-center py-4">Aucune tache assignee</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b-2 border-mist">
              <th className="py-2 text-left text-storm font-medium">Tache</th>
              <th className="py-2 text-left text-storm font-medium">Employe</th>
              <th className="py-2 text-center text-storm font-medium">Complexite</th>
              <th className="py-2 text-right text-storm font-medium">Bonus prevu</th>
              <th className="py-2 text-right text-storm font-medium">Bonus agree</th>
              <th className="py-2 text-center text-storm font-medium">Score</th>
              <th className="py-2 text-right text-storm font-medium">Paiement</th>
              <th className="py-2 text-center text-storm font-medium">Statut</th>
              <th className="py-2 text-center text-storm font-medium">Actions</th>
            </tr></thead>
            <tbody>
              {assignments.map((a: any) => (
                <tr key={a.id} className="border-b border-mist hover:bg-[#FAFAFA]">
                  <td className="py-3">
                    <p className="font-medium text-sm">{a.title}</p>
                    {a.deadline && <p className="text-[10px] text-storm">Deadline: {a.deadline}</p>}
                  </td>
                  <td className="py-3 text-sm">{a.employee}</td>
                  <td className="py-3 text-center">
                    <span className="text-[10px] font-bold text-white px-2 py-0.5 rounded" style={{ background: COMPLEXITY_COLORS[a.complexity] || '#636E72' }}>
                      {a.complexity}
                    </span>
                  </td>
                  <td className="py-3 text-right font-mono text-xs">{formatDA(a.est_bonus)}</td>
                  <td className="py-3 text-right font-mono text-xs font-bold">{a.agreed_bonus ? formatDA(a.agreed_bonus) : '--'}</td>
                  <td className="py-3 text-center">
                    {a.final_score ? (
                      <span className={`font-mono font-bold ${parseFloat(a.final_score) >= 80 ? 'text-mint' : parseFloat(a.final_score) >= 50 ? 'text-honey' : 'text-coral'}`}>
                        {parseFloat(a.final_score).toFixed(0)}/100
                      </span>
                    ) : '--'}
                  </td>
                  <td className="py-3 text-right font-mono text-xs font-bold text-iris">{a.actual_payment ? formatDA(a.actual_payment) : '--'}</td>
                  <td className="py-3 text-center"><Badge variant={STATUS_VARIANT[a.status] || 'neutral'}>{a.status}</Badge></td>
                  <td className="py-3 text-center">
                    {a.status === 'PROPOSITION_SOUMISE' && (
                      <button onClick={() => respondToAssignment(a.id, 'ACCEPTED_EMPLOYEE')}
                        className="text-xs text-mint font-medium hover:underline">Accepter</button>
                    )}
                    {a.status === 'VALIDE_IA' && (
                      <button onClick={() => finalizeAssignment(a.id, 85)}
                        className="text-xs text-iris font-medium hover:underline">Finaliser</button>
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
