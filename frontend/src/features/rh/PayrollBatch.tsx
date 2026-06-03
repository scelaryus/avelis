import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { formatDA } from '../../lib/format';
import { Badge } from '../../components/ui/Badge';
import api from '../../lib/api-client';

export function PayrollBatch() {
  const nav = useNavigate();
  const [period, setPeriod] = useState('2026-03');
  const [batch, setBatch] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get(`/drh/payroll/batch/${period}`).then(r => { setBatch(r.data.data); setLoading(false); }).catch(() => setLoading(false));
  }, [period]);

  if (loading) return <div className="space-y-4">{[1,2,3].map(i => <div key={i} className="h-16 bg-mist rounded-lg animate-pulse" />)}</div>;

  const payslips = batch?.payslips || [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div><h1 className="text-[32px] font-bold">Paie Mensuelle</h1>
          <p className="text-sm text-storm">{batch?.employee_count} employés — {batch?.entity_count} entités</p></div>
        <div className="flex items-center gap-3">
          <input type="month" value={period} onChange={e => setPeriod(e.target.value)}
            className="border border-mist rounded-input px-3 py-2 text-sm focus:border-iris outline-none" />
          <button onClick={() => api.post(`/drh/payroll/batch/${period}/calculate`)}
            className="px-4 py-2 bg-iris text-white rounded-button text-sm font-semibold hover:bg-rose-800">
            Calculer la paie
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Masse brute</p><p className="text-xl font-bold font-mono">{formatDA(batch?.total_gross)}</p>
        </div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Masse nette</p><p className="text-xl font-bold font-mono text-iris">{formatDA(batch?.total_net)}</p>
        </div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">Statut batch</p><Badge variant={batch?.status === 'CALCULATED' ? 'warning' : batch?.status === 'APPROVED' ? 'success' : 'info'}>{batch?.status}</Badge>
        </div>
        <div className="bg-white rounded-card border border-mist p-4 shadow-card">
          <p className="text-xs text-storm">À valider</p><p className="text-xl font-bold text-coral">{batch?.payslips_pending_review}</p>
        </div>
      </div>

      {/* Verification pipeline */}
      {batch?.verification_status && (
        <div className="bg-white rounded-card border border-mist p-4 shadow-card mb-6">
          <p className="text-sm font-semibold mb-3">Pipeline de vérification batch</p>
          <div className="flex gap-2">
            {Object.entries(batch.verification_status).map(([level, result]) => (
              <div key={level} className={`flex-1 py-2 rounded-lg text-center text-xs font-bold ${
                result === 'PASS' ? 'bg-[rgba(85,239,196,0.15)] text-mint' : result === 'FLAG' ? 'bg-[rgba(253,203,110,0.2)] text-[#E17055]' : result === 'FAIL' ? 'bg-[rgba(253,121,168,0.15)] text-coral' : 'bg-mist text-storm'
              }`}>
                {level} — {result as string}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Payslips table */}
      <div className="bg-white rounded-card border border-[#E0E0E0] shadow-card overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-[#FAFAFA] border-b-2 border-mist">
            <th className="py-3 px-4 text-left text-storm font-medium">Matricule</th>
            <th className="py-3 px-4 text-left text-storm font-medium">Employé</th>
            <th className="py-3 px-4 text-left text-storm font-medium">Entité</th>
            <th className="py-3 px-4 text-right text-storm font-medium">Brut</th>
            <th className="py-3 px-4 text-right text-storm font-medium">Net</th>
            <th className="py-3 px-4 text-left text-storm font-medium">Statut</th>
            <th className="py-3 px-4 text-left text-storm font-medium">Actions</th>
          </tr></thead>
          <tbody>
            {payslips.length === 0 ? (
              <tr><td colSpan={7} className="py-8 text-center text-storm">Aucun bulletin pour cette période. Cliquez "Calculer la paie" pour démarrer.</td></tr>
            ) : payslips.map((p: any) => (
              <tr key={p.id} className="border-b border-mist hover:bg-[#FAFAFA] transition">
                <td className="py-3 px-4 font-mono text-xs text-iris">{p.matricule}</td>
                <td className="py-3 px-4 font-medium">{p.employee}</td>
                <td className="py-3 px-4 text-storm">{p.entity}</td>
                <td className="py-3 px-4 text-right font-mono">{formatDA(p.gross)}</td>
                <td className="py-3 px-4 text-right font-mono font-bold">{formatDA(p.net)}</td>
                <td className="py-3 px-4">
                  <Badge variant={p.status === 'APPROVED_DRH' || p.status === 'APPROVED_PDG' ? 'success' : p.status === 'REJECTED' ? 'error' : 'warning'}>
                    {p.status?.replace(/_/g, ' ')}
                  </Badge>
                </td>
                <td className="py-3 px-4">
                  {(p.status === 'PENDING_L6' || p.status === 'CALCULATED') && (
                    <Link to={`/rh/payroll/payslips/${p.id}/verify`}
                      className="text-xs text-iris font-semibold hover:underline">Vérifier L1-L6</Link>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
