import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import { MfaConfirm } from '../../components/shared/MfaConfirm';
import api from '../../lib/api-client';

const LEVELS = [
  { key: 'L1', name: 'Règles déterministes', desc: 'SNMG, CNAS, IRG, arithmétique' },
  { key: 'L2', name: 'Analyse LLM', desc: 'Cohérence sémantique (données pseudonymisées)' },
  { key: 'L3', name: 'Consistance structurelle', desc: 'Entité, contrat, grille salariale' },
  { key: 'L4', name: 'Détection anomalies', desc: 'Écarts statistiques vs 12 derniers mois' },
  { key: 'L5', name: 'Vérification croisée', desc: 'Badge, pointeuse, congés approuvés' },
  { key: 'L6', name: 'Validation humaine', desc: 'Approbation DRH avec MFA' },
];

export function PayslipVerify() {
  const { id } = useParams();
  const [payslip, setPayslip] = useState<any>(null);
  const [verification, setVerification] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showMfa, setShowMfa] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  useEffect(() => {
    Promise.all([
      api.get(`/drh/payroll/payslips/${id}`),
      api.get(`/drh/payroll/payslips/${id}/verification`),
    ]).then(([pR, vR]) => {
      setPayslip(pR.data.data);
      setVerification(vR.data.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="grid grid-cols-5 gap-6"><div className="col-span-3 h-96 bg-mist rounded-card animate-pulse" /><div className="col-span-2 h-96 bg-mist rounded-card animate-pulse" /></div>;
  if (!payslip) return <p className="text-storm">Bulletin introuvable</p>;

  const hasAnyFail = (verification?.levels || []).some((l: any) => l.result === 'FAIL');

  const approve = async () => {
    try {
      await api.post(`/drh/payroll/payslips/${id}/approve`);
      window.location.reload();
    } catch {}
  };

  const reject = async () => {
    try {
      await api.post(`/drh/payroll/payslips/${id}/reject`, { reason: rejectReason });
      window.location.reload();
    } catch {}
  };

  return (
    <div>
      <Link to="/rh/payroll" className="text-sm text-iris hover:underline">← Paie</Link>
      <h1 className="text-[32px] font-bold mt-2 mb-6">Vérification Bulletin #{payslip.id?.slice(0, 8)}</h1>

      {/* Progress bar */}
      <div className="flex gap-1 mb-6">
        {LEVELS.map((l, i) => {
          const lv = (verification?.levels || [])[i];
          const color = lv?.result === 'PASS' ? 'bg-mint' : lv?.result === 'FLAG' ? 'bg-honey' : lv?.result === 'FAIL' ? 'bg-coral' : 'bg-mist';
          return <div key={l.key} className={`flex-1 h-2 rounded-full ${color}`} title={`${l.key}: ${lv?.result || 'PENDING'}`} />;
        })}
      </div>

      <div className="grid grid-cols-5 gap-6">
        {/* Left: Payslip */}
        <div className="col-span-3 bg-white rounded-card border border-[#E0E0E0] p-6 shadow-card">
          <div className="flex justify-between mb-4">
            <div><p className="font-semibold">{payslip.employee_name}</p><p className="text-xs text-storm font-mono">{payslip.matricule} — {payslip.entity}</p></div>
            <p className="text-sm text-storm">{payslip.period}</p>
          </div>
          <table className="w-full text-sm">
            <thead><tr className="border-b-2 border-mist">
              <th className="py-2 text-left text-storm">Désignation</th><th className="py-2 text-right text-storm">Base</th>
              <th className="py-2 text-right text-storm">Taux</th><th className="py-2 text-right text-storm">Salarié</th><th className="py-2 text-right text-storm">Patronal</th>
            </tr></thead>
            <tbody>
              {(payslip.lines || []).map((l: any, i: number) => (
                <tr key={i} className="border-b border-mist">
                  <td className="py-2 font-medium">{l.label}</td>
                  <td className="py-2 text-right font-mono">{l.base ? formatDA(l.base) : '—'}</td>
                  <td className="py-2 text-right font-mono">{l.rate ? `${l.rate}%` : '—'}</td>
                  <td className="py-2 text-right font-mono">{l.employee ? formatDA(l.employee) : '—'}</td>
                  <td className="py-2 text-right font-mono">{l.employer ? formatDA(l.employer) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t-2 border-iris mt-4 pt-4 flex justify-between">
            <span className="font-bold text-iris">Net à payer</span>
            <span className="text-xl font-bold font-mono text-iris">{formatDA(payslip.net)}</span>
          </div>
        </div>

        {/* Right: Pipeline */}
        <div className="col-span-2 space-y-3">
          {LEVELS.map((l, i) => {
            const lv = (verification?.levels || [])[i];
            const result = lv?.result || 'PENDING';
            return (
              <div key={l.key} className={`rounded-lg border p-4 ${result === 'FAIL' ? 'border-coral bg-[rgba(255,107,107,0.04)]' : result === 'FLAG' ? 'border-honey' : result === 'PASS' ? 'border-mint' : 'border-mist'}`}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs text-white font-bold ${result === 'PASS' ? 'bg-mint' : result === 'FLAG' ? 'bg-honey' : result === 'FAIL' ? 'bg-coral' : 'bg-mist text-storm'}`}>
                      {result === 'PASS' ? '✓' : result === 'FLAG' ? '!' : result === 'FAIL' ? '✗' : '?'}
                    </span>
                    <span className="text-sm font-semibold">{l.key} — {l.name}</span>
                  </div>
                  <Badge variant={result === 'PASS' ? 'success' : result === 'FLAG' ? 'warning' : result === 'FAIL' ? 'error' : 'neutral'}>{result}</Badge>
                </div>
                <p className="text-xs text-storm ml-8">{l.desc}</p>
                {lv?.detail && <p className="text-xs mt-1 ml-8 text-charcoal bg-[#FAFAFA] rounded p-2">{lv.detail}</p>}
                {l.key === 'L2' && result === 'PENDING' && payslip && (
                  <button onClick={async () => {
                    try {
                      const r = await api.post('/agents/payroll/verify-l2', {
                        employee_name: payslip.employee_name,
                        gross: payslip.gross, net: payslip.net,
                        position: payslip.position || 'Employe',
                      });
                      const aiResult = r.data.data;
                      alert(`L2 AI: ${aiResult.verdict || 'PASS'}\n${aiResult.anomalies?.map((a: any) => a.description).join('\n') || 'Aucune anomalie detectee'}`);
                    } catch (e: any) { alert('Erreur L2: ' + (e.response?.data?.detail || e.message)); }
                  }}
                    className="ml-8 mt-2 px-3 py-1 bg-iris text-white text-xs rounded font-medium hover:bg-rose-800">
                    Lancer l'analyse IA (L2)
                  </button>
                )}
              </div>
            );
          })}

          <div className="flex gap-3 mt-4">
            <button onClick={() => setShowMfa(true)} disabled={hasAnyFail}
              className="flex-1 py-3 rounded-button bg-mint text-white font-semibold text-sm hover:bg-[#00A884] disabled:bg-mist disabled:text-silver">
              🔐 Approuver
            </button>
            <button onClick={() => setShowReject(true)}
              className="flex-1 py-3 rounded-button bg-coral text-white font-semibold text-sm hover:bg-[#E55555]">
              Rejeter
            </button>
          </div>
          {hasAnyFail && <p className="text-xs text-coral text-center">Approbation bloquée — niveau(x) en échec</p>}
        </div>
      </div>

      <MfaConfirm open={showMfa} onConfirm={() => { setShowMfa(false); approve(); }} onCancel={() => setShowMfa(false)} actionLabel="Approuver le bulletin" />

      {showReject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-[4px]" onClick={() => setShowReject(false)} />
          <div className="relative bg-white rounded-2xl p-8 w-[500px] shadow-xl">
            <h3 className="text-lg font-bold mb-4">Motif du rejet</h3>
            <textarea value={rejectReason} onChange={e => setRejectReason(e.target.value)}
              className="w-full border border-mist rounded-lg p-4 text-sm h-32 focus:border-iris outline-none resize-none"
              placeholder="Minimum 50 caractères..." />
            <p className="text-xs text-storm mt-1">{rejectReason.length}/50 caractères minimum</p>
            <div className="flex gap-3 mt-4">
              <button onClick={() => setShowReject(false)} className="flex-1 py-2.5 rounded-button border border-mist text-storm text-sm">Annuler</button>
              <button onClick={() => { setShowReject(false); reject(); }} disabled={rejectReason.length < 50}
                className="flex-1 py-2.5 rounded-button bg-coral text-white text-sm font-semibold disabled:bg-mist disabled:text-silver">Confirmer le rejet</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
